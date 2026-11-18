import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cli_jira
from jira_client import JiraApiError

ENV = {
    "JIRA_URL": "https://jira.example.com",
    "JIRA_USERNAME": "me@example.com",
    "JIRA_API_TOKEN": "secret-token",
}


def run_main(monkeypatch, argv, env=ENV):
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(sys, "argv", ["cli_jira.py"] + argv)


class TestClientFromEnv:
    def test_exits_when_env_vars_missing(self, monkeypatch, capsys):
        monkeypatch.delenv("JIRA_URL", raising=False)
        monkeypatch.delenv("JIRA_API_TOKEN", raising=False)

        try:
            cli_jira.client_from_env()
            assert False, "expected SystemExit"
        except SystemExit as e:
            assert e.code == 1

        captured = capsys.readouterr()
        assert "JIRA_URL" in captured.err
        assert "JIRA_API_TOKEN" in captured.err


class TestGet:
    def test_prints_issue_json(self, monkeypatch, capsys):
        run_main(monkeypatch, ["get", "--key", "PROJ-42"])
        mock_client = MagicMock()
        mock_client.get_issue.return_value = {"key": "PROJ-42", "summary": "Fix", "description": "D", "status": "To Do"}

        with patch("cli_jira.client_from_env", return_value=mock_client):
            try:
                cli_jira.main()
            except SystemExit as e:
                assert e.code == 0

        assert "PROJ-42" in capsys.readouterr().out

    def test_exits_1_on_api_error(self, monkeypatch, capsys):
        run_main(monkeypatch, ["get", "--key", "PROJ-999"])
        mock_client = MagicMock()
        mock_client.get_issue.side_effect = JiraApiError("Issue does not exist")

        with patch("cli_jira.client_from_env", return_value=mock_client):
            try:
                cli_jira.main()
                assert False, "expected SystemExit"
            except SystemExit as e:
                assert e.code == 1

        assert "Issue does not exist" in capsys.readouterr().err


class TestCreate:
    def test_prints_issue_key_on_success(self, monkeypatch, capsys):
        run_main(monkeypatch, ["create", "--project", "PROJ", "--summary", "New ticket", "--type", "Task"])
        mock_client = MagicMock()
        mock_client.create_issue.return_value = {"key": "PROJ-100"}

        with patch("cli_jira.client_from_env", return_value=mock_client):
            try:
                cli_jira.main()
            except SystemExit as e:
                assert e.code == 0

        assert "ISSUE_KEY=PROJ-100" in capsys.readouterr().out

    def test_exits_1_when_description_file_missing(self, monkeypatch, capsys):
        run_main(
            monkeypatch,
            [
                "create", "--project", "PROJ", "--summary", "New ticket", "--type", "Task",
                "--description-file", "/nonexistent/path.md",
            ],
        )
        mock_client = MagicMock()

        with patch("cli_jira.client_from_env", return_value=mock_client):
            try:
                cli_jira.main()
                assert False, "expected SystemExit"
            except SystemExit as e:
                assert e.code == 1


class TestTransition:
    def test_prints_status_on_success(self, monkeypatch, capsys):
        run_main(monkeypatch, ["transition", "--key", "PROJ-42", "--status", "In Progress"])
        mock_client = MagicMock()
        mock_client.transition_issue.return_value = {"status": "In Progress"}

        with patch("cli_jira.client_from_env", return_value=mock_client):
            try:
                cli_jira.main()
            except SystemExit as e:
                assert e.code == 0

        assert "STATUS=In Progress" in capsys.readouterr().out

    def test_exits_1_on_no_matching_transition(self, monkeypatch, capsys):
        run_main(monkeypatch, ["transition", "--key", "PROJ-42", "--status", "Bogus"])
        mock_client = MagicMock()
        mock_client.transition_issue.side_effect = JiraApiError("No transition found to status: Bogus")

        with patch("cli_jira.client_from_env", return_value=mock_client):
            try:
                cli_jira.main()
                assert False, "expected SystemExit"
            except SystemExit as e:
                assert e.code == 1

        assert "Bogus" in capsys.readouterr().err


