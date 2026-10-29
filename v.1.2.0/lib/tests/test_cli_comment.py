import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cli_comment
from ado_client import ADOApiError

ENV = {
    "ADO_ORG": "myorg",
    "ADO_PROJECT": "myproj",
    "ADO_REPO": "myrepo",
    "ADO_PAT": "secret-pat",
}


def run_main(monkeypatch, argv, env=ENV):
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(sys, "argv", ["cli_comment.py"] + argv)


class TestPost:
    def test_prints_comment_id_for_line_anchored_comment(self, monkeypatch, capsys, tmp_path):
        content_file = tmp_path / "comment.md"
        content_file.write_text("`[HIGH]` : something is wrong here")

        run_main(
            monkeypatch,
            [
                "post",
                "--pr-id", "927",
                "--content-file", str(content_file),
                "--file", "/src/foo.py",
                "--line", "42",
            ],
        )
        mock_client = MagicMock()
        mock_client.post_comment.return_value = {"thread_id": 5}

        with patch("cli_comment.client_from_env", return_value=mock_client):
            try:
                cli_comment.main()
            except SystemExit as e:
                assert e.code == 0

        mock_client.post_comment.assert_called_once_with(
            927, "`[HIGH]` : something is wrong here", file_path="/src/foo.py", line=42
        )
        assert "COMMENT_ID=5" in capsys.readouterr().out

    def test_prints_comment_id_for_general_comment(self, monkeypatch, capsys, tmp_path):
        content_file = tmp_path / "comment.md"
        content_file.write_text("General note")

        run_main(monkeypatch, ["post", "--pr-id", "927", "--content-file", str(content_file)])
        mock_client = MagicMock()
        mock_client.post_comment.return_value = {"thread_id": 6}

        with patch("cli_comment.client_from_env", return_value=mock_client):
            try:
                cli_comment.main()
            except SystemExit as e:
                assert e.code == 0

        mock_client.post_comment.assert_called_once_with(
            927, "General note", file_path=None, line=None
        )

    def test_exits_1_when_file_given_without_line(self, monkeypatch, capsys, tmp_path):
        content_file = tmp_path / "comment.md"
        content_file.write_text("Note")

        run_main(
            monkeypatch,
            ["post", "--pr-id", "927", "--content-file", str(content_file), "--file", "/src/foo.py"],
        )
        mock_client = MagicMock()

        with patch("cli_comment.client_from_env", return_value=mock_client):
            try:
                cli_comment.main()
                assert False, "expected SystemExit"
            except SystemExit as e:
                assert e.code == 1

    def test_exits_1_on_api_error(self, monkeypatch, capsys, tmp_path):
        content_file = tmp_path / "comment.md"
        content_file.write_text("Note")

        run_main(monkeypatch, ["post", "--pr-id", "927", "--content-file", str(content_file)])
        mock_client = MagicMock()
        mock_client.post_comment.side_effect = ADOApiError("PR not found")

        with patch("cli_comment.client_from_env", return_value=mock_client):
            try:
                cli_comment.main()
                assert False, "expected SystemExit"
            except SystemExit as e:
                assert e.code == 1

        assert "PR not found" in capsys.readouterr().err


