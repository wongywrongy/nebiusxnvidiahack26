"""Authenticated controller cron requests must never forward their token through redirects."""

import ast
from email.message import Message
from io import BytesIO
from pathlib import Path
import textwrap
from urllib.error import HTTPError
from urllib.request import HTTPHandler, HTTPRedirectHandler, Request, build_opener
from urllib.response import addinfourl

import pytest


def test_nightly_request_refuses_cross_origin_redirect_before_forwarding_credentials():
    workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/nightly-recheck.yml").read_text()
    script = textwrap.dedent(workflow.split("python3 - <<'PY'\n", 1)[1].split("          PY", 1)[0])
    tree = ast.parse(script)
    handler = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "NoRedirect")
    namespace = {"HTTPRedirectHandler": HTTPRedirectHandler}
    exec(compile(ast.Module(body=[handler], type_ignores=[]), "nightly-workflow", "exec"), namespace)
    assert any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "build_opener"
               and any(isinstance(arg, ast.Name) and arg.id == "NoRedirect" for arg in node.args) for node in ast.walk(tree))
    requests = []
    class RedirectingServer(HTTPHandler):
        def http_open(self, request):
            requests.append(request)
            headers = Message()
            headers["Location"] = "http://untrusted.test/steal"
            response = addinfourl(BytesIO(b""), headers, request.full_url, code=302)
            response.msg = "Found"
            return response
    client = build_opener(RedirectingServer(), namespace["NoRedirect"])
    with pytest.raises(HTTPError) as error:
        client.open(Request("http://controller.test/api/watch/run", data=b"", headers={"X-Admin-Token": "synthetic-token"}))
    assert error.value.code == 302 and len(requests) == 1
    assert requests[0].host == "controller.test"
