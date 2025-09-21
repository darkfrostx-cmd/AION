# AION

Utilities for interacting with the Hugging Face Hub and Cloudflare services.

## Features
- **Hugging Face client** for listing models, retrieving model metadata, and downloading files from repositories.
- **Repository helpers** for surfacing metadata and file listings from any Hugging Face project, including `darkfrostx/neuro-mechanism-backend` and `darkfrostx/ssra-auditor`.
- **Cloudflare client** for listing zones and working with Workers KV namespaces.
- **Command line interface** that wires all clients together for quick manual usage.
- **Cloudflare Worker scaffold** that proxies `/neuro/*` and `/auditor/*` routes to the Hugging Face repositories, ready for Wrangler deploys.

## Installation
The project only depends on the Python standard library. Clone the repository and run the CLI with Python 3.9+:

```bash
python -m aion.cli --help
```

## Usage
### Hugging Face
Provide a token via the `--token` flag or the `HF_TOKEN` environment variable.

```bash
# List models from an author
python -m aion.cli huggingface list-models --author my-username

# Download a file from a repo
python -m aion.cli huggingface download my-username/my-model config.json --output ./config.json

# Fetch repository metadata
python -m aion.cli huggingface repo-info darkfrostx/neuro-mechanism-backend

# List files in a specific revision
python -m aion.cli huggingface repo-files darkfrostx/ssra-auditor --revision main
```

### Cloudflare
Provide a token via the `--token` flag or the `CLOUDFLARE_API_TOKEN` environment variable.

```bash
# List all accessible zones
python -m aion.cli cloudflare list-zones

# Create a Workers KV namespace (requires account id)
python -m aion.cli cloudflare --account-id <ACCOUNT_ID> create-kv-namespace "My Namespace"
```

The CLI surfaces API errors with readable messages. See the unit tests in `tests/` for examples of how to mock the clients in automated workflows.

### Cloudflare Worker proxy
A scaffolded Worker that mirrors your dashboard configuration lives in [`cloudflare/worker`](cloudflare/worker/). It proxies:

- `https://<worker-domain>/neuro/*` → raw files from the `darkfrostx/neuro-mechanism-backend` repository
- `https://<worker-domain>/auditor/*` → raw files from the `darkfrostx/ssra-auditor` repository

Key files:

- `wrangler.toml` – base configuration and environment variable defaults.
- `src/index.ts` – proxy implementation that forwards headers to `https://huggingface.co/<repo>/resolve/<revision>/<path>`.
- `package.json` / `tsconfig.json` – TypeScript + Wrangler tooling with a Prettier hook.

To deploy:

1. Install Wrangler and authenticate: `npm install -g wrangler && wrangler login`.
2. From `cloudflare/worker/`, configure secrets if the repositories require tokens:

   ```bash
   wrangler secret put HF_API_TOKEN
   wrangler secret put NEURO_REPO_TOKEN  # optional override per repository
   wrangler secret put AUDITOR_REPO_TOKEN
   ```

3. Adjust `wrangler.toml` (e.g. rename the Worker, configure revisions, or set routes), then deploy:

   ```bash
   npm install
   npm run deploy
   ```

4. In the Cloudflare dashboard, link the Worker to your Git repository (screenshot flow you shared) so `wrangler deploy` runs automatically when you push to `main`.

Once published, sending requests to `/neuro/<path>` or `/auditor/<path>` on the Worker domain streams files straight from the configured Hugging Face repository revision. Provide `?revision=<branch>` to override the default per request.

## Running tests
```bash
python -m pytest
```
