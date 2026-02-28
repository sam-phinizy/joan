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

    def fail_primary(*_args, **_kwargs):
        raise ForgejoError("no endpoint")

    fallback_resp = make_response(200, json_data={"ok": True})
    fallback_calls: list[tuple[str, str, dict]] = []

    def fake_request_raw(method, path, **kwargs):
        fallback_calls.append((method, path, kwargs))
        return fallback_resp

    monkeypatch.setattr(client, "_request_json", fail_primary)
    monkeypatch.setattr(client, "_request_raw", fake_request_raw)

    client.resolve_comment("sam", "joan", 1, 9)
    assert fallback_calls[0][0] == "PATCH"
    assert fallback_calls[0][1].endswith("/pulls/comments/9")
    assert fallback_calls[0][2]["json"] == {"resolved": True}


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


def test_raise_for_status_truncates_long_body() -> None:
    client = ForgejoClient("http://forgejo.local", "abc")
    long_body = "x" * 300
    response = make_response(500, body=long_body)

    with pytest.raises(ForgejoError) as exc:
        client._raise_for_status(response)

    message = str(exc.value)
    assert "500" in message
    assert "..." in message
    assert len(message) < 280
