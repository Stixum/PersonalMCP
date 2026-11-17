#!/usr/bin/env bash
set -euo pipefail

FUNCTION_NAME="personal-mcp-server"
ALIAS_NAME="live"
PYTHON_BIN="python3.13"
# AWS_PROFILE must be set (no default — keeps the account-specific profile name
# out of the repo). Operator's actual profile is documented in their private notes.
: "${AWS_PROFILE:?must be set, e.g. AWS_PROFILE=AdminAccess-<acct-id> ./deploy.sh}"
AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"

export AWS_PROFILE AWS_DEFAULT_REGION
export PATH="/opt/homebrew/bin:/opt/homebrew/Cellar/python@3.13/3.13.13_1/bin:/usr/local/bin:$PATH"

# Invoke grant for the Function URL. Since late 2025 a URL with auth type NONE needs
# lambda:InvokeFunction for "*" as well as lambda:InvokeFunctionUrl. That grant must
# carry lambda:InvokedViaFunctionUrl = true: without it any AWS account can call the
# Invoke API directly with an event it wrote, bypassing the URL (finding A1,
# 2026-11-17). Checked on the function and on the alias the URL targets, before
# anything is built or changed.
invoke_grant_state() {
  # Prints "open" (an unconditioned public Invoke grant), "ok" or "missing".
  python3 -c '
import json, sys
try:
    stmts = json.loads(sys.argv[1]).get("Statement", [])
except ValueError:
    stmts = []
def public(s):
    p = s.get("Principal")
    return p == "*" or (isinstance(p, dict) and p.get("AWS") in ("*", ["*"]))
def invokes(s):
    a = s.get("Action")
    a = [a] if isinstance(a, str) else (a or [])
    return any(x in ("lambda:InvokeFunction", "lambda:*", "*") for x in a)
grants = [s for s in stmts if s.get("Effect") == "Allow" and public(s) and invokes(s)]
via_url = lambda s: str(s.get("Condition", {}).get("Bool", {}).get("lambda:InvokedViaFunctionUrl", "")).lower() == "true"
if any(not s.get("Condition") for s in grants):
    print("open")
elif any(via_url(s) for s in grants):
    print("ok")
else:
    print("missing")
' "$1"
}

ensure_invoke_grant() {
  # Args: optional --qualifier <alias>
  local where="${FUNCTION_NAME}${2:+:$2}"
  local policy state
  policy=$(aws lambda get-policy --function-name "${FUNCTION_NAME}" "$@" \
    --query Policy --output text 2>/dev/null || echo '{}')
  state=$(invoke_grant_state "${policy}")
  case "${state}" in
    open)
      echo "✗ ${where} grants lambda:InvokeFunction to \"*\" with no condition." >&2
      echo "  Any AWS account can invoke it directly, bypassing the Function URL. Remove that" >&2
      echo "  statement (aws lambda get-policy shows its Sid, e.g. AllowPublicInvoke):" >&2
      echo "  aws lambda remove-permission --function-name ${FUNCTION_NAME} $* --statement-id <Sid>" >&2
      echo "  Nothing was deployed." >&2
      exit 1 ;;
    missing)
      aws lambda add-permission --function-name "${FUNCTION_NAME}" "$@" \
        --statement-id FunctionURLAllowInvokeAction \
        --action lambda:InvokeFunction --principal '*' \
        --invoked-via-function-url --output text --query Statement >/dev/null
      echo "  added conditioned Invoke grant on ${where}" ;;
    *)
      echo "  ✓ ${where}: Invoke only via the Function URL" ;;
  esac
}

echo "→ Checking Function URL invoke grants..."
ensure_invoke_grant
ensure_invoke_grant --qualifier "${ALIAS_NAME}"

echo "→ Cleaning previous build..."
rm -rf package/ function.zip

echo "→ Installing dependencies (Python 3.13 to match Lambda runtime, arm64/Graviton)..."
${PYTHON_BIN} -m pip install -r requirements.txt -t package/ --quiet \
  --platform manylinux2014_aarch64 --only-binary=:all:

echo "→ Packaging..."
cp server.py auth.py package/
# Strip bytecode caches — they get regenerated on Lambda and only inflate the zip.
find package -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
cd package && zip -r ../function.zip . --quiet && cd ..

echo "→ Updating \$LATEST code..."
aws lambda update-function-code \
  --function-name "${FUNCTION_NAME}" \
  --zip-file fileb://function.zip \
  --output text \
  --query 'FunctionArn'

echo "→ Waiting for function to be Active..."
aws lambda wait function-updated --function-name "${FUNCTION_NAME}"

