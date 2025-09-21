"""Client helpers for the Hugging Face Hub REST API and Spaces."""

from __future__ import annotations

import json
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union
from urllib import error, parse, request

from .exceptions import APIError


@dataclass
class HuggingFaceClient:
    """A minimal wrapper around the Hugging Face Hub API."""

    token: Optional[str] = None
    base_url: str = "https://huggingface.co"

    def _build_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def list_models(self, author: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Return metadata about models available on the hub."""

        params = {"limit": str(limit)}
        if author:
            params["author"] = author
        query = parse.urlencode(params)
        url = f"{self.base_url}/api/models?{query}" if query else f"{self.base_url}/api/models"
        return self._get_json(url)

    def get_model_card(self, model_id: str) -> Dict[str, Any]:
        """Fetch detailed metadata for a specific model."""

        url = f"{self.base_url}/api/models/{parse.quote(model_id, safe='')}"
        return self._get_json(url)

    def download_file(
        self,
        repo_id: str,
        filename: str,
        revision: str = "main",
        destination: Optional[Path] = None,
    ) -> Union[bytes, Path]:
        """Download a file from a repository.

        If *destination* is provided the contents are written to disk and the
        path is returned. Otherwise the raw bytes are returned.
        """

        normalized_filename = filename.lstrip("/")
        url = (
            f"{self.base_url}/{parse.quote(repo_id, safe='')}/resolve/"
            f"{parse.quote(revision, safe='')}/{parse.quote(normalized_filename)}"
        )
        content = self._get_bytes(url)
        if destination is not None:
            destination_path = Path(destination)
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            destination_path.write_bytes(content)
            return destination_path
        return content

    def _get_json(self, url: str) -> Any:
        try:
            req = request.Request(url, headers=self._build_headers())
            with closing(request.urlopen(req)) as resp:
                return json.load(resp)
        except error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="ignore") or exc.reason
            raise APIError("Hugging Face", message, status=exc.code) from exc
        except error.URLError as exc:  # pragma: no cover - network failure path
            raise APIError("Hugging Face", str(exc.reason)) from exc

    def _get_bytes(self, url: str) -> bytes:
        try:
            req = request.Request(url, headers=self._build_headers())
            with closing(request.urlopen(req)) as resp:
                return resp.read()
        except error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="ignore") or exc.reason
            raise APIError("Hugging Face", message, status=exc.code) from exc
        except error.URLError as exc:  # pragma: no cover - network failure path
            raise APIError("Hugging Face", str(exc.reason)) from exc


@dataclass
class HuggingFaceSpaceClient:
    """HTTP client for interacting with a specific Hugging Face Space."""

    space_id: str
    token: Optional[str] = None
    base_url: str = "https://huggingface.co"

    def _build_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _build_url(self, path: str, params: Optional[Mapping[str, Union[str, Sequence[str]]]]) -> str:
        encoded_space = parse.quote(self.space_id, safe="/")
        normalized_path = path.lstrip("/")
        url = f"{self.base_url}/spaces/{encoded_space}"
        if normalized_path:
            url = f"{url}/{normalized_path}"
        if params:
            query = parse.urlencode(params, doseq=True)
            url = f"{url}?{query}"
        return url

    def request(
        self,
        path: str,
        *,
        method: str = "GET",
        params: Optional[Mapping[str, Union[str, Sequence[str]]]] = None,
        json_payload: Optional[Any] = None,
        data: Optional[bytes] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Perform an HTTP request against the Space.

        The response body is decoded as JSON when possible; otherwise the raw
        bytes are returned.
        """

        if json_payload is not None and data is not None:
            raise ValueError("Provide either json_payload or data, not both")

        payload: Optional[bytes]
        headers = self._build_headers()
        if json_payload is not None:
            payload = json.dumps(json_payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        else:
            payload = data

        url = self._build_url(path, params)
        try:
            req = request.Request(url, data=payload, headers=headers, method=method.upper())
            with closing(request.urlopen(req, timeout=timeout)) as resp:
                raw = resp.read()
                if not raw:
                    return {}
                try:
                    return json.loads(raw.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    return raw
        except error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="ignore") or exc.reason
            raise APIError("Hugging Face Space", message, status=exc.code) from exc
        except error.URLError as exc:  # pragma: no cover - network failure path
            raise APIError("Hugging Face Space", str(exc.reason)) from exc

    def get(
        self,
        path: str,
        *,
        params: Optional[Mapping[str, Union[str, Sequence[str]]]] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Convenience helper for ``GET`` requests."""

        return self.request(path, method="GET", params=params, timeout=timeout)

    def post(
        self,
        path: str,
        *,
        json_payload: Optional[Any] = None,
        data: Optional[bytes] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """Convenience helper for ``POST`` requests."""

        return self.request(
            path,
            method="POST",
            json_payload=json_payload,
            data=data,
            timeout=timeout,
        )
