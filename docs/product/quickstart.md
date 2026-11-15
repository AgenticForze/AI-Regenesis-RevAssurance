# Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

ra seed                         # creates demo users, prints a generated password
ra run --period 2026-10         # reconcile synthetic data for ten sources
ra report --format html > before-after.html
ra serve                        # console at http://localhost:8080
```

Sign in with any demo user and the password `ra seed` printed (or set `RA_DEMO_PASSWORD`
before seeding).

| User | Role | Try |
| --- | --- | --- |
| `alice.analyst` | analyst | Browse exceptions, run an investigation |
| `ed.enterprise` | analyst, enterprise only | See that other business units are hidden |
| `bob.approver` | approver, limit 10,000 | Approve small adjustments; larger ones are refused |
| `carol.controller` | approver, limit 250,000 | Approve the large partner disputes |
| `dana.auditor` | auditor | Audit trail, hash-chain check, triage quality |
| `omar.operator` | operator | Start runs, watch traces, deliver plug-in events |
| `root.admin` | admin | Everything, except approving their own proposals |

Full stack with tracing and dashboards:

```bash
cp .env.example .env            # set PARTNER_TOKEN and RA_DEMO_PASSWORD
docker compose up --build -d
docker compose exec app python -m ra.cli seed
```

Console on 8080, Jaeger on 16686, Prometheus on 9090, Grafana on 3000. The compose stack is
provided as configuration and was not started in the build environment; the product itself was
run and tested directly.

Checks: `pytest -q` (37 tests) and `ruff check .`.
