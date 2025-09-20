# AION

Toolkit code for integrating Hugging Face assets and Cloudflare Workers.

## Features
- **Hugging Face Hub client** – list models, fetch metadata, and download files without third-party dependencies.
- **Hugging Face Space client** – call custom REST endpoints exposed by Spaces such as `darkfrostx/neuro-mechanism-backend` and `darkfrostx/ssra-auditor`.
- **Cloudflare client** – manage zones and Workers KV namespaces from scripts or CI jobs.
- **Space proxy Worker** – Cloudflare Worker project that forwards `/neuro/*` and `/auditor/*` requests to the corresponding Hugging Face Spaces, making it easy to expose them under your domain.
- **Command line interface** that ties all of the above together for local experiments and automation.

## Installation
The Python components only depend on the standard library. Clone the repository and run the CLI with Python 3.9+:

```bash
python -m aion.cli --help
```

For the Cloudflare Worker, install dependencies inside `workers/space-proxy/`:

```bash
cd workers/space-proxy
npm install
```

## CLI usage
### Hugging Face Hub
Provide a token via the `--token` flag or the `HF_TOKEN` environment variable.

```bash
# List models from an author
python -m aion.cli huggingface list-models --author darkfrostx

# Download a file from a repo
python -m aion.cli huggingface download darkfrostx/some-model config.json --output ./config.json
```

### Hugging Face Spaces
The CLI can talk directly to the two Spaces that need to be integrated with Cloudflare. Use `space-template` to view a ready-made request and then `space-get` / `space-post` to execute it.

```bash
# Inspect the suggested parameters/payload for each space
python -m aion.cli huggingface space-template darkfrostx/neuro-mechanism-backend
python -m aion.cli huggingface space-template darkfrostx/ssra-auditor

# Call the neuro-mechanism backend (GET)
python -m aion.cli huggingface space-get darkfrostx/neuro-mechanism-backend \
  /mechanism_graph_manifest --param receptor=HTR2A --param symptom=apathy

# A ready-to-use payload lives at `examples/auditor-request.json`.

# Call the SSRA auditor (POST)
python -m aion.cli huggingface space-post darkfrostx/ssra-auditor /audit \
  --payload-file examples/auditor-request.json
```

### Cloudflare REST API helpers
Provide a token via the `--token` flag or the `CLOUDFLARE_API_TOKEN` environment variable.

```bash
# List all accessible zones
python -m aion.cli cloudflare list-zones

# Create a Workers KV namespace (requires account id)
python -m aion.cli cloudflare --account-id <ACCOUNT_ID> create-kv-namespace "My Namespace"
```

## Cloudflare Worker deployment
The `workers/space-proxy` project contains a Wrangler configuration ready for the setup shown in the Cloudflare dashboard screenshot.

1. From the repository root run `cd workers/space-proxy && npm install`.
2. Authenticate Wrangler with `npx wrangler login` (or use `wrangler config --api-token ...`).
3. Configure secrets used by the Worker:
   ```bash
   npx wrangler secret put HF_TOKEN           # optional – only if the Spaces require auth
   npx wrangler secret put NEURO_SPACE        # defaults to darkfrostx/neuro-mechanism-backend
   npx wrangler secret put AUDITOR_SPACE      # defaults to darkfrostx/ssra-auditor
   ```
4. Deploy with `npx wrangler deploy`.

Requests that hit the Worker under `/neuro/*` are proxied to the neuro-mechanism backend Space, while `/auditor/*` flows to the SSRA auditor. The worker adds permissive CORS headers so that static sites or other clients can call these endpoints directly.

You can also enable Pull Request previews in the Cloudflare dashboard by pointing the build command at `npx wrangler deploy` and setting `npx wrangler versions upload` for previews (as in the screenshot provided by the user).

## Running tests
```bash
python -m pytest
```
