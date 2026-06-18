
import os
import inspect
import pytest


def test_exactly_five_required_tools():

    from tools import ALL_TOOLS
    expected = {"get_otb_summary", "get_segment_mix", "get_pickup_delta",
                "get_as_of_otb", "get_block_vs_transient_mix"}
    actual = {t.name for t in ALL_TOOLS}
    assert expected == actual, f"Expected {expected}, got {actual}"

def test_tools_importable_without_server():

    from tools import ALL_TOOLS
    assert len(ALL_TOOLS) == 5

def test_no_run_sql_tool():

    from tools import ALL_TOOLS
    for t in ALL_TOOLS:
        assert "sql" not in t.name.lower(), f"Tool {t.name} looks like a raw SQL tool"

def test_hitl_on_get_as_of_otb():

    from agent import build_agent

    src = inspect.getsource(build_agent)
    assert "get_as_of_otb" in src, "build_agent should reference get_as_of_otb"
    assert "interrupt_on" in src, "build_agent should configure interrupt_on"
    assert '"get_as_of_otb"' in src or "'get_as_of_otb'" in src, \
        "interrupt_on must include get_as_of_otb"


def test_segment_subagent_exists():

    src = inspect.getsource(__import__("agent"))
    assert "segment" in src.lower(), "Agent should have a segment-focused subagent"
    assert "SubAgent" in src, "Agent should use SubAgent for segment routing"
    # Verify segment tools are assigned to the subagent
    assert "get_segment_mix" in src, "Segment subagent should have get_segment_mix"
    assert "get_block_vs_transient_mix" in src, "Segment subagent should have get_block_vs_transient_mix"




def test_agent_has_multiple_tools_for_decomposition():

    from tools import ALL_TOOLS
    names = {t.name for t in ALL_TOOLS}
    assert "get_otb_summary" in names and "get_pickup_delta" in names, \
        "Agent needs both OTB and pickup tools for multi-part questions"


# ─── Scenario 5: Skill loading is on-demand ────────────────────────────────────

def test_skills_configured():

    src = inspect.getsource(__import__("agent"))
    assert 'skills=' in src or 'skills =' in src, "Agent should configure skills parameter"
    assert "./skills" in src or "skills/" in src, "Skills directory should be referenced"


# ─── Scenario 6: Memory or filesystem used ─────────────────────────────────────

def test_memory_configured():

    src = inspect.getsource(__import__("agent"))
    assert 'memory=' in src or 'memory =' in src, "Agent should configure memory parameter"