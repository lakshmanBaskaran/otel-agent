"""
app.py - Chainlit UI for the Revenue Manager Agent.
Handles HITL interrupts for get_as_of_otb.
Uses ThreadPoolExecutor to avoid blocking the WebSocket.
"""
import asyncio
import json
import os
from concurrent.futures import ThreadPoolExecutor

import chainlit as cl
from agent import build_agent

agent = build_agent()
executor = ThreadPoolExecutor(max_workers=2)

BASIC_AUTH_USER = os.environ.get("BASIC_AUTH_USER", "otel")
BASIC_AUTH_PASS = os.environ.get("BASIC_AUTH_PASS", "revenue2026")


@cl.password_auth_callback
def auth_callback(username: str, password: str):
    if username == BASIC_AUTH_USER and password == BASIC_AUTH_PASS:
        return cl.User(identifier=username)
    return None


def _run_agent(messages, config):
    """Run agent synchronously in thread. Returns (result, interrupted, interrupt_data)."""
    result = agent.invoke({"messages": messages}, config=config)

    # Check if agent was interrupted (HITL)
    # LangGraph sets __interrupt__ in the result when interrupted
    if isinstance(result, dict):
        interrupts = result.get("__interrupt__", [])
        if interrupts:
            return result, True, interrupts[0] if interrupts else None

    return result, False, None


def _resume_agent(config):
    """Resume agent after HITL approval."""
    from langgraph.types import Command
    result = agent.invoke(Command(resume="approved"), config=config)
    return result


@cl.on_message
async def main(message: cl.Message):
    session_id = cl.user_session.get("id", "default")
    config = {"configurable": {"thread_id": session_id}}

    # Check if we're resuming a HITL interrupt
    pending_hitl = cl.user_session.get("pending_hitl", False)

    if pending_hitl:
        user_response = message.content.strip().lower()
        cl.user_session.set("pending_hitl", False)

        if user_response in ("yes", "y", "approve", "ok", "go ahead", "confirm"):
            thinking = cl.Message(content="✅ Approved. Running point-in-time query...")
            await thinking.send()

            loop = asyncio.get_event_loop()
            try:
                result = await loop.run_in_executor(
                    executor,
                    lambda: _resume_agent(config)
                )
            except Exception as e:
                await thinking.remove()
                await cl.Message(content=f"Error resuming: {str(e)}").send()
                return

            await thinking.remove()
            await _send_result(result)
        else:
            await cl.Message(
                content="Cancelled. The point-in-time query was not run. Ask me something else."
            ).send()
        return

    # Normal message flow
    thinking = cl.Message(content="⏳ Analysing...")
    await thinking.send()

    loop = asyncio.get_event_loop()
    try:
        result, interrupted, interrupt_data = await loop.run_in_executor(
            executor,
            lambda: _run_agent(message.content, config)
        )
    except Exception as e:
        await thinking.remove()
        await cl.Message(content=f"Error: {str(e)}").send()
        return

    await thinking.remove()

    if interrupted:
        # HITL gate fired — ask GM for approval
        cl.user_session.set("pending_hitl", True)
        await cl.Message(
            content=(
                "⚠️ **Approval required**\n\n"
                "I need to run a point-in-time database scan (`get_as_of_otb`). "
                "This is an expensive query that reconstructs the book at a past timestamp.\n\n"
                "**Type `yes` to approve or `no` to cancel.**"
            )
        ).send()
        return

    await _send_result(result)


async def _send_result(result):
    """Extract tool calls and final response from agent result and send to UI."""
    if not isinstance(result, dict) or "messages" not in result:
        await cl.Message(content=str(result)).send()
        return

    messages = result["messages"]

    # Show tool calls and skill loads
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

    # Final AI response
    final = ""
    for msg in reversed(messages):
        if hasattr(msg, "content") and msg.content and type(msg).__name__ == "AIMessage":
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
        db_url = os.environ.get("HOTEL_DATABASE_URL") or os.environ.get("DATABASE_URL")
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
            return JSONResponse({"status": "db_error", "error": str(e)}, status_code=500)

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