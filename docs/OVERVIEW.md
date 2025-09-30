# AION repository overview

This document summarises how the Git repository, Hugging Face Spaces, and the Cloudflare
worker fit together. Use it as a quick orientation guide before diving into the more
procedural walkthrough in [`INTEGRATION.md`](./INTEGRATION.md).

## Purpose at a glance

- **Central toolbox** – The `aion/` Python package exposes shared clients for the Hugging
  Face Hub and Cloudflare APIs so you can script audits, downloads, and metadata fetches
  from a single CLI entry point.
- **Infrastructure as code** – Everything required to deploy the Cloudflare worker that
  proxies Hugging Face repositories lives under `cloudflare/worker/`, including
  TypeScript sources, the Wrangler configuration, and npm scripts.
- **Operational playbooks** – Shell scripts, Make targets, and GitHub Actions workflows
  automate common verification flows (smoke tests, CI dry runs, and integration checks)
  so you can prove push/deploy access end-to-end.

## Repository layout

| Path | What lives here | Highlights |
| --- | --- | --- |
| `aion/` | Python package with CLI entrypoints. | `cli.py` wires subcommands for Hugging Face and Cloudflare helpers; clients live in `huggingface_client.py` and `cloudflare_client.py`. |
| `cloudflare/worker/` | Cloudflare Worker implementation. | TypeScript sources in `src/`, deployment metadata in `wrangler.toml`, npm scripts (`npm run deploy`) for publishing. |
| `docs/` | Human-facing documentation. | `INTEGRATION.md` is a step-by-step onboarding guide; this file provides the big-picture map. |
| `scripts/` | Automation helpers. | `smoke.sh` clones the Spaces, commits harmless changes, deploys the worker, and probes the proxy routes. |
| `tests/` | Unit tests for the Python package. | Mocked clients demonstrate how to exercise the CLI without hitting remote services. |
| `.github/` | Continuous integration workflows. | `codex-ci.yml` runs the smoke test from GitHub Actions using repository/secret credentials. |

Use the table as the canonical reference when onboarding contributors or when you need to
explain where a specific piece of functionality lives.

## Source of truth per surface

| Surface | Primary location | Sync strategy |
| --- | --- | --- |
| Git repository (this repo) | GitHub (or your chosen remote) | Normal Git workflows (`git pull`, `git push`). Automations that stamp the repo (e.g. CI) use dedicated PATs. |
| Hugging Face Spaces | Remote repos under `darkfrostx/neuro-mechanism-backend` and `darkfrostx/ssra-auditor`. | Clone with Git (see `docs/INTEGRATION.md` §2) and keep write tokens handy. Use `scripts/smoke.sh` or the CLI to validate access without manual pushes. |
| Cloudflare Worker | Worker named `aion-neuro-auditor-proxy` by default. | Deploy from `cloudflare/worker/` via `npm run deploy` or the `codex-ci` workflow. Secrets for private Spaces are managed through `wrangler secret put`. |

## Daily workflow checklist

1. **Pull the Git repository** – `git pull origin main` to bring in the latest tooling and
   worker code.
2. **Validate Space access** – Run `python -m aion.cli huggingface repo-info <repo> --repo-type space`
   with your token to ensure credentials are still valid before attempting writes.
3. **Edit and test locally** – Modify the Space clones, adjust the worker, or extend the CLI.
   Use `make smoke` to perform the full push + deploy smoke test when needed.
4. **Commit and push** – Commit changes here and, for Space-specific edits, push the
   corresponding Hugging Face repo so deployments are reproducible.
5. **Deploy the worker** – From `cloudflare/worker/`, run `npm run deploy` (or trigger the
   GitHub Action) to publish proxy updates.
6. **Document the changes** – Update `docs/` or inline READMEs so future contributors know
   the intent and configuration decisions.

## When in doubt

- Refer to [`docs/INTEGRATION.md`](./INTEGRATION.md) for a command-by-command walkthrough
  that proves push access to Hugging Face and Cloudflare.
- Check `Makefile` targets for repeatable commands (`make smoke`, `make smoke-hf`, `make smoke-cf`).
- Use the Python CLI (`python -m aion.cli --help`) to explore new repositories without
  leaving the terminal.

Keeping these touchpoints aligned ensures the Git repository, Hugging Face Spaces, and the
Cloudflare worker stay organised and auditable.
