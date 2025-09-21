# AION

Utilities for interacting with the Hugging Face Hub, Hugging Face Spaces, and Cloudflare services.

## Features
- **Hugging Face client** for listing models, retrieving model metadata, and downloading files from repositories.
- **Hugging Face Space client** with CLI helpers tailored to `darkfrostx/neuro-mechanism-backend` and `darkfrostx/ssra-auditor` plus reusable payload templates.
- **Cloudflare client** for listing zones and working with Workers KV namespaces.
- **Command line interface** that wires all clients together for quick manual usage.
- **Cloudflare Worker scaffold** that proxies `/neuro/*` and `/auditor/*` routes to the Spaces, ready for Wrangler deploys.

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

### Hugging Face Spaces
The CLI can now talk directly to Spaces, including the two services you linked (`darkfrostx/neuro-mechanism-backend` and `darkfrostx/ssra-auditor`).

#### Quick shortcuts

```bash
# Health check against the neuro backend (defaults to /health)
python -m aion.cli huggingface space neuro-backend

# Request the mechanism graph manifest with query parameters from the sample template
python -m aion.cli huggingface space neuro-backend \
  --path mechanism_graph_manifest \
  --query receptor=HTR2A --query symptom=apathy

# Invoke the SSRA auditor with the ready-made payload template
python -m aion.cli huggingface space ssra-auditor \
  --payload-file aion/templates/ssra_auditor_payload.json

# Call any other Space endpoint explicitly
python -m aion.cli huggingface space call darkfrostx/ssra-auditor \
  --path audit --payload '{"bundle": {}, "metrics": {}}'
```

The command automatically prints JSON responses. If a Space returns binary content (e.g. a `.gz` archive) the CLI advises redirecting output to a file.

Templates backing the shortcuts live under [`aion/templates/`](aion/templates). `neuro_manifest_query.json` documents a common query to the neuro backend, while `ssra_auditor_payload.json` is a drop-in request body for the auditor's `/audit` endpoint.

### Cloudflare Worker proxy
A scaffolded Worker that mirrors your dashboard configuration lives in [`cloudflare/worker`](cloudflare/worker/). It proxies:

- `https://<worker-domain>/neuro/*` → `https://darkfrostx-neuro-mechanism-backend.hf.space`
- `https://<worker-domain>/auditor/*` → `https://darkfrostx-ssra-auditor.hf.space`

Key files:

- `wrangler.toml` – base configuration and environment variable defaults.
- `src/index.ts` – proxy implementation that forwards headers, query strings, and optionally sets bearer tokens stored as Worker secrets.
- `package.json` / `tsconfig.json` – TypeScript + Wrangler tooling with a Prettier hook.

To deploy:

1. Install Wrangler and authenticate: `npm install -g wrangler && wrangler login`.
2. From `cloudflare/worker/`, configure secrets if the Spaces require tokens:

   ```bash
   wrangler secret put NEURO_SPACE_TOKEN
   wrangler secret put AUDITOR_SPACE_TOKEN
   ```

3. Adjust `wrangler.toml` (e.g. rename the Worker or set routes), then deploy:

   ```bash
   npm install
   npm run deploy
   ```

4. In the Cloudflare dashboard, link the Worker to your repository (screenshot flow you shared) so `wrangler deploy` runs automatically when you push to `main`.

Once published, sending requests to `/neuro/*` or `/auditor/*` on the Worker domain forwards them to the respective Hugging Face Space with preserved methods, bodies, and query parameters.

## Running tests
```bash
python -m pytest
```
