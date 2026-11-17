import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ado_client import ADOApiError, ADOClient


def make_client():
    return ADOClient(org="myorg", project="myproj", repo="myrepo", pat="secret-pat")


def mock_response(json_data):
    response = MagicMock()
    response.json.return_value = json_data
    return response


class TestFindActivePr:
    @patch("ado_client.requests.get")
    def test_returns_pr_when_found(self, mock_get):
        mock_get.return_value = mock_response(
            {"count": 1, "value": [{"pullRequestId": 927}]}
        )
        client = make_client()

        result = client.find_active_pr("user/mykhailo/42-foo")

        assert result == {
            "pr_id": 927,
            "pr_url": "https://dev.azure.com/myorg/myproj/_git/myrepo/pullrequest/927",
        }

    @patch("ado_client.requests.get")
    def test_returns_none_when_not_found(self, mock_get):
        mock_get.return_value = mock_response({"count": 0, "value": []})
        client = make_client()

        assert client.find_active_pr("user/mykhailo/42-foo") is None

    @patch("ado_client.requests.get")
    def test_raises_on_api_error(self, mock_get):
        mock_get.return_value = mock_response({"message": "Unauthorized"})
        client = make_client()

        try:
            client.find_active_pr("user/mykhailo/42-foo")
            assert False, "expected ADOApiError"
        except ADOApiError as e:
            assert "Unauthorized" in str(e)


class TestCreatePr:
    @patch("ado_client.requests.post")
    def test_returns_pr_on_success(self, mock_post):
        mock_post.return_value = mock_response({"pullRequestId": 100})
        client = make_client()

        result = client.create_pr("source", "target", "Title", "Description")

        assert result["pr_id"] == 100
        assert result["pr_url"].endswith("/pullrequest/100")

    @patch("ado_client.requests.post")
    def test_raises_on_failure(self, mock_post):
        mock_post.return_value = mock_response({"message": "Invalid target branch"})
        client = make_client()

        try:
            client.create_pr("source", "target", "Title", "Description")
            assert False, "expected ADOApiError"
        except ADOApiError as e:
            assert "Invalid target branch" in str(e)


class TestUpdatePr:
    @patch("ado_client.requests.patch")
    def test_returns_pr_on_success(self, mock_patch):
        mock_patch.return_value = mock_response({"pullRequestId": 100})
        client = make_client()

        result = client.update_pr(100, title="New title")

        assert result["pr_id"] == 100

    def test_raises_without_title_or_description(self):
        client = make_client()

        try:
            client.update_pr(100)
            assert False, "expected ValueError"
        except ValueError:
            pass


class TestListThreads:
    @patch("ado_client.requests.get")
    def test_returns_active_threads_with_comments(self, mock_get):
        mock_get.return_value = mock_response(
            {
                "value": [
                    {
                        "id": 1,
                        "status": "active",
                        "threadContext": {
                            "filePath": "/src/foo.py",
                            "rightFileStart": {"line": 42},
                        },
                        "comments": [
                            {"id": 1, "content": "Fix this", "author": {"displayName": "Alice"}}
                        ],
                    }
                ]
            }
        )
        client = make_client()

        result = client.list_threads(100)

        assert result == [
            {
                "thread_id": 1,
                "status": "active",
                "file_path": "/src/foo.py",
                "line": 42,
                "comments": [{"id": 1, "content": "Fix this", "author": "Alice"}],
            }
        ]

    @patch("ado_client.requests.get")
    def test_excludes_resolved_threads_by_default(self, mock_get):
        mock_get.return_value = mock_response(
            {
                "value": [
                    {
                        "id": 1,
                        "status": "fixed",
                        "comments": [{"id": 1, "content": "Done"}],
                    }
                ]
            }
        )
        client = make_client()

        assert client.list_threads(100) == []
        assert client.list_threads(100, active_only=False) != []

    @patch("ado_client.requests.get")
    def test_skips_deleted_threads_and_comments(self, mock_get):
        mock_get.return_value = mock_response(
            {
                "value": [
                    {"id": 1, "status": "active", "isDeleted": True, "comments": []},
                    {
                        "id": 2,
                        "status": "active",
                        "comments": [
                            {"id": 1, "content": "gone", "isDeleted": True},
                            {"id": 2, "content": "kept", "author": {"displayName": "Bob"}},
                        ],
                    },
                ]
            }
        )
        client = make_client()

        result = client.list_threads(100)

        assert len(result) == 1
        assert result[0]["thread_id"] == 2
        assert result[0]["comments"] == [{"id": 2, "content": "kept", "author": "Bob"}]

    @patch("ado_client.requests.get")
    def test_omits_general_comment_thread_context(self, mock_get):
        mock_get.return_value = mock_response(
            {"value": [{"id": 1, "status": "active", "comments": [{"id": 1, "content": "note"}]}]}
        )
        client = make_client()

        result = client.list_threads(100)

        assert result[0]["file_path"] is None
        assert result[0]["line"] is None

    @patch("ado_client.requests.get")
    def test_raises_on_api_error(self, mock_get):
        mock_get.return_value = mock_response({"message": "Unauthorized"})
        client = make_client()

        try:
            client.list_threads(100)
            assert False, "expected ADOApiError"
        except ADOApiError as e:
            assert "Unauthorized" in str(e)


