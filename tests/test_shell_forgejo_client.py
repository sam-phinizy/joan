from __future__ import annotations

from dataclasses import dataclass

import httpx
import pytest

from joan.shell.forgejo_client import ForgejoClient, ForgejoError


@dataclass
class DummyCtxClient:
    response: httpx.Response

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, _url, json):
        self.post_payload = json
        return self.response

    def request(self, _method, _url, **_kwargs):
        return self.response


def make_response(status: int, body: str = "", json_data: object | None = None) -> httpx.Response:
    req = httpx.Request("GET", "http://forgejo.local/api")
    if json_data is not None:
        return httpx.Response(status, request=req, json=json_data)
    return httpx.Response(status, request=req, text=body)


def test_headers_include_token() -> None:
    client = ForgejoClient("http://forgejo.local", "abc")
    assert client._headers()["Authorization"] == "token abc"


def test_create_token_prefers_sha1(monkeypatch) -> None:
    response = make_response(200, json_data={"sha1": "tok"})
    holder: dict[str, object] = {}

    def fake_client(*_args, **_kwargs):
        c = DummyCtxClient(response)
        holder["client"] = c
        return c

    monkeypatch.setattr(httpx, "Client", fake_client)

    client = ForgejoClient("http://forgejo.local")
    assert client.create_token("user", "pw", "name") == "tok"
    assert holder["client"].post_payload["scopes"] == ["all"]


def test_create_token_fallback_and_missing(monkeypatch) -> None:
    token_response = make_response(200, json_data={"token": "tok2"})
    monkeypatch.setattr(httpx, "Client", lambda *args, **kwargs: DummyCtxClient(token_response))

    client = ForgejoClient("http://forgejo.local")
    assert client.create_token("user", "pw", "name") == "tok2"

    missing_response = make_response(200, json_data={})
    monkeypatch.setattr(httpx, "Client", lambda *args, **kwargs: DummyCtxClient(missing_response))
    with pytest.raises(ForgejoError, match="did not include token"):
        client.create_token("user", "pw", "name")


def test_create_repo_and_list_pulls(monkeypatch) -> None:
    client = ForgejoClient("http://forgejo.local", "abc")
    calls: list[tuple[str, str, dict]] = []

    def fake_request_json(method, path, **kwargs):
        calls.append((method, path, kwargs))
        if path.endswith("/pulls"):
            return [{"number": 1}]
        return {"id": 1}

    monkeypatch.setattr(client, "_request_json", fake_request_json)

    assert client.create_repo("repo") == {"id": 1}
    assert client.list_pulls("sam", "joan", head="sam:branch") == [{"number": 1}]

    assert calls[0][0] == "POST"
    assert calls[0][1] == "/api/v1/user/repos"
    assert calls[1][2]["params"]["head"] == "sam:branch"


def test_get_current_user_repo_and_collaborator_permission(monkeypatch) -> None:
    client = ForgejoClient("http://forgejo.local", "abc")
    calls: list[tuple[str, str, dict]] = []

    def fake_request_json(method, path, **kwargs):
        calls.append((method, path, kwargs))
        if path == "/api/v1/user":
            return {"login": "joan"}
        if path == "/api/v1/repos/sam/joan":
            return {"name": "joan"}
        return {"permission": "admin"}

    monkeypatch.setattr(client, "_request_json", fake_request_json)

    assert client.get_current_user()["login"] == "joan"
    assert client.get_repo("sam", "joan")["name"] == "joan"
    assert client.get_repo_collaborator_permission("sam", "joan", "alex")["permission"] == "admin"
    assert calls[0][:2] == ("GET", "/api/v1/user")
    assert calls[1][:2] == ("GET", "/api/v1/repos/sam/joan")
    assert calls[2][:2] == ("GET", "/api/v1/repos/sam/joan/collaborators/alex/permission")


