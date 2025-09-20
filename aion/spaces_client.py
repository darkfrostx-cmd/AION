"""Client helpers for interacting with Hugging Face Spaces."""

from __future__ import annotations

import json
from contextlib import closing
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib import error, parse, request

from .exceptions import APIError


@dataclass
class HuggingFaceSpaceClient:
    """A lightweight REST client that targets a single Hugging Face Space."""

    space_id: str
    token: Optional[str] = None
    domain: str = "hf.space"
    timeout: Optional[float] = 30.0

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Perform a GET request against the Space."""

        url = self._build_url(path)
        if params:
            query = parse.urlencode(params, doseq=True)
            url = f"{url}?{query}"
        return self._request(url, method="GET")

    def post(self, path: str, payload: Dict[str, Any]) -> Any:
        """Perform a POST request against the Space, sending JSON payload."""

        url = self._build_url(path)
        data = json.dumps(payload).encode("utf-8")
        return self._request(url, data=data, method="POST", content_type="application/json")

    # Internal helpers -------------------------------------------------

    def _build_url(self, path: str) -> str:
        slug = self.space_id.replace("/", "-")
        normalized_path = "/" + path.lstrip("/")
        return f"https://{slug}.{self.domain}{normalized_path}"

    def _headers(self, *, content_type: Optional[str] = None) -> Dict[str, str]:
        headers: Dict[str, str] = {"Accept": "application/json"}
        if content_type:
            headers["Content-Type"] = content_type
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _request(
        self,
        url: str,
        *,
        method: str,
        data: Optional[bytes] = None,
        content_type: Optional[str] = None,
        expect_json: bool = True,
    ) -> Any:
        headers = self._headers(content_type=content_type)
        try:
            req = request.Request(url, data=data, headers=headers, method=method)
            with closing(request.urlopen(req, timeout=self.timeout)) as resp:
                raw = resp.read()
        except error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="ignore") or exc.reason
            raise APIError("Hugging Face Space", message, status=exc.code) from exc
        except error.URLError as exc:  # pragma: no cover - network failure path
            raise APIError("Hugging Face Space", str(exc.reason)) from exc

        if not expect_json:
            return raw

        if not raw:
            return None

        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise APIError("Hugging Face Space", "Invalid JSON response") from exc
