"""Shared branch-naming helpers for dev-pr-open and dev-pr-review.

Default convention: user/{username}/{ticket}-{description}. A profile's
`branch_pattern` may use the same three placeholders in another layout.
"""

import re

DEFAULT_PATTERN = "user/{username}/{ticket}-{description}"

_PLACEHOLDERS = {
    "{username}": r"[^/]+",
    "{ticket}": r"(?P<ticket>\d+)",
    "{description}": r".*",
}


def pattern_regex(pattern=DEFAULT_PATTERN):
    """Compile a branch pattern into an anchored regex; literals are escaped."""
    parts = re.split(r"(\{username\}|\{ticket\}|\{description\})", pattern)
    return re.compile("^" + "".join(_PLACEHOLDERS.get(p, re.escape(p)) for p in parts) + "$")


def parse_ticket_from_branch(branch, jira_project, pattern=None):
    """Return the Jira ticket key (e.g. "EPMPMVISTC-42") for a branch matching
    `pattern` (default DEFAULT_PATTERN), or None if it doesn't match, the
    pattern has no {ticket}, or jira_project is falsy."""
    if not branch or not jira_project:
        return None
    match = pattern_regex(pattern or DEFAULT_PATTERN).match(branch)
    if not match or "ticket" not in match.groupdict():
        return None
    return f"{jira_project}-{match.group('ticket')}"
