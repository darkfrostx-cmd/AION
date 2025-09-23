# Integrating Hugging Face Spaces with the Cloudflare Worker

The repository contains everything you need to connect the `darkfrostx/neuro-mechanism-backend` and `darkfrostx/ssra-auditor` Hugging Face Spaces to the Cloudflare worker that proxies their metadata, file listings, and raw file contents. The steps below walk through the full workflow at a "one minute per step" pace so you can follow along without prior experience.

---

## 0. Prerequisites checklist

| Tool | Why you need it | How to install |
| --- | --- | --- |
| Python 3.9+ | Runs the `aion` command-line helpers | <https://www.python.org/downloads/> |
| Git + Git LFS | Pulls and pushes Space repositories | <https://git-scm.com/download/win> (select the default Git LFS option during setup) |
| Node.js 18+ | Provides the runtime for Cloudflare's Wrangler CLI | <https://nodejs.org/en> (LTS or current) |
| Wrangler CLI | Deploys the worker | `npm install -g wrangler` |

> **Tip:** After installation, reopen PowerShell or your terminal so the new commands (`git`, `node`, `wrangler`) are available.

---

## 1. Prepare Hugging Face access

1. Log in at <https://huggingface.co/settings/tokens>.
2. Click **New token**, name it (for example, `worker-integration`), choose the **Write** role, and click **Create**.
3. Copy the token and keep it safe – you will paste it when Git or the CLI asks for a password.
4. Optional: store it in an environment variable while working in a terminal session:
   ```powershell
   setx HF_TOKEN "hf_xxx"  # on Windows (opens a new session to take effect)
   export HF_TOKEN=hf_xxx   # on macOS/Linux
   ```

---

## 2. Clone the Spaces locally (read/write access test)

Perform the steps below for **each** Space (`neuro-mechanism-backend` and `ssra-auditor`).

1. Create a folder to hold the clones and move into it:
   ```powershell
   mkdir "$HOME\Documents\hf-spaces"
   cd "$HOME\Documents\hf-spaces"
   ```
2. Clone the Space:
   ```powershell
   git clone https://huggingface.co/spaces/darkfrostx/neuro-mechanism-backend
   ```
   *(Repeat with `darkfrostx/ssra-auditor`)*
3. Open the folder in File Explorer if you prefer a GUI:
   ```powershell
   Start-Process "$HOME\Documents\hf-spaces"
   ```
4. Make a small reversible change (for example, append `# integration test` to `README.md`).
5. Back in the terminal, commit and push the change to confirm write access:
   ```powershell
   git status
   git add .
   git commit -m "Integration test"
   git push
   ```
   When prompted:
   * Username → your Hugging Face username (`darkfrostx`).
   * Password → the write token you generated.
6. Undo the test change if you do not want to keep it:
   ```powershell
   git revert HEAD
   git push
   ```

---

## 3. Explore the Spaces using the AION CLI (read-only)

1. Open a terminal in the project root (the folder with `README.md`, `aion/`, and `cloudflare/`).
2. View the CLI help to confirm it is available:
   ```powershell
   python -m aion.cli --help
   ```
3. Inspect metadata for each Space:
   ```powershell
   python -m aion.cli huggingface repo-info darkfrostx/neuro-mechanism-backend --repo-type space --token hf_xxx
   python -m aion.cli huggingface repo-info darkfrostx/ssra-auditor --repo-type space --token hf_xxx
   ```
4. List the tracked files on `main` (read-only):
   ```powershell
   python -m aion.cli huggingface repo-files darkfrostx/neuro-mechanism-backend --repo-type space --revision main --token hf_xxx
   python -m aion.cli huggingface repo-files darkfrostx/ssra-auditor --repo-type space --revision main --token hf_xxx
   ```
5. Download a specific file if you need to review it locally (optional):
   ```powershell
   python -m aion.cli huggingface download darkfrostx/neuro-mechanism-backend README.md --repo-type space --revision main --output README.md --token hf_xxx
   ```

---

## 4. Deploy the Cloudflare worker

1. Authenticate Wrangler:
   ```powershell
   wrangler login
   ```
   Approve the browser prompt.
2. Move into the worker folder and install dependencies:
   ```powershell
   cd cloudflare/worker
   npm install
   ```
3. (Optional) If you ever make a Space private, add the matching secret so the worker forwards the token automatically:
   ```powershell
   wrangler secret put NEURO_REPO_TOKEN
   wrangler secret put AUDITOR_REPO_TOKEN
   ```
   Answer **yes** when Wrangler asks to create/use `aion-neuro-auditor-proxy`.
4. Deploy:
   ```powershell
   npm run deploy
   ```
   Wrangler prints a `workers.dev` URL such as `https://aion-neuro-auditor-proxy.<name>.workers.dev`.
5. Verify the routes:
   * `https://<worker-domain>/neuro/__info__`
   * `https://<worker-domain>/neuro/__files__?recursive=0`
   * `https://<worker-domain>/auditor/__info__`
   * `https://<worker-domain>/auditor/__files__?recursive=0`

---

## 5. Keep everything in sync

* Edit your Spaces locally, push with `git`, and redeploy the worker with `npm run deploy` whenever you change the proxy logic.
* Use `wrangler tail` while exercising the worker to watch live logs:
  ```powershell
  wrangler tail --env production
  ```
* Rotate Hugging Face tokens by updating the secrets (`wrangler secret put ...`) and redeploying.

---

## Troubleshooting quick reference

| Symptom | Fix |
| --- | --- |
| `python -m aion.cli …` reports `ModuleNotFoundError` | Change directory to the project root where the `aion/` package lives before running the command. |
| `git push` prompts for a password | Always use the Hugging Face **write token** instead of your account password (password-based pushes are disabled). |
| Wrangler asks to create a worker during `secret put` | Answer **yes** — it links the secret to the `aion-neuro-auditor-proxy` worker defined in `wrangler.toml`. |
| Worker returns 403 for a private Space | Store the corresponding `*_REPO_TOKEN` secret so requests include the token. |

By following these steps you confirm end-to-end control: edit both Hugging Face Spaces, deploy the worker proxy, and test the integrated routes without needing any additional repositories or hidden automation.
