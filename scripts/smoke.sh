#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-all}"
ROOT_DIR="$(pwd)"
WORK_DIR="$ROOT_DIR/.smoke"
mkdir -p "$WORK_DIR"

if [ -f "$ROOT_DIR/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$ROOT_DIR/.env"
  set +a
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
  local space="$1"
  local dir="$2"
  local hf_url="https://huggingface.co/spaces/$space"

  if [ -d "$dir/.git" ]; then
    log "Updating $space ..."
    git -C "$dir" pull --ff-only
  else
    log "Cloning $space ..."
    if command -v huggingface-cli >/dev/null 2>&1; then
      git clone "$hf_url" "$dir"
    else
      require_env HF_USERNAME
      require_env HF_TOKEN
      git clone "https://${HF_USERNAME}:${HF_TOKEN}@huggingface.co/spaces/${space}" "$dir"
    fi
  fi
}

push_smoke_commit() {
  local dir="$1"
  local tag="$2"
  local space="$3"

  log "Creating smoke commit in $(basename "$dir") ..."
  git -C "$dir" config user.email "codex@local"
  git -C "$dir" config user.name  "Codex Smoke"
  printf "codex smoke test %s\n" "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" > "$dir/CODEx_OK.txt"
  git -C "$dir" add CODEx_OK.txt
  git -C "$dir" commit -m "codex: smoke test ${tag}" || warn "No changes to commit (already smoke-tested)"

  if ! git -C "$dir" push 2>/dev/null; then
    require_env HF_USERNAME
    require_env HF_TOKEN
    git -C "$dir" remote set-url origin "https://${HF_USERNAME}:${HF_TOKEN}@huggingface.co/spaces/${space}"
    git -C "$dir" push
  fi
  ok "Pushed smoke commit → Space will rebuild."
}

deploy_worker() {
  local wdir="$1"
  log "Publishing Worker from $wdir ..."
  local out="$WORK_DIR/wrangler.out"
  (cd "$wdir" && npx --yes wrangler publish | tee "$out") || {
    err "Wrangler publish failed"
    exit 1
  }

  local url
  url="$(grep -Eo 'https://[a-zA-Z0-9._/-]+\.workers\.dev' "$out" | tail -1 || true)"
  if [ -z "$url" ] && [ -n "${CF_SCRIPT_NAME:-}" ]; then
    warn "Could not parse workers.dev URL from output. If you know it, set CF_WORKER_URL in .env."
  fi
  echo "$url"
}

await_200() {
  local url="$1"
  local name="$2"
  local max="${SMOKE_MAX_RETRIES:-30}"
  local slp="${SMOKE_SLEEP_SECONDS:-5}"

  log "Probing $name → $url"
  for ((i=1; i<=max; i++)); do
    code="$(curl -s -o /dev/null -w "%{http_code}" "$url" || true)"
    if [ "$code" = "200" ]; then
      ok "$name OK (200)"
      return 0
    fi
    printf " [%d/%d] got %s, retrying in %ss...\n" "$i" "$max" "${code:-err}" "$slp"
    sleep "$slp"
  done
  err "$name FAILED (no 200 after $max tries)"
  return 1
}

run_hf() {
  need git
  need curl
  if command -v huggingface-cli >/dev/null 2>&1; then
    if [ -n "${HF_TOKEN:-}" ]; then
      log "huggingface-cli login (non-interactive)"
      huggingface-cli login --token "$HF_TOKEN" --add-to-git-credential -y || true
    fi
  fi

  require_env HF_NEURO_SPACE
  require_env HF_AUDITOR_SPACE

  local neuro_dir="$WORK_DIR/neuro-mechanism-backend"
  local audit_dir="$WORK_DIR/ssra-auditor"

  clone_or_update_space "$HF_NEURO_SPACE" "$neuro_dir"
  clone_or_update_space "$HF_AUDITOR_SPACE" "$audit_dir"

  push_smoke_commit "$neuro_dir" "neuro" "$HF_NEURO_SPACE"
  push_smoke_commit "$audit_dir" "auditor" "$HF_AUDITOR_SPACE"

  ok "Hugging Face push phase complete."
}

run_cf() {
  need node
  need npm
  need curl
  require_env CF_API_TOKEN
  require_env CF_ACCOUNT_ID
  require_env WORKER_DIR

  local url="${CF_WORKER_URL:-}"
  if [ -z "$url" ]; then
    url="$(deploy_worker "$ROOT_DIR/$WORKER_DIR")"
  fi

  if [ -z "$url" ]; then
    warn "Worker URL unknown. You can still test manually once you know it."
    exit 1
  fi

  local neuro_path="${NEURO_PING:-/__info__}"
  local auditor_path="${AUDITOR_PING:-/__info__}"

  await_200 "${url%/}/neuro${neuro_path}"   "NEURO via Worker"
  await_200 "${url%/}/auditor${auditor_path}" "AUDITOR via Worker"

  ok "Cloudflare proxy checks passed."
}

case "$MODE" in
  hf) run_hf ;;
  cf) run_cf ;;
  all) run_hf; run_cf ;;
  *) err "Usage: $0 [hf|cf|all]"; exit 1 ;;
esac

ok "SMOKE COMPLETE."
