"""
Runs deploy.sh against fake aws/curl/pip/zip executables.

Safety: deploy.sh prepends Homebrew to PATH, which would put the real aws CLI ahead
of the fake one. The harness strips that line from a temp copy and runs with a PATH
that has no real aws or curl, and asserts both before executing anything.
"""
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

FAKE_AWS = r"""#!/bin/bash
echo "aws $*" >> "$CALL_LOG"
case "$*" in
  *"get-function-configuration"*"StateReason"*)
    echo "$FAKE_STATE_REASON" ;;
  *"get-function-configuration"*"State"*)
    # Walks FAKE_STATES one read at a time, then repeats the last entry.
    n=$(cat "$STATE_COUNTER" 2>/dev/null || echo 0)
    echo $((n + 1)) > "$STATE_COUNTER"
    IFS=',' read -ra states <<< "$FAKE_STATES"
    last=$(( ${#states[@]} - 1 ))
    [ "$n" -gt "$last" ] && n=$last
    echo "${states[$n]}" ;;
  *"publish-version"*) echo "7" ;;
  *"get-alias"*) echo "6" ;;
  *"get-function-url-config"*) echo "https://fake.invalid/" ;;
  *"list-aliases"*) echo "7" ;;
  *"list-versions-by-function"*) printf '4\t5\t6\t7\n' ;;
  *) echo "ok" ;;
esac
"""

FAKE_CURL = r"""#!/bin/bash
echo "curl $*" >> "$CALL_LOG"
if [ "$FAKE_HTTP" = "timeout" ]; then
  # Real curl prints the -w output and exits 28 when --max-time expires.
  printf '000'
  exit 28
fi
printf '%s' "$FAKE_HTTP"
"""

FAKE_PYTHON = '#!/bin/bash\nmkdir -p package\n'
FAKE_ZIP = '#!/bin/bash\ntouch ../function.zip\n'
FAKE_SLEEP = '#!/bin/bash\nexit 0\n'


def _write_executable(path, content):
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


@pytest.fixture
def run_deploy(tmp_path):
    """Returns run(states, http) -> (CompletedProcess, list of logged calls)."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, content in {
        "aws": FAKE_AWS,
        "curl": FAKE_CURL,
        "python3.13": FAKE_PYTHON,
        "zip": FAKE_ZIP,
        "sleep": FAKE_SLEEP,
    }.items():
        _write_executable(bin_dir / name, content)

    work = tmp_path / "work"
    work.mkdir()
    (work / "server.py").write_text("")
    (work / "auth.py").write_text("")
    (work / "requirements.txt").write_text("")

    lines = (REPO / "deploy.sh").read_text().splitlines(keepends=True)
    kept = [line for line in lines if not line.startswith("export PATH=")]
    assert len(lines) - len(kept) == 1, "expected to strip exactly one PATH export"
    script = work / "deploy.sh"
    script.write_text("".join(kept))

    path = f"{bin_dir}:/usr/bin:/bin"
    assert shutil.which("aws", path=path) == str(bin_dir / "aws")
    assert shutil.which("curl", path=path) == str(bin_dir / "curl")

    call_log = tmp_path / "calls.log"

    def run(states, http="401", reason="import failed: no module named x"):
        env = {
            "PATH": path,
            "AWS_PROFILE": "fake-test-profile",
            "AWS_CONFIG_FILE": os.devnull,
            "AWS_SHARED_CREDENTIALS_FILE": os.devnull,
            "CALL_LOG": str(call_log),
            "STATE_COUNTER": str(tmp_path / "state_counter"),
            "FAKE_STATES": ",".join(states),
            "FAKE_STATE_REASON": reason,
            "FAKE_HTTP": http,
        }
        result = subprocess.run(
            ["/bin/bash", str(script)],
            cwd=work,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        calls = call_log.read_text().splitlines() if call_log.exists() else []
        return result, calls

    return run


def _index_of(calls, needle):
    return next(i for i, call in enumerate(calls) if needle in call)


def _last_index_of(calls, needle):
    return max(i for i, call in enumerate(calls) if needle in call)


def _called(calls, needle):
    return any(needle in call for call in calls)


def test_alias_moves_only_after_version_is_active(run_deploy):
    result, calls = run_deploy(["Pending", "Pending", "Active"])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "✓ Deployed" in result.stdout
    state_reads = [c for c in calls if "get-function-configuration" in c and "State" in c]
    assert len(state_reads) == 3
    assert all("--qualifier 7" in c for c in state_reads)
    assert _last_index_of(calls, "get-function-configuration") < _index_of(calls, "update-alias")


def test_verified_deploy_prunes_all_but_new_and_rollback(run_deploy):
    _, calls = run_deploy(["Active"])
    deleted = [c.split("--qualifier ")[1] for c in calls if "delete-function" in c]
    assert deleted == ["4", "5"]


def test_failed_version_stops_before_alias_and_reports_reason(run_deploy):
    result, calls = run_deploy(["Pending", "Failed"], reason="No module named mcp.server.fastmcp")
    assert result.returncode != 0
    assert not _called(calls, "update-alias")
    assert not _called(calls, "delete-function")
    assert "No module named mcp.server.fastmcp" in result.stderr
    assert "✓ Deployed" not in result.stdout


def test_version_stuck_pending_stops_before_alias(run_deploy):
    result, calls = run_deploy(["Pending"])
    assert result.returncode != 0
    assert not _called(calls, "update-alias")
    assert "✓ Deployed" not in result.stdout
    assert "Pending" in result.stderr


@pytest.mark.parametrize("http", ["504", "timeout"])
def test_failed_url_check_exits_nonzero_and_gives_rollback(run_deploy, http):
    """A curl timeout must count as a failed attempt, not abort silently under set -e."""
    result, calls = run_deploy(["Active"], http=http)
    assert result.returncode != 0
    assert "✓ Deployed" not in result.stdout
    assert not _called(calls, "delete-function")
    assert len([c for c in calls if c.startswith("curl ")]) == 12
    assert "--function-version 6" in result.stderr


def test_published_version_state_is_read_with_expected_query(run_deploy):
    """Guards the fake against drift: the script must ask for State, not OptimizationStatus."""
    _, calls = run_deploy(["Active"])
    assert not _called(calls, "OptimizationStatus")
