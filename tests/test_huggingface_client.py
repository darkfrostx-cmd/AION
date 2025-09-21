import io
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib import error

import pytest

from aion.exceptions import APIError
from aion.huggingface_client import HuggingFaceClient


def _mock_response(payload: object) -> MagicMock:
    response = MagicMock()
    response.read.return_value = json.dumps(payload).encode("utf-8")
    return response


@patch("aion.huggingface_client.request.urlopen")
def test_list_models_includes_author(mock_urlopen: MagicMock, tmp_path: Path) -> None:
    mock_urlopen.return_value = _mock_response([{"modelId": "demo/model"}])

    client = HuggingFaceClient(token="secret")
    result = client.list_models(author="demo", limit=5)

    assert result == [{"modelId": "demo/model"}]
    request_obj = mock_urlopen.call_args[0][0]
    assert request_obj.get_full_url().startswith("https://huggingface.co/api/models")
    assert request_obj.get_header("Authorization") == "Bearer secret"


@patch("aion.huggingface_client.request.urlopen")
def test_download_file_to_disk(mock_urlopen: MagicMock, tmp_path: Path) -> None:
    mock_resp = MagicMock()
    mock_resp.read.return_value = b"content"
    mock_urlopen.return_value = mock_resp

    destination = tmp_path / "model" / "config.json"
    client = HuggingFaceClient()
    output = client.download_file("demo/model", "config.json", destination=destination)

    assert output == destination
    assert destination.read_bytes() == b"content"


@patch("aion.huggingface_client.request.urlopen")
def test_huggingface_http_error_raises_api_error(mock_urlopen: MagicMock) -> None:
    error_payload = b"{\"error\": \"not found\"}"
    http_error = error.HTTPError(
        url="https://huggingface.co/api/models/demo",
        code=404,
        msg="Not Found",
        hdrs=None,
        fp=io.BytesIO(error_payload),
    )
    mock_urlopen.side_effect = http_error

    client = HuggingFaceClient()
    with pytest.raises(APIError) as exc:
        client.get_model_card("demo")

    assert "Hugging Face API error" in str(exc.value)
    assert exc.value.status == 404


@patch("aion.huggingface_client.request.urlopen")
def test_get_repo_info_appends_revision_query(mock_urlopen: MagicMock) -> None:
    payload = {"id": "demo/model", "siblings": []}
    mock_urlopen.return_value = _mock_response(payload)

    client = HuggingFaceClient(token="token")
    info = client.get_repo_info("demo/model", revision="develop")

    assert info == payload
    request_obj = mock_urlopen.call_args[0][0]
    assert request_obj.get_full_url().endswith("/api/models/demo%2Fmodel?revision=develop")
    assert request_obj.get_header("Authorization") == "Bearer token"


@patch("aion.huggingface_client.request.urlopen")
def test_list_repo_files_returns_siblings(mock_urlopen: MagicMock) -> None:
    payload = {"id": "demo/model", "siblings": [{"rfilename": "config.json"}]}
    mock_urlopen.return_value = _mock_response(payload)

    client = HuggingFaceClient()
    files = client.list_repo_files("demo/model")

    assert files == payload["siblings"]
