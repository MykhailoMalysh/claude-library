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
