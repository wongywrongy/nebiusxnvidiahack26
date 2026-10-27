# Published networking prices — 2026-10-23

An unauthenticated public `GET https://nebius.com/prices` at 10:57:20 UTC returned HTTP 200.
The [recorded response hash and short quotations](source.json) verify that the current advertised
networking ingress/egress and public-IP rates are free. The same page excludes applicable taxes.
This closes the public-rate lookup; it does not establish private account pricing, a tax amount,
future rates, quotas, a bill or deployment approval.

The worksheet records these separately from Standard Object Storage egress, whose existing
$0.015/GiB rate remains unchanged. The proposed initial controller trial uses a private filesystem,
so that bucket-egress charge is not part of it. Resource forecast rows remain unchanged: adding a
zero published network charge changes no subtotal. Actual account price/tax bounds, cloud/provider
grant terms and owner approval remain pending; no spending allowance was approved.

The response body stays in ignored `.cache/research/public-network-pricing-20261023/prices.html`.
No provider credential, paid provider request or cloud mutation was used. The campaign remains at
**$3.36648982 / 490 settled**, plus **one credit of unknown usage held**; paid admission stays blocked.

To reproduce without an account or API key:

```bash
python - <<'PY'
import hashlib
from html.parser import HTMLParser
import httpx

class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
    def handle_data(self, value):
        self.parts.append(value)

r = httpx.get('https://nebius.com/prices', timeout=30, follow_redirects=True)
r.raise_for_status()
p = Text()
p.feed(r.text)
text = ' '.join(' '.join(p.parts).split())
assert 'Networking: Egress/Ingress traffic Free' in text
assert 'Networking: Public IP address Free' in text
assert 'All prices are shown without any applicable taxes, including VAT.' in text
print(r.status_code, hashlib.sha256(r.content).hexdigest())
PY
```

Run that command with network access. A changing page hash is not proof a rate changed; inspect the
actual rows again before approving deployment. The raw key/checklist/recording hashes and runtime
source are unchanged by this documentation update. G2 and later gates remain open.
