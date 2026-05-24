#!/usr/bin/env bash
set -euo pipefail

FUNCTION_NAME="personal-mcp-server"
PYTHON_BIN="python3.13"
AWS_PROFILE="${AWS_PROFILE:-AdminAccess-<ACCT-REDACTED>}"
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

echo "→ Deploying to Lambda..."
aws lambda update-function-code \
  --function-name "${FUNCTION_NAME}" \
  --zip-file fileb://function.zip \
  --output text \
  --query 'FunctionArn'

echo "✓ Deployed: ${FUNCTION_NAME}"
