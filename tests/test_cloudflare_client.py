import io
import json
from unittest.mock import MagicMock, patch
from urllib import error

import pytest

from aion.cloudflare_client import CloudflareClient
from aion.exceptions import APIError


def _response(payload: dict) -> MagicMock:
    resp = MagicMock()
    resp.read.return_value = json.dumps(payload).encode("utf-8")
    return resp


@patch("aion.cloudflare_client.request.urlopen")
def test_list_zones_uses_authorization_header(mock_urlopen: MagicMock) -> None:
    mock_urlopen.return_value = _response({"success": True, "result": [{"name": "example.com"}]})
    client = CloudflareClient(token="abc123")

    result = client.list_zones()

    assert result == [{"name": "example.com"}]
    req = mock_urlopen.call_args[0][0]
    assert req.get_header("Authorization") == "Bearer abc123"


@patch("aion.cloudflare_client.request.urlopen")
def test_create_kv_namespace_requires_account_id(mock_urlopen: MagicMock) -> None:
    client = CloudflareClient(token="token")
    with pytest.raises(ValueError):
        client.create_kv_namespace("demo")
    mock_urlopen.assert_not_called()


@patch("aion.cloudflare_client.request.urlopen")
def test_write_kv_value_parses_result(mock_urlopen: MagicMock) -> None:
    mock_urlopen.return_value = _response({"success": True, "result": {"id": "ns"}})
    client = CloudflareClient(token="token", account_id="account")

    result = client.write_kv_value("namespace", "key", "value")

    assert result == {"success": True, "result": {"id": "ns"}}
    req = mock_urlopen.call_args[0][0]
    assert req.method == "PUT"
    assert req.get_header("Content-type") == "text/plain"


@patch("aion.cloudflare_client.request.urlopen")
def test_cloudflare_http_error(mock_urlopen: MagicMock) -> None:
    http_error = error.HTTPError(
        url="https://api.cloudflare.com/client/v4/zones",
        code=403,
        msg="Forbidden",
        hdrs=None,
        fp=io.BytesIO(b"{\"success\":false}"),
    )
    mock_urlopen.side_effect = http_error

    client = CloudflareClient(token="token")
    with pytest.raises(APIError) as exc:
        client.list_zones()

    assert "Cloudflare API error" in str(exc.value)
    assert exc.value.status == 403
