"""Style and contract lint for skills, agents, and shared references.

Per-file style tests run over MIGRATED, the set of skills, agents, and
references rewritten to the v1.2.0 style. Repo-wide checks run over every
file.
"""
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MIGRATED = {
    "agents/preflight-planner.md",
    "agents/preflight-runner.md",
    "skills/dev-pr-preflight/SKILL.md",
    "agents/verifier.md",
    "agents/error-handler.md",
    "agents/griller.md",
    "agents/review-business-logic.md",
    "agents/review-conventions.md",
    "agents/review-correctness.md",
    "agents/review-cross-file.md",
    "agents/review-removed-behavior.md",
    "agents/review-security.md",
    "agents/review-simplification.md",
    "skills/dev-pr-review/SKILL.md",
    "references/agent-contract.md",
    "references/conventions.md",
    "references/prompt-style.md",
    "skills/dev-pr-address-comments/SKILL.md",
    "skills/dev-pr-open/SKILL.md",
    "skills/dev-implement/SKILL.md",
    "skills/dev-profile-init/SKILL.md",
    "skills/dev-task-start/SKILL.md",
    "skills/dev-task-summary/SKILL.md",
    "skills/dev-impl-plan/SKILL.md",
    "skills/pm-create-ticket/SKILL.md",
    "skills/dev-grill-me/SKILL.md",
    "skills/dev-wayfinder/SKILL.md",
    "skills/dev-prototype/SKILL.md",
}

SHOUTING = re.compile(r"\b(CRITICAL|IMPORTANT|MUST)\b")
ENV_READS = re.compile(
    r"source\s+(\./)?\.env\b|cat\s+(\./)?\.env\b|load_dotenv|(^|[\s;&|])\.\s+(\./)?\.env\b"
)
DEV_BUG_FIX = "dev-bug-fix"
ORCHESTRATORS = ["dev-pr-review", "dev-pr-preflight", "dev-implement"]
PLACEHOLDER_PATTERN = "PLACEHOLDER|<[^>]+>|TODO"


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def skill_files():
    skills = os.path.join(ROOT, "skills")
    return sorted(
        f"skills/{d}/SKILL.md"
        for d in os.listdir(skills)
        if os.path.isfile(os.path.join(skills, d, "SKILL.md"))
    )


def agent_files():
    return sorted(
        f"agents/{f}" for f in os.listdir(os.path.join(ROOT, "agents")) if f.endswith(".md")
    )


def reference_files():
    return sorted(
        f"references/{f}"
        for f in os.listdir(os.path.join(ROOT, "references"))
        if f.endswith(".md")
    )


def _migrated(predicate=lambda p: True):
    return sorted(p for p in MIGRATED if predicate(p))


def _frontmatter(text):
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    return m.group(1) if m else ""


# --- helpers sanity ----------------------------------------------------------

def test_migrated_files_exist():
    for rel in MIGRATED:
        assert os.path.isfile(os.path.join(ROOT, rel)), rel


def test_helpers_find_files():
    assert skill_files() and agent_files() and reference_files()


# --- per-file style (MIGRATED only) -----------------------------------------

_MIGRATED_SKILLS = _migrated(lambda p: p.startswith("skills/") and p.endswith("/SKILL.md"))


@pytest.mark.skipif(not _MIGRATED_SKILLS, reason="no migrated skills yet")
@pytest.mark.parametrize("rel", _MIGRATED_SKILLS or ["-"])
def test_every_skill_has_role(rel):
    fm = _frontmatter(_read(rel))
    assert re.search(r"^role:\s*(planning|implementation|team)\s*$", fm, re.M), rel


@pytest.mark.parametrize("rel", _migrated())
def test_no_shouting(rel):
    bad = [
        line
        for line in _read(rel).splitlines()
        if SHOUTING.search(line) and "severity" not in line and "| CRITICAL |" not in line
    ]
    assert not bad, f"{rel}: {bad}"


@pytest.mark.parametrize("rel", _migrated())
def test_no_env_file_reads(rel):
    bad = [line for line in _read(rel).splitlines() if ENV_READS.search(line)]
    assert not bad, f"{rel}: {bad}"


@pytest.mark.parametrize("rel", _migrated(lambda p: p != "README.md"))
def test_migrated_file_has_no_dev_bug_fix_refs(rel):
    assert DEV_BUG_FIX not in _read(rel), rel


def test_env_read_pattern():
    for s in ["source .env", "cat .env", "load_dotenv()", ". ./.env", "x && . .env"]:
        assert ENV_READS.search(s), s
    for s in ["Never open `.env`.", "agents never read .env files", "settings.local.json"]:
        assert not ENV_READS.search(s), s


# --- repo-wide checks owned by later tasks ----------------------------------

def test_no_dev_bug_fix_refs():
    files = skill_files() + agent_files() + reference_files()
    bad = [rel for rel in files if DEV_BUG_FIX in _read(rel)]
    assert not os.path.isdir(os.path.join(ROOT, "skills", DEV_BUG_FIX))
    assert not bad, bad


@pytest.mark.parametrize(
    "name",
    [
        "dev-pr-preflight",
        "dev-implement",
        "dev-pr-review",
    ],
)
def test_orchestrators_reject_unevidenced_ok(name):
    text = _read(f"skills/{name}/SKILL.md")
    assert "MALFORMED_OUTPUT" in text and "evidence" in text, name


def test_preflight_rejects_placeholders():
    skill = _read("skills/dev-pr-preflight/SKILL.md")
    assert re.search(r"reject[\s\S]{0,300}pattern `" + re.escape(PLACEHOLDER_PATTERN) + "`", skill, re.I)
    assert "NEEDS_DECISION" in skill
    planner = _read("agents/preflight-planner.md")
    assert re.search(r"Never emit placeholders", planner)
    assert re.search(r"`blocked` \+ `NEEDS_DECISION`", planner)


# --- contract ---------------------------------------------------------------

def test_contract_defines_v2_fields():
    text = _read("references/agent-contract.md")
    for token in ["`evidence`", "`escalation`", "`NEEDS_DECISION`", "`implementation`"]:
        assert token in text, token
    for field in ["files_changed", "tests_run", "local_test_steps", "recommendation"]:
        assert field in text, field


def test_conventions_configuration_section():
    text = _read("references/conventions.md")
    assert not re.search(r"^#+ .*\.env.? schema", text, re.M)
    assert re.search(r"^## Configuration", text, re.M)
    assert "settings.local.json" in text
