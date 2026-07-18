# AimiliVPN Backend Architecture

## Scope

The backend keeps the existing VPNGate behavior while adding a lazy
PublicVPNList source and make-before-break OpenVPN switching. The management
frontend now consumes the lightweight v2 APIs and uses asynchronous switching.

## Modules

- `vpn_sources.py`: filter validation, PublicVPNList pagination/cache,
  normalization, lazy profile download, and OpenVPN profile safety checks.
- `tunnel_slots.py`: two-slot active/draining tunnel state.
- `proxy_server.py`: HTTP/SOCKS5 data plane. Each accepted client snapshots
  the active egress interface so an interface switch only affects new clients.
- `config_cleanup.py`: bounded OpenVPN profile cache cleanup with active,
  draining, fixed-IP, and favorite-node protection.
- `vpngate_manager.py`: compatibility API, orchestration, OpenVPN process
  lifecycle, policy routing, health checks, scheduled cleanup, and persisted
  state.

## Switching Sequence

1. Keep the current active tunnel and proxy traffic running.
2. Start the candidate on the inactive interface (`tun0` or `tun1`).
3. Install the candidate's independent route table (`100` or `101`).
4. Verify public egress directly through the candidate interface.
5. Atomically change the proxy's active interface.
6. Route new proxy clients through the candidate.
7. Keep existing clients on the previous interface until they drain or the
   hard drain timeout expires.

A failed candidate never replaces a healthy active tunnel.

## Web UI

- `webui/index.html`: authenticated management console shell.
- `webui/assets/app.css`: responsive route-stage and settings presentation.
- `webui/assets/app.js`: API client, incremental rendering, polling, latency
  measurement, asynchronous switching, filters, routing, and account settings.
- `vpngate_manager.py` serves these files below the configured secure path and
  falls back to the legacy embedded HTML if the external index is missing.

The UI polls lightweight state without replacing the node table on every poll.
During make-before-break switching it keeps showing the current exit until the
candidate job completes, then refreshes node metadata.

## Backend APIs For The New Frontend

- `GET /api/state`: lightweight connection and tunnel state.
- `GET /api/v2/nodes?page=1&page_size=50`: paginated node metadata without
  embedded OpenVPN profiles.
- `GET /api/node_source_options`: supported catalogs, protocols, and current
  PublicVPNList source names.
- `POST /api/update_node_filters`: validate/save filters and start a background
  metadata refresh.
- `POST /api/v2/latency`: fast endpoint latency measurement without starting
  OpenVPN or downloading lazy profiles.
- `POST /api/connect_async`: queue a connection and return `202` plus a job ID.

Existing APIs remain available for the current frontend.

## Environment Variables

```text
NODE_SOURCE=vpngate
PUBLICVPNLIST_PAGE_SIZE=100
PUBLICVPNLIST_MAX_PAGES=20
PUBLICVPNLIST_METADATA_TTL=900
BACKGROUND_TEST_NODE_LIMIT=15
LATENCY_PROBE_WORKERS=10
TUNNEL_DRAIN_SECONDS=45
TUNNEL_DRAIN_MAX_SECONDS=180
CONFIG_CLEANUP_INITIAL_DELAY_SECONDS=60
CONFIG_CLEANUP_INTERVAL_SECONDS=3600
CONFIG_MAX_FILES=300
CONFIG_MAX_AGE_SECONDS=259200
CONFIG_INVALID_GRACE_SECONDS=1800
CONFIG_ORPHAN_GRACE_SECONDS=21600
CONFIG_TEMP_MAX_AGE_SECONDS=3600
```

`NODE_SOURCE` accepts `vpngate`, `publicvpnlist`, or `all`.

VPN profiles are downloaded lazily by both sources. Cleanup runs after the
initial delay and then at the configured interval. It removes unavailable,
orphaned, abandoned test, expired, and over-capacity profiles while preserving
profiles used by active/draining tunnels, fixed-IP selection, and favorites.
The latest cleanup result is exposed in `state.json` as `config_cleanup`.

## Linux Validation Required

Unit tests cover source normalization/filtering, caching, profile validation,
proxy interface selection, and slot transitions. Before production rollout,
validate these Linux-specific operations on a staging VPS:

- simultaneous `tun0` and `tun1` OpenVPN processes;
- `ip rule ... oif` lookup against route tables 100 and 101;
- `curl --interface tunX` candidate health checks;
- old HTTP/SOCKS5 connections remaining alive during drain;
- rapid consecutive switches while an old slot is still draining.
