"""
tests/test_skills.py — Skill structure tests (Phase 3)
Covers scenarios 1-6 from SKILL_TEST_SCENARIOS.md.
No LLM calls — filesystem and content checks only.
"""
import os
import re
import glob
import pytest

SKILLS_DIR = os.path.join(os.path.dirname(__file__), "..", "skills")
REQUIRED_TOOLS = {"get_otb_summary", "get_segment_mix", "get_pickup_delta",
                  "get_as_of_otb", "get_block_vs_transient_mix"}


def load_skill(path):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    # Parse YAML frontmatter
    fm = {}
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            for line in parts[1].strip().split("\n"):
                if ":" in line:
                    key, val = line.split(":", 1)
                    fm[key.strip()] = val.strip().strip('"').strip("'")
            body = parts[2].strip()
        else:
            body = content
    else:
        body = content
    return fm, body, content


def get_all_skills():
    patterns = [
        os.path.join(SKILLS_DIR, "*.md"),
        os.path.join(SKILLS_DIR, "*", "SKILL.md"),
    ]
    paths = []
    for p in patterns:
        paths.extend(glob.glob(p))
    return paths


# ─── Scenario 1: Pack version pin ─────────────────────────────────────────────

def test_challenge_skill_exists():
    path = os.path.join(SKILLS_DIR, "CHALLENGE_SKILL.md")
    assert os.path.exists(path), "skills/CHALLENGE_SKILL.md not found"

def test_challenge_skill_version():
    path = os.path.join(SKILLS_DIR, "CHALLENGE_SKILL.md")
    if not os.path.exists(path):
        pytest.skip("CHALLENGE_SKILL.md missing")
    fm, body, content = load_skill(path)
    desc = fm.get("description", "")
    assert "otel-rm-v2" in desc, f"CHALLENGE_SKILL.md description must contain 'otel-rm-v2', got: {desc}"


# ─── Scenario 2: Minimum skill count ──────────────────────────────────────────

def test_minimum_skill_count():
    skills = get_all_skills()
    assert len(skills) >= 6, f"Need at least 6 skills, found {len(skills)}"

def test_all_skills_have_frontmatter():
    for path in get_all_skills():
        fm, body, content = load_skill(path)
        assert fm.get("name"), f"{os.path.basename(path)} missing 'name' in frontmatter"
        assert fm.get("description"), f"{os.path.basename(path)} missing 'description' in frontmatter"


# ─── Scenario 3: Judgment -old ──────────────────────────────────────────────

def test_judgment_skills_count():
    """At least 3 skills have a numeric threshold AND a recommended action AND >= 80 words body."""
    judgment_count = 0
    for path in get_all_skills():
        fm, body, content = load_skill(path)
        has_threshold = bool(re.search(r'[\d]+\s*%|>\s*[\d]|<\s*[\d]|above|below|under|over', body, re.IGNORECASE))
        has_action = bool(re.search(r'recommend|should|push|close|open|shift|target|confirm|activate|protect|hold', body, re.IGNORECASE))
        word_count = len(body.split())
        if has_threshold and has_action and word_count >= 80:
            judgment_count += 1
    assert judgment_count >= 3, f"Need at least 3 judgment skills (threshold+action+80 words), found {judgment_count}"


# ─── Scenario 4: Tool routing declared ────────────────────────────────────────

def test_skills_reference_required_tools():
    """Every skill names at least one required tool."""
    for path in get_all_skills():
        fm, body, content = load_skill(path)
        full_text = (fm.get("description", "") + " " + body).lower()
        has_tool = any(t in full_text for t in REQUIRED_TOOLS)
        assert has_tool, f"{os.path.basename(path)} does not reference any required tool"

def test_no_skill_instructs_raw_sql():
    """No skill tells the model to run raw SQL or query reservations_hackathon."""
    for path in get_all_skills():
        fm, body, content = load_skill(path)
        lower = content.lower()
        assert "run_sql" not in lower, f"{os.path.basename(path)} references run_sql"
        assert "select " not in lower or "reservations_hackathon" not in lower, \
            f"{os.path.basename(path)} references raw SQL on reservations_hackathon"


# ─── Scenario 5: Distinct routing ─────────────────────────────────────────────

def test_no_duplicate_skill_names():
    names = []
    for path in get_all_skills():
        fm, body, content = load_skill(path)
        names.append(fm.get("name", ""))
    assert len(names) == len(set(names)), f"Duplicate skill names: {[n for n in names if names.count(n) > 1]}"

def test_no_duplicate_descriptions():
    descs = []
    for path in get_all_skills():
        fm, body, content = load_skill(path)
        descs.append(" ".join(fm.get("description", "").split()))
    assert len(descs) == len(set(descs)), "Duplicate skill descriptions found"

def test_covers_otb_pickup_mix():
    """At least one skill targets OTB, one pickup, one segment mix."""
    all_text = ""
    for path in get_all_skills():
        fm, body, content = load_skill(path)
        all_text += " " + content.lower()
    assert "get_otb_summary" in all_text, "No skill targets OTB summary"
    assert "get_pickup_delta" in all_text, "No skill targets pickup"
    assert "get_segment_mix" in all_text, "No skill targets segment mix"


# ─── Scenario 6: Adversarial guardrail ────────────────────────────────────────

def test_at_least_one_trap_warning():
    """At least one skill warns against a known trap."""
    traps = ["row", "rows vs", "reservation", "property_date", "provisional",
             "cancelled", "count(*)", "grain", "stay_date"]
    for path in get_all_skills():
        fm, body, content = load_skill(path)
        lower = content.lower()
        if any(t in lower for t in traps):
            return  # Found at least one
    pytest.fail("No skill warns against a known trap (rows vs reservations, property_date, provisional, etc.)")