class TestReplyToThread:
    @patch("ado_client.requests.post")
    def test_returns_comment_id_on_success(self, mock_post):
        mock_post.return_value = mock_response({"id": 9})
        client = make_client()

        result = client.reply_to_thread(100, 1, "Fixed in abc123")

        assert result == {"comment_id": 9}
        body = mock_post.call_args.kwargs["json"]
        assert body == {"content": "Fixed in abc123", "commentType": 1, "parentCommentId": 1}

    @patch("ado_client.requests.post")
    def test_raises_on_failure(self, mock_post):
        mock_post.return_value = mock_response({"message": "Thread not found"})
        client = make_client()

        try:
            client.reply_to_thread(100, 1, "Fixed")
            assert False, "expected ADOApiError"
        except ADOApiError as e:
            assert "Thread not found" in str(e)


class TestResolveThread:
    @patch("ado_client.requests.patch")
    def test_returns_status_on_success(self, mock_patch):
        mock_patch.return_value = mock_response({"status": "fixed"})
        client = make_client()

        result = client.resolve_thread(100, 1)

        assert result == {"status": "fixed"}
        body = mock_patch.call_args.kwargs["json"]
        assert body == {"status": "fixed"}

    @patch("ado_client.requests.patch")
    def test_supports_custom_status(self, mock_patch):
        mock_patch.return_value = mock_response({"status": "wontFix"})
        client = make_client()

        client.resolve_thread(100, 1, status="wontFix")

        body = mock_patch.call_args.kwargs["json"]
        assert body == {"status": "wontFix"}

    @patch("ado_client.requests.patch")
    def test_raises_on_failure(self, mock_patch):
        mock_patch.return_value = mock_response({"message": "Thread not found"})
        client = make_client()

        try:
            client.resolve_thread(100, 1)
            assert False, "expected ADOApiError"
        except ADOApiError as e:
            assert "Thread not found" in str(e)


class TestPostComment:
    @patch("ado_client.requests.post")
    def test_includes_thread_context_when_line_given(self, mock_post):
        mock_post.return_value = mock_response({"id": 5})
        client = make_client()

        client.post_comment(100, "Looks wrong", file_path="/src/foo.py", line=42)

        body = mock_post.call_args.kwargs["json"]
        assert body["threadContext"] == {
            "filePath": "/src/foo.py",
            "rightFileStart": {"line": 42, "offset": 1},
            "rightFileEnd": {"line": 42, "offset": 1},
        }

    @patch("ado_client.requests.post")
    def test_omits_thread_context_for_general_comment(self, mock_post):
        mock_post.return_value = mock_response({"id": 6})
        client = make_client()

        client.post_comment(100, "General note")

        body = mock_post.call_args.kwargs["json"]
        assert "threadContext" not in body

    @patch("ado_client.requests.post")
    def test_raises_on_failure(self, mock_post):
        mock_post.return_value = mock_response({"message": "PR not found"})
        client = make_client()

        try:
            client.post_comment(100, "General note")
            assert False, "expected ADOApiError"
        except ADOApiError as e:
            assert "PR not found" in str(e)
