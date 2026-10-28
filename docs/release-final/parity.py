import asyncio, hashlib, json, os, sys
sys.path.insert(0, os.getcwd())
from api import llm
from api.pipeline.runner import Run, execute
calls = []
orig = llm.Router.call
async def call(self, task, schema, messages, ctx=None):
    calls.append(json.dumps([task, messages, {k: v for k, v in (ctx or {}).items() if k != "tools"}], sort_keys=True, default=str))
    return await orig(self, task, schema, messages, ctx)
llm.Router.call = call
cases = ["c01","c02","c03","c04","c05","c06","c07","c08"]
run = asyncio.run(execute(Run(cases, delay_ms=0)))
import collections; by=collections.defaultdict(list)
for c in calls: by[json.loads(c)[0]].append(c)
print(json.dumps({t: [len(v), hashlib.sha256("\n".join(sorted(v)).encode()).hexdigest()[:12]] for t, v in sorted(by.items())}))
