#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-all}"  # hf | cf | all
ROOT_DIR="$(pwd)"
WORK_DIR="$ROOT_DIR/.smoke"
mkdir -p "$WORK_DIR"

# Load .env if present
if [ -f "$ROOT_DIR/.env" ]; then
  # shellcheck disable=SC1091
  set -a; . "$ROOT_DIR/.env"; set +a
fi

log()  { printf "\033[1;36m%s\033[0m\n" "$*"; }
ok()   { printf "\033[1;32m%s\033[0m\n" "$*"; }
warn() { printf "\033[1;33m%s\033[0m\n" "$*"; }
err()  { printf "\033[1;31m%s\033[0m\n" "$*"; }

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    err "Missing dependency: $1"
    exit 1
  fi
}

require_env() {
  local var="$1"
  if [ -z "${!var:-}" ]; then
    err "Missing env var: $var"
    exit 1
  fi
}

clone_or_update_space() {
  local SPACE="$1"   # owner/name
  local DIR="$2"     # local dir
  local HF_URL="https://huggingface.co/spaces/$SPACE"

  if [ -d "$DIR/.git" ]; then
    log "Updating $SPACE ..."
    git -C "$DIR" pull --ff-only
  else
    log "Cloning $SPACE ..."
    # Prefer authenticated remote (works even if private)
    if command -v huggingface-cli >/dev/null 2>&1; then
      git clone "$HF_URL" "$DIR"
    else
      require_env HF_USERNAME
      require_env HF_TOKEN
      # token-in-URL fallback
      git clone "https://${HF_USERNAME}:${HF_TOKEN}@huggingface.co/spaces/${SPACE}" "$DIR"
    fi
  fi
}

push_smoke_commit() {
  local DIR="$1"
  local TAG="$2"
  log "Creating smoke commit in $(basename "$DIR") ..."
  git -C "$DIR" config user.email "codex@local"
  git -C "$DIR" config user.name  "Codex Smoke"
  echo "codex smoke test $(date -u +'%Y-%m-%dT%H:%M:%SZ')" > "$DIR/CODEx_OK.txt"
  git -C "$DIR" add CODEx_OK.txt
  git -C "$DIR" commit -m "codex: smoke test ${TAG}" || warn "No changes to commit (already smoke-tested)"
  # Ensure remote is authenticated if CLI login not used
  if ! git -C "$DIR" push 2>/dev/null; then
    require_env HF_USERNAME
    require_env HF_TOKEN
    local current_remote
    current_remote="$(git -C "$DIR" remote get-url origin)"
    if [[ "$current_remote" != *"@huggingface.co"* ]]; then
      git -C "$DIR" remote set-url origin "https://${HF_USERNAME}:${HF_TOKEN}@huggingface.co/${current_remote#https://}"
    fi
    git -C "$DIR" push
  fi
  ok "Pushed smoke commit → Space will rebuild."
}

deploy_worker() {
  local WDIR="$1"
  log "Publishing Worker from $WDIR ..."
  # Keep output to a file so we can parse URL
  local OUT="$WORK_DIR/wrangler.out"
  (cd "$WDIR" && npx --yes wrangler publish | tee "$OUT") || { err "Wrangler publish failed"; exit 1; }

  # Try to grab workers.dev URL from output
  local URL
  URL="$(grep -Eo 'https://[a-zA-Z0-9._/-]+\.workers\.dev' "$OUT" | tail -1 || true)"
  if [ -z "$URL" ] && [ -n "${CF_SCRIPT_NAME:-}" ]; then
    # Fallback if name is known and account subdomain is unmapped in output:
    # Users can also export CF_WORKER_URL to skip parsing.
    warn "Could not parse workers.dev URL from output. If you know it, set CF_WORKER_URL in .env."
  fi
  echo "$URL"
}

await_200() {
  local URL="$1"
  local NAME="$2"
  local MAX="${SMOKE_MAX_RETRIES:-30}"
  local SLP="${SMOKE_SLEEP_SECONDS:-5}"

  log "Probing $NAME → $URL"
  for ((i=1; i<=MAX; i++)); do
    code="$(curl -s -o /dev/null -w "%{http_code}" "$URL" || true)"
    if [ "$code" = "200" ]; then
      ok "$NAME OK (200)"
      return 0
    fi
    printf " [%d/%d] got %s, retrying in %ss...\n" "$i" "$MAX" "${code:-err}" "$SLP"
    sleep "$SLP"
  done
  err "$NAME FAILED (no 200 after $MAX tries)"
  return 1
}

run_hf() {
  need git
  need curl
  # Optional but nice
  if command -v huggingface-cli >/dev/null 2>&1; then
    if [ -n "${HF_TOKEN:-}" ]; then
      log "huggingface-cli login (non-interactive)"
      huggingface-cli login --token "$HF_TOKEN" --add-to-git-credential -y || true
    fi
  fi

  require_env HF_NEURO_SPACE
  require_env HF_AUDITOR_SPACE

  local NEURO_DIR="$WORK_DIR/neuro-mechanism-backend"
  local AUDIT_DIR="$WORK_DIR/ssra-auditor"

  clone_or_update_space "$HF_NEURO_SPACE" "$NEURO_DIR"
  clone_or_update_space "$HF_AUDITOR_SPACE" "$AUDIT_DIR"

  push_smoke_commit "$NEURO_DIR"   "neuro"
  push_smoke_commit "$AUDIT_DIR"   "auditor"

  ok "Hugging Face push phase complete."
}

run_cf() {
  need node
  need npm
  need curl
  # wrangler is brought via npx; ensure it can auth by token
  require_env CF_API_TOKEN
  require_env CF_ACCOUNT_ID
  require_env WORKER_DIR

  local URL="${CF_WORKER_URL:-}"
  URL="${URL:-$(deploy_worker "$ROOT_DIR/$WORKER_DIR")}"

  if [ -z "$URL" ]; then
    warn "Worker URL unknown. You can still test manually once you know it."
    exit 1
  fi

  local NEURO_PATH="${NEURO_PING:-/ping}"
  local AUDIT_PATH="${AUDITOR_PING:-/ping}"

  await_200 "${URL%/}/neuro${NEURO_PATH}"   "NEURO via Worker"
  await_200 "${URL%/}/auditor${AUDIT_PATH}" "AUDITOR via Worker"

  ok "Cloudflare proxy checks passed."
}

case "$MODE" in
  hf) run_hf ;;
  cf) run_cf ;;
  all) run_hf; run_cf ;;
  *) err "Usage: $0 [hf|cf|all]"; exit 1 ;;
esac

ok "SMOKE COMPLETE."
