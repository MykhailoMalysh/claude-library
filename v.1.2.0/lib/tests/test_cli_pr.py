import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cli_pr
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
    monkeypatch.setattr(sys, "argv", ["cli_pr.py"] + argv)


class TestClientFromEnv:
    def test_exits_when_env_vars_missing(self, monkeypatch, capsys):
        monkeypatch.delenv("ADO_ORG", raising=False)
        monkeypatch.delenv("ADO_PAT", raising=False)

        try:
            cli_pr.client_from_env()
            assert False, "expected SystemExit"
        except SystemExit as e:
            assert e.code == 1

        captured = capsys.readouterr()
        assert "ADO_ORG" in captured.err
        assert "ADO_PAT" in captured.err


class TestCheck:
    def test_prints_pr_id_and_url_when_found(self, monkeypatch, capsys):
        run_main(monkeypatch, ["check", "--source", "user/mykhailo/42-foo"])
        mock_client = MagicMock()
        mock_client.find_active_pr.return_value = {"pr_id": 927, "pr_url": "https://example/927"}

        with patch("cli_pr.client_from_env", return_value=mock_client):
            try:
                cli_pr.main()
            except SystemExit as e:
                assert e.code == 0

        captured = capsys.readouterr()
        assert "PR_ID=927" in captured.out
        assert "PR_URL=https://example/927" in captured.out

    def test_exits_1_when_not_found(self, monkeypatch, capsys):
        run_main(monkeypatch, ["check", "--source", "user/mykhailo/42-foo"])
        mock_client = MagicMock()
        mock_client.find_active_pr.return_value = None

        with patch("cli_pr.client_from_env", return_value=mock_client):
            try:
                cli_pr.main()
                assert False, "expected SystemExit"
            except SystemExit as e:
                assert e.code == 1

    def test_exits_2_on_api_error(self, monkeypatch, capsys):
        run_main(monkeypatch, ["check", "--source", "user/mykhailo/42-foo"])
        mock_client = MagicMock()
        mock_client.find_active_pr.side_effect = ADOApiError("Unauthorized")

        with patch("cli_pr.client_from_env", return_value=mock_client):
            try:
                cli_pr.main()
                assert False, "expected SystemExit"
            except SystemExit as e:
                assert e.code == 2

        assert "Unauthorized" in capsys.readouterr().err


class TestCreate:
    def test_prints_pr_id_and_url_on_success(self, monkeypatch, capsys, tmp_path):
        description_file = tmp_path / "desc.md"
        description_file.write_text("Some description")

        run_main(
            monkeypatch,
            [
                "create",
                "--source", "source-branch",
                "--target", "master",
                "--title", "My PR",
                "--description-file", str(description_file),
            ],
        )
        mock_client = MagicMock()
        mock_client.create_pr.return_value = {"pr_id": 100, "pr_url": "https://example/100"}

        with patch("cli_pr.client_from_env", return_value=mock_client):
            try:
                cli_pr.main()
            except SystemExit as e:
                assert e.code == 0

        mock_client.create_pr.assert_called_once_with(
            "source-branch", "master", "My PR", "Some description"
        )
        captured = capsys.readouterr()
        assert "PR_ID=100" in captured.out

    def test_exits_1_when_description_file_missing(self, monkeypatch, capsys):
        run_main(
            monkeypatch,
            [
                "create",
                "--source", "source-branch",
                "--target", "master",
                "--title", "My PR",
                "--description-file", "/nonexistent/path.md",
            ],
        )
        mock_client = MagicMock()

        with patch("cli_pr.client_from_env", return_value=mock_client):
            try:
                cli_pr.main()
                assert False, "expected SystemExit"
            except SystemExit as e:
                assert e.code == 1