class TestList:
    def test_prints_threads_as_json_active_only_by_default(self, monkeypatch, capsys):
        run_main(monkeypatch, ["list", "--pr-id", "927"])
        mock_client = MagicMock()
        mock_client.list_threads.return_value = [{"thread_id": 1, "status": "active"}]

        with patch("cli_comment.client_from_env", return_value=mock_client):
            try:
                cli_comment.main()
            except SystemExit as e:
                assert e.code == 0

        mock_client.list_threads.assert_called_once_with(927, active_only=True)
        assert '"thread_id": 1' in capsys.readouterr().out

    def test_all_flag_includes_resolved_threads(self, monkeypatch, capsys):
        run_main(monkeypatch, ["list", "--pr-id", "927", "--all"])
        mock_client = MagicMock()
        mock_client.list_threads.return_value = []

        with patch("cli_comment.client_from_env", return_value=mock_client):
            try:
                cli_comment.main()
            except SystemExit as e:
                assert e.code == 0

        mock_client.list_threads.assert_called_once_with(927, active_only=False)

    def test_exits_1_on_api_error(self, monkeypatch, capsys):
        run_main(monkeypatch, ["list", "--pr-id", "927"])
        mock_client = MagicMock()
        mock_client.list_threads.side_effect = ADOApiError("PR not found")

        with patch("cli_comment.client_from_env", return_value=mock_client):
            try:
                cli_comment.main()
                assert False, "expected SystemExit"
            except SystemExit as e:
                assert e.code == 1

        assert "PR not found" in capsys.readouterr().err


class TestReply:
    def test_prints_reply_id(self, monkeypatch, capsys, tmp_path):
        content_file = tmp_path / "reply.md"
        content_file.write_text("Fixed in abc123")

        run_main(
            monkeypatch,
            ["reply", "--pr-id", "927", "--thread-id", "5", "--content-file", str(content_file)],
        )
        mock_client = MagicMock()
        mock_client.reply_to_thread.return_value = {"comment_id": 9}

        with patch("cli_comment.client_from_env", return_value=mock_client):
            try:
                cli_comment.main()
            except SystemExit as e:
                assert e.code == 0

        mock_client.reply_to_thread.assert_called_once_with(927, 5, "Fixed in abc123")
        assert "REPLY_ID=9" in capsys.readouterr().out

    def test_exits_1_on_api_error(self, monkeypatch, capsys, tmp_path):
        content_file = tmp_path / "reply.md"
        content_file.write_text("Fixed")

        run_main(
            monkeypatch,
            ["reply", "--pr-id", "927", "--thread-id", "5", "--content-file", str(content_file)],
        )
        mock_client = MagicMock()
        mock_client.reply_to_thread.side_effect = ADOApiError("Thread not found")

        with patch("cli_comment.client_from_env", return_value=mock_client):
            try:
                cli_comment.main()
                assert False, "expected SystemExit"
            except SystemExit as e:
                assert e.code == 1

        assert "Thread not found" in capsys.readouterr().err


class TestResolve:
    def test_prints_resolved_status_default_fixed(self, monkeypatch, capsys):
        run_main(monkeypatch, ["resolve", "--pr-id", "927", "--thread-id", "5"])
        mock_client = MagicMock()
        mock_client.resolve_thread.return_value = {"status": "fixed"}

        with patch("cli_comment.client_from_env", return_value=mock_client):
            try:
                cli_comment.main()
            except SystemExit as e:
                assert e.code == 0

        mock_client.resolve_thread.assert_called_once_with(927, 5, status="fixed")
        assert "RESOLVED=fixed" in capsys.readouterr().out

    def test_supports_custom_status(self, monkeypatch, capsys):
        run_main(monkeypatch, ["resolve", "--pr-id", "927", "--thread-id", "5", "--status", "wontFix"])
        mock_client = MagicMock()
        mock_client.resolve_thread.return_value = {"status": "wontFix"}

        with patch("cli_comment.client_from_env", return_value=mock_client):
            try:
                cli_comment.main()
            except SystemExit as e:
                assert e.code == 0

        mock_client.resolve_thread.assert_called_once_with(927, 5, status="wontFix")

    def test_exits_1_on_api_error(self, monkeypatch, capsys):
        run_main(monkeypatch, ["resolve", "--pr-id", "927", "--thread-id", "5"])
        mock_client = MagicMock()
        mock_client.resolve_thread.side_effect = ADOApiError("Thread not found")

        with patch("cli_comment.client_from_env", return_value=mock_client):
            try:
                cli_comment.main()
                assert False, "expected SystemExit"
            except SystemExit as e:
                assert e.code == 1

        assert "Thread not found" in capsys.readouterr().err
