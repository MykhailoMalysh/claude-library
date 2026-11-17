"""GitLab REST API client for merge request read, create, and comment operations.

Used by dev-pr-review: `get_mr` reads MR context during a review (read-only), and
`post_note` / `post_inline_discussion` post comments only when the developer
explicitly asks. Used by dev-pr-open (for GitLab-hosted repos): `find_active_mr` /
`create_mr` mirror ADOClient's find_active_pr/create_pr. Authenticated with a
personal/project access token via the PRIVATE-TOKEN header.

`base_url` must be the GitLab instance root (e.g. "https://git.epam.com"), not a
project URL — a project-path base_url looks like a valid host to `requests` but
every API call 404s into GitLab's HTML SAML-redirect page instead of JSON.
"""

import re
from urllib.parse import quote

import requests

API_BASE = "api/v4"


class GitLabApiError(Exception):
    """Raised when a GitLab REST call fails or returns an error payload."""


def project_from_remote(remote_url):
    """Return the 'group/subgroup/project' path from a git remote URL, or None.

    Handles ssh (git@host:group/proj.git), ssh:// (ssh://git@host:2222/group/proj.git)
    and https (https://host/group/proj.git) forms.
    """
    url = remote_url.strip()
    match = re.match(r"^[\w.-]+@[\w.-]+:(?!\d+/)(.+?)(?:\.git)?/?$", url)
    if not match:
        match = re.match(r"^(?:ssh|https?)://[^/]+/(.+?)(?:\.git)?/?$", url)
    return match.group(1) if match else None


class GitLabClient:
    def __init__(self, base_url, token, project):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.project = project

    def _headers(self):
        return {"PRIVATE-TOKEN": self.token}

    def _mrs_url(self, suffix=""):
        project_id = quote(self.project, safe="")
        return f"{self.base_url}/{API_BASE}/projects/{project_id}/merge_requests{suffix}"

    def _mr_url(self, iid, suffix=""):
        project_id = quote(self.project, safe="")
        return f"{self.base_url}/{API_BASE}/projects/{project_id}/merge_requests/{iid}{suffix}"

    @staticmethod
    def _parse(response):
        try:
            data = response.json()
        except ValueError:
            data = response.text
        if response.status_code >= 400:
            if isinstance(data, dict):
                message = data.get("message") or data.get("error") or data
                raise GitLabApiError(f"HTTP {response.status_code}: {message}")
            raise GitLabApiError(f"HTTP {response.status_code}: {data}")
        return data

    def find_active_mr(self, source_branch):
        """Return {"mr_iid": int, "mr_url": str} for an open MR on source_branch, or None."""
        response = requests.get(
            self._mrs_url(),
            headers=self._headers(),
            params={"source_branch": source_branch, "state": "opened"},
        )
        data = self._parse(response)

        if data:
            return {"mr_iid": data[0]["iid"], "mr_url": data[0]["web_url"]}

        return None

    def create_mr(self, source_branch, target_branch, title, description, remove_source_branch=True):
        """Create an MR and return {"mr_iid": int, "mr_url": str}."""
        body = {
            "source_branch": source_branch,
            "target_branch": target_branch,
            "title": title,
            "description": description,
            "remove_source_branch": remove_source_branch,
        }
        response = requests.post(self._mrs_url(), headers=self._headers(), json=body)
        data = self._parse(response)

        mr_iid = data.get("iid")
        if not mr_iid:
            raise GitLabApiError(data.get("message") or str(data))

        return {"mr_iid": mr_iid, "mr_url": data["web_url"]}

    def get_mr(self, iid):
        """Return MR summary fields plus diff_refs for merge request iid."""
        data = self._parse(requests.get(self._mr_url(iid), headers=self._headers()))
        return {
            "iid": data["iid"],
            "title": data.get("title"),
            "description": data.get("description"),
            "state": data.get("state"),
            "source_branch": data.get("source_branch"),
            "target_branch": data.get("target_branch"),
            "web_url": data.get("web_url"),
            "diff_refs": data.get("diff_refs"),
        }

    def post_note(self, iid, content):
        """Post a general MR note. Returns {"note_id": int}."""
        response = requests.post(self._mr_url(iid, "/notes"), headers=self._headers(), json={"body": content})
        data = self._parse(response)
        return {"note_id": data["id"]}

    def post_inline_discussion(self, iid, content, file_path, line):
        """Start a diff discussion on file_path:line (new side). Returns {"note_id": int}.

        Uses the MR's current diff_refs so the comment anchors to the latest version.
        """
        diff_refs = self.get_mr(iid).get("diff_refs") or {}
        if not all(diff_refs.get(k) for k in ("base_sha", "start_sha", "head_sha")):
            raise GitLabApiError(f"MR !{iid} has no diff_refs; cannot post an inline comment")

        body = {
            "body": content,
            "position": {
                "position_type": "text",
                "base_sha": diff_refs["base_sha"],
                "start_sha": diff_refs["start_sha"],
                "head_sha": diff_refs["head_sha"],
                "old_path": file_path,
                "new_path": file_path,
                "new_line": int(line),
            },
        }
        response = requests.post(self._mr_url(iid, "/discussions"), headers=self._headers(), json=body)
        data = self._parse(response)
        notes = data.get("notes") or [{}]
        return {"note_id": notes[0].get("id")}