def test_add_repo_collaborator_sends_permission(monkeypatch) -> None:
    client = ForgejoClient("http://forgejo.local", "abc")
    calls: list[tuple[str, str, dict]] = []

    def fake_request_raw(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return make_response(204)

    monkeypatch.setattr(client, "_request_raw", fake_request_raw)

    client.add_repo_collaborator("joan", "demo", "sam")

    assert calls == [
        (
            "PUT",
            "/api/v1/repos/joan/demo/collaborators/sam",
            {"json": {"permission": "admin"}},
        )
    ]


def test_request_pr_reviewers_posts_requested_reviewers(monkeypatch) -> None:
    client = ForgejoClient("http://forgejo.local", "abc")
    calls: list[tuple[str, str, dict]] = []

    def fake_request_json(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return {"ok": True}

    monkeypatch.setattr(client, "_request_json", fake_request_json)

    assert client.request_pr_reviewers("joan", "demo", 5, ["sam"]) == {"ok": True}
    assert calls == [
        (
            "POST",
            "/api/v1/repos/joan/demo/pulls/5/requested_reviewers",
            {"json": {"reviewers": ["sam"]}},
        )
    ]


def test_list_and_create_ssh_keys(monkeypatch) -> None:
    client = ForgejoClient("http://forgejo.local", "abc")
    calls: list[tuple[str, str, dict]] = []

    def fake_request_json(method, path, **kwargs):
        calls.append((method, path, kwargs))
        if method == "GET":
            return [{"id": 1, "key": "ssh-ed25519 AAA"}]
        return {"id": 2}

    monkeypatch.setattr(client, "_request_json", fake_request_json)

    keys = client.list_ssh_keys()
    created = client.create_ssh_key("joan-test", "ssh-ed25519 BBB")

    assert keys[0]["id"] == 1
    assert created["id"] == 2
    assert calls[0][0] == "GET"
    assert calls[0][1] == "/api/v1/user/keys"
    assert calls[1][0] == "POST"
    assert calls[1][1] == "/api/v1/user/keys"
    assert calls[1][2]["json"]["title"] == "joan-test"


def test_get_comments_uses_issue_comments_endpoint(monkeypatch) -> None:
    client = ForgejoClient("http://forgejo.local", "abc")
    calls: list[tuple[str, str, dict]] = []

    def fake_request_json(method, path, **kwargs):
        calls.append((method, path, kwargs))
        if path.endswith("/reviews"):
            return []
        return [{"id": 1}]

    monkeypatch.setattr(client, "_request_json", fake_request_json)

    assert client.get_comments("sam", "joan", 7) == [{"id": 1}]
    assert calls == [
        (
            "GET",
            "/api/v1/repos/sam/joan/issues/7/comments",
            {},
        ),
        (
            "GET",
            "/api/v1/repos/sam/joan/pulls/7/reviews",
            {},
        ),
    ]


def test_get_comments_falls_back_to_pull_comments_on_404(monkeypatch) -> None:
    client = ForgejoClient("http://forgejo.local", "abc")
    calls: list[tuple[str, str, dict]] = []

    def fake_request_json(method, path, **kwargs):
        calls.append((method, path, kwargs))
        if path.endswith("/issues/7/comments"):
            raise ForgejoError("Forgejo API 404: not found")
        if path.endswith("/reviews"):
            return []
        return [{"id": 2}]

    monkeypatch.setattr(client, "_request_json", fake_request_json)

    assert client.get_comments("sam", "joan", 7) == [{"id": 2}]
    assert calls == [
        (
            "GET",
            "/api/v1/repos/sam/joan/issues/7/comments",
            {},
        ),
        (
            "GET",
            "/api/v1/repos/sam/joan/pulls/7/comments",
            {},
        ),
        (
            "GET",
            "/api/v1/repos/sam/joan/pulls/7/reviews",
            {},
        ),
    ]


def test_get_comments_includes_inline_review_comments(monkeypatch) -> None:
    client = ForgejoClient("http://forgejo.local", "abc")
    calls: list[tuple[str, str, dict]] = []

    def fake_request_json(method, path, **kwargs):
        calls.append((method, path, kwargs))
        if path.endswith("/issues/7/comments"):
            return [{"id": 1, "body": "top-level"}]
        if path.endswith("/pulls/7/reviews"):
            return [{"id": 4}, {"id": 5}]
        if path.endswith("/pulls/7/reviews/4/comments"):
            return [{"id": 9, "body": "inline"}]
        if path.endswith("/pulls/7/reviews/5/comments"):
            return [{"id": 1, "body": "duplicate top-level"}]
        raise AssertionError(path)

    monkeypatch.setattr(client, "_request_json", fake_request_json)

    assert client.get_comments("sam", "joan", 7) == [
        {"id": 1, "body": "top-level"},
        {"id": 9, "body": "inline"},
    ]


def test_resolve_comment_primary_success(monkeypatch) -> None:
    client = ForgejoClient("http://forgejo.local", "abc")

    def fake_request_json(method, path, **kwargs):
        assert method == "POST"
        assert path.endswith("/resolve")
        return {}

    monkeypatch.setattr(client, "_request_json", fake_request_json)
    monkeypatch.setattr(client, "_request_raw", lambda *_a, **_kw: pytest.fail("fallback should not run"))

    client.resolve_comment("sam", "joan", 1, 9)


def test_resolve_comment_uses_fallback_on_primary_error(monkeypatch) -> None:
    client = ForgejoClient("http://forgejo.local", "abc")
    call_count = 0

    def fail_primary_then_succeed(method, path, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Primary resolve endpoint fails
            raise ForgejoError("no endpoint")
        # Fallback: create_issue_comment succeeds
        return {"id": 42}

    fallback_calls: list[tuple[str, str, dict]] = []
    orig_request_json = client._request_json

    def tracking_request_json(method, path, **kwargs):
        fallback_calls.append((method, path, kwargs))
        return fail_primary_then_succeed(method, path, **kwargs)

    monkeypatch.setattr(client, "_request_json", tracking_request_json)

    client.resolve_comment("sam", "joan", 1, 9, human_user="alex")
    # First call: primary resolve (fails), second call: create_issue_comment (fallback)
    assert len(fallback_calls) == 2
    assert fallback_calls[1][0] == "POST"
    assert fallback_calls[1][1].endswith("/issues/1/comments")
    assert "@alex" in fallback_calls[1][2]["json"]["body"]
    assert "resolved by joan" in fallback_calls[1][2]["json"]["body"]


def test_create_review_posts_correct_payload(monkeypatch) -> None:
    captured: dict = {}

    def fake_request_json(self, method, path, **kwargs):
        captured["method"] = method
        captured["path"] = path
        captured["payload"] = kwargs.get("json", {})
        return {"id": 99}

    monkeypatch.setattr(ForgejoClient, "_request_json", fake_request_json)

    client = ForgejoClient("http://forgejo.local", "tok")
    result = client.create_review(
        owner="sam",
        repo="joan",
        index=7,
        body="Looks mostly fine.",
        verdict="request_changes",
        comments=[{"path": "src/foo.py", "new_position": 10, "body": "This will break."}],
    )

    assert captured["method"] == "POST"
    assert captured["path"] == "/api/v1/repos/sam/joan/pulls/7/reviews"
    assert captured["payload"]["event"] == "REQUEST_CHANGES"
    assert captured["payload"]["body"] == "Looks mostly fine."
    assert len(captured["payload"]["comments"]) == 1
    assert result == {"id": 99}


def test_create_review_approve_verdict(monkeypatch) -> None:
    captured: dict = {}

    def fake_request_json(self, method, path, **kwargs):
        captured["payload"] = kwargs.get("json", {})
        return {}

    monkeypatch.setattr(ForgejoClient, "_request_json", fake_request_json)
    client = ForgejoClient("http://forgejo.local", "tok")
    client.create_review("sam", "joan", 7, body="lgtm", verdict="approve", comments=[])
    assert captured["payload"]["event"] == "APPROVE"


def test_create_inline_pr_comment_posts_correct_payload(monkeypatch) -> None:
    captured: dict = {}

    def fake_request_json(self, method, path, **kwargs):
        captured["method"] = method
        captured["path"] = path
        captured["payload"] = kwargs.get("json", {})
        return {"id": 12}

    monkeypatch.setattr(ForgejoClient, "_request_json", fake_request_json)
    client = ForgejoClient("http://forgejo.local", "tok")
    result = client.create_inline_pr_comment("sam", "joan", 7, "src/foo.py", 42, "This breaks.")

    assert captured["method"] == "POST"
    assert captured["path"] == "/api/v1/repos/sam/joan/pulls/7/comments"
    assert captured["payload"] == {
        "body": "This breaks.",
        "path": "src/foo.py",
        "line": 42,
        "side": "RIGHT",
    }
    assert result == {"id": 12}


def test_get_pr_diff_returns_text(monkeypatch) -> None:
    diff_text = "diff --git a/foo.py b/foo.py\n+new line"

    def fake_request_raw(self, method, path, **kwargs):
        return make_response(200, body=diff_text)

    monkeypatch.setattr(ForgejoClient, "_request_raw", fake_request_raw)
    client = ForgejoClient("http://forgejo.local", "tok")
    result = client.get_pr_diff("sam", "joan", 7)
    assert result == diff_text


def test_create_user_via_admin(monkeypatch) -> None:
    client = ForgejoClient("http://forgejo.local")
    calls: list[tuple[str, str, dict]] = []

    def fake_client_cls(*args, **kwargs):
        class C:
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False
            def post(self, url, json):
                calls.append(("POST", url, json))
                return make_response(201, json_data={"id": 5, "login": "joan"})
        return C()

    monkeypatch.setattr(httpx, "Client", fake_client_cls)

    result = client.create_user(
        admin_username="admin",
        admin_password="adminpw",
        username="joan",
        email="joan@localhost",
        password="secret",
    )

    assert result["login"] == "joan"
    assert len(calls) == 1
    assert calls[0][1].endswith("/api/v1/admin/users")
    assert calls[0][2]["username"] == "joan"
    assert calls[0][2]["must_change_password"] is False


def test_create_token_with_admin_auth(monkeypatch) -> None:
    holder: dict[str, object] = {}

    def fake_client_cls(*args, auth=None, **kwargs):
        holder["auth"] = auth

        class C:
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False
            def post(self, _url, json):
                return make_response(200, json_data={"sha1": "joan-tok"})
        return C()

    monkeypatch.setattr(httpx, "Client", fake_client_cls)

    client = ForgejoClient("http://forgejo.local")
    token = client.create_token("joan", "adminpw", "my-token", auth_username="admin")

    assert token == "joan-tok"
    assert holder["auth"] == ("admin", "adminpw")


def test_create_issue_comment_posts_to_issues_endpoint(monkeypatch) -> None:
    captured: dict = {}

    def fake_request_json(self, method, path, **kwargs):
        captured["method"] = method
        captured["path"] = path
        captured["payload"] = kwargs.get("json", {})
        return {"id": 42}

    monkeypatch.setattr(ForgejoClient, "_request_json", fake_request_json)
    client = ForgejoClient("http://forgejo.local", "tok")
    result = client.create_issue_comment("sam", "joan", 7, "Great work!")

    assert captured["method"] == "POST"
    assert captured["path"] == "/api/v1/repos/sam/joan/issues/7/comments"
    assert captured["payload"] == {"body": "Great work!"}
    assert result == {"id": 42}


def test_create_get_list_and_close_issue_endpoints(monkeypatch) -> None:
    calls: list[tuple[str, str, dict]] = []

    def fake_request_json(self, method, path, **kwargs):
        calls.append((method, path, kwargs))
        if method == "POST":
            return {"number": 9, "title": "Bug"}
        if method == "GET" and path.endswith("/issues/9"):
            return {"number": 9, "title": "Bug", "state": "open"}
        if method == "GET" and path.endswith("/issues"):
            return [{"number": 9, "title": "Bug", "state": "open"}]
        if method == "PATCH":
            return {"number": 9, "state": "closed"}
        raise AssertionError(path)

    monkeypatch.setattr(ForgejoClient, "_request_json", fake_request_json)
    client = ForgejoClient("http://forgejo.local", "tok")

    created = client.create_issue("sam", "joan", "Bug", "details")
    issue = client.get_issue("sam", "joan", 9)
    issues = client.list_issues("sam", "joan", state="all", limit=25)
    closed = client.close_issue("sam", "joan", 9)

    assert created["number"] == 9
    assert issue["state"] == "open"
    assert len(issues) == 1
    assert closed["state"] == "closed"
    assert calls[0] == (
        "POST",
        "/api/v1/repos/sam/joan/issues",
        {"json": {"title": "Bug", "body": "details"}},
    )
    assert calls[2] == (
        "GET",
        "/api/v1/repos/sam/joan/issues",
        {"params": {"state": "all", "limit": "25"}},
    )
    assert calls[3] == (
        "PATCH",
        "/api/v1/repos/sam/joan/issues/9",
        {"json": {"state": "closed"}},
    )


def test_add_issue_dependency_retries_payload_shapes(monkeypatch) -> None:
    calls: list[dict] = []

    def fake_request_json(self, method, path, **kwargs):
        calls.append(kwargs.get("json", {}))
        if len(calls) <= 3:
            raise ForgejoError("Forgejo API 422: invalid payload")
        return {"ok": True}

    monkeypatch.setattr(ForgejoClient, "_request_json", fake_request_json)
    client = ForgejoClient("http://forgejo.local", "tok")

    result = client.add_issue_dependency("sam", "joan", 10, 4)

    assert result == {"ok": True}
    assert calls[0] == {"owner": "sam", "repo": "joan", "index": 4}
    assert calls[1] == {"index": 4}
    assert calls[2] == {"dependent_issue_id": 4}
    assert calls[3] == {"issue_index": 4}


def test_add_issue_dependency_retries_on_404_then_succeeds(monkeypatch) -> None:
    calls: list[dict] = []

    def fake_request_json(self, method, path, **kwargs):
        calls.append(kwargs.get("json", {}))
        if len(calls) == 1:
            raise ForgejoError(
                'Forgejo API 404: {"message":"IsErrRepoNotExist","errors":["repository does not exist [id: 0, uid: 0, owner_name: , name: ]"]}'
            )
        return {"ok": True}

    monkeypatch.setattr(ForgejoClient, "_request_json", fake_request_json)
    client = ForgejoClient("http://forgejo.local", "tok")

    result = client.add_issue_dependency("sam", "joan", 10, 4)

    assert result == {"ok": True}
    assert calls[0] == {"owner": "sam", "repo": "joan", "index": 4}
    assert calls[1] == {"index": 4}


def test_list_issue_blocked_by_uses_dependencies_endpoint(monkeypatch) -> None:
    calls: list[tuple[str, str, dict]] = []

    def fake_request_json(self, method, path, **kwargs):
        calls.append((method, path, kwargs))
        if path.endswith("/dependencies"):
            return [{"number": 2, "title": "A"}]
        raise AssertionError(path)

    monkeypatch.setattr(ForgejoClient, "_request_json", fake_request_json)
    client = ForgejoClient("http://forgejo.local", "tok")

    result = client.list_issue_blocked_by("sam", "joan", 7)

    assert result == [{"number": 2, "title": "A"}]
    assert calls == [
        (
            "GET",
            "/api/v1/repos/sam/joan/issues/7/dependencies",
            {},
        )
    ]


def test_list_issue_blocks_falls_back_to_scan(monkeypatch) -> None:
    client = ForgejoClient("http://forgejo.local", "tok")

    monkeypatch.setattr(
        client,
        "_list_issue_relation",
        lambda **_kwargs: ([], False),
    )
    monkeypatch.setattr(
        client,
        "list_issues",
        lambda owner, repo, state="open", limit=50: [
            {"number": 1, "title": "root"},
            {"number": 2, "title": "other"},
            {"number": 3, "title": "child"},
        ],
    )

    def fake_blocked_by(_owner, _repo, issue_number):
        if issue_number == 2:
            return []
        if issue_number == 3:
            return [{"number": 1, "title": "root"}]
        return []

    monkeypatch.setattr(client, "list_issue_blocked_by", fake_blocked_by)

    result = client.list_issue_blocks("sam", "joan", 1)

    assert result == [{"number": 3, "title": "child"}]


def test_update_pr_patches_pull_body(monkeypatch) -> None:
    captured: dict = {}

    def fake_request_json(self, method, path, **kwargs):
        captured["method"] = method
        captured["path"] = path
        captured["payload"] = kwargs.get("json", {})
        return {"number": 7, "body": "updated body"}

    monkeypatch.setattr(ForgejoClient, "_request_json", fake_request_json)
    client = ForgejoClient("http://forgejo.local", "tok")
    result = client.update_pr("sam", "joan", 7, "updated body")

    assert captured["method"] == "PATCH"
    assert captured["path"] == "/api/v1/repos/sam/joan/pulls/7"
    assert captured["payload"] == {"body": "updated body"}
    assert result["number"] == 7


def test_raise_for_status_truncates_long_body() -> None:
    client = ForgejoClient("http://forgejo.local", "abc")
    long_body = "x" * 300
    response = make_response(500, body=long_body)

    with pytest.raises(ForgejoError) as exc:
        client._raise_for_status(response)

    message = str(exc.value)
    assert "500" in message
    assert "..." in message


def test_raise_for_status_includes_request_payload() -> None:
    client = ForgejoClient("http://forgejo.local", "abc")
    response = make_response(500, body="internal error")
    payload = {"title": "test", "head": "branch", "base": "main"}

    with pytest.raises(ForgejoError) as exc:
        client._raise_for_status(response, request_context=payload)

    message = str(exc.value)
    assert "500" in message
    assert "request payload:" in message
    assert '"title": "test"' in message
    assert '"head": "branch"' in message


def test_raise_for_status_no_payload_omits_context() -> None:
    client = ForgejoClient("http://forgejo.local", "abc")
    response = make_response(422, body="bad request")

    with pytest.raises(ForgejoError) as exc:
        client._raise_for_status(response)

    message = str(exc.value)
    assert "422" in message
    assert "request payload:" not in message
