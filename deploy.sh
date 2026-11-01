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

echo "→ Waiting for SnapStart optimization on version ${VERSION}..."
for i in $(seq 1 20); do
  STATUS=$(aws lambda get-function-configuration \
    --function-name "${FUNCTION_NAME}" --qualifier "${VERSION}" \
    --query 'SnapStart.OptimizationStatus' --output text)
  if [ "${STATUS}" = "On" ]; then
    echo "  snapshot ready"
    break
  fi
  echo "  attempt ${i}: ${STATUS}"
  sleep 6
done

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
    -H 'Content-Type: application/json' -d '{}' --max-time 10)
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
  echo "⚠ URL check did not pass — skipping version prune so v${PREV_VERSION} stays available for rollback"
fi

echo "✓ Deployed: ${FUNCTION_NAME} (alias ${ALIAS_NAME} → v${VERSION})"
