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

    def _build_headers(self, content_type: str = "application/json") -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": content_type,
        }
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
