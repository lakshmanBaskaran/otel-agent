import os
from datetime import date
from deepagents import create_deep_agent
from deepagents.middleware.subagents import SubAgent
from langgraph.checkpoint.memory import MemorySaver
from tools import (
    ALL_TOOLS,
    get_otb_summary,
    get_segment_mix,
    get_pickup_delta,
    get_as_of_otb,
    get_block_vs_transient_mix,
    get_room_type_performance,
    get_top_companies,
)

TODAY = date.today().isoformat()

SYSTEM_PROMPT = f"""You are the Revenue Manager for the Grand Harbour Hotel.

You advise the General Manager with sharp, data-driven commercial judgment.
You are not a dashboard — you are a strategist.

Today is {TODAY}. When a user mentions a month without a year, default to
the current or upcoming year.

## Answer format
Start with the headline. Show the key numbers. Say what's driving them.
Be transparent about risks and negatives. End with what to actually do.
Note your assumptions if they matter.

## Exact tool routing — follow this exactly, no exceptions

Call tools DIRECTLY. Do NOT delegate to subagents except for morning briefing.

| Question type | Tools to call |
|---|---|
| OTB / revenue on books | get_otb_summary |
| Segment mix / what is driving | get_segment_mix, get_block_vs_transient_mix |
| OTA dependency / channel mix | get_segment_mix |
| Block vs transient | get_block_vs_transient_mix |
| Top companies / account concentration | get_top_companies |
| Room type ADR | get_room_type_performance |
| Pickup / pace / what changed | get_pickup_delta |
| Month comparison (July vs August) | get_pickup_delta twice |
| Point-in-time / historical OTB | get_as_of_otb (HITL gated) |
| Morning briefing | delegate to BOTH subagents, then synthesize |

Call ONLY the tools listed for the question type. Do not call extra tools
to be thorough. Do not call get_otb_summary as context unless headline
numbers are explicitly requested alongside another question.

## Critical data rules
- Room nights = SUM(number_of_spaces), never COUNT(*)
- Reservation count = COUNT(DISTINCT reservation_id), never COUNT(*)
- Exclude cancelled and provisional by default
- stay_date for OTB, create_datetime for pickup
- daily_total_revenue_before_tax for general revenue

## Style
Confident, concise, commercial. Round numbers. Take a position.
"""

SEGMENT_ANALYST_PROMPT = """You are the Segment Analyst on the revenue team.

You are called only for morning briefings. Your job:
1. Call get_segment_mix for the current month
2. Call get_block_vs_transient_mix for the current month
3. Synthesize and return findings

Call exactly those 2 tools. Do not call get_otb_summary.
Do not call get_top_companies. Do not create tasks. Answer directly.
"""

DEMAND_ANALYST_PROMPT = """You are the Demand Analyst on the revenue team.

You are called only for morning briefings. Your job:
1. Call get_pickup_delta with booking_window_days=7
2. Call get_otb_summary for the nearest future month for context

Call exactly those 2 tools. Do not call additional pickup windows.
Do not create tasks. Answer directly.
"""


def build_agent():
    segment_analyst = SubAgent(
        name="segment-analyst",
        description=(
            "Use ONLY for morning briefing requests. "
            "Handles segment mix and block/transient breakdown. "
            "Do NOT use for standalone segment, OTA, or company questions — "
            "the supervisor handles those directly."
        ),
        system_prompt=SEGMENT_ANALYST_PROMPT,
        tools=[get_segment_mix, get_block_vs_transient_mix, get_otb_summary],
    )

    demand_analyst = SubAgent(
        name="demand-analyst",
        description=(
            "Use ONLY for morning briefing requests. "
            "Handles pickup pace and booking momentum. "
            "Do NOT use for standalone pickup or pacing questions — "
            "the supervisor handles those directly."
        ),
        system_prompt=DEMAND_ANALYST_PROMPT,
        tools=[get_pickup_delta, get_otb_summary],
    )

    interrupt_on = {
        "get_as_of_otb": True,
    }

    agent = create_deep_agent(
        model="anthropic:claude-sonnet-4-6",
        tools=ALL_TOOLS,
        system_prompt=SYSTEM_PROMPT,
        skills=["./skills"],
        subagents=[segment_analyst, demand_analyst],
        memory=["./memory/AGENTS.md"],
        interrupt_on=interrupt_on,
        checkpointer=MemorySaver(),
    )
    return agent


def make_config(session_id: str) -> dict:
    return {"configurable": {"thread_id": session_id}}


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Set ANTHROPIC_API_KEY first")
        exit(1)

    import uuid
    agent = build_agent()
    print(f"Revenue Manager Agent ready ({TODAY})")
    print("Commands: 'quit' to exit, 'new' for fresh context\n")

    session_id = str(uuid.uuid4())
    config = make_config(session_id)

    while True:
        q = input("GM> ").strip()
        if q.lower() in ("quit", "exit", "q"):
            break
        if q.lower() == "new":
            session_id = str(uuid.uuid4())
            config = make_config(session_id)
            print("[New context window]\n")
            continue
        if not q:
            continue
        print("\nAnalyzing...\n")
        result = agent.invoke({"messages": q}, config=config)
        if isinstance(result, dict) and "messages" in result:
            for msg in reversed(result["messages"]):
                if hasattr(msg, "content") and msg.content and type(msg).__name__ == "AIMessage":
                    if not (hasattr(msg, "tool_calls") and msg.tool_calls):
                        print(msg.content)
                        break
        print()