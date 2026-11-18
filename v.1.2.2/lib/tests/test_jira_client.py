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


class TestListEpics:
    @patch("jira_client.requests.post")
    def test_returns_open_epics_by_default(self, mock_post):
        mock_post.return_value = mock_response(
            {
                "issues": [
                    {"key": "PROJ-1", "fields": {"summary": "Epic A", "status": {"name": "In Progress"}}},
                    {"key": "PROJ-2", "fields": {"summary": "Epic B", "status": {"name": "To Do"}}},
                ]
            }
        )
        client = make_client()

        result = client.list_epics("PROJ")

        assert result == [
            {"key": "PROJ-1", "summary": "Epic A", "status": "In Progress"},
            {"key": "PROJ-2", "summary": "Epic B", "status": "To Do"},
        ]
        body = mock_post.call_args.kwargs["json"]
        assert "issuetype = Epic" in body["jql"]
        assert "project = PROJ" in body["jql"]
        assert "statusCategory != Done" in body["jql"]

    @patch("jira_client.requests.post")
    def test_includes_done_epics_when_requested(self, mock_post):
        mock_post.return_value = mock_response(
            {
                "issues": [
                    {"key": "PROJ-1", "fields": {"summary": "Epic A", "status": {"name": "Done"}}},
                ]
            }
        )
        client = make_client()

        result = client.list_epics("PROJ", include_done=True)

        assert result == [{"key": "PROJ-1", "summary": "Epic A", "status": "Done"}]
        body = mock_post.call_args.kwargs["json"]
        assert "statusCategory != Done" not in body["jql"]

    @patch("jira_client.requests.post")
    def test_raises_on_api_error(self, mock_post):
        mock_post.return_value = mock_response({"errorMessages": ["Invalid JQL"]}, status_code=400)
        client = make_client()

        try:
            client.list_epics("PROJ")
            assert False, "expected JiraApiError"
        except JiraApiError as e:
            assert "Invalid JQL" in str(e)


class TestListEpicsTotal:
    @patch("jira_client.requests.post")
    def test_records_total_reported_by_jira(self, mock_post):
        mock_post.return_value = mock_response(
            {"total": 150, "issues": [{"key": "PROJ-1", "fields": {"summary": "A", "status": {"name": "To Do"}}}]}
        )
        client = make_client()

        result = client.list_epics("PROJ")

        assert len(result) == 1
        assert client.last_epics_total == 150


class TestEpicLinkFieldId:
    @patch("jira_client.requests.get")
    def test_returns_field_id_for_gh_epic_link(self, mock_get):
        mock_get.return_value = mock_response(
            [
                {"id": "customfield_10001", "name": "Story Points", "schema": {"custom": "com.atlassian.jira.plugin:points"}},
                {"id": "customfield_10100", "name": "Epic Link", "schema": {"custom": "com.pyxis.greenhopper.jira:gh-epic-link"}},
            ]
        )
        client = make_client()

        result = client.epic_link_field_id()

        assert result == "customfield_10100"
        mock_get.assert_called_once()

    @patch("jira_client.requests.get")
    def test_returns_field_id_by_name_epic_link(self, mock_get):
        mock_get.return_value = mock_response(
            [
                {"id": "customfield_10001", "name": "Story Points", "schema": {"type": "number"}},
                {"id": "customfield_10200", "name": "Epic Link", "schema": {"type": "any"}},
            ]
        )
        client = make_client()

        result = client.epic_link_field_id()

        assert result == "customfield_10200"

    @patch("jira_client.requests.get")
    def test_returns_none_when_no_epic_link_field(self, mock_get):
        mock_get.return_value = mock_response(
            [
                {"id": "customfield_10001", "name": "Story Points", "schema": {"custom": "com.atlassian.jira.plugin:points"}},
            ]
        )
        client = make_client()

        result = client.epic_link_field_id()

        assert result is None

    @patch("jira_client.requests.get")
    def test_caches_result(self, mock_get):
        mock_get.return_value = mock_response(
            [
                {"id": "customfield_10100", "name": "Epic Link", "schema": {"custom": "com.pyxis.greenhopper.jira:gh-epic-link"}},
            ]
        )
        client = make_client()

        result1 = client.epic_link_field_id()
        result2 = client.epic_link_field_id()

        assert result1 == result2 == "customfield_10100"
        assert mock_get.call_count == 1


