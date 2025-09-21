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

    def get_repo_info(self, repo_id: str, revision: Optional[str] = None) -> Dict[str, Any]:
        """Return the repository metadata returned by the Hub API.

        Parameters
        ----------
        repo_id:
            The repository identifier, e.g. ``"user/project"``.
        revision:
            Optional Git revision. When provided the metadata reflects the
            specified branch, tag, or commit.
        """

        encoded_repo = parse.quote(repo_id, safe="")
        url = f"{self.base_url}/api/models/{encoded_repo}"
        if revision:
            query = parse.urlencode({"revision": revision})
            url = f"{url}?{query}"
        result = self._get_json(url)
        if not isinstance(result, dict):  # pragma: no cover - defensive guard
            raise APIError("Hugging Face", "Unexpected response payload from Hub API")
        return result

    def list_repo_files(self, repo_id: str, revision: Optional[str] = None) -> List[Dict[str, Any]]:
        """List files available in a repository revision.

        The response mirrors the ``siblings`` entries from the Hub API.
        """

        info = self.get_repo_info(repo_id, revision=revision)
        siblings = info.get("siblings", [])
        if not isinstance(siblings, list):  # pragma: no cover - defensive guard
            raise APIError("Hugging Face", "Repository metadata does not contain file listings")
        return siblings

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


