"""
app.py - Chainlit UI for the Revenue Manager Agent.
Handles HITL interrupts for get_as_of_otb.
On approval: calls the tool directly (bypassing interrupt gate),
then asks the agent to synthesize the result.
Context accumulation fix: each Chainlit session uses its own thread_id.
Follow-up questions within a session retain context.
"""
import asyncio
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import chainlit as cl
from agent import build_agent, make_config
from tools import get_as_of_otb

agent = build_agent()
executor = ThreadPoolExecutor(max_workers=2)

BASIC_AUTH_USER = os.environ.get("BASIC_AUTH_USER", "otel")
BASIC_AUTH_PASS = os.environ.get("BASIC_AUTH_PASS", "revenue2026")

# Store pending HITL state outside Chainlit context
_pending_questions: dict = {}   # session_id -> original question
_pending_tool_args: dict = {}   # session_id -> {stay_month, as_of_utc}


@cl.password_auth_callback
def auth_callback(username: str, password: str):
    if username == BASIC_AUTH_USER and password == BASIC_AUTH_PASS:
        return cl.User(identifier=username)
    return None


def _run_agent(messages, config):
    """Run agent synchronously in thread.
    Returns (result, interrupted, tool_args).
    """
    result = agent.invoke({"messages": messages}, config=config)

    if isinstance(result, dict):
        interrupts = result.get("__interrupt__", [])
        if interrupts:
            interrupt = interrupts[0]
            tool_args = {}
            try:
                if hasattr(interrupt, "value"):
                    val = interrupt.value
                    if isinstance(val, dict):
                        tool_args = val.get("args", {})
                    elif isinstance(val, list) and val:
                        tool_args = val[0].get("args", {}) if isinstance(val[0], dict) else {}
            except Exception:
                pass
            return result, True, tool_args

    return result, False, {}


