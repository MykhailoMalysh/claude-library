"""Jira REST API client for issue read/search/create/transition/comment operations.

Replaces the Jira MCP tool calls previously used across ai-sdlc skills (get_issue,
search_issues, create_issue, transition_issue/update_issue, add_comment) with direct
calls to the Jira REST API, authenticated via basic auth (username + API token).
"""

import requests

API_BASE = "rest/api/2"


class JiraApiError(Exception):
    """Raised when a Jira REST call fails or returns an error payload."""


class JiraClient:
    def __init__(self, base_url, username, api_token):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.api_token = api_token
        self._epic_link_field_id = None
        self.last_epics_total = None

    def _auth(self):
        return (self.username, self.api_token)

    def _url(self, path):
        return f"{self.base_url}/{API_BASE}/{path}"

    @staticmethod
    def _error_message(response, data):
        if isinstance(data, dict):
            messages = data.get("errorMessages")
            if messages:
                return "; ".join(messages)
            if data.get("message"):
                return data["message"]
        return f"HTTP {response.status_code}: {data}"

    @staticmethod
    def _issue_from_payload(data):
        fields = data.get("fields", {})
        return {
            "key": data["key"],
            "summary": fields.get("summary"),
            "description": fields.get("description"),
            "status": (fields.get("status") or {}).get("name"),
        }

    def get_issue(self, issue_key):
        """Return {"key", "summary", "description", "status"} for issue_key."""
        url = self._url(f"issue/{issue_key}?fields=summary,description,status")
        response = requests.get(url, auth=self._auth())
        data = response.json()

        if response.status_code >= 400:
            raise JiraApiError(self._error_message(response, data))

        return self._issue_from_payload(data)

    def search_issues(self, jql, max_results=50):
        """Return a list of issues (same shape as get_issue) matching jql."""
        url = self._url("search")
        body = {
            "jql": jql,
            "fields": ["summary", "description", "status"],
            "maxResults": max_results,
        }
        response = requests.post(url, auth=self._auth(), json=body)
        data = response.json()

        if response.status_code >= 400:
            raise JiraApiError(self._error_message(response, data))

        return [self._issue_from_payload(issue) for issue in data.get("issues", [])]

    def create_issue(self, project_key, summary, issue_type, description=None, assignee=None, priority=None, parent_key=None, epic_key=None):
        """Create an issue and return {"key": str}. parent_key links a Sub-task to its parent. epic_key sets the Epic Link."""
        fields = {
            "project": {"key": project_key},
            "summary": summary,
            "issuetype": {"name": issue_type},
        }
        if description is not None:
            fields["description"] = description
        if assignee:
            fields["assignee"] = {"name": assignee}
        if priority:
            fields["priority"] = {"name": priority}
        if parent_key:
            fields["parent"] = {"key": parent_key}
        if epic_key:
            field_id = self.epic_link_field_id()
            if field_id is None:
                raise JiraApiError("Epic Link field not found in this Jira instance. Epic linking is not supported.")
            fields[field_id] = epic_key

        url = self._url("issue")
        response = requests.post(url, auth=self._auth(), json={"fields": fields})
        data = response.json()

        if response.status_code >= 400 or not data.get("key"):
            raise JiraApiError(self._error_message(response, data))

        return {"key": data["key"]}

    def get_transitions(self, issue_key):
        """Return the list of available transitions for issue_key, as returned by Jira."""
        url = self._url(f"issue/{issue_key}/transitions")
        response = requests.get(url, auth=self._auth())
        data = response.json()

        if response.status_code >= 400:
            raise JiraApiError(self._error_message(response, data))

        return data.get("transitions", [])

    def transition_issue(self, issue_key, status_name):
        """Transition issue_key to the workflow status named status_name.

        Matches against the transition's target status name (case-insensitive) rather
        than the transition's own name, since transition names and target status names
        commonly differ per project workflow.
        """
        transitions = self.get_transitions(issue_key)
        match = next(
            (t for t in transitions if t.get("to", {}).get("name", "").lower() == status_name.lower()),
            None,
        )
        if match is None:
            available = ", ".join(t.get("to", {}).get("name", "?") for t in transitions)
            raise JiraApiError(f"No transition found to status: {status_name}. Available: {available}")

        url = self._url(f"issue/{issue_key}/transitions")
        response = requests.post(url, auth=self._auth(), json={"transition": {"id": match["id"]}})

        if response.status_code >= 400:
            data = response.json() if response.content else {}
            raise JiraApiError(self._error_message(response, data))

        return {"status": match["to"]["name"]}

    def add_comment(self, issue_key, body):
        """Post a plain-text comment on issue_key. Returns {"comment_id": str}."""
        url = self._url(f"issue/{issue_key}/comment")
        response = requests.post(url, auth=self._auth(), json={"body": body})
        data = response.json()

        if response.status_code >= 400 or not data.get("id"):
            raise JiraApiError(self._error_message(response, data))

        return {"comment_id": data["id"]}

    def link_issues(self, blocker_key, blocked_key, link_type="Blocks"):
        """Create an issue link between blocker_key and blocked_key.

        Args:
            blocker_key: The issue that blocks
            blocked_key: The issue that is blocked
            link_type: The link type name (default: "Blocks")

        Returns:
            {"link_id": str} on success
        """
        url = self._url("issueLink")
        body = {
            "type": {"name": link_type},
            "inwardIssue": {"key": blocked_key},
            "outwardIssue": {"key": blocker_key},
        }
        response = requests.post(url, auth=self._auth(), json=body)

        if response.status_code >= 400:
            data = response.json() if response.content else {}
            raise JiraApiError(self._error_message(response, data))

        # Issue link creation returns 201 with no body or location header with link ID
        return {"status": "linked"}

    def assign_issue(self, issue_key, assignee):
        """Assign issue_key to assignee username.

        Args:
            issue_key: The issue to assign
            assignee: Username to assign to, or None to unassign

        Returns:
            {"assignee": str} on success
        """
        url = self._url(f"issue/{issue_key}/assignee")
        body = {"name": assignee} if assignee else {"name": None}
        response = requests.put(url, auth=self._auth(), json=body)

        if response.status_code >= 400:
            data = response.json() if response.content else {}
            raise JiraApiError(self._error_message(response, data))

        return {"assignee": assignee or "unassigned"}

    def add_labels(self, issue_key, labels):
        """Add labels to issue_key.

        Args:
            issue_key: The issue to label
            labels: List of label strings to add

        Returns:
            {"labels": list} on success
        """
        if not labels:
            return {"labels": []}

        url = self._url(f"issue/{issue_key}")
        body = {
            "update": {
                "labels": [{"add": label} for label in labels]
            }
        }
        response = requests.put(url, auth=self._auth(), json=body)

        if response.status_code >= 400:
            data = response.json() if response.content else {}
            raise JiraApiError(self._error_message(response, data))

        return {"labels": labels}

    def list_epics(self, project_key, include_done=False):
        """Return a list of epics in the project as [{"key", "summary", "status"}].
        Sets self.last_epics_total to Jira's reported total (may exceed the list)."""
        jql = f"project = {project_key} AND issuetype = Epic"
        if not include_done:
            jql += " AND statusCategory != Done"

        url = self._url("search")
        body = {
            "jql": jql,
            "fields": ["summary", "status"],
            "maxResults": 100,
        }
        response = requests.post(url, auth=self._auth(), json=body)
        data = response.json()

        if response.status_code >= 400:
            raise JiraApiError(self._error_message(response, data))

        self.last_epics_total = data.get("total")
        epics = []
        for issue in data.get("issues", []):
            fields = issue.get("fields", {})
            epics.append({
                "key": issue["key"],
                "summary": fields.get("summary"),
                "status": (fields.get("status") or {}).get("name"),
            })
        return epics

    def epic_link_field_id(self):
        """Return the Epic Link custom field ID, or None if not found. Result is cached."""
        if self._epic_link_field_id is not None:
            return self._epic_link_field_id

        url = self._url("field")
        response = requests.get(url, auth=self._auth())
        data = response.json()

        if response.status_code >= 400:
            raise JiraApiError(self._error_message(response, data))

        # Look for the field by schema.custom ending in :gh-epic-link (Jira Server/DC)
        for field in data:
            schema = field.get("schema", {})
            custom = schema.get("custom", "")
            if custom.endswith(":gh-epic-link"):
                self._epic_link_field_id = field["id"]
                return self._epic_link_field_id

        # Fallback: look for field with name "Epic Link"
        for field in data:
            if field.get("name") == "Epic Link":
                self._epic_link_field_id = field["id"]
                return self._epic_link_field_id

        # No Epic Link field found
        self._epic_link_field_id = None
        return None

    def set_epic(self, issue_key, epic_key):
        """Set the Epic Link field for issue_key to epic_key. Raises error if no Epic Link field."""
        field_id = self.epic_link_field_id()
        if field_id is None:
            raise JiraApiError("Epic Link field not found in this Jira instance. Epic linking is not supported.")

        url = self._url(f"issue/{issue_key}")
        body = {"fields": {field_id: epic_key}}
        response = requests.put(url, auth=self._auth(), json=body)

        if response.status_code >= 400:
            data = response.json() if response.content else {}
            raise JiraApiError(self._error_message(response, data))

    def project_statuses(self, project_key):
        """Return available statuses for each issue type in the project as {issue_type: [status_names]}."""
        url = self._url(f"project/{project_key}/statuses")
        response = requests.get(url, auth=self._auth())
        data = response.json()

        if response.status_code >= 400:
            raise JiraApiError(self._error_message(response, data))

        statuses_by_type = {}
        for issue_type_data in data:
            issue_type = issue_type_data.get("name")
            statuses = issue_type_data.get("statuses", [])
            statuses_by_type[issue_type] = [s.get("name") for s in statuses]

        return statuses_by_type
