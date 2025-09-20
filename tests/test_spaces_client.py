import json
from unittest.mock import MagicMock, patch
from urllib import error

import pytest

from aion.exceptions import APIError
from aion.spaces_client import HuggingFaceSpaceClient


@patch("aion.spaces_client.request.urlopen")
def test_space_get_builds_correct_url(mock_urlopen: MagicMock) -> None:
    response = MagicMock()
    response.read.return_value = json.dumps({"ok": True}).encode("utf-8")
    mock_urlopen.return_value = response

    client = HuggingFaceSpaceClient("darkfrostx/ssra-auditor")
    data = client.get("/health")

    assert data == {"ok": True}
    request_obj = mock_urlopen.call_args[0][0]
    assert request_obj.full_url == "https://darkfrostx-ssra-auditor.hf.space/health"
    assert request_obj.get_header("Accept") == "application/json"


@patch("aion.spaces_client.request.urlopen")
def test_space_post_sends_json_payload(mock_urlopen: MagicMock) -> None:
    response = MagicMock()
    response.read.return_value = json.dumps({"decision": "APPROVE"}).encode("utf-8")
    mock_urlopen.return_value = response

    client = HuggingFaceSpaceClient("darkfrostx/ssra-auditor", token="secret")
    payload = {"metrics": {"TCS": 0.2}, "bundle": {}}
    data = client.post("/audit", payload)

    assert data == {"decision": "APPROVE"}
    request_obj = mock_urlopen.call_args[0][0]
    assert request_obj.full_url == "https://darkfrostx-ssra-auditor.hf.space/audit"
    assert request_obj.get_header("Authorization") == "Bearer secret"
    assert json.loads(request_obj.data.decode("utf-8")) == payload


@patch("aion.spaces_client.request.urlopen")
def test_space_http_error_raises_api_error(mock_urlopen: MagicMock) -> None:
    http_error = error.HTTPError(
        url="https://darkfrostx-ssra-auditor.hf.space/audit",
        code=500,
        msg="Internal Server Error",
        hdrs=None,
        fp=None,
    )
    mock_urlopen.side_effect = http_error

    client = HuggingFaceSpaceClient("darkfrostx/ssra-auditor")
    with pytest.raises(APIError) as exc:
        client.post("/audit", {"bundle": {}})

    assert "Hugging Face Space API error" in str(exc.value)
    assert exc.value.status == 500
