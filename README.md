# AION

Utilities for interacting with Hugging Face repositories and Cloudflare services.

> 📚 **New to the project?** Start with [`docs/OVERVIEW.md`](docs/OVERVIEW.md) for a
> high-level map of the repository and how the Git, Hugging Face, and Cloudflare
> pieces align before diving into the step-by-step guides below.

## Features
- **Hugging Face repository client** for listing models, retrieving cross-repository metadata, exploring file trees, and downloading artifacts pinned to revisions.
- **Repository-centric CLI** that surfaces the Hub helpers through commands such as `repo-info`, `repo-files`, and `download`.
- **Cloudflare client** for listing zones and managing Workers KV namespaces from the same toolbox.
- **Cloudflare Worker scaffold** that proxies repository metadata, file listings, and raw file fetches for pre-configured Hugging Face repos.

## Installation
The project only depends on the Python standard library. Clone the repository and run the CLI with Python 3.9+:

```bash
python -m aion.cli --help
```

## Repository-centric workflows
The CLI is opinionated around Hugging Face repositories. Authenticate with an access token via `--token` or the `HF_TOKEN` environment variable, then chain the commands below to inspect, audit, and mirror repository contents.

### 1. Inspect repository metadata
```bash
# Fetch metadata for a Space repository
python -m aion.cli huggingface repo-info \
  darkfrostx/neuro-mechanism-backend \
  --repo-type space

# Inspect a dataset repository
python -m aion.cli huggingface repo-info \
  darkfrostx/ssra-auditor-dataset \
  --repo-type dataset
```

### 2. Explore repository files
```bash
# List everything tracked on main
python -m aion.cli huggingface repo-files \
  darkfrostx/neuro-mechanism-backend \
  --repo-type space \
  --revision main

# Only show direct children within a subdirectory
python -m aion.cli huggingface repo-files \
  darkfrostx/neuro-mechanism-backend \
  --repo-type space \
  --path app \
  --non-recursive
```

### 3. Retrieve revision-pinned artifacts
```bash
# Download a file while staying on a specific revision
python -m aion.cli huggingface download \
  darkfrostx/neuro-mechanism-backend \
  app/main.py \
  --revision main \
  --output ./main.py
```

### 4. Discover related models
```bash
# Use model listings to find additional repos under an author
python -m aion.cli huggingface list-models --author darkfrostx --limit 5
```

All commands print JSON responses with stable formatting so they can feed into scripts or documentation generators. The updated unit tests in `tests/` demonstrate how to mock the client for CI flows.

## Cloudflare
Provide a token via the `--token` flag or the `CLOUDFLARE_API_TOKEN` environment variable.

```bash
# List all accessible zones
python -m aion.cli cloudflare list-zones

# Create a Workers KV namespace (requires account id)
python -m aion.cli cloudflare --account-id <ACCOUNT_ID> create-kv-namespace "My Namespace"

# Discover Worker services (new in this release)
python -m aion.cli cloudflare --account-id <ACCOUNT_ID> list-worker-services

# Inspect a specific service and show its environments
python -m aion.cli cloudflare --account-id <ACCOUNT_ID> worker-service-info ssra-orchestrator --include-environments

# Download the production script for a service
python -m aion.cli cloudflare --account-id <ACCOUNT_ID> worker-service-script ssra-orchestrator --environment production --output cloudflare/ssra-orchestrator.js
```

These helpers make it easy to pull existing Worker services—such as `ssra-orchestrator` or `ssra-gateway`—into the repository. Save the downloaded script anywhere under `cloudflare/` (for example `cloudflare/ssra-orchestrator/index.js`) and pair it with a `wrangler.toml` that matches the remote configuration so everything is versioned alongside the Hugging Face worker.

## Cloudflare Worker for Hugging Face repositories
[`cloudflare/worker`](cloudflare/worker/) contains a Worker that understands Hugging Face repositories and a pinned revision for each route alias. It exposes three behaviours per alias (`/neuro/*` and `/auditor/*` by default):

- `/<alias>/__info__` → returns the repository metadata from the Hub API.
- `/<alias>/__files__` (supports `path` and `recursive` query parameters) → returns the Hub tree listing for the configured revision.
- `/<alias>/<file path>` → streams the raw file content via the Hub `resolve/` endpoint.

