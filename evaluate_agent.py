import csv
import json
import time
from collections import Counter

from agent import build_agent

agent = build_agent()

# ---------------------------
# TEST SUITE
# ---------------------------

TEST_CASES = [
    ("What's driving revenue in July 2026?", "segment"),
    ("Show segment mix for August 2026.", "segment"),
    ("Are we too dependent on OTA business?", "segment"),
    ("Which companies contribute most revenue?", "segment"),
    ("Analyze block versus transient mix.", "segment"),

    ("How has pickup performed over the last 7 days?", "demand"),
    ("What changed in bookings this week?", "demand"),
    ("How is August pacing?", "demand"),
    ("Which month has weak booking momentum?", "demand"),
    ("Compare pickup between July and August.", "demand"),

    ("Give me a morning briefing.", "both"),
    ("Summarize hotel performance and risks.", "both"),
    ("What should I be worried about next month?", "both"),
    ("Provide a commercial strategy update.", "both"),
    ("What actions should I take to improve revenue?", "both"),

    ("What's our current OTB position?", "supervisor"),
    ("How many room nights are on the books?", "supervisor"),
    ("Which room types generate the most revenue?", "supervisor"),
    ("What ADR are we achieving?", "supervisor"),
    ("Where is our largest revenue opportunity?", "both"),
]

# ---------------------------
# RESULTS STORAGE
# ---------------------------

results = []
tool_counter = Counter()
success_count = 0
latencies = []

# ---------------------------
# EXECUTION
# ---------------------------

for idx, (question, expected_route) in enumerate(TEST_CASES, start=1):

    # Fresh thread per test — no context bleed between questions
    config = {"configurable": {"thread_id": f"eval-{idx}"}}

    print(f"\n{'='*70}")
    print(f"TEST {idx}/20")
    print(question)

    start_time = time.time()

    try:
        response = agent.invoke(
            {"messages": question},
            config=config
        )

        latency = round(time.time() - start_time, 2)
        latencies.append(latency)

        final_answer = ""
        tools_used = []

        if isinstance(response, dict):
            messages = response.get("messages", [])

            for msg in messages:
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        name = tc.get("name", "unknown")
                        tools_used.append(name)
                        tool_counter[name] += 1

                if type(msg).__name__ == "AIMessage":
                    if not getattr(msg, "tool_calls", None):
                        final_answer = str(msg.content)

        success_count += 1

        results.append({
            "question": question,
            "expected_route": expected_route,
            "latency_seconds": latency,
            "tools_used": ", ".join(tools_used),
            "response_length": len(final_answer),
            "status": "PASS"
        })

        print(f"✓ Success")
        print(f"Latency: {latency}s")
        print(f"Tools: {tools_used}")

    except Exception as e:
        results.append({
            "question": question,
            "expected_route": expected_route,
            "latency_seconds": 0,
            "tools_used": "",
            "response_length": 0,
            "status": "FAIL",
            "error": str(e)
        })

        print(f"✗ Failed")
        print(str(e))

# ---------------------------
# SAVE CSV
# ---------------------------

with open("evaluation_results.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "question", "expected_route", "latency_seconds",
        "tools_used", "response_length", "status"
    ])
    writer.writeheader()
    writer.writerows(results)

# ---------------------------
# SUMMARY REPORT
# ---------------------------

avg_latency = sum(latencies) / len(latencies) if latencies else 0

print("\n")
print("="*70)
print("FINAL EVALUATION REPORT")
print("="*70)
print(f"Tests Run:       {len(TEST_CASES)}")
print(f"Successful:      {success_count}")
print(f"Failed:          {len(TEST_CASES) - success_count}")
print(f"Success Rate:    {(success_count / len(TEST_CASES)) * 100:.1f}%")
print(f"Average Latency: {avg_latency:.2f}s")

print("\nMost Used Tools")
for tool, count in tool_counter.most_common():
    print(f"  {tool}: {count}")

# ---------------------------
# SAVE JSON REPORT
# ---------------------------

summary = {
    "tests_run": len(TEST_CASES),
    "successes": success_count,
    "failures": len(TEST_CASES) - success_count,
    "success_rate": round(success_count / len(TEST_CASES) * 100, 2),
    "average_latency": round(avg_latency, 2),
    "tool_usage": dict(tool_counter)
}

with open("evaluation_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2)

print("\nSaved: evaluation_results.csv, evaluation_summary.json")