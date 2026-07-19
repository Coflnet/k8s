#!/usr/bin/env bash
# =============================================================================
# copy-k8s-secrets-to-openbao.sh
# =============================================================================
#
# Migrate Kubernetes Secret values into OpenBao KV secrets.
#
# This is the canonical way to move secrets out of k8s Secrets and into
# OpenBao so that Kyverno's `no-env-secretkeyref` policy does not block
# pods that use `env[].valueFrom.secretKeyRef`.
#
# ── Requirements ───────────────────────────────────────────────────────────
#   - Run from WITHIN an OpenBao session (see openbao-local-session.sh)
#   - kubectl access to the source cluster
#   - python3
#
# ── Quick start ────────────────────────────────────────────────────────────
#   Start an OpenBao session:
#     KUBECONFIG=.../talos-rancher-hcloud/kubeconfig \
#       sh openbao/scripts/openbao-local-session.sh -c admin@talos-eu-hcloud
#
#   Then run:
#     ./scripts/copy-k8s-secrets-to-openbao.sh --help
#
# ── Examples ───────────────────────────────────────────────────────────────
#
#   1. Kafka secrets with key remapping (the original use case):
#      ./scripts/copy-k8s-secrets-to-openbao.sh \
#        -n sky -s redpanda -s redpanda-credentials \
#        -m brokers=KAFKA__BROKERS \
#        -m username=KAFKA__USERNAME \
#        -m password=KAFKA__PASSWORD \
#        -p sky/sky-player-state
#
#   2. Copy all keys 1:1 from a single secret:
#      ./scripts/copy-k8s-secrets-to-openbao.sh \
#        -n payment -s payment-secret \
#        -p payment/stripe
#
#   3. Copy with env-var prefix on every key:
#      ./scripts/copy-k8s-secrets-to-openbao.sh \
#        -n sky -s scylla-credentials \
#        -p sky/sky-player-state --prefix SCYLLA__
#
#   4. Dry-run to preview without writing:
#      ./scripts/copy-k8s-secrets-to-openbao.sh \
#        -n sky -s redpanda -p sky/test --dry-run
#
# ── How it works ───────────────────────────────────────────────────────────
#   1. Reads every k8s Secret specified by --secret into memory.
#   2. Applies --key-map (src=dest) and --prefix transformations.
#   3. By default skips PEM certificate / private-key values (--skip-certs).
#   4. Shows the destination keys (values hidden) and asks for confirmation.
#   5. Writes each key to OpenBao with `bao kv patch` (never overwrites
#      existing keys unless the same key name is used).
#
# ── Safety ──────────────────────────────────────────────────────────────────
#   - Values are NEVER printed to stdout.
#   - Values go through temp files, read with $(< file) — no shell escaping.
#   - `bao kv patch` preserves existing keys at the same OpenBao path.
#   - Confirmation prompt (unless --yes).
# =============================================================================

set -uo pipefail

show_help() {
    sed -n '2,/^$/s/^# //p' "$0" | head -70
    cat << 'ENDHELP'

OPTIONS:
  -c, --context CTX       kubectl context   (default: $__OB_CTX from session)
  -n, --namespace NS      k8s namespace     (required)
  -s, --secret NAME       k8s Secret name   (repeatable, at least one)
  -m, --key-map SRC=DEST  Map k8s key SRC → OpenBao key DEST (repeatable)
                          If omitted, all keys are copied with original names.
  -p, --openbao-path P    OpenBao KV path   (required)
  -M, --openbao-mount MT  OpenBao KV mount  (default: kv)
      --prefix PFX        Prefix every OpenBao key with PFX
      --no-skip-certs     Do NOT skip PEM cert/key values
      --dry-run           Show what would be stored, do not write
  -y, --yes               Skip confirmation prompt
  -h, --help              Show this help

ENVIRONMENT:
  __OB_CTX               Default kubectl context (set by OpenBao session)
ENDHELP
    exit 0
}

# ── Parse arguments ────────────────────────────────────────────────────────
CONTEXT="${__OB_CTX:-}"
NAMESPACE=""
SECRETS=()
KEY_MAP_ARGS=()
OB_PATH=""
OB_MOUNT="kv"
PREFIX=""
SKIP_CERTS=true
DRY_RUN=false
YES=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        -c|--context)       CONTEXT="$2"; shift 2 ;;
        -n|--namespace)     NAMESPACE="$2"; shift 2 ;;
        -s|--secret)        SECRETS+=("$2"); shift 2 ;;
        -m|--key-map)       KEY_MAP_ARGS+=("$2"); shift 2 ;;
        -p|--openbao-path)  OB_PATH="$2"; shift 2 ;;
        -M|--openbao-mount) OB_MOUNT="$2"; shift 2 ;;
        --prefix)           PREFIX="$2"; shift 2 ;;
        --no-skip-certs)    SKIP_CERTS=false; shift ;;
        --dry-run)          DRY_RUN=true; shift ;;
        -y|--yes)           YES=true; shift ;;
        -h|--help)          show_help ;;
        *)                  echo "ERROR: Unknown option: $1"; echo "Try --help"; exit 1 ;;
    esac
done

