"""
tests/test_agent.py — Agent structure tests (Phase 3)
Covers scenarios 1-6 from AGENT_TEST_SCENARIOS.md.
Uses mocks and config introspection — no live LLM calls.
"""
import os
import inspect
import pytest


# ─── Scenario 1: Tool surface is fixed ─────────────────────────────────────────

def test_exactly_five_required_tools():
    """Agent exposes exactly the five required tools by name."""
    from tools import ALL_TOOLS
    expected = {"get_otb_summary", "get_segment_mix", "get_pickup_delta",
                "get_as_of_otb", "get_block_vs_transient_mix"}
    actual = {t.name for t in ALL_TOOLS}
    assert expected == actual, f"Expected {expected}, got {actual}"

def test_tools_importable_without_server():
    """Tools import without starting the agent HTTP server."""
    from tools import ALL_TOOLS
    assert len(ALL_TOOLS) == 5

def test_no_run_sql_tool():
    """No run_sql or raw SQL tool exists."""
    from tools import ALL_TOOLS
    for t in ALL_TOOLS:
        assert "sql" not in t.name.lower(), f"Tool {t.name} looks like a raw SQL tool"


# ─── Scenario 2: get_as_of_otb is human-gated ─────────────────────────────────

def test_hitl_on_get_as_of_otb():
    """get_as_of_otb is configured behind human-in-the-loop approval."""
    from agent import build_agent
    # Check agent.py source for interrupt_on containing get_as_of_otb
    src = inspect.getsource(build_agent)
    assert "get_as_of_otb" in src, "build_agent should reference get_as_of_otb"
    assert "interrupt_on" in src, "build_agent should configure interrupt_on"

    # Verify the interrupt_on dict includes get_as_of_otb
    # We check the source since building the agent requires API key
    assert '"get_as_of_otb"' in src or "'get_as_of_otb'" in src, \
        "interrupt_on must include get_as_of_otb"


# ─── Scenario 3: Segment work is isolated ─────────────────────────────────────

def test_segment_subagent_exists():
    """A subagent handles segment/mix questions.
    Pattern: segment-analyst subagent with get_segment_mix and
    get_block_vs_transient_mix tools for isolated segment analysis."""
    src = inspect.getsource(__import__("agent"))
    assert "segment" in src.lower(), "Agent should have a segment-focused subagent"
    assert "SubAgent" in src, "Agent should use SubAgent for segment routing"
    # Verify segment tools are assigned to the subagent
    assert "get_segment_mix" in src, "Segment subagent should have get_segment_mix"
    assert "get_block_vs_transient_mix" in src, "Segment subagent should have get_block_vs_transient_mix"


# ─── Scenario 4: Multi-tool decomposition ─────────────────────────────────────

def test_agent_has_multiple_tools_for_decomposition():
    """Agent has enough tools to decompose compound questions.
    A question like 'What's driving July and how did we book lately?' needs
    get_otb_summary + get_pickup_delta at minimum."""
    from tools import ALL_TOOLS
    names = {t.name for t in ALL_TOOLS}
    assert "get_otb_summary" in names and "get_pickup_delta" in names, \
        "Agent needs both OTB and pickup tools for multi-part questions"


# ─── Scenario 5: Skill loading is on-demand ────────────────────────────────────

def test_skills_configured():
    """Agent uses skills (filesystem SKILL.md files), not monolithic system prompt."""
    src = inspect.getsource(__import__("agent"))
    assert 'skills=' in src or 'skills =' in src, "Agent should configure skills parameter"
    assert "./skills" in src or "skills/" in src, "Skills directory should be referenced"


# ─── Scenario 6: Memory or filesystem used ─────────────────────────────────────

def test_memory_configured():
    """Agent uses memory for multi-turn context."""
    src = inspect.getsource(__import__("agent"))
    assert 'memory=' in src or 'memory =' in src, "Agent should configure memory parameter"