from __future__ import annotations

from typing import Optional

import requests

from quant_client.bundle_builder import bundle_to_gzip_bytes


class QuantTaskClient:
    def __init__(self, base_url: str, token: Optional[str] = None, user: str = "", password: str = "", timeout: int = 60):
        self.base_url = base_url.rstrip("/")
        self.token = token or ""
        self.user = user
        self.password = password
        self.timeout = timeout

    def _headers(self) -> dict:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _auth_payload(self) -> dict:
        if self.token:
            return {}
        payload = {}
        if self.user:
            payload["user"] = self.user
        if self.password:
            payload["password"] = self.password
        return payload

    def claim_task(self, client_id: str, capabilities: Optional[list[str]] = None) -> dict:
        payload = {"client_id": client_id, "capabilities": capabilities or []}
        payload.update(self._auth_payload())
        response = requests.post(
            f"{self.base_url}/never_guess_my_usage/quant/client/tasks/claim",
            json=payload,
            headers=self._headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def report_task_success(self, client_id: str, task_id: str, bundle: dict, message: str = "") -> dict:
        files = {
            "bundle": ("bundle.json.gz", bundle_to_gzip_bytes(bundle), "application/gzip"),
        }
        data = {
            "client_id": client_id,
            "task_id": task_id,
            "status": "success",
            "message": message,
        }
        data.update(self._auth_payload())
        response = requests.post(
            f"{self.base_url}/never_guess_my_usage/quant/client/tasks/report",
            data=data,
            files=files,
            headers={key: value for key, value in self._headers().items() if key.lower() != "content-type"},
            timeout=max(self.timeout, 300),
        )
        response.raise_for_status()
        return response.json()

    def report_task_failure(self, client_id: str, task_id: str, message: str) -> dict:
        payload = {
            "client_id": client_id,
            "task_id": task_id,
            "status": "failed",
            "message": message,
        }
        payload.update(self._auth_payload())
        response = requests.post(
            f"{self.base_url}/never_guess_my_usage/quant/client/tasks/report",
            json=payload,
            headers=self._headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()
