"""
app.py - Chainlit UI for the Revenue Manager Agent.
Streams tool calls and skill loads so reviewers can see what fired.
"""
import json
import os
import chainlit as cl
from agent import build_agent

agent = build_agent()

# Credentials from env vars (set in Railway)
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
    result = agent.invoke({"messages": message.content}, config=config)

    if isinstance(result, dict) and "messages" in result:
        messages = result["messages"]

        for msg in messages:
            msg_type = type(msg).__name__

            # Tool calls (including skill file reads)
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_name = tc.get("name", "unknown")
                    tool_args = tc.get("args", {})

                    if "read" in tool_name.lower() or "ls" in tool_name.lower():
                        # Skill load
                        step = cl.Step(name=f"Loaded skill", type="tool")
                        async with step:
                            step.output = json.dumps(tool_args, indent=2)
                    else:
                        step = cl.Step(name=f"{tool_name}", type="tool")
                        async with step:
                            step.output = json.dumps(tool_args, indent=2)

            # Tool results
            elif msg_type == "ToolMessage":
                content = msg.content if hasattr(msg, "content") else str(msg)
                if len(content) > 500:
                    content = content[:500] + "..."
                step = cl.Step(name=f"{msg.name} result", type="tool")
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