class TestComment:
    def test_prints_comment_id_on_success(self, monkeypatch, capsys, tmp_path):
        content_file = tmp_path / "comment.txt"
        content_file.write_text("Pull request opened: ...")

        run_main(monkeypatch, ["comment", "--key", "PROJ-42", "--content-file", str(content_file)])
        mock_client = MagicMock()
        mock_client.add_comment.return_value = {"comment_id": "500"}

        with patch("cli_jira.client_from_env", return_value=mock_client):
            try:
                cli_jira.main()
            except SystemExit as e:
                assert e.code == 0

        assert "COMMENT_ID=500" in capsys.readouterr().out

    def test_exits_1_when_content_file_missing(self, monkeypatch, capsys):
        run_main(monkeypatch, ["comment", "--key", "PROJ-42", "--content-file", "/nonexistent/comment.txt"])
        mock_client = MagicMock()

        with patch("cli_jira.client_from_env", return_value=mock_client):
            try:
                cli_jira.main()
                assert False, "expected SystemExit"
            except SystemExit as e:
                assert e.code == 1


class TestEpics:
    def test_prints_epics_json(self, monkeypatch, capsys):
        run_main(monkeypatch, ["epics", "--project", "PROJ"])
        mock_client = MagicMock()
        mock_client.list_epics.return_value = [
            {"key": "PROJ-1", "summary": "Epic A", "status": "In Progress"},
            {"key": "PROJ-2", "summary": "Epic B", "status": "To Do"},
        ]

        with patch("cli_jira.client_from_env", return_value=mock_client):
            try:
                cli_jira.main()
            except SystemExit as e:
                assert e.code == 0

        output = capsys.readouterr().out
        assert "PROJ-1" in output
        assert "Epic A" in output

    def test_includes_done_epics_when_requested(self, monkeypatch, capsys):
        run_main(monkeypatch, ["epics", "--project", "PROJ", "--include-done"])
        mock_client = MagicMock()
        mock_client.list_epics.return_value = [
            {"key": "PROJ-1", "summary": "Epic A", "status": "Done"},
        ]

        with patch("cli_jira.client_from_env", return_value=mock_client):
            try:
                cli_jira.main()
            except SystemExit as e:
                assert e.code == 0

        mock_client.list_epics.assert_called_once_with("PROJ", include_done=True)

    def test_exits_1_on_api_error(self, monkeypatch, capsys):
        run_main(monkeypatch, ["epics", "--project", "PROJ"])
        mock_client = MagicMock()
        mock_client.list_epics.side_effect = JiraApiError("Invalid JQL")

        with patch("cli_jira.client_from_env", return_value=mock_client):
            try:
                cli_jira.main()
                assert False, "expected SystemExit"
            except SystemExit as e:
                assert e.code == 1

        assert "Invalid JQL" in capsys.readouterr().err


class TestStatuses:
    def test_prints_statuses_json(self, monkeypatch, capsys):
        run_main(monkeypatch, ["statuses", "--project", "PROJ"])
        mock_client = MagicMock()
        mock_client.project_statuses.return_value = {
            "Task": ["To Do", "In Progress", "Done"],
            "Bug": ["Open", "In Review", "Resolved"],
        }

        with patch("cli_jira.client_from_env", return_value=mock_client):
            try:
                cli_jira.main()
            except SystemExit as e:
                assert e.code == 0

        output = capsys.readouterr().out
        assert "Task" in output
        assert "To Do" in output

    def test_exits_1_on_api_error(self, monkeypatch, capsys):
        run_main(monkeypatch, ["statuses", "--project", "PROJ"])
        mock_client = MagicMock()
        mock_client.project_statuses.side_effect = JiraApiError("Project not found")

        with patch("cli_jira.client_from_env", return_value=mock_client):
            try:
                cli_jira.main()
                assert False, "expected SystemExit"
            except SystemExit as e:
                assert e.code == 1

        assert "Project not found" in capsys.readouterr().err