class TestSetEpic:
    @patch("jira_client.requests.put")
    def test_sets_epic_link_field(self, mock_put):
        mock_put.return_value = mock_response({}, status_code=204)
        client = make_client()
        client._epic_link_field_id = "customfield_10100"

        client.set_epic("PROJ-42", "PROJ-1")

        body = mock_put.call_args.kwargs["json"]
        assert body == {"fields": {"customfield_10100": "PROJ-1"}}

    @patch("jira_client.requests.get")
    def test_raises_clear_error_when_no_epic_link_field(self, mock_get):
        mock_get.return_value = mock_response([])
        client = make_client()

        try:
            client.set_epic("PROJ-42", "PROJ-1")
            assert False, "expected JiraApiError"
        except JiraApiError as e:
            assert str(e).startswith("Epic Link field not found")

    @patch("jira_client.requests.put")
    def test_raises_on_api_error(self, mock_put):
        mock_put.return_value = mock_response({"errorMessages": ["Issue does not exist"]}, status_code=404)
        client = make_client()
        client._epic_link_field_id = "customfield_10100"

        try:
            client.set_epic("PROJ-999", "PROJ-1")
            assert False, "expected JiraApiError"
        except JiraApiError as e:
            assert "Issue does not exist" in str(e)


class TestCreateIssueWithEpic:
    @patch("jira_client.requests.post")
    def test_includes_epic_link_when_given(self, mock_post):
        mock_post.return_value = mock_response({"key": "PROJ-100"})
        client = make_client()
        client._epic_link_field_id = "customfield_10100"

        result = client.create_issue("PROJ", "New ticket", "Task", epic_key="PROJ-1")

        assert result == {"key": "PROJ-100"}
        body = mock_post.call_args.kwargs["json"]
        assert body["fields"]["customfield_10100"] == "PROJ-1"

    @patch("jira_client.requests.get")
    def test_raises_clear_error_when_epic_requested_but_no_field(self, mock_get):
        mock_get.return_value = mock_response([])
        client = make_client()

        try:
            client.create_issue("PROJ", "New ticket", "Task", epic_key="PROJ-1")
            assert False, "expected JiraApiError"
        except JiraApiError as e:
            assert str(e).startswith("Epic Link field not found")

    @patch("jira_client.requests.post")
    @patch("jira_client.requests.get")
    def test_no_post_when_epic_field_missing(self, mock_get, mock_post):
        mock_get.return_value = mock_response([])
        client = make_client()

        try:
            client.create_issue("PROJ", "New ticket", "Task", epic_key="PROJ-1")
            assert False, "expected JiraApiError"
        except JiraApiError:
            pass
        mock_post.assert_not_called()


class TestProjectStatuses:
    @patch("jira_client.requests.get")
    def test_returns_statuses_grouped_by_issue_type(self, mock_get):
        mock_get.return_value = mock_response(
            [
                {
                    "name": "Task",
                    "statuses": [
                        {"name": "To Do"},
                        {"name": "In Progress"},
                        {"name": "Done"},
                    ]
                },
                {
                    "name": "Bug",
                    "statuses": [
                        {"name": "Open"},
                        {"name": "In Review"},
                        {"name": "Resolved"},
                    ]
                },
            ]
        )
        client = make_client()

        result = client.project_statuses("PROJ")

        assert result == {
            "Task": ["To Do", "In Progress", "Done"],
            "Bug": ["Open", "In Review", "Resolved"],
        }

    @patch("jira_client.requests.get")
    def test_raises_on_api_error(self, mock_get):
        mock_get.return_value = mock_response({"errorMessages": ["Project not found"]}, status_code=404)
        client = make_client()

        try:
            client.project_statuses("BOGUS")
            assert False, "expected JiraApiError"
        except JiraApiError as e:
            assert "Project not found" in str(e)
