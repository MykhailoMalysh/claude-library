import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from branch_utils import DEFAULT_PATTERN, parse_ticket_from_branch


def test_parses_valid_branch():
    assert parse_ticket_from_branch("user/mykhailo/42-foo", "EPMPMVISTC") == "EPMPMVISTC-42"


def test_parses_branch_with_multi_word_description():
    assert (
        parse_ticket_from_branch("user/mykhailo/70-add-migvisor-tokenization-skill", "EPMPMVISTC")
        == "EPMPMVISTC-70"
    )


def test_returns_none_for_non_matching_branch():
    assert parse_ticket_from_branch("master", "EPMPMVISTC") is None
    assert parse_ticket_from_branch("feature/no-user-prefix", "EPMPMVISTC") is None


def test_returns_none_when_jira_project_missing():
    assert parse_ticket_from_branch("user/mykhailo/42-foo", "") is None
    assert parse_ticket_from_branch("user/mykhailo/42-foo", None) is None


def test_returns_none_when_branch_missing():
    assert parse_ticket_from_branch("", "EPMPMVISTC") is None
    assert parse_ticket_from_branch(None, "EPMPMVISTC") is None


def test_custom_pattern():
    pattern = "feature/{ticket}/{username}-{description}"
    assert parse_ticket_from_branch("feature/7/bob-fix", "PRJ", pattern) == "PRJ-7"
    assert parse_ticket_from_branch("user/bob/7-fix", "PRJ", pattern) is None


def test_default_pattern_explicit():
    assert parse_ticket_from_branch("user/bob/42-x", "PRJ", DEFAULT_PATTERN) == "PRJ-42"


def test_pattern_escapes_literals():
    assert parse_ticket_from_branch("a.b/9-x", "P", "a.b/{ticket}-{description}") == "P-9"
    assert parse_ticket_from_branch("axb/9-x", "P", "a.b/{ticket}-{description}") is None


def test_pattern_without_ticket_returns_none():
    assert parse_ticket_from_branch("user/bob/x", "P", "user/{username}/{description}") is None
