import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gitlab_client import GitLabApiError, GitLabClient, project_from_remote

MR_PAYLOAD = {
    "iid": 52,
    "title": "Fix backup role",
    "description": "Details",
    "state": "opened",
    "source_branch": "fix-lakebase-backup-role",
    "target_branch": "develop",
    "web_url": "https://gitlab.example.com/group/proj/-/merge_requests/52",
    "diff_refs": {"base_sha": "b", "start_sha": "s", "head_sha": "h"},
}


def make_client():
    return GitLabClient(base_url="https://gitlab.example.com/", token="secret-token", project="group/sub/proj")


def mock_response(json_data, status_code=200):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data
    return response


class TestProjectFromRemote:
    def test_scp_style_ssh(self):
        assert project_from_remote("git@gitlab.example.com:group/sub/proj.git\n") == "group/sub/proj"

    def test_ssh_url_with_port(self):
        assert project_from_remote("ssh://git@gitlab.example.com:2222/group/proj.git") == "group/proj"

    def test_https(self):
        assert project_from_remote("https://gitlab.example.com/group/proj") == "group/proj"

    def test_unrecognised(self):
        assert project_from_remote("not a url") is None


class TestGetMr:
    @patch("gitlab_client.requests.get")
    def test_returns_fields_and_encodes_project(self, mock_get):
        mock_get.return_value = mock_response(MR_PAYLOAD)

        result = make_client().get_mr(52)

        assert result["target_branch"] == "develop"
        assert result["diff_refs"]["head_sha"] == "h"
        url = mock_get.call_args[0][0]
        assert url == "https://gitlab.example.com/api/v4/projects/group%2Fsub%2Fproj/merge_requests/52"
        assert mock_get.call_args[1]["headers"] == {"PRIVATE-TOKEN": "secret-token"}

    @patch("gitlab_client.requests.get")
    def test_raises_on_api_error(self, mock_get):
        mock_get.return_value = mock_response({"message": "401 Unauthorized"}, status_code=401)

        try:
            make_client().get_mr(52)
            assert False, "expected GitLabApiError"
        except GitLabApiError as e:
            assert "401" in str(e)


class TestFindActiveMr:
    @patch("gitlab_client.requests.get")
    def test_returns_first_open_mr(self, mock_get):
        mock_get.return_value = mock_response([MR_PAYLOAD])

        result = make_client().find_active_mr("fix-lakebase-backup-role")

        assert result == {"mr_iid": 52, "mr_url": MR_PAYLOAD["web_url"]}
        assert mock_get.call_args[0][0] == "https://gitlab.example.com/api/v4/projects/group%2Fsub%2Fproj/merge_requests"
        assert mock_get.call_args[1]["params"] == {
            "source_branch": "fix-lakebase-backup-role",
            "state": "opened",
        }

    @patch("gitlab_client.requests.get")
    def test_returns_none_when_no_mr_found(self, mock_get):
        mock_get.return_value = mock_response([])

        assert make_client().find_active_mr("no-such-branch") is None


class TestCreateMr:
    @patch("gitlab_client.requests.post")
    def test_creates_and_returns_iid_and_url(self, mock_post):
        mock_post.return_value = mock_response(MR_PAYLOAD, status_code=201)

        result = make_client().create_mr(
            source_branch="fix-lakebase-backup-role",
            target_branch="develop",
            title="Fix backup role",
            description="Details",
        )

        assert result == {"mr_iid": 52, "mr_url": MR_PAYLOAD["web_url"]}
        assert mock_post.call_args[0][0] == "https://gitlab.example.com/api/v4/projects/group%2Fsub%2Fproj/merge_requests"
        assert mock_post.call_args[1]["json"] == {
            "source_branch": "fix-lakebase-backup-role",
            "target_branch": "develop",
            "title": "Fix backup role",
            "description": "Details",
            "remove_source_branch": True,
        }

    @patch("gitlab_client.requests.post")
    def test_raises_on_api_error(self, mock_post):
        mock_post.return_value = mock_response({"message": "403 Forbidden"}, status_code=403)

        try:
            make_client().create_mr("src", "develop", "title", "desc")
            assert False, "expected GitLabApiError"
        except GitLabApiError as e:
            assert "403" in str(e)


class TestPostNote:
    @patch("gitlab_client.requests.post")
    def test_posts_body_and_returns_id(self, mock_post):
        mock_post.return_value = mock_response({"id": 991}, status_code=201)

        result = make_client().post_note(52, "Looks off")

        assert result == {"note_id": 991}
        assert mock_post.call_args[0][0].endswith("/merge_requests/52/notes")
        assert mock_post.call_args[1]["json"] == {"body": "Looks off"}


class TestPostInlineDiscussion:
    @patch("gitlab_client.requests.post")
    @patch("gitlab_client.requests.get")
    def test_uses_diff_refs_for_position(self, mock_get, mock_post):
        mock_get.return_value = mock_response(MR_PAYLOAD)
        mock_post.return_value = mock_response({"id": "abc", "notes": [{"id": 1234}]}, status_code=201)

        result = make_client().post_inline_discussion(52, "Bug here", "src/x.py", "158")

        assert result == {"note_id": 1234}
        assert mock_post.call_args[0][0].endswith("/merge_requests/52/discussions")
        position = mock_post.call_args[1]["json"]["position"]
        assert position["base_sha"] == "b"
        assert position["start_sha"] == "s"
        assert position["head_sha"] == "h"
        assert position["new_path"] == "src/x.py"
        assert position["new_line"] == 158

    @patch("gitlab_client.requests.post")
    @patch("gitlab_client.requests.get")
    def test_raises_without_diff_refs(self, mock_get, mock_post):
        mock_get.return_value = mock_response({**MR_PAYLOAD, "diff_refs": None})

        try:
            make_client().post_inline_discussion(52, "Bug", "src/x.py", 1)
            assert False, "expected GitLabApiError"
        except GitLabApiError as e:
            assert "diff_refs" in str(e)
        mock_post.assert_not_called()
