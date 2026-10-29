"""Azure DevOps REST API client for pull request operations.

Ports the logic previously in scripts/create-ado-pr.sh (check/create/update)
and adds inline/general PR comment posting for dev-pr-review.
"""

import requests

API_VERSION = "7.1"


class ADOApiError(Exception):
    """Raised when an ADO REST call fails or returns an error payload."""


class ADOClient:
    def __init__(self, org, project, repo, pat):
        self.org = org
        self.project = project
        self.repo = repo
        self.pat = pat
        self.base_url = f"https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}"
        self.web_base_url = f"https://dev.azure.com/{org}/{project}/_git/{repo}"

    def _auth(self):
        return ("", self.pat)

    def _pr_url(self, pr_id):
        return f"{self.web_base_url}/pullrequest/{pr_id}"

    def find_active_pr(self, source_branch):
        """Return {"pr_id": int, "pr_url": str} for an active PR on source_branch, or None."""
        url = (
            f"{self.base_url}/pullrequests"
            f"?searchCriteria.sourceRefName=refs/heads/{source_branch}"
            f"&searchCriteria.status=active&api-version={API_VERSION}"
        )
        response = requests.get(url, auth=self._auth())
        data = response.json()

        if data.get("message"):
            raise ADOApiError(data["message"])

        if data.get("count", 0) > 0:
            pr_id = data["value"][0]["pullRequestId"]
            return {"pr_id": pr_id, "pr_url": self._pr_url(pr_id)}

        return None

    def create_pr(self, source_branch, target_branch, title, description):
        """Create a PR and return {"pr_id": int, "pr_url": str}."""
        url = f"{self.base_url}/pullrequests?api-version={API_VERSION}"
        body = {
            "sourceRefName": f"refs/heads/{source_branch}",
            "targetRefName": f"refs/heads/{target_branch}",
            "title": title,
            "description": description,
        }
        response = requests.post(url, auth=self._auth(), json=body)
        data = response.json()

        pr_id = data.get("pullRequestId")
        if not pr_id:
            raise ADOApiError(data.get("message") or str(data))

        return {"pr_id": pr_id, "pr_url": self._pr_url(pr_id)}

    def update_pr(self, pr_id, title=None, description=None):
        """Update a PR's title and/or description, return {"pr_id": int, "pr_url": str}."""
        if title is None and description is None:
            raise ValueError("update_pr requires at least one of title or description")

        body = {}
        if title is not None:
            body["title"] = title
        if description is not None:
            body["description"] = description

        url = f"{self.base_url}/pullrequests/{pr_id}?api-version={API_VERSION}"
        response = requests.patch(url, auth=self._auth(), json=body)
        data = response.json()

        returned_id = data.get("pullRequestId")
        if not returned_id:
            raise ADOApiError(data.get("message") or str(data))

        return {"pr_id": returned_id, "pr_url": self._pr_url(returned_id)}

    def list_threads(self, pr_id, active_only=True):
        """Return PR comment threads as a list of dicts:
        {"thread_id", "status", "file_path", "line", "comments": [{"id", "content", "author"}]}.
        Deleted threads/comments are skipped; general (non-anchored) threads have
        file_path/line as None. Pass active_only=False to include resolved threads too."""
        url = f"{self.base_url}/pullRequests/{pr_id}/threads?api-version={API_VERSION}"
        response = requests.get(url, auth=self._auth())
        data = response.json()

        if data.get("message"):
            raise ADOApiError(data["message"])

        threads = []
        for thread in data.get("value", []):
            if thread.get("isDeleted"):
                continue

            status = thread.get("status", "unknown")
            if active_only and status != "active":
                continue

            comments = [
                {
                    "id": comment["id"],
                    "content": comment.get("content", ""),
                    "author": (comment.get("author") or {}).get("displayName"),
                }
                for comment in thread.get("comments", [])
                if not comment.get("isDeleted")
            ]
            if not comments:
                continue

            context = thread.get("threadContext") or {}
            threads.append(
                {
                    "thread_id": thread["id"],
                    "status": status,
                    "file_path": context.get("filePath"),
                    "line": (context.get("rightFileStart") or {}).get("line"),
                    "comments": comments,
                }
            )

        return threads

    def reply_to_thread(self, pr_id, thread_id, content):
        """Post a reply comment in an existing thread. Returns {"comment_id": int}."""
        url = f"{self.base_url}/pullRequests/{pr_id}/threads/{thread_id}/comments?api-version={API_VERSION}"
        body = {"content": content, "commentType": 1, "parentCommentId": 1}
        response = requests.post(url, auth=self._auth(), json=body)
        data = response.json()

        comment_id = data.get("id")
        if not comment_id:
            raise ADOApiError(data.get("message") or str(data))

        return {"comment_id": comment_id}

    def resolve_thread(self, pr_id, thread_id, status="fixed"):
        """Set a thread's status (default "fixed"). Returns {"status": str}."""
        url = f"{self.base_url}/pullRequests/{pr_id}/threads/{thread_id}?api-version={API_VERSION}"
        body = {"status": status}
        response = requests.patch(url, auth=self._auth(), json=body)
        data = response.json()

        returned_status = data.get("status")
        if not returned_status:
            raise ADOApiError(data.get("message") or str(data))

        return {"status": returned_status}

    def post_comment(self, pr_id, content, file_path=None, line=None):
        """Post a PR comment thread. Anchored to file_path/line when both are given,
        otherwise posted as a general (top-level) PR comment."""
        body = {
            "comments": [{"parentCommentId": 0, "content": content, "commentType": 1}],
            "status": 1,
        }

        if file_path is not None and line is not None:
            body["threadContext"] = {
                "filePath": file_path,
                "rightFileStart": {"line": line, "offset": 1},
                "rightFileEnd": {"line": line, "offset": 1},
            }

        url = f"{self.base_url}/pullRequests/{pr_id}/threads?api-version={API_VERSION}"
        response = requests.post(url, auth=self._auth(), json=body)
        data = response.json()

        thread_id = data.get("id")
        if not thread_id:
            raise ADOApiError(data.get("message") or str(data))

        return {"thread_id": thread_id}
