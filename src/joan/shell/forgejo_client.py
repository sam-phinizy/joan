from __future__ import annotations

from typing import Any

import httpx


class ForgejoError(RuntimeError):
    pass


class ForgejoClient:
    _VERDICT_MAP = {
        "approve": "APPROVE",
        "request_changes": "REQUEST_CHANGES",
        "comment": "COMMENT",
    }

    def __init__(self, base_url: str, token: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    def create_token(
        self,
        username: str,
        password: str,
        token_name: str,
        scopes: list[str] | None = None,
        auth_username: str | None = None,
    ) -> str:
        url = f"{self.base_url}/api/v1/users/{username}/tokens"
        payload = {"name": token_name, "scopes": scopes or ["all"]}
        auth = (auth_username if auth_username is not None else username, password)
        with httpx.Client(timeout=30.0, auth=auth) as client:
            response = client.post(url, json=payload)
        self._raise_for_status(response)
        data = response.json()
        token = data.get("sha1") or data.get("token")
        if not token:
            raise ForgejoError("Forgejo token response did not include token value")
        return str(token)

    def create_user(
        self,
        admin_username: str,
        admin_password: str,
        username: str,
        email: str,
        password: str,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/api/v1/admin/users"
        payload = {
            "email": email,
            "login_name": username,
            "must_change_password": False,
            "password": password,
            "send_notify": False,
            "source_id": 0,
            "username": username,
        }
        with httpx.Client(timeout=30.0, auth=(admin_username, admin_password)) as client:
            response = client.post(url, json=payload)
        self._raise_for_status(response)
        return response.json()

    def create_webhook(
        self,
        admin_username: str,
        admin_password: str,
        owner: str,
        repo: str,
        webhook_url: str,
        secret: str,
        events: list[str] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/api/v1/repos/{owner}/{repo}/hooks"
        payload = {
            "active": True,
            "config": {
                "content_type": "json",
                "secret": secret,
                "url": webhook_url,
            },
            "events": events or ["pull_request"],
            "type": "gitea",
        }
        with httpx.Client(timeout=30.0, auth=(admin_username, admin_password)) as client:
            response = client.post(url, json=payload)
        self._raise_for_status(response)
        return response.json()

    def create_repo(self, name: str, private: bool = True) -> dict[str, Any]:
        return self._request_json("POST", "/api/v1/user/repos", json={"name": name, "private": private})

    def add_repo_collaborator(
        self,
        owner: str,
        repo: str,
        username: str,
        permission: str = "admin",
    ) -> None:
        path = f"/api/v1/repos/{owner}/{repo}/collaborators/{username}"
        response = self._request_raw("PUT", path, json={"permission": permission})
        self._raise_for_status(response)

    def get_current_user(self) -> dict[str, Any]:
        return self._request_json("GET", "/api/v1/user")

    def get_repo(self, owner: str, repo: str) -> dict[str, Any]:
        return self._request_json("GET", f"/api/v1/repos/{owner}/{repo}")

    def get_repo_collaborator_permission(self, owner: str, repo: str, username: str) -> dict[str, Any]:
        path = f"/api/v1/repos/{owner}/{repo}/collaborators/{username}/permission"
        return self._request_json("GET", path)

    def list_ssh_keys(self) -> list[dict[str, Any]]:
        data = self._request_json("GET", "/api/v1/user/keys")
        return list(data)

    def create_ssh_key(self, title: str, key: str, read_only: bool = False) -> dict[str, Any]:
        payload = {"title": title, "key": key, "read_only": read_only}
        return self._request_json("POST", "/api/v1/user/keys", json=payload)

    def create_pr(self, owner: str, repo: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request_json("POST", f"/api/v1/repos/{owner}/{repo}/pulls", json=payload)

    def list_pulls(self, owner: str, repo: str, head: str | None = None) -> list[dict[str, Any]]:
        params: dict[str, str] = {"state": "open"}
        if head:
            params["head"] = head
        data = self._request_json("GET", f"/api/v1/repos/{owner}/{repo}/pulls", params=params)
        return list(data)

    def get_pr(self, owner: str, repo: str, index: int) -> dict[str, Any]:
        return self._request_json("GET", f"/api/v1/repos/{owner}/{repo}/pulls/{index}")

    def get_reviews(self, owner: str, repo: str, index: int) -> list[dict[str, Any]]:
        data = self._request_json("GET", f"/api/v1/repos/{owner}/{repo}/pulls/{index}/reviews")
        return list(data)

    def get_comments(self, owner: str, repo: str, index: int) -> list[dict[str, Any]]:
        data = self._request_json("GET", f"/api/v1/repos/{owner}/{repo}/pulls/{index}/comments")
        return list(data)

    def create_inline_pr_comment(
        self,
        owner: str,
        repo: str,
        index: int,
        path: str,
        line: int,
        body: str,
    ) -> dict[str, Any]:
        payload = {
            "body": body,
            "path": path,
            "line": line,
            "side": "RIGHT",
        }
        return self._request_json("POST", f"/api/v1/repos/{owner}/{repo}/pulls/{index}/comments", json=payload)

    def get_pr_diff(self, owner: str, repo: str, index: int) -> str:
        response = self._request_raw("GET", f"/api/v1/repos/{owner}/{repo}/pulls/{index}.diff")
        self._raise_for_status(response)
        return response.text

    def resolve_comment(self, owner: str, repo: str, index: int, comment_id: int) -> None:
        # Forgejo installations vary on thread resolution endpoints.
        primary = f"/api/v1/repos/{owner}/{repo}/pulls/{index}/comments/{comment_id}/resolve"
        fallback = f"/api/v1/repos/{owner}/{repo}/pulls/comments/{comment_id}"

        try:
            self._request_json("POST", primary)
            return
        except ForgejoError:
            pass

        response = self._request_raw("PATCH", fallback, json={"resolved": True})
        self._raise_for_status(response)

    def create_review(
        self,
        owner: str,
        repo: str,
        index: int,
        body: str,
        verdict: str,
        comments: list[dict],
    ) -> dict[str, Any]:
        event = self._VERDICT_MAP.get(verdict.lower(), "COMMENT")
        payload: dict[str, Any] = {
            "body": body,
            "event": event,
            "comments": comments,
        }
        return self._request_json("POST", f"/api/v1/repos/{owner}/{repo}/pulls/{index}/reviews", json=payload)

    def _request_json(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self._request_raw(method, path, **kwargs)
        self._raise_for_status(response)
        return response.json()

    def _request_raw(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        url = f"{self.base_url}{path}"
        headers = self._headers()
        extra_headers = kwargs.pop("headers", None)
        if extra_headers:
            headers.update(extra_headers)
        with httpx.Client(timeout=30.0, headers=headers) as client:
            return client.request(method, url, **kwargs)

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.is_success:
            return
        body = response.text.strip()
        if len(body) > 200:
            body = f"{body[:200]}..."
        raise ForgejoError(f"Forgejo API {response.status_code}: {body}")
