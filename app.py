"""
app.py - Chainlit UI for the Revenue Manager Agent.
Streams tool calls and skill loads so reviewers can see what fired.
Uses ThreadPoolExecutor to run the blocking agent.invoke() without
dropping the WebSocket connection on slow free-tier hosts.
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


@cl.on_message
async def main(message: cl.Message):
    config = {"configurable": {"thread_id": cl.user_session.get("id", "default")}}

    # Send immediate acknowledgement so the connection stays alive
    thinking = cl.Message(content="⏳ Analysing...")
    await thinking.send()

    # Run blocking agent.invoke() in a thread so the WebSocket doesn't time out
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            executor,
            lambda: agent.invoke({"messages": message.content}, config=config)
        )
    except Exception as e:
        await thinking.remove()
        await cl.Message(content=f"Error: {str(e)}").send()
        return

    await thinking.remove()

    if isinstance(result, dict) and "messages" in result:
        messages = result["messages"]

        # Show tool calls and skill loads as steps
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
    else:
        await cl.Message(content=str(result)).send()


# Mount /health directly on Chainlit's FastAPI app
# so it's accessible at the main URL (not a separate port)
try:
    from chainlit.server import app as chainlit_app
    from fastapi.responses import JSONResponse
    import psycopg2
    import hashlib
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
    pass  # Health endpoint is best-effort; don't crash the whole app