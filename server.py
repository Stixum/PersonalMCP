"""
Personal MCP Server — Lambda handler

Serves 10 personal context portfolio files from S3 as MCP resources.
Auth is handled by BearerAuthMiddleware (custom ASGI, constant-time compare).
Transport: Streamable HTTP via Mangum (BUFFERED Lambda Function URL).

Environment variables required:
  MCP_BEARER_TOKEN  - bearer token for all MCP clients
  S3_BUCKET         - S3 bucket name containing the 10 .md files
"""

import os
import boto3
from mcp.server.fastmcp import FastMCP

from auth import BearerAuthMiddleware

PORTFOLIO_FILES = [
    "identity",
    "role-and-responsibilities",
    "goals-and-priorities",
    "domain-knowledge",
    "communication-style",
    "preferences-and-constraints",
    "tools-and-systems",
    "team-and-relationships",
    "current-projects",
    "decision-log",
]

# transport_security=None: DNS-rebinding protection is unnecessary for a Lambda
# deployment (no direct localhost exposure); disabling avoids 421 on non-localhost hosts.
from mcp.server.transport_security import TransportSecuritySettings as _TSS

mcp = FastMCP("personal-context", stateless_http=True, transport_security=_TSS(
    enable_dns_rebinding_protection=False,
))
s3_client = boto3.client("s3")


def _register_resource(name: str) -> None:
    """Register one portfolio file as an MCP resource. Factory avoids closure bug."""

    @mcp.resource(f"context://{name}", name=name)
    def _get() -> str:
        bucket = os.environ["S3_BUCKET"]
        response = s3_client.get_object(Bucket=bucket, Key=f"{name}.md")
        return response["Body"].read().decode("utf-8")


for _name in PORTFOLIO_FILES:
    _register_resource(_name)


def create_app():
    """
    Return the ASGI app. Called at module load for the Lambda handler,
    and by tests to get a fresh app instance.
    """
    asgi_app = mcp.streamable_http_app()
    return BearerAuthMiddleware(asgi_app)


# Lambda entry point — Mangum translates Lambda JSON event → ASGI
# Only instantiate at module load when running inside Lambda to avoid
# boto3 credential errors during test imports.
if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
    from mangum import Mangum
    handler = Mangum(create_app(), lifespan="off")
