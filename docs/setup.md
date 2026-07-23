# Setup

Standing up your own instance. Assumes an AWS account, the AWS CLI configured, and
`python3.13` on PATH (`brew install python@3.13` — the version must match the Lambda
runtime, so `python3` is not good enough).

---

## 1. Write your context

```bash
cp -R placeholder.example/* placeholder/    # placeholder/ is gitignored
$EDITOR placeholder/identity.md
```

You do not need all ten files filled in to start. `identity`, `communication-style`, and
`current-projects` are enough to be useful on day one; the rules files fill themselves in
as you work. See [context-model.md](context-model.md) for what belongs where.

---

## 2. Create the bucket

```bash
aws s3 mb s3://personal-context-portfolio-<your-account-id>
```

Turn on versioning before you write anything. `update_context` is an unversioned full
overwrite — versioning is your only undo:

```bash
aws s3api put-bucket-versioning \
  --bucket personal-context-portfolio-<your-account-id> \
  --versioning-configuration Status=Enabled
```

Keep public access blocked (the default). The Lambda reads via its execution role, not
via public URLs.

```bash
aws s3 sync placeholder/ s3://personal-context-portfolio-<your-account-id>/
```

**This is the only time a blind `sync` is safe.** After the server is live, clients write
directly to S3 and your local copy is a snapshot that drifts. See [Keeping local copies in
sync](#keeping-local-copies-in-sync).

---

## 3. Create the Lambda

- **Runtime:** Python 3.13
- **Architecture:** arm64
- **Handler:** `server.handler`
- **Memory:** 512 MB is comfortable; it's a network-bound workload
- **Timeout:** 30s
- **SnapStart:** `PublishedVersions`
- **Execution role:** `s3:GetObject` and `s3:PutObject` on `arn:aws:s3:::<bucket>/*`, plus
  basic CloudWatch Logs

Environment variables:

| Var | Value |
|-----|-------|
| `MCP_BEARER_TOKEN` | A long random string — `openssl rand -hex 32` |
| `S3_BUCKET` | Your bucket name |

The token lives here and nowhere else. Not in the repo, not in a dotfile, not in a
committed client config.

---

## 4. Create the alias and Function URL

SnapStart requires the URL to target a published version, which means an alias:

```bash
aws lambda publish-version --function-name personal-mcp-server
aws lambda create-alias --function-name personal-mcp-server \
  --name live --function-version 1
```

Create the Function URL **against the alias**, with auth type `NONE` (the bearer
middleware is the auth boundary) and invoke mode **BUFFERED** — `RESPONSE_STREAM` does not
work with the Mangum/ASGI path here.

```bash
aws lambda create-function-url-config \
  --function-name personal-mcp-server --qualifier live \
  --auth-type NONE --invoke-mode BUFFERED
```

---

## 5. Deploy

```bash
./deploy.sh
```

Requires `AWS_PROFILE` to be set. The script builds an arm64 zip, updates `$LATEST`,
publishes a version, waits for the SnapStart snapshot, re-points `live`, and then polls
the URL until it returns 401 — proof the new version is serving.

**Never run `aws lambda update-function-code` on its own.** It changes `$LATEST` only; the
URL targets the alias, so the deploy appears to succeed while the old version keeps
serving.

---

## 6. Point clients at it

Claude Desktop / Claude Code, via `mcp-remote`:

```json
{
  "mcpServers": {
    "personal-context": {
      "command": "npx",
      "args": [
        "-y", "mcp-remote",
        "https://<your-function-url>/mcp",
        "--header", "Authorization: Bearer ${MCP_TOKEN}"
      ],
      "env": { "MCP_TOKEN": "<your-token>" }
    }
  }
}
```

Smoke test without a client:

```bash
curl -sX POST "https://<your-function-url>/mcp" \
  -H "Authorization: Bearer $MCP_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

A 401 means the token is wrong. A 405 means you sent a GET.

---

## Keeping local copies in sync

Once clients can write, **S3 leads and any local copy trails.** The write tools update S3
directly; nothing pushes back down to your machine.

Pull before you edit locally, and never sync up without checking what you'd overwrite:

```bash
# safe: pull S3 down
aws s3 sync s3://personal-context-portfolio-<your-account-id>/ placeholder/

# check first: what would a push actually change?
aws s3 sync placeholder/ s3://personal-context-portfolio-<your-account-id>/ --dryrun
```

A stale local directory pushed up with `sync` silently reverts every edit made through the
MCP tools since your last pull. With versioning on it's recoverable; without it, it isn't.

---

## Updating context after setup

Three paths, in descending order of preference:

1. **`update_subsection`** from any MCP client — rewrites one heading in place.
2. **`update_context`** — full-file replace, for restructuring.
3. **`aws s3 cp`** for a single file, after pulling current content down.

No redeploy is needed for any of them. Redeploy only when `server.py` or `auth.py`
changes.
