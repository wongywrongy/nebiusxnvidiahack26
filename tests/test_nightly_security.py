"""The daily workflow never sends a credential over HTTP: keys reach the job only through MysteryBox."""

from pathlib import Path
import re


def test_nightly_workflow_keeps_credentials_out_of_http_and_job_arguments():
    workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/nightly-recheck.yml").read_text()
    # The only GitHub secret is the service account key, written to a private file for the CLI profile.
    assert re.findall(r"secrets\.(\w+)", workflow) == ["NEBIUS_SA_CREDENTIALS"]
    assert "umask 077" in workflow
    # Provider keys and the admin token come from MysteryBox, never as plain --env values.
    for key in ("NEBIUS_API_KEY", "TAVILY_API_KEY", "ADMIN_TOKEN"):
        assert f'--env-secret "{key}=$SECRET"' in workflow
        assert f"--env {key}" not in workflow and f'--env "{key}' not in workflow
    # Completion is read from the public report: no auth header, and curl never follows a redirect.
    curls = [line for line in workflow.splitlines() if "curl " in line and "install.sh" not in line]
    assert curls and all("-L" not in line and "Token" not in line and "-H" not in line for line in curls)
