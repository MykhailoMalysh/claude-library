import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cli_gitlab
from gitlab_client import GitLabApiError

ENV = {
    "GITLAB_URL": "https://gitlab.example.com",
    "GITLAB_TOKEN": "secret-token",
    "GITLAB_PROJECT": "group/proj",
}


def run_main(monkeypatch, argv, env=ENV):
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(sys, "argv", ["cli_gitlab.py"] + argv)


def call_main():
    try:
        cli_gitlab.main()
    except SystemExit as e:
        return e.code
    return None


class TestClientFromEnv:
    def test_exits_when_env_vars_missing(self, monkeypatch, capsys):
        monkeypatch.delenv("GITLAB_URL", raising=False)
        monkeypatch.delenv("GITLAB_TOKEN", raising=False)

        try:
            cli_gitlab.client_from_env()
            assert False, "expected SystemExit"
        except SystemExit as e:
            assert e.code == 1

        err = capsys.readouterr().err
        assert "GITLAB_URL" in err
        assert "GITLAB_TOKEN" in err

    def test_uses_project_env_var(self, monkeypatch):
        for key, value in ENV.items():
            monkeypatch.setenv(key, value)

        assert cli_gitlab.client_from_env().project == "group/proj"

    def test_derives_project_from_remote(self, monkeypatch):
        monkeypatch.delenv("GITLAB_PROJECT", raising=False)
        completed = MagicMock(stdout="git@gitlab.example.com:team/repo.git\n")

        with patch("cli_gitlab.subprocess.run", return_value=completed):
            assert cli_gitlab.resolve_project() == "team/repo"

    def test_normalizes_a_project_url_down_to_the_instance_root(self, monkeypatch):
        env = {**ENV, "GITLAB_URL": "https://gitlab.example.com/group/sub/proj"}
        for key, value in env.items():
            monkeypatch.setenv(key, value)

        assert cli_gitlab.client_from_env().base_url == "https://gitlab.example.com"


class TestInstanceRoot:
    def test_strips_project_path(self):
        assert cli_gitlab.instance_root("https://gitlab.example.com/group/sub/proj") == "https://gitlab.example.com"

    def test_leaves_instance_root_unchanged(self):
        assert cli_gitlab.instance_root("https://gitlab.example.com") == "https://gitlab.example.com"

    def test_strips_trailing_slash(self):
        assert cli_gitlab.instance_root("https://gitlab.example.com/") == "https://gitlab.example.com"


class TestMrGet:
    def test_prints_mr_json(self, monkeypatch, capsys):
        run_main(monkeypatch, ["mr-get", "--iid", "52"])
        mock_client = MagicMock()
        mock_client.get_mr.return_value = {"iid": 52, "title": "Fix", "target_branch": "develop"}

        with patch("cli_gitlab.client_from_env", return_value=mock_client):
            assert call_main() == 0

        assert '"target_branch": "develop"' in capsys.readouterr().out
        mock_client.get_mr.assert_called_once_with(52)

    def test_exits_1_on_api_error(self, monkeypatch, capsys):
        run_main(monkeypatch, ["mr-get", "--iid", "52"])
        mock_client = MagicMock()
        mock_client.get_mr.side_effect = GitLabApiError("HTTP 404: Not Found")

        with patch("cli_gitlab.client_from_env", return_value=mock_client):
            assert call_main() == 1

        assert "404" in capsys.readouterr().err


class TestCheck:
    def test_prints_mr_iid_and_url_when_found(self, monkeypatch, capsys):
        run_main(monkeypatch, ["check", "--source", "fix-lakebase-backup-role"])
        mock_client = MagicMock()
        mock_client.find_active_mr.return_value = {
            "mr_iid": 52,
            "mr_url": "https://gitlab.example.com/group/proj/-/merge_requests/52",
        }

        with patch("cli_gitlab.client_from_env", return_value=mock_client):
            assert call_main() == 0

        out = capsys.readouterr().out
        assert "MR_IID=52" in out
        assert "MR_URL=https://gitlab.example.com/group/proj/-/merge_requests/52" in out
        mock_client.find_active_mr.assert_called_once_with("fix-lakebase-backup-role")

    def test_exits_1_when_not_found(self, monkeypatch):
        run_main(monkeypatch, ["check", "--source", "no-such-branch"])
        mock_client = MagicMock()
        mock_client.find_active_mr.return_value = None

        with patch("cli_gitlab.client_from_env", return_value=mock_client):
            assert call_main() == 1

    def test_exits_2_on_api_error(self, monkeypatch, capsys):
        run_main(monkeypatch, ["check", "--source", "src"])
        mock_client = MagicMock()
        mock_client.find_active_mr.side_effect = GitLabApiError("HTTP 500: boom")

        with patch("cli_gitlab.client_from_env", return_value=mock_client):
            assert call_main() == 2

        assert "500" in capsys.readouterr().err


