"""Local Linux Docker proof only: synthetic credentials/wallet, network disabled, no real state mounted."""

import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import time


def docker(*args, input=None):
    return subprocess.run(["docker", *args], input=input, text=True, capture_output=True, check=True).stdout


context = json.loads(docker("context", "inspect"))[0]
host = os.environ.get("DOCKER_HOST", context["Endpoints"]["docker"]["Host"])
if not host.startswith("unix://"):
    raise SystemExit("This proof requires a local Unix Docker socket")
image = "speccheck:controller-startup-local"
docker("image", "inspect", image)  # Refuse an absent local image before creating anything.
proof_root = Path(tempfile.mkdtemp(prefix="speccheck-synthetic-", dir="/tmp"))
(proof_root / "mount").mkdir(mode=0o700)
env = proof_root / "synthetic.env"
values = {"SPECCHECK_MODE":"live", "CONTROLLER_STATE_DIR":"/controller",
          "CAMPAIGN_BUDGET_FILE":"/controller/campaign.sqlite3", "ENABLE_NEBIUS_JOBS":"false"}
values.update({key:"synthetic-"+secrets.token_hex(12) for key in ("NEBIUS_API_KEY","TAVILY_API_KEY","ADMIN_TOKEN")})
env.write_text("\n".join(f"{key}={value}" for key,value in values.items())+"\n")
env.chmod(0o600)
name = "speccheck-synthetic-"+secrets.token_hex(4)
started = False


def execute(code):
    return json.loads(docker("exec", "-i", name, "python", "-", input=code))


health_code = """
import json,time
from urllib.error import URLError
from urllib.request import urlopen
for attempt in range(100):
    try:
        with urlopen('http://127.0.0.1:8000/api/health',timeout=1) as response: health=json.load(response)
        break
    except URLError: time.sleep(0.1)
else: raise RuntimeError('Local API did not start')
"""
try:
    docker("run", "--detach", "--name", name, "--network", "none", "--mount",
           f"type=bind,source={proof_root / 'mount'},target=/controller", "--env-file", str(env), image)
    started = True
    before = execute(health_code+"""
from pathlib import Path
assert health['today']['blocked'] and health['today']['accounting_available'] is False
assert not Path('/controller/campaign.sqlite3').exists()
print(json.dumps({'blocked_without_wallet':True,'wallet_created':False}))
""")
    imported = execute("""
import json
from datetime import datetime,timezone
from pathlib import Path
from api import authority_transfer as transfer
from api.config import settings
from api.controller_startup import prepare
from api.providers import campaign
root=Path('/controller');source=Path('/tmp/synthetic-source.sqlite3');bundle=Path('/tmp/synthetic-transfer.json')
settings.controller_state_dir=None;settings.evidence_dir=None
seed=campaign.Amount(usd_nano=123000000,credits=4)
campaign.initialize(source,seed,{datetime.now(timezone.utc).date().isoformat():seed},
    campaign.Amount(usd_nano=20000000000,credits=2000),campaign.Amount(usd_nano=10000000000,credits=1000))
request=transfer.prepare(root,'synthetic-local-container')
export=transfer.export(source,root/'handoff.json',bundle,request['sha256'])
transfer.receive(bundle,root,export['sha256'])
settings.controller_state_dir=root;prepare()
with campaign.transaction(settings.campaign_budget_file) as state: state_hash=transfer.digest(transfer.encoded(state.model_dump()))
for path in (settings.cache_dir/'synthetic-retained.json',settings.uploads_dir/'synthetic-retained.txt',settings.runs_dir/'synthetic-retained.txt'):
    path.write_bytes(b'synthetic restart marker')
result={'synthetic_only':True,'source_retired':export['source_retired'],'state_sha256':state_hash,
        'authority_sha256':transfer.digest((root/'authority.json').read_bytes())}
(root/'app/synthetic-proof.json').write_text(json.dumps(result))
print(json.dumps(result))
""")
    docker("restart", name)
    restarted = execute(health_code+"""
from pathlib import Path
from api import authority_transfer as transfer
from api.config import settings
from api.controller_startup import prepare
from api.providers import campaign
prepare();root=Path('/controller');before=json.loads((root/'app/synthetic-proof.json').read_text())
with campaign.transaction(settings.campaign_budget_file) as state: state_hash=transfer.digest(transfer.encoded(state.model_dump()))
assert state_hash==before['state_sha256']
assert transfer.digest((root/'authority.json').read_bytes())==before['authority_sha256']
assert not health['today']['blocked'] and health['today']['total_usd']==0.123 and health['today']['total_credits']==4
assert all(path.read_bytes()==b'synthetic restart marker' for path in (
    settings.cache_dir/'synthetic-retained.json',settings.uploads_dir/'synthetic-retained.txt',settings.runs_dir/'synthetic-retained.txt'))
print(json.dumps({'state_preserved':True,'authority_preserved':True,'app_files_preserved':True,'accounting_available':True}))
""")
    result = {"synthetic_only":True,"before":before,"imported":imported,"restarted":restarted}
    (proof_root / "result.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"passed":True,"synthetic_only":True,"report":str(proof_root / "result.json")}))
finally:
    if started:
        docker("rm", "--force", name)
