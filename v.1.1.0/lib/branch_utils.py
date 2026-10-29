"""Shared branch-naming helpers for dev-pr-open and dev-pr-review.

Convention: user/{username}/{ticket-number}-{description}
"""

import re

BRANCH_PATTERN = re.compile(r"^user/[^/]+/(\d+)-")


def parse_ticket_from_branch(branch, jira_project):
    """Return the Jira ticket key (e.g. "EPMPMVISTC-42") for a branch matching
    user/{username}/{ticket-number}-{desc}, or None if it doesn't match or
    jira_project is falsy."""
    if not branch or not jira_project:
        return None

    match = BRANCH_PATTERN.match(branch)
    if not match:
        return None

    return f"{jira_project}-{match.group(1)}"
