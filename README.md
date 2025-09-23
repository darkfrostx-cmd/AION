# AION

Utilities for interacting with Hugging Face repositories and Cloudflare services.

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

## Running tests
```bash
python -m pytest
```
