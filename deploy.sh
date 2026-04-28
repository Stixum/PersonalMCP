#!/usr/bin/env bash
set -euo pipefail

FUNCTION_NAME="personal-mcp-server"
PYTHON_BIN="python3.13"

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
