"""Command line interface to interact with Hugging Face and Cloudflare."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .cloudflare_client import CloudflareClient
from .exceptions import APIError
from .huggingface_client import HuggingFaceClient, HuggingFaceSpaceClient


TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def _load_template(name: str) -> Any:
    path = TEMPLATES_DIR / name
    if not path.exists():
        raise SystemExit(f"Template '{name}' was not found under {TEMPLATES_DIR}")
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive guard
        raise SystemExit(f"Template '{name}' contains invalid JSON: {exc}") from exc


def _resolve_payload(
    inline_payload: Optional[str],
    payload_file: Optional[str],
    template_name: Optional[str] = None,
) -> Tuple[Any, bool]:
    if inline_payload and payload_file:
        raise SystemExit("Provide either --payload or --payload-file, not both")

    if payload_file:
        try:
            with Path(payload_file).open("r", encoding="utf-8") as handle:
                return json.load(handle), True
        except FileNotFoundError as exc:
            raise SystemExit(f"Payload file '{payload_file}' could not be found") from exc
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Payload file '{payload_file}' is not valid JSON: {exc}") from exc

    if inline_payload is not None:
        try:
            return json.loads(inline_payload), True
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Inline payload is not valid JSON: {exc}") from exc

    if template_name:
        return _load_template(template_name), True

    return {}, False


def _parse_key_value_args(pairs: Optional[List[str]]) -> Dict[str, List[str]]:
    params: Dict[str, List[str]] = {}
    for item in pairs or []:
        if "=" not in item:
            raise SystemExit(f"Parameters must be in key=value form; received '{item}'")
        key, value = item.split("=", 1)
        params.setdefault(key, []).append(value)
    return params


def _print_space_response(response: Any) -> None:
    if isinstance(response, (dict, list)):
        _print_json(response)
    elif isinstance(response, bytes):
        try:
            text = response.decode("utf-8")
        except UnicodeDecodeError:
            raise SystemExit("The Space returned binary data; redirect to a file instead") from None
        print(text)
    else:
        print(response)


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
    elif args.action == "space":
        _handle_huggingface_space(args)


def _handle_huggingface_space(args: argparse.Namespace) -> None:
    token = args.token or os.getenv("HF_TOKEN")
    client = HuggingFaceSpaceClient(space_id=args.space_id, token=token)

    params = _parse_key_value_args(getattr(args, "query", None))
    payload, provided = _resolve_payload(
        getattr(args, "payload", None),
        getattr(args, "payload_file", None),
        getattr(args, "payload_template", None),
    )

    send_payload = provided or getattr(args, "allow_empty_payload", False)
    json_payload = payload if send_payload else None

    response = client.request(
        args.path,
        method=args.method,
        params=params or None,
        json_payload=json_payload,
        timeout=args.timeout,
    )
    _print_space_response(response)


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

    space_parser = hf_sub.add_parser("space", help="Call Hugging Face Spaces endpoints")
    space_parser.add_argument("--token", help="API token (defaults to HF_TOKEN environment variable)")
    space_sub = space_parser.add_subparsers(dest="space_action", required=True)

    def _add_space_common_arguments(
        space_subparser: argparse.ArgumentParser,
        *,
        default_path: str,
        default_method: str,
    ) -> None:
        space_subparser.add_argument(
            "--path",
            default=default_path,
            help=f"Relative endpoint inside the Space (default: {default_path})",
        )
        space_subparser.add_argument(
            "--method",
            default=default_method,
            help=f"HTTP method to use (default: {default_method})",
        )
        space_subparser.add_argument("--payload", help="Inline JSON payload to send")
        space_subparser.add_argument("--payload-file", help="Path to a JSON payload file")
        space_subparser.add_argument(
            "--allow-empty-payload",
            action="store_true",
            help="Send an empty JSON object when no payload data is provided",
        )
        space_subparser.add_argument(
            "--query",
            action="append",
            help="Append query parameters as key=value entries (repeatable)",
        )
        space_subparser.add_argument("--timeout", type=float, help="Optional request timeout in seconds")

    space_call_parser = space_sub.add_parser("call", help="Call an arbitrary Space endpoint")
    space_call_parser.add_argument("space_id", help="Space identifier (e.g. author/my-space)")
    _add_space_common_arguments(space_call_parser, default_path="api/predict", default_method="POST")

    neuro_parser = space_sub.add_parser(
        "neuro-backend",
        help="Shortcut for darkfrostx/neuro-mechanism-backend",
    )
    neuro_parser.set_defaults(
        space_id="darkfrostx/neuro-mechanism-backend",
        allow_empty_payload=False,
    )
    _add_space_common_arguments(neuro_parser, default_path="health", default_method="GET")

    auditor_parser = space_sub.add_parser(
        "ssra-auditor",
        help="Shortcut for darkfrostx/ssra-auditor",
    )
    auditor_parser.set_defaults(
        space_id="darkfrostx/ssra-auditor",
        payload_template="ssra_auditor_payload.json",
    )
    _add_space_common_arguments(auditor_parser, default_path="audit", default_method="POST")

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
