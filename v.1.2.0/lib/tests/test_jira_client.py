import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jira_client import JiraApiError, JiraClient


def make_client():
    return JiraClient(base_url="https://jira.example.com", username="me@example.com", api_token="secret-token")


def mock_response(json_data, status_code=200):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data
    response.content = b"x" if json_data else b""
    return response


class TestGetIssue:
    @patch("jira_client.requests.get")
    def test_returns_issue_fields(self, mock_get):
        mock_get.return_value = mock_response(
            {
                "key": "PROJ-42",
                "fields": {
                    "summary": "Fix the thing",
                    "description": "Details here",
                    "status": {"name": "To Do"},
                },
            }
        )
        client = make_client()

        result = client.get_issue("PROJ-42")

        assert result == {
            "key": "PROJ-42",
            "summary": "Fix the thing",
            "description": "Details here",
            "status": "To Do",
        }

    @patch("jira_client.requests.get")
    def test_raises_on_api_error(self, mock_get):
        mock_get.return_value = mock_response({"errorMessages": ["Issue does not exist"]}, status_code=404)
        client = make_client()

        try:
            client.get_issue("PROJ-999")
            assert False, "expected JiraApiError"
        except JiraApiError as e:
            assert "Issue does not exist" in str(e)


class TestSearchIssues:
    @patch("jira_client.requests.post")
    def test_returns_list_of_issues(self, mock_post):
        mock_post.return_value = mock_response(
            {
                "issues": [
                    {"key": "PROJ-1", "fields": {"summary": "A", "description": None, "status": {"name": "To Do"}}},
                    {"key": "PROJ-2", "fields": {"summary": "B", "description": None, "status": {"name": "In Progress"}}},
                ]
            }
        )
        client = make_client()

        result = client.search_issues("project = PROJ AND assignee = currentUser()")

        assert [issue["key"] for issue in result] == ["PROJ-1", "PROJ-2"]
        body = mock_post.call_args.kwargs["json"]
        assert body["jql"] == "project = PROJ AND assignee = currentUser()"

    @patch("jira_client.requests.post")
    def test_raises_on_api_error(self, mock_post):
        mock_post.return_value = mock_response({"errorMessages": ["Invalid JQL"]}, status_code=400)
        client = make_client()

        try:
            client.search_issues("not valid jql")
            assert False, "expected JiraApiError"
        except JiraApiError as e:
            assert "Invalid JQL" in str(e)


class TestCreateIssue:
    @patch("jira_client.requests.post")
    def test_returns_key_on_success(self, mock_post):
        mock_post.return_value = mock_response({"key": "PROJ-100"})
        client = make_client()

        result = client.create_issue("PROJ", "New ticket", "Task", assignee="me@example.com")

        assert result == {"key": "PROJ-100"}
        body = mock_post.call_args.kwargs["json"]
        assert body["fields"]["project"] == {"key": "PROJ"}
        assert body["fields"]["assignee"] == {"name": "me@example.com"}

    @patch("jira_client.requests.post")
    def test_omits_optional_fields_when_not_given(self, mock_post):
        mock_post.return_value = mock_response({"key": "PROJ-101"})
        client = make_client()

        client.create_issue("PROJ", "New ticket", "Task")

        body = mock_post.call_args.kwargs["json"]
        assert "assignee" not in body["fields"]
        assert "priority" not in body["fields"]

    @patch("jira_client.requests.post")
    def test_raises_on_failure(self, mock_post):
        mock_post.return_value = mock_response({"errorMessages": ["Field 'summary' is required"]}, status_code=400)
        client = make_client()

        try:
            client.create_issue("PROJ", "", "Task")
            assert False, "expected JiraApiError"
        except JiraApiError as e:
            assert "summary" in str(e)

    @patch("jira_client.requests.post")
    def test_includes_parent_when_given(self, mock_post):
        mock_post.return_value = mock_response({"key": "PROJ-102"})
        client = make_client()

        client.create_issue("PROJ", "Sub-task", "Sub-task", parent_key="PROJ-1")

        body = mock_post.call_args.kwargs["json"]
        assert body["fields"]["parent"] == {"key": "PROJ-1"}


class TestTransitionIssue:
    @patch("jira_client.requests.post")
    @patch("jira_client.requests.get")
    def test_transitions_to_matching_status(self, mock_get, mock_post):
        mock_get.return_value = mock_response(
            {
                "transitions": [
                    {"id": "11", "name": "Start Progress", "to": {"name": "In Progress"}},
                    {"id": "21", "name": "Resolve", "to": {"name": "Resolved"}},
                ]
            }
        )
        mock_post.return_value = mock_response({})
        client = make_client()

        result = client.transition_issue("PROJ-42", "In Progress")

        assert result == {"status": "In Progress"}
        body = mock_post.call_args.kwargs["json"]
        assert body == {"transition": {"id": "11"}}

    @patch("jira_client.requests.get")
    def test_raises_when_no_matching_transition(self, mock_get):
        mock_get.return_value = mock_response(
            {"transitions": [{"id": "11", "name": "Start Progress", "to": {"name": "In Progress"}}]}
        )
        client = make_client()

        try:
            client.transition_issue("PROJ-42", "Done")
            assert False, "expected JiraApiError"
        except JiraApiError as e:
            assert "Done" in str(e)
            assert "In Progress" in str(e)

    @patch("jira_client.requests.get")
    def test_raises_on_transitions_lookup_failure(self, mock_get):
        mock_get.return_value = mock_response({"errorMessages": ["Unauthorized"]}, status_code=401)
        client = make_client()

        try:
            client.transition_issue("PROJ-42", "In Progress")
            assert False, "expected JiraApiError"
        except JiraApiError as e:
            assert "Unauthorized" in str(e)


class TestAddComment:
    @patch("jira_client.requests.post")
    def test_returns_comment_id_on_success(self, mock_post):
        mock_post.return_value = mock_response({"id": "500"})
        client = make_client()

        result = client.add_comment("PROJ-42", "Pull request opened: ...")

        assert result == {"comment_id": "500"}
        body = mock_post.call_args.kwargs["json"]
        assert body == {"body": "Pull request opened: ..."}

    @patch("jira_client.requests.post")
    def test_raises_on_failure(self, mock_post):
        mock_post.return_value = mock_response({"errorMessages": ["Issue does not exist"]}, status_code=404)
        client = make_client()

        try:
            client.add_comment("PROJ-999", "note")
            assert False, "expected JiraApiError"
        except JiraApiError as e:
            assert "Issue does not exist" in str(e)