class TestCreateWithEpic:
    def test_sets_epic_when_provided(self, monkeypatch, capsys):
        run_main(monkeypatch, ["create", "--project", "PROJ", "--summary", "New ticket", "--type", "Task", "--epic", "PROJ-1"])
        mock_client = MagicMock()
        mock_client.create_issue.return_value = {"key": "PROJ-100"}

        with patch("cli_jira.client_from_env", return_value=mock_client):
            try:
                cli_jira.main()
            except SystemExit as e:
                assert e.code == 0

        mock_client.create_issue.assert_called_once()
        call_kwargs = mock_client.create_issue.call_args[1]
        assert call_kwargs.get("epic_key") == "PROJ-1"

    def test_exits_1_when_epic_not_supported(self, monkeypatch, capsys):
        run_main(monkeypatch, ["create", "--project", "PROJ", "--summary", "New ticket", "--type", "Task", "--epic", "PROJ-1"])
        mock_client = MagicMock()
        mock_client.create_issue.side_effect = JiraApiError("Epic Link field not found")

        with patch("cli_jira.client_from_env", return_value=mock_client):
            try:
                cli_jira.main()
                assert False, "expected SystemExit"
            except SystemExit as e:
                assert e.code == 1

        err = capsys.readouterr().err
        assert "Epic Link field not found" in err


class TestEpicsTotalWarning:
    def test_warns_when_more_epics_than_returned(self, monkeypatch, capsys):
        run_main(monkeypatch, ["epics", "--project", "PROJ"])
        mock_client = MagicMock()
        mock_client.list_epics.return_value = [{"key": "PROJ-1", "summary": "A", "status": "To Do"}]
        mock_client.last_epics_total = 150

        with patch("cli_jira.client_from_env", return_value=mock_client):
            try:
                cli_jira.main()
            except SystemExit as e:
                assert e.code == 0

        captured = capsys.readouterr()
        assert "showing first 1 of 150 epics" in captured.err
        assert "PROJ-1" in captured.out

    def test_no_warning_when_all_returned(self, monkeypatch, capsys):
        run_main(monkeypatch, ["epics", "--project", "PROJ"])
        mock_client = MagicMock()
        mock_client.list_epics.return_value = [{"key": "PROJ-1", "summary": "A", "status": "To Do"}]
        mock_client.last_epics_total = 1

        with patch("cli_jira.client_from_env", return_value=mock_client):
            try:
                cli_jira.main()
            except SystemExit as e:
                assert e.code == 0

        assert capsys.readouterr().err == ""


class TestSetEpic:
    def test_sets_epic_and_prints_json(self, monkeypatch, capsys):
        run_main(monkeypatch, ["set-epic", "--key", "PROJ-42", "--epic", "PROJ-1"])
        mock_client = MagicMock()

        with patch("cli_jira.client_from_env", return_value=mock_client):
            try:
                cli_jira.main()
            except SystemExit as e:
                assert e.code == 0

        mock_client.set_epic.assert_called_once_with("PROJ-42", "PROJ-1")
        import json
        assert json.loads(capsys.readouterr().out) == {"key": "PROJ-42", "epic": "PROJ-1"}

    def test_exits_1_on_error(self, monkeypatch, capsys):
        run_main(monkeypatch, ["set-epic", "--key", "PROJ-42", "--epic", "PROJ-1"])
        mock_client = MagicMock()
        mock_client.set_epic.side_effect = JiraApiError("Epic Link field not found in this Jira instance.")

        with patch("cli_jira.client_from_env", return_value=mock_client):
            try:
                cli_jira.main()
                assert False, "expected SystemExit"
            except SystemExit as e:
                assert e.code == 1

        assert "Epic Link field not found" in capsys.readouterr().err
