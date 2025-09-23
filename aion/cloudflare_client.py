"""Client helpers for Cloudflare's REST API."""

from __future__ import annotations

import json
from contextlib import closing
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib import error, parse, request

from .exceptions import APIError


@dataclass
class CloudflareClient:
    """A lightweight helper for a subset of Cloudflare API operations."""

    token: str
    account_id: Optional[str] = None
    base_url: str = "https://api.cloudflare.com/client/v4"

    def _build_headers(
        self,
        content_type: Optional[str] = "application/json",
        *,
        accept: Optional[str] = None,
    ) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.token}",
        }
        if content_type:
            headers["Content-Type"] = content_type
        if accept:
            headers["Accept"] = accept
        return headers

    def list_zones(self, name: Optional[str] = None) -> Any:
        """List Cloudflare zones accessible with the provided token."""

        params = {"per_page": "50"}
        if name:
            params["name"] = name
        query = parse.urlencode(params)
        url = f"{self.base_url}/zones?{query}" if query else f"{self.base_url}/zones"
        data = self._request(url)
        return data.get("result", [])

    def create_kv_namespace(self, title: str) -> Dict[str, Any]:
        """Create a new Workers KV namespace."""

        if not self.account_id:
            raise ValueError("account_id is required for KV operations")
        payload = json.dumps({"title": title}).encode("utf-8")
        url = f"{self.base_url}/accounts/{self.account_id}/storage/kv/namespaces"
        data = self._request(url, payload)
        return data.get("result", {})

    def write_kv_value(self, namespace_id: str, key: str, value: str) -> Dict[str, Any]:
        """Write a value into a Workers KV namespace."""

        if not self.account_id:
            raise ValueError("account_id is required for KV operations")
        encoded_key = parse.quote(key, safe="")
        url = (
            f"{self.base_url}/accounts/{self.account_id}/storage/kv/namespaces/"
            f"{namespace_id}/values/{encoded_key}"
        )
        payload = value.encode("utf-8")
        return self._request(url, payload, method="PUT", content_type="text/plain")

    def _request(
        self,
        url: str,
        data: Optional[bytes] = None,
        method: Optional[str] = None,
        content_type: str = "application/json",
    ) -> Any:
        try:
            headers = self._build_headers(content_type=content_type)
            req = request.Request(url, data=data, headers=headers)
            if method is not None:
                req.method = method
            with closing(request.urlopen(req)) as resp:
                payload = resp.read().decode("utf-8")
            return self._parse_response(payload)
        except error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="ignore") or exc.reason
            raise APIError("Cloudflare", message, status=exc.code) from exc
        except error.URLError as exc:  # pragma: no cover - network failure path
            raise APIError("Cloudflare", str(exc.reason)) from exc

    @staticmethod
    def _parse_response(payload: str) -> Any:
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            raise APIError("Cloudflare", "Invalid JSON response")
        if not data.get("success", False):
            errors = data.get("errors") or "Unknown error"
            raise APIError("Cloudflare", str(errors))
        return data

    def _require_account_id(self) -> str:
        if not self.account_id:
            raise ValueError("account_id is required for this operation")
        return self.account_id

    def list_worker_services(self) -> Any:
        """Return Worker services available on the current account."""

        account_id = self._require_account_id()
        url = f"{self.base_url}/accounts/{account_id}/workers/services"
        data = self._request(url)
        return data.get("result", [])

    def get_worker_service(self, service: str) -> Dict[str, Any]:
        """Fetch metadata about a specific Worker service."""

        account_id = self._require_account_id()
        encoded = parse.quote(service, safe="")
        url = f"{self.base_url}/accounts/{account_id}/workers/services/{encoded}"
        data = self._request(url)
        return data.get("result", {})

    def list_worker_service_environments(self, service: str) -> Any:
        """List environments configured for a Worker service."""

        account_id = self._require_account_id()
        encoded = parse.quote(service, safe="")
        url = (
            f"{self.base_url}/accounts/{account_id}/workers/services/{encoded}/environments"
        )
        data = self._request(url)
        return data.get("result", [])

    def get_worker_service_script(self, service: str, environment: str = "production") -> str:
        """Download the Worker script for an environment as plain text."""

        account_id = self._require_account_id()
        encoded_service = parse.quote(service, safe="")
        encoded_env = parse.quote(environment, safe="")
        url = (
            f"{self.base_url}/accounts/{account_id}/workers/services/"
            f"{encoded_service}/environments/{encoded_env}/content"
        )

        try:
            headers = self._build_headers(content_type=None, accept="application/javascript")
            req = request.Request(url, headers=headers)
            with closing(request.urlopen(req)) as resp:
                return resp.read().decode("utf-8")
        except error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="ignore") or exc.reason
            raise APIError("Cloudflare", message, status=exc.code) from exc
        except error.URLError as exc:  # pragma: no cover - network failure path
            raise APIError("Cloudflare", str(exc.reason)) from exc