# ── Validate ────────────────────────────────────────────────────────────────
if ! type bao &>/dev/null || [ -z "${__OB_CTX:-}" ]; then
    echo "ERROR: Must run inside an OpenBao session."
    echo "  Start: KUBECONFIG=... sh openbao/scripts/openbao-local-session.sh -c admin@talos-eu-hcloud"
    exit 1
fi
[ -z "$CONTEXT" ]   && { echo "ERROR: --context required"; exit 1; }
[ -z "$NAMESPACE" ] && { echo "ERROR: --namespace required"; exit 1; }
[ ${#SECRETS[@]} -eq 0 ] && { echo "ERROR: at least one --secret required"; exit 1; }
[ -z "$OB_PATH" ]   && { echo "ERROR: --openbao-path required"; exit 1; }

echo "=== Copy k8s secrets → OpenBao ==="
echo "  Context:      $CONTEXT"
echo "  Namespace:    $NAMESPACE"
echo "  Secrets:      ${SECRETS[*]}"
echo "  OpenBao path: $OB_MOUNT/$OB_PATH"
if [ ${#KEY_MAP_ARGS[@]} -gt 0 ]; then
    echo "  Key mappings:"
    for m in "${KEY_MAP_ARGS[@]}"; do echo "    ${m%%=*} → ${m#*=}"; done
fi
[ -n "$PREFIX" ] && echo "  Key prefix:   $PREFIX"
$DRY_RUN && echo "  MODE:         DRY-RUN (no writes)"
echo

# ── Read secrets ────────────────────────────────────────────────────────────
echo "Reading k8s secrets..."

ALL_SECRETS_JSON="[]"
for secret_name in "${SECRETS[@]}"; do
    SECRET_JSON=$(kubectl --context="$CONTEXT" get secret "$secret_name" -n "$NAMESPACE" -o json 2>&1) || {
        echo "ERROR: $SECRET_JSON"; exit 1
    }
    ALL_SECRETS_JSON=$(echo "$ALL_SECRETS_JSON" | python3 -c "
import json, sys
arr = json.load(sys.stdin)
arr.append(json.loads(sys.argv[1]))
print(json.dumps(arr))
" "$SECRET_JSON")
    echo "  ✓ $secret_name"
done

# ── Build key-map JSON ──────────────────────────────────────────────────────
KEY_MAP_JSON="{}"
if [ ${#KEY_MAP_ARGS[@]} -gt 0 ]; then
    KEY_MAP_JSON=$(python3 -c "
import json, sys
m = {}
for arg in sys.argv[1:]:
    k, v = arg.split('=', 1)
    m[k] = v
print(json.dumps(m))
" "${KEY_MAP_ARGS[@]}")
fi

# ── Build payload ───────────────────────────────────────────────────────────
PAYLOAD=$(python3 -c "
import json, sys, base64

secrets = json.loads(sys.argv[1])
key_map = json.loads(sys.argv[2])
prefix = sys.argv[3]
skip_certs = sys.argv[4] == 'True'

data = {}
for secret in secrets:
    for key, encoded in secret.get('data', {}).items():
        val = base64.b64decode(encoded).decode().strip()
        if skip_certs and ('CERTIFICATE' in val or 'PRIVATE KEY' in val):
            continue
        dest = key_map.get(key, key)
        if prefix:
            dest = prefix + dest
        data[dest] = val

print(json.dumps(data, indent=2))
" "$ALL_SECRETS_JSON" "$KEY_MAP_JSON" "$PREFIX" "$SKIP_CERTS" 2>&1)

KEY_COUNT=$(echo "$PAYLOAD" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo 0)

if [ "$KEY_COUNT" -eq 0 ]; then
    echo "ERROR: No keys after filtering. Use --no-skip-certs to include certs."
    exit 1
fi

echo "  → $KEY_COUNT keys prepared"
echo
echo "Keys to store (values hidden):"
echo "$PAYLOAD" | python3 -c "import json,sys; [print(f'  {k:40s} ****') for k in json.load(sys.stdin)]"

# ── Dry-run ─────────────────────────────────────────────────────────────────
if $DRY_RUN; then
    echo; echo "Dry-run complete. No keys written."; exit 0
fi

# ── Confirm ─────────────────────────────────────────────────────────────────
if ! $YES; then
    echo
    read -p "Write these keys to OpenBao $OB_MOUNT/$OB_PATH? [y/N] " -r CONFIRM
    if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
        echo "Aborted."; exit 0
    fi
fi

# ── Write to OpenBao ────────────────────────────────────────────────────────
echo; echo "Writing to OpenBao..."

echo "$PAYLOAD" | python3 -c "
import json, sys, os, tempfile
data = json.load(sys.stdin)
for key, value in data.items():
    fd, path = tempfile.mkstemp(prefix='ob_', suffix='.txt')
    with os.fdopen(fd, 'w') as f:
        f.write(value)
    print(f'{key}\t{path}')
" | while IFS=$'\t' read -r key valfile; do
    value=$(< "$valfile")
    if bao kv patch -mount="$OB_MOUNT" "$OB_PATH" "$key=$value" </dev/null 2>/dev/null; then
        echo "  ✓ $key"
    else
        echo "  ✗ $key FAILED"
    fi
    rm -f "$valfile"
done

echo; echo "✅ Done. Verify with: bao kv get -mount=$OB_MOUNT $OB_PATH"
