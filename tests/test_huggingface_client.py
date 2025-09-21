import io
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib import error

import pytest

from aion.exceptions import APIError
from aion.huggingface_client import HuggingFaceClient, HuggingFaceSpaceClient


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
def test_space_client_posts_json(mock_urlopen: MagicMock) -> None:
    response_payload = {"ok": True}
    mock_response = _mock_response(response_payload)
    mock_urlopen.return_value = mock_response

    client = HuggingFaceSpaceClient("demo/space", token="secret")
    payload = {"inputs": [1, 2, 3]}
    result = client.post("api/predict", json_payload=payload)

    assert result == response_payload
    request_obj = mock_urlopen.call_args[0][0]
    assert request_obj.get_header("Authorization") == "Bearer secret"
    assert request_obj.data == json.dumps(payload).encode("utf-8")
    assert request_obj.get_full_url().endswith("/spaces/demo/space/api/predict")


@patch("aion.huggingface_client.request.urlopen")
def test_space_client_returns_bytes_when_not_json(mock_urlopen: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.read.return_value = b"binary"
    mock_urlopen.return_value = mock_response

    client = HuggingFaceSpaceClient("demo/space")
    result = client.get("artifact.tar.gz")

    assert result == b"binary"


@patch("aion.huggingface_client.request.urlopen")
def test_space_client_http_error_raises_api_error(mock_urlopen: MagicMock) -> None:
    http_error = error.HTTPError(
        url="https://huggingface.co/spaces/demo/space/api/predict",
        code=500,
        msg="Internal Server Error",
        hdrs=None,
        fp=io.BytesIO(b"{\"error\": \"boom\"}"),
    )
    mock_urlopen.side_effect = http_error

    client = HuggingFaceSpaceClient("demo/space")
    with pytest.raises(APIError) as exc:
        client.post("api/predict", json_payload={})

    assert "Hugging Face Space API error" in str(exc.value)
    assert exc.value.status == 500
