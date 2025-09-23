"""Command line interface to interact with Hugging Face and Cloudflare."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Optional

from .cloudflare_client import CloudflareClient
from .exceptions import APIError
from .huggingface_client import HuggingFaceClient


def _print_json(data: Any) -> None:
    import json

    print(json.dumps(data, indent=2, sort_keys=True))


def _parse_repo_type(repo_type: Optional[str]) -> str:
    if repo_type is None:
        return "model"
    normalized = repo_type.lower()
    if normalized not in {"model", "dataset", "space"}:
        raise SystemExit("repo-type must be 'model', 'dataset', or 'space'")
    return normalized


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
    elif args.action == "repo-info":
        repo_type = _parse_repo_type(args.repo_type)
        info = client.get_repo_info(args.repo_id, repo_type=repo_type)
        _print_json(info)
    elif args.action == "repo-files":
        repo_type = _parse_repo_type(args.repo_type)
        files = client.list_repo_files(
            args.repo_id,
            repo_type=repo_type,
            revision=args.revision,
            path=args.path or "",
            recursive=not args.non_recursive,
        )
        _print_json(files)


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
    elif args.action == "list-worker-services":
        services = client.list_worker_services()
        _print_json(services)
    elif args.action == "worker-service-info":
        info = client.get_worker_service(args.service_name)
        if args.include_environments:
            environments = client.list_worker_service_environments(args.service_name)
            info = dict(info)
            info["environments"] = environments
        _print_json(info)
    elif args.action == "worker-service-script":
        script = client.get_worker_service_script(args.service_name, args.environment)
        if args.output:
            output_path = Path(args.output)
            output_path.write_text(script, encoding="utf-8")
            print(f"Saved to {output_path}")
        else:
            print(script)


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

    repo_info_parser = hf_sub.add_parser(
        "repo-info",
        help="Show metadata for a repository",
    )
    repo_info_parser.add_argument("repo_id", help="Repository identifier (e.g. user/name)")
    repo_info_parser.add_argument(
        "--repo-type",
        dest="repo_type",
        help="Repository type: model, dataset, or space (default: model)",
    )

    repo_files_parser = hf_sub.add_parser(
        "repo-files",
        help="List files within a repository revision",
    )
    repo_files_parser.add_argument("repo_id", help="Repository identifier (e.g. user/name)")
    repo_files_parser.add_argument(
        "--repo-type",
        dest="repo_type",
        help="Repository type: model, dataset, or space (default: model)",
    )
    repo_files_parser.add_argument(
        "--revision",
        default="main",
        help="Repository revision to inspect (default: main)",
    )
    repo_files_parser.add_argument(
        "--path",
        help="List files under a specific directory inside the repo",
    )
    repo_files_parser.add_argument(
        "--non-recursive",
        action="store_true",
        help="Only show direct children of the requested path",
    )

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

    worker_services_parser = cf_sub.add_parser(
        "list-worker-services",
        help="List Worker services for the configured account",
    )

    worker_service_info_parser = cf_sub.add_parser(
        "worker-service-info",
        help="Show metadata for a Worker service",
    )
    worker_service_info_parser.add_argument("service_name", help="Worker service name")
    worker_service_info_parser.add_argument(
        "--include-environments",
        action="store_true",
        help="Include environment listings in the output",
    )

    worker_service_script_parser = cf_sub.add_parser(
        "worker-service-script",
        help="Download the script for a Worker service environment",
    )
    worker_service_script_parser.add_argument("service_name", help="Worker service name")
    worker_service_script_parser.add_argument(
        "--environment",
        default="production",
        help="Environment to fetch (default: production)",
    )
    worker_service_script_parser.add_argument(
        "--output",
        help="Optional path to save the script locally",
    )

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