### Default configuration
`wrangler.toml` ships with values targeting the repos backing the neuro mechanism backend and SSRA auditor:

- `NEURO_REPO_ID = "darkfrostx/neuro-mechanism-backend"`
- `NEURO_REPO_TYPE = "space"`
- `NEURO_REPO_REVISION = "main"`
- `AUDITOR_REPO_ID = "darkfrostx/ssra-auditor"`
- `AUDITOR_REPO_TYPE = "space"`
- `AUDITOR_REPO_REVISION = "main"`

Add secrets if the repos are private:

```bash
wrangler secret put NEURO_REPO_TOKEN
wrangler secret put AUDITOR_REPO_TOKEN
```

### Deploying
1. Install Wrangler and authenticate: `npm install -g wrangler && wrangler login`.
2. From `cloudflare/worker/`, review `wrangler.toml` and adjust names, route bindings, or the `HF_API_BASE` override if you need to target the Hugging Face staging environment.
3. Install dependencies and deploy:
   ```bash
   npm install
   npm run deploy
   ```
4. (Optional) Link the Worker to your Git repository in the Cloudflare dashboard so `wrangler deploy` runs on pushes to `main`.

Once deployed you can serve metadata, file listings, or raw files directly from the Worker domain while guaranteeing every request stays on the expected repository revision.

## Continuous integration (codex-ci)

The repository ships with `.github/workflows/codex-ci.yml`, a GitHub Actions workflow that mirrors the manual smoke test. To use it:

1. Open **Settings → Secrets and variables → Actions → New repository secret** in GitHub and add the credentials generated for Hugging Face and Cloudflare:
   - `HF_TOKEN` – Hugging Face access token with **Write** permissions.
   - `HF_USERNAME` – your Hugging Face username (used for cloning the Spaces).
   - `CF_API_TOKEN` – Cloudflare API token with the **Workers Scripts:Read, Workers Scripts:Edit** scope.
   - `CF_ACCOUNT_ID` – Cloudflare account identifier visible in the dashboard URL.
   - *(Optional)* `GH_PAT` – a fine-grained Personal Access Token with `contents:read` and `contents:write` if workflow-generated commits should trigger other workflows.
2. Push to `main` or trigger **codex-ci** from the Actions tab.

The workflow:

- Commits a timestamped `.codex-ci-stamp` file (ignored locally via `.gitignore`) to prove the Actions runner can push back to the repository.
- Installs the Hugging Face CLI, authenticates with the provided token, and pushes harmless `CODEx_OK.txt` updates to both Spaces. Each push rebuilds the Space.
- Deploys the Cloudflare Worker from `cloudflare/worker/` via the official `cloudflare/wrangler-action` using `wrangler deploy`.

Extend the final step to curl your `workers.dev` routes once you know the worker URL.

## End-to-end smoke test

Drop-in automation under `scripts/smoke.sh` exercises the full workflow—pushing harmless commits to both Spaces, deploying the Cloudflare Worker, and probing the proxy routes until they return HTTP 200 responses.

1. Copy the environment template and fill in your credentials:
   ```bash
   cp .env.example .env
   # edit .env with your HF/Cloudflare tokens and any custom paths
   ```
2. Run the combined smoke test (or use `make smoke-hf` / `make smoke-cf` to isolate phases):
   ```bash
   make smoke
   ```

The command creates a temporary `.smoke/` workspace for cloning, commits a timestamped `CODEx_OK.txt` file to each Space to trigger rebuilds, publishes the Worker with `npx wrangler publish`, and keeps polling `https://<worker>.workers.dev/neuro/*` and `/auditor/*` until both return `200`.

## Full integration walkthrough

If you need a step-by-step guide (including where to paste tokens and how to confirm write access to each Space before deploying the worker), follow [docs/INTEGRATION.md](docs/INTEGRATION.md). It breaks the workflow into one-minute actions covering:

1. Generating Hugging Face write tokens.
2. Cloning and testing pushes to both Spaces locally.
3. Using the `aion` CLI to explore metadata and file listings.
4. Deploying the Cloudflare worker and adding secrets when required.
5. Troubleshooting the most common pitfalls (`ModuleNotFoundError`, missing Git credentials, or worker auth failures).

## Running tests
```bash
python -m pytest
```
