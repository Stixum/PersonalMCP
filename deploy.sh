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

echo "→ Installing dependencies (Python 3.13 to match Lambda runtime)..."
${PYTHON_BIN} -m pip install -r requirements.txt -t package/ --quiet \
  --platform manylinux2014_x86_64 --only-binary=:all:

echo "→ Packaging..."
cp server.py auth.py package/
cd package && zip -r ../function.zip . --quiet && cd ..

echo "→ Deploying to Lambda..."
aws lambda update-function-code \
  --function-name "${FUNCTION_NAME}" \
  --zip-file fileb://function.zip \
  --output text \
  --query 'FunctionArn'

echo "✓ Deployed: ${FUNCTION_NAME}"
