# AION

Utilities for interacting with the Hugging Face Hub and Cloudflare REST APIs.

## Features
- **Hugging Face client** for listing models, retrieving model metadata, and downloading files from repositories.
- **Cloudflare client** for listing zones and working with Workers KV namespaces.
- **Command line interface** that wires both clients together for quick manual usage.

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

## Running tests
```bash
python -m pytest
```
