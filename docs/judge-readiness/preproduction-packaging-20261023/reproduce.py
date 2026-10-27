"""Local Linux Docker proof only: synthetic credentials/wallet, network disabled, no real state mounted."""

import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import time


def docker(*args, input=None):
    result = subprocess.run(["docker", *args], input=input, text=True, capture_output=True)
    if result.returncode:
        error = result.stderr
        for value in globals().get("values",{}).values():
            if value.startswith("synthetic-"): error=error.replace(value,"[REDACTED]")
        raise RuntimeError("Local proof failed: " + error)
    return result.stdout


context = json.loads(docker("context", "inspect"))[0]
host = os.environ.get("DOCKER_HOST", context["Endpoints"]["docker"]["Host"])
if not host.startswith("unix://"):
    raise SystemExit("This proof requires a local Unix Docker socket")
image = "sha256:60c7b9f12562ef1db4210c7a651b9ae6dc5aa9cdbcadd5337aa2e893b3e56ad1"
docker("image", "inspect", image)  # Refuse an absent local image before creating anything.
proof_root = Path(tempfile.mkdtemp(prefix="speccheck-synthetic-", dir="/tmp"))
(proof_root / "mount").mkdir(mode=0o700)
env = proof_root / "synthetic.env"
values = {"SPECCHECK_MODE":"live", "CONTROLLER_STATE_DIR":"/controller",
          "CAMPAIGN_BUDGET_FILE":"/controller/campaign.sqlite3", "BUDGET_USD_PER_DAY":"0"}
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
    api = execute("""
import json,time
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from pathlib import Path
def get(path,body=None):
    data=None if body is None else json.dumps(body).encode()
    with urlopen(Request('http://127.0.0.1:8000'+path,data=data,headers={'Content-Type':'application/json'}),timeout=5) as r:
        return json.load(r)
scores=get('/api/scores');assert scores['mode']=='live'
recorded=scores['run_id'];project=get('/api/project')
tray_ids=sorted(item['id'] for group in project['tray'] for item in group['items'])
watched_ids=sorted(item['id'] for item in project['watched'])
ids=sorted(set(tray_ids+watched_ids))
assert len(tray_ids)==7 and len(watched_ids)==1 and len(ids)==8 and {'s3','s4'}<=set(tray_ids)
assert len(get('/api/specs')['sections'])==2
before=get('/api/health')['today']
assert get('/api/health')['caps']['budget_usd_per_day']==0
explicit=get('/api/runs/replay',{'source_run_id':recorded,'speed':1000})
scan=get('/api/scan',{'ids':ids})
assert scan['replay_of']==recorded and scan['note'].startswith('Replayed from the live run recorded on ')
def results(run_id,expected):
    for attempt in range(100):
        result=get('/api/runs/'+run_id+'/results')
        if result['done']:break
        time.sleep(0.1)
    assert result['done'] and len(result['results'])==expected
    assert all(r['mode']=='live' and r['replayed_from']==recorded for r in result['results'])
    return result
results(explicit['run_id'],10)
tray=results(scan['run_id'],8)
assert sorted(r['case_id'] for r in tray['results'])==ids
try:
    get('/api/scan',{'ids':ids,'refresh_web':True})
    raise AssertionError('Fresh re-check must not replay')
except HTTPError as error: assert error.code==429
assert get('/api/health')['today']==before
proof={'synthetic_accounting_only':True,'real_provider_requests':0,'loopback_only':True,
       'scoreboard_source':recorded,'scoreboard_mode':'live','explicit_replay_count':10,'tray_item_count':7,
       'watched_item_count':1,'full_public_item_count':8,'public_ids':ids,'full_public_replayed':True,'fresh_recheck_at_zero_cap_http':429,
       'synthetic_accounting_unchanged':True,'trial_cap_zero_only_in_temporary_container':True,
       'scan_run_id':scan['run_id'],'explicit_replay_run_id':explicit['run_id']}
Path('/controller/app/capped-api-proof.json').write_text(json.dumps(proof))
print(json.dumps(proof))
""")
    docker("restart",name)
    replay_restart = execute(health_code+"""
from urllib.request import urlopen
from pathlib import Path
proof=json.loads(Path('/controller/app/capped-api-proof.json').read_text())
with urlopen('http://127.0.0.1:8000/api/runs/'+proof['scan_run_id']+'/results',timeout=5) as r: data=json.load(r)
assert data['done'] and len(data['results'])==8
assert all(item['replayed_from']==proof['scoreboard_source'] for item in data['results'])
assert health['today']['total_usd']==0.123 and health['today']['total_credits']==4
print(json.dumps({'replayed_results_persist_across_restart':True,'result_count':8,'synthetic_wallet_unchanged':True}))
""")
    result = {"synthetic_only":True,"before":before,"imported":imported,"restarted":restarted,
              "capped_api":api,"replay_restart":replay_restart}
    (proof_root / "result.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps({"passed":True,"synthetic_only":True,"report":str(proof_root / "result.json")}))
finally:
    if started:
        docker("rm", "--force", name)