# SnapStart requires the Function URL to target a published version (via alias).
# Each deploy must publish a new version and re-point the 'live' alias at it,
# otherwise the URL keeps serving the old snapshot.
echo "→ Publishing new version (triggers SnapStart snapshot)..."
VERSION=$(aws lambda publish-version \
  --function-name "${FUNCTION_NAME}" \
  --description "deploy $(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --query 'Version' --output text)
echo "  published version: ${VERSION}"

# Wait on State, not SnapStart.OptimizationStatus: that reads "On" while the version
# is still Pending, and even after it has Failed. Pointing the alias at a version
# that isn't Active takes the URL down (504) for every client.
echo "→ Waiting for version ${VERSION} to be Active (SnapStart snapshot)..."
STATE=""
for i in $(seq 1 60); do
  STATE=$(aws lambda get-function-configuration \
    --function-name "${FUNCTION_NAME}" --qualifier "${VERSION}" \
    --query 'State' --output text)
  if [ "${STATE}" = "Active" ] || [ "${STATE}" = "Failed" ]; then
    break
  fi
  echo "  attempt ${i}: ${STATE}"
  sleep 5
done

if [ "${STATE}" != "Active" ]; then
  REASON=$(aws lambda get-function-configuration \
    --function-name "${FUNCTION_NAME}" --qualifier "${VERSION}" \
    --query 'StateReason' --output text)
  echo "✗ Version ${VERSION} is ${STATE}, not Active: ${REASON}" >&2
  echo "  Alias '${ALIAS_NAME}' was not moved, so the live version is unchanged." >&2
  exit 1
fi
echo "  version ${VERSION} is Active"

# Remember where the alias pointed before the swap — that is the rollback target
# the prune step below keeps.
PREV_VERSION=$(aws lambda get-alias \
  --function-name "${FUNCTION_NAME}" --name "${ALIAS_NAME}" \
  --query 'FunctionVersion' --output text)

echo "→ Pointing alias '${ALIAS_NAME}' at version ${VERSION}..."
aws lambda update-alias \
  --function-name "${FUNCTION_NAME}" \
  --name "${ALIAS_NAME}" \
  --function-version "${VERSION}" \
  --output text --query 'AliasArn'

# Function URL routing to the new alias version takes ~10-15s to propagate.
# Poll the URL with an unauthenticated POST and wait for a 401 (auth middleware
# is up = the new version is serving). 504 = still routing to a dead/initialising
# container.
URL=$(aws lambda get-function-url-config \
  --function-name "${FUNCTION_NAME}" --qualifier "${ALIAS_NAME}" \
  --query 'FunctionUrl' --output text)
echo "→ Verifying URL routing to v${VERSION} (${URL}mcp)..."
LIVE_OK=0
for i in $(seq 1 12); do
  CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST "${URL}mcp" \
    -H 'Content-Type: application/json' -d '{}' --max-time 10) || true
  if [ "${CODE}" = "401" ]; then
    echo "  ✓ live (HTTP 401 from auth middleware)"
    LIVE_OK=1
    break
  fi
  echo "  attempt ${i}: HTTP ${CODE} — waiting 5s..."
  sleep 5
done

# Prune old versions. SnapStart bills a cached snapshot for every published
# version (~$1/mo each at 256 MB), and this script publishes one per deploy, so
# without this they accumulate. Keep the new version, the previous alias target
# (rollback), and anything any alias points at. If publish-version returned the
# existing version (no code change), keep the highest version below it instead.
# Skipped when the URL check above did not pass — the old version is the rollback.
if [ "${LIVE_OK}" = "1" ]; then
  KEEP="${VERSION} ${PREV_VERSION} $(aws lambda list-aliases \
    --function-name "${FUNCTION_NAME}" \
    --query 'Aliases[].FunctionVersion' --output text | tr '\t' ' ')"
  ALL=$(aws lambda list-versions-by-function \
    --function-name "${FUNCTION_NAME}" \
    --query 'Versions[?Version!=`$LATEST`].Version' --output text | tr '\t' '\n' | sort -n)
  if [ "${PREV_VERSION}" = "${VERSION}" ]; then
    KEEP="${KEEP} $(echo "${ALL}" | awk -v v="${VERSION}" '$1 < v' | tail -1)"
  fi
  echo "→ Pruning old versions (keeping: $(echo ${KEEP} | tr ' ' '\n' | sort -nu | tr '\n' ' '))..."
  for v in ${ALL}; do
    case " ${KEEP} " in
      *" ${v} "*) continue ;;
    esac
    aws lambda delete-function --function-name "${FUNCTION_NAME}" --qualifier "${v}" >/dev/null
    echo "  deleted v${v}"
  done
else
  echo "✗ URL check failed: alias '${ALIAS_NAME}' is on v${VERSION}, but the URL never answered 401." >&2
  echo "  No versions were pruned. To roll back to v${PREV_VERSION}:" >&2
  echo "  aws lambda update-alias --function-name ${FUNCTION_NAME} --name ${ALIAS_NAME} --function-version ${PREV_VERSION}" >&2
  exit 1
fi

echo "✓ Deployed: ${FUNCTION_NAME} (alias ${ALIAS_NAME} → v${VERSION})"
