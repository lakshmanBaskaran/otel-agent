import os
from datetime import date
from deepagents import create_deep_agent
from deepagents.middleware.subagents import SubAgent
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

## When to delegate
- Segment or block mix questions → segment-analyst subagent
- Pickup or pace questions → demand-analyst subagent
- Morning briefing → both subagents, then synthesize

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

Your job is to break down the business mix — which segments drive revenue,
where concentration sits, and how block vs transient splits.

Use get_segment_mix for market-level breakdown and get_block_vs_transient_mix
for block analysis. Always state shares as percentages. Flag any single
segment or company taking an outsized share.
"""

DEMAND_ANALYST_PROMPT = """You are the Demand Analyst on the revenue team.

Your job is to read booking momentum. Use get_pickup_delta to check recent
booking pace. Compare pickup volume and ADR across months. Flag months
with weak pickup that are close to arrival.

Always pair pickup with the current OTB position for context.
"""


def build_agent():
    segment_analyst = SubAgent(
        name="segment-analyst",
        description=(
            "Specialist in segment and block mix analysis. Use for questions about "
            "what's driving a month, segment breakdown, OTA dependency, group vs "
            "transient, or company concentration."
        ),
        system_prompt=SEGMENT_ANALYST_PROMPT,
        tools=[get_segment_mix, get_block_vs_transient_mix, get_top_companies, get_otb_summary],
    )

    demand_analyst = SubAgent(
        name="demand-analyst",
        description=(
            "Specialist in booking pace and pickup. Use for questions about "
            "what changed recently, pickup trends, or booking momentum."
        ),
        system_prompt=DEMAND_ANALYST_PROMPT,
        tools=[get_pickup_delta, get_otb_summary],
    )

    # HITL: gate get_as_of_otb — expensive point-in-time rebuild
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
    )
    return agent


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Set ANTHROPIC_API_KEY first")
        exit(1)

    agent = build_agent()
    print(f"Revenue Manager Agent ready ({TODAY})")
    print("Type a question or 'quit'\n")

    config = {"configurable": {"thread_id": "main"}}
    while True:
        q = input("GM> ").strip()
        if q.lower() in ("quit", "exit", "q"):
            break
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