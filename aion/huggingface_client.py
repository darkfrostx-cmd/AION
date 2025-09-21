"""Client helpers for the Hugging Face Hub REST API."""

from __future__ import annotations

import json
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib import error, parse, request

from .exceptions import APIError


@dataclass
class HuggingFaceClient:
    """A minimal wrapper around the Hugging Face Hub API."""

    token: Optional[str] = None
    base_url: str = "https://huggingface.co"

    def _build_headers(self, *, accept: str = "application/json") -> Dict[str, str]:
        headers: Dict[str, str] = {"Accept": accept}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    @staticmethod
    def _normalize_repo_type(repo_type: str) -> str:
        normalized = repo_type.lower().rstrip("s")
        if normalized not in {"model", "dataset", "space"}:
            raise ValueError("repo_type must be 'model', 'dataset', or 'space'")
        return normalized + "s"

    def _build_repo_api_url(self, repo_id: str, repo_type: str) -> str:
        repo_scope = self._normalize_repo_type(repo_type)
        encoded_id = parse.quote(repo_id, safe="/")
        return f"{self.base_url}/api/{repo_scope}/{encoded_id}"

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

    def get_repo_info(self, repo_id: str, repo_type: str = "model") -> Dict[str, Any]:
        """Fetch metadata for any Hugging Face repository type."""

        url = self._build_repo_api_url(repo_id, repo_type)
        return self._get_json(url)

    def list_repo_files(
        self,
        repo_id: str,
        *,
        repo_type: str = "model",
        revision: str = "main",
        path: str = "",
        recursive: bool = True,
    ) -> List[Dict[str, Any]]:
        """List files tracked inside a repository revision.

        Parameters mirror the Hub tree endpoint: *path* limits the listing to a
        directory and *recursive* controls whether nested files are returned.
        """

        base_url = self._build_repo_api_url(repo_id, repo_type)
        encoded_revision = parse.quote(revision, safe="")
        tree_url = f"{base_url}/tree/{encoded_revision}"
        params: Dict[str, str] = {}
        normalized_path = path.lstrip("/")
        if normalized_path:
            params["path"] = normalized_path
        if recursive:
            params["recursive"] = "1"
        query = parse.urlencode(params)
        if query:
            tree_url = f"{tree_url}?{query}"
        result = self._get_json(tree_url)
        if isinstance(result, dict) and "tree" in result:
            # Some Hub responses wrap results inside a ``tree`` key.
            tree_data = result.get("tree")
            if isinstance(tree_data, list):
                return tree_data
        if isinstance(result, list):
            return result
        raise APIError("Hugging Face", "Unexpected response format when listing files")

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
            req = request.Request(url, headers=self._build_headers(accept="*/*"))
            with closing(request.urlopen(req)) as resp:
                return resp.read()
        except error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="ignore") or exc.reason
            raise APIError("Hugging Face", message, status=exc.code) from exc
        except error.URLError as exc:  # pragma: no cover - network failure path
            raise APIError("Hugging Face", str(exc.reason)) from exc