def _resume_agent(original_question, tool_args, config):
    """Resume after HITL approval.
    Calls get_as_of_otb directly (bypasses interrupt gate),
    then asks a fresh agent instance to synthesize the result.
    Runs entirely in a thread — no Chainlit context needed.
    """
    stay_month = tool_args.get("stay_month", "2026-07")
    as_of_utc = tool_args.get("as_of_utc") or (
        (datetime.now(timezone.utc) - timedelta(days=30))
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    # Step 1: Call tool directly — no agent, no interrupt gate
    try:
        tool_result = get_as_of_otb.invoke({
            "stay_month": stay_month,
            "as_of_utc": as_of_utc,
        })
    except Exception as e:
        return {
            "messages": [
                type("AIMessage", (), {
                    "content": f"Error running point-in-time query: {str(e)}",
                    "tool_calls": None,
                })()
            ]
        }, False, {}

    # Step 2: Fresh thread_id for synthesis — avoids re-triggering interrupt
    session_id = config["configurable"]["thread_id"]
    fresh_config = make_config(f"{session_id}_resume_{int(time.time())}")

    synthesis_prompt = (
        f"I have the point-in-time OTB data you requested. "
        f"Here is what the book looked like as of {as_of_utc}:\n\n"
        f"{tool_result}\n\n"
        f"Please answer this question using this data: {original_question}\n\n"
        f"Compare to the current OTB if relevant, and give a sharp RM analysis."
    )
    result = agent.invoke({"messages": synthesis_prompt}, config=fresh_config)

    # Fallback if fresh agent also triggers interrupt
    if isinstance(result, dict) and result.get("__interrupt__"):
        data = json.loads(tool_result)
        summary = (
            f"**Point-in-time snapshot as of {as_of_utc}**\n\n"
            f"| Metric | Value |\n|---|---|\n"
            f"| Reservations | {data.get('reservation_count', 'N/A')} |\n"
            f"| Room Nights | {data.get('room_nights', 'N/A')} |\n"
            f"| Total Revenue | £{data.get('total_revenue', 0):,.0f} |\n\n"
            f"Compare to current OTB to see pickup since that date."
        )
        result = {"messages": [
            type("FakeAI", (), {
                "content": summary,
                "tool_calls": None,
                "__class__": type("cls", (), {"__name__": "AIMessage"})()
            })()
        ]}

    return result, False, {}


@cl.on_message
async def main(message: cl.Message):
    session_id = cl.user_session.get("id", "default")
    # Each Chainlit session has its own thread_id — follow-up questions
    # within the same session retain context. New login = new session = fresh context.
    config = make_config(session_id)

    # One request at a time per session
    if cl.user_session.get("processing", False):
        await cl.Message(
            content="⏳ Still processing previous request, please wait..."
        ).send()
        return

    cl.user_session.set("processing", True)

    try:
        pending_hitl = cl.user_session.get("pending_hitl", False)

        # ── HITL resume path ──────────────────────────────────────────────
        if pending_hitl:
            user_response = message.content.strip().lower()
            cl.user_session.set("pending_hitl", False)

            if user_response in ("yes", "y", "approve", "ok", "go ahead", "confirm"):
                thinking = cl.Message(
                    content="✅ Approved. Running point-in-time query..."
                )
                await thinking.send()

                original_question = _pending_questions.pop(session_id, "point-in-time OTB")
                tool_args = _pending_tool_args.pop(session_id, {})

                loop = asyncio.get_event_loop()
                try:
                    result, _, __ = await loop.run_in_executor(
                        executor,
                        lambda: _resume_agent(original_question, tool_args, config),
                    )
                except Exception as e:
                    await thinking.remove()
                    await cl.Message(content=f"Error: {str(e)}").send()
                    return

                await thinking.remove()
                await _send_result(result)

            else:
                _pending_questions.pop(session_id, None)
                _pending_tool_args.pop(session_id, None)
                await cl.Message(
                    content="Cancelled. Ask me something else."
                ).send()
            return

        # ── Normal message path ───────────────────────────────────────────
        thinking = cl.Message(content="⏳ Analysing...")
        await thinking.send()

        loop = asyncio.get_event_loop()
        try:
            result, interrupted, tool_args = await loop.run_in_executor(
                executor,
                lambda: _run_agent(message.content, config),
            )
        except Exception as e:
            await thinking.remove()
            await cl.Message(content=f"Error: {str(e)}").send()
            return

        await thinking.remove()

        if interrupted:
            _pending_questions[session_id] = message.content
            _pending_tool_args[session_id] = tool_args
            cl.user_session.set("pending_hitl", True)
            await cl.Message(
                content=(
                    "⚠️ **Approval required**\n\n"
                    "I need to run a point-in-time database scan (`get_as_of_otb`). "
                    "This is an expensive query that reconstructs the book "
                    "at a past timestamp.\n\n"
                    "**Type `yes` to approve or `no` to cancel.**"
                )
            ).send()
            return

        await _send_result(result)

    finally:
        cl.user_session.set("processing", False)


async def _send_result(result):
    """Extract tool calls and final response from agent result."""
    if not isinstance(result, dict) or "messages" not in result:
        await cl.Message(content=str(result)).send()
        return

    messages = result["messages"]

    for msg in messages:
        msg_type = type(msg).__name__

        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_name = tc.get("name", "unknown")
                tool_args = tc.get("args", {})

                if "read" in tool_name.lower() or "ls" in tool_name.lower():
                    step = cl.Step(name="📚 Loaded skill", type="tool")
                    async with step:
                        step.output = json.dumps(tool_args, indent=2)
                else:
                    step = cl.Step(name=f"🔧 {tool_name}", type="tool")
                    async with step:
                        step.output = json.dumps(tool_args, indent=2)

        elif msg_type == "ToolMessage":
            content = msg.content if hasattr(msg, "content") else str(msg)
            if len(content) > 500:
                content = content[:500] + "..."
            step = cl.Step(name=f"📊 {msg.name} result", type="tool")
            async with step:
                step.output = content

    final = ""
    for msg in reversed(messages):
        if (
            hasattr(msg, "content")
            and msg.content
            and type(msg).__name__ == "AIMessage"
        ):
            if not (hasattr(msg, "tool_calls") and msg.tool_calls):
                final = msg.content
                break

    if final:
        await cl.Message(content=final).send()
    else:
        await cl.Message(content="Could not generate a response.").send()


# Mount /health on Chainlit's FastAPI app
try:
    from chainlit.server import app as chainlit_app
    from fastapi.responses import JSONResponse
    import psycopg2
    from pathlib import Path

    @chainlit_app.get("/health")
    def health():
        db_url = (
            os.environ.get("HOTEL_DATABASE_URL")
            or os.environ.get("DATABASE_URL")
        )
        try:
            conn = psycopg2.connect(db_url)
            cur = conn.cursor()
            cur.execute("""
                SELECT dataset_revision, row_hash
                FROM load_manifest
                ORDER BY scraped_at DESC NULLS LAST
                LIMIT 1
            """)
            row = cur.fetchone()
            cur.execute("""
                SELECT COUNT(*) FROM reservations_hackathon
                WHERE financial_status = 'Posted'
                  AND reservation_status != 'Cancelled'
            """)
            posted = cur.fetchone()[0]
            conn.close()
        except Exception as e:
            return JSONResponse(
                {"status": "db_error", "error": str(e)}, status_code=500
            )

        proof = {}
        p = Path("etl/LOAD_PROOF.json")
        if p.exists():
            import json as _json
            proof = _json.loads(p.read_text())

        return JSONResponse({
            "status": "ok",
            "dataset_revision": row[0] if row else None,
            "row_hash": row[1] if row else None,
            "financial_status_posted_only_rows": posted,
            "proof_committed_fingerprint": proof.get(
                "reservation_stay_status_sha256", "not_found"
            ),
        })

except Exception:
    pass