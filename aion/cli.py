"""Command line interface to interact with Hugging Face and Cloudflare."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from .cloudflare_client import CloudflareClient
from .exceptions import APIError
from .huggingface_client import HuggingFaceClient
from .spaces_client import HuggingFaceSpaceClient

SPACE_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "darkfrostx/neuro-mechanism-backend": {
        "description": "Fetch a sample mechanism graph manifest for receptor HTR2A and symptom apathy.",
        "method": "GET",
        "path": "/mechanism_graph_manifest",
        "params": {"receptor": "HTR2A", "symptom": "apathy"},
    },
    "darkfrostx/ssra-auditor": {
        "description": "Submit a minimal bundle to the SSRA auditor for evaluation.",
        "method": "POST",
        "path": "/audit",
        "payload": {
            "metrics": {"TCS": 0.2, "HDI": 0.4, "PDS": 0.25, "EVI": 1, "CBS": 0.3, "LQS": 0.4},
            "bundle": {
                "network": {"data": [{"source": "HTR2A", "target": "5-HT", "weight": 0.8}]},
                "regions": {"data": {"regions_ranked": ["ACC", "PFC", "HPC"]}},
                "literature": [
                    {"title": "Selective serotonin reuptake modulates apathy", "pmid": "123456"}
                ],
            },
        },
    },
}


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def _parse_kv_pairs(pairs: Optional[list[str]]) -> Dict[str, str]:
    params: Dict[str, str] = {}
    if not pairs:
        return params
    for item in pairs:
        if "=" not in item:
            raise SystemExit(f"Invalid parameter '{item}'. Expected key=value format.")
        key, value = item.split("=", 1)
        params[key] = value
    return params


def _load_payload(args: argparse.Namespace) -> Dict[str, Any]:
    if args.payload_file:
        payload_text = Path(args.payload_file).read_text(encoding="utf-8")
    elif args.payload:
        payload_text = args.payload
    else:
        raise SystemExit("A JSON payload is required (use --payload or --payload-file)")
    try:
        return json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON payload: {exc}")


def _handle_huggingface(args: argparse.Namespace) -> None:
    token = args.token or os.getenv("HF_TOKEN")
    client = HuggingFaceClient(token=token)

    if args.action == "list-models":
        models = client.list_models(author=args.author, limit=args.limit)
        _print_json(models)
    elif args.action == "model-card":
        card = client.get_model_card(args.model_id)
        _print_json(card)
    elif args.action == "download":
        destination = Path(args.output) if args.output else None
        content = client.download_file(
            args.repo_id,
            args.filename,
            revision=args.revision,
            destination=destination,
        )
        if destination is None:
            print(content.decode("utf-8", errors="replace"))
        else:
            print(f"Downloaded to {content}")
    elif args.action in {"space-get", "space-post", "space-template"}:
        _handle_space(args, token)


def _handle_space(args: argparse.Namespace, token: Optional[str]) -> None:
    if args.action == "space-template":
        template = SPACE_TEMPLATES.get(args.space_id)
        if not template:
            raise SystemExit(f"No template available for Space '{args.space_id}'.")
        _print_json(template)
        return

    space_client = HuggingFaceSpaceClient(space_id=args.space_id, token=token)

    if args.action == "space-get":
        params = _parse_kv_pairs(args.params)
        response = space_client.get(args.path, params=params or None)
        _print_json(response)
    elif args.action == "space-post":
        payload = _load_payload(args)
        response = space_client.post(args.path, payload)
        _print_json(response)


def _handle_cloudflare(args: argparse.Namespace) -> None:
    token = args.token or os.getenv("CLOUDFLARE_API_TOKEN")
    if not token:
        raise SystemExit("A Cloudflare API token is required")
    client = CloudflareClient(token=token, account_id=args.account_id)

    if args.action == "list-zones":
        zones = client.list_zones(name=args.name)
        _print_json(zones)
    elif args.action == "create-kv-namespace":
        result = client.create_kv_namespace(args.title)
        _print_json(result)
    elif args.action == "write-kv":
        result = client.write_kv_value(args.namespace_id, args.key, args.value)
        _print_json(result)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Interact with Hugging Face and Cloudflare services")
    subparsers = parser.add_subparsers(dest="service", required=True)

    hf_parser = subparsers.add_parser("huggingface", help="Commands for the Hugging Face Hub")
    hf_parser.add_argument("--token", help="API token (defaults to HF_TOKEN environment variable)")
    hf_sub = hf_parser.add_subparsers(dest="action", required=True)

    list_models_parser = hf_sub.add_parser("list-models", help="List models available on the hub")
    list_models_parser.add_argument("--author", help="Filter models by author")
    list_models_parser.add_argument("--limit", type=int, default=10, help="Limit the number of models returned")

    model_card_parser = hf_sub.add_parser("model-card", help="Fetch a model card")
    model_card_parser.add_argument("model_id", help="The repository id of the model")

    download_parser = hf_sub.add_parser("download", help="Download a file from a repository")
    download_parser.add_argument("repo_id", help="Repository identifier (e.g. user/model)")
    download_parser.add_argument("filename", help="Path to the file inside the repository")
    download_parser.add_argument("--revision", default="main", help="Repository revision to download from")
    download_parser.add_argument("--output", help="Destination path to write the file")

    space_get_parser = hf_sub.add_parser("space-get", help="Send a GET request to a Hugging Face Space")
    space_get_parser.add_argument("space_id", help="Space identifier (e.g. owner/space-name)")
    space_get_parser.add_argument("path", help="Endpoint path inside the Space (e.g. /health)")
    space_get_parser.add_argument("--param", dest="params", action="append", help="Query parameter in key=value form (repeatable)")

    space_post_parser = hf_sub.add_parser("space-post", help="Send a POST request to a Hugging Face Space")
    space_post_parser.add_argument("space_id", help="Space identifier (e.g. owner/space-name)")
    space_post_parser.add_argument("path", help="Endpoint path inside the Space")
    group = space_post_parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--payload", help="Inline JSON payload to send")
    group.add_argument("--payload-file", help="Path to a JSON file to send")

    space_template_parser = hf_sub.add_parser("space-template", help="Show a template payload/params for a known Space")
    space_template_parser.add_argument("space_id", help="Space identifier (e.g. owner/space-name)")

    cf_parser = subparsers.add_parser("cloudflare", help="Commands for the Cloudflare API")
    cf_parser.add_argument("--token", help="API token (defaults to CLOUDFLARE_API_TOKEN environment variable)")
    cf_parser.add_argument("--account-id", dest="account_id", help="Cloudflare account identifier")
    cf_sub = cf_parser.add_subparsers(dest="action", required=True)

    list_zones_parser = cf_sub.add_parser("list-zones", help="List Cloudflare zones")
    list_zones_parser.add_argument("--name", help="Optional filter for a zone name")

    kv_namespace_parser = cf_sub.add_parser("create-kv-namespace", help="Create a Workers KV namespace")
    kv_namespace_parser.add_argument("title", help="Display title for the namespace")

    kv_write_parser = cf_sub.add_parser("write-kv", help="Write a value to a Workers KV namespace")
    kv_write_parser.add_argument("namespace_id", help="Namespace identifier")
    kv_write_parser.add_argument("key", help="Key for the value")
    kv_write_parser.add_argument("value", help="Value to store")

    return parser


def main(argv: Optional[list[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.service == "huggingface":
            _handle_huggingface(args)
        elif args.service == "cloudflare":
            _handle_cloudflare(args)
    except APIError as exc:
        raise SystemExit(str(exc))


if __name__ == "__main__":  # pragma: no cover - manual execution entrypoint
    main()
