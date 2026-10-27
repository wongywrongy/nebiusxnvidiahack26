# Approved Fly fallback

Nebius rejected the requested CPU endpoint because tenant non-GPU CPU quota is zero. The empty filesystem and unused MysteryBox secret created for that attempt have been deleted. No Nebius endpoint was created.

The prepared [fly.toml](fly.toml) uses the already published clean image, one always-on shared-CPU Machine with 2 GB RAM in Ashburn, and one 10 GB `speccheck_state` volume mounted at `/state`. Estimated compute plus volume is about $15/month, within Kyle's $25/month ceiling; traffic and snapshots are usage-priced. No paid reservation block, dedicated IPv4 address or extra Machine is requested. [Official pricing](https://docs.fly.io/about/pricing).

After account login, validate the config, create the app in Kyle's personal organization, create its volume in `iad`, import the three configured credentials via `fly secrets import` stdin, and deploy the public image with `--ha=false` so only one Machine owns the SQLite database. Provider keys never enter TOML, command arguments or image layers.

Use the shared IPv4/IPv6 HTTPS service. Check live health and the retained allowance, run the no-admin smoke and private-window a–e, then apply the approved UI polish and freeze. Keep the paid app running through December 15, 2026 at 20:00 UTC. Login/account billing must support this duration; a two-hour trial is insufficient.