class TestCreate:
    def test_creates_and_prints_mr_iid_and_url(self, monkeypatch, capsys, tmp_path):
        description = tmp_path / "d.md"
        description.write_text("Description")
        run_main(
            monkeypatch,
            [
                "create",
                "--source",
                "fix-lakebase-backup-role",
                "--target",
                "develop",
                "--title",
                "Fix backup role",
                "--description-file",
                str(description),
            ],
        )
        mock_client = MagicMock()
        mock_client.create_mr.return_value = {
            "mr_iid": 52,
            "mr_url": "https://gitlab.example.com/group/proj/-/merge_requests/52",
        }

        with patch("cli_gitlab.client_from_env", return_value=mock_client):
            assert call_main() == 0

        out = capsys.readouterr().out
        assert "MR_IID=52" in out
        assert "MR_URL=https://gitlab.example.com/group/proj/-/merge_requests/52" in out
        mock_client.create_mr.assert_called_once_with(
            "fix-lakebase-backup-role", "develop", "Fix backup role", "Description"
        )

    def test_exits_1_on_api_error(self, monkeypatch, capsys, tmp_path):
        description = tmp_path / "d.md"
        description.write_text("Description")
        run_main(
            monkeypatch,
            [
                "create",
                "--source",
                "src",
                "--target",
                "develop",
                "--title",
                "title",
                "--description-file",
                str(description),
            ],
        )
        mock_client = MagicMock()
        mock_client.create_mr.side_effect = GitLabApiError("HTTP 403: Forbidden")

        with patch("cli_gitlab.client_from_env", return_value=mock_client):
            assert call_main() == 1

        assert "403" in capsys.readouterr().err


class TestNote:
    def test_general_note(self, monkeypatch, capsys, tmp_path):
        content = tmp_path / "c.md"
        content.write_text("Comment")
        run_main(monkeypatch, ["note", "--iid", "52", "--content-file", str(content)])
        mock_client = MagicMock()
        mock_client.post_note.return_value = {"note_id": 7}

        with patch("cli_gitlab.client_from_env", return_value=mock_client):
            assert call_main() == 0

        assert "NOTE_ID=7" in capsys.readouterr().out
        mock_client.post_note.assert_called_once_with(52, "Comment")
        mock_client.post_inline_discussion.assert_not_called()

    def test_inline_note(self, monkeypatch, capsys, tmp_path):
        content = tmp_path / "c.md"
        content.write_text("Inline")
        run_main(monkeypatch, ["note", "--iid", "52", "--content-file", str(content), "--file", "src/x.py", "--line", "10"])
        mock_client = MagicMock()
        mock_client.post_inline_discussion.return_value = {"note_id": 8}

        with patch("cli_gitlab.client_from_env", return_value=mock_client):
            assert call_main() == 0

        assert "NOTE_ID=8" in capsys.readouterr().out
        mock_client.post_inline_discussion.assert_called_once_with(52, "Inline", "src/x.py", 10)

    def test_file_without_line_is_rejected(self, monkeypatch, capsys, tmp_path):
        content = tmp_path / "c.md"
        content.write_text("Inline")
        run_main(monkeypatch, ["note", "--iid", "52", "--content-file", str(content), "--file", "src/x.py"])
        mock_client = MagicMock()

        with patch("cli_gitlab.client_from_env", return_value=mock_client):
            assert call_main() == 1

        assert "together" in capsys.readouterr().err
        mock_client.post_note.assert_not_called()
