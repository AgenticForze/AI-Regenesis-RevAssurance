"""Command line: `ra <command>` (or `python -m ra.cli`)."""
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys

from ra import audit, db, obs, plugins, reporting
from ra.auth import SYSTEM, idp
from ra.settings import get_settings


def _seed(args) -> None:
    password = os.environ.get("RA_DEMO_PASSWORD") or secrets.token_urlsafe(12)
    users = idp.seed_demo_users(password)
    mcp_secret = idp.create_client("mcp-client", ["integration"])
    print("Demo users (all share one password):")
    for u in users:
        print(f"  {u['username']:<18} roles={u['roles']} bu={u['bu_scope']} "
              f"limit={u['approval_limit']}")
    if not os.environ.get("RA_DEMO_PASSWORD"):
        print(f"\nGenerated password: {password}")
    print(f"Machine client 'mcp-client' secret (shown once): {mcp_secret}")


def _run(args) -> None:
    from ra.recon import engine
    out = engine.run(SYSTEM, args.period, args.accounts, args.seed, args.data)
    print(json.dumps(out, indent=2))


def _report(args) -> None:
    run = db.one("SELECT id FROM runs ORDER BY started DESC LIMIT 1")
    if not run:
        sys.exit("no run yet: `ra run --period 2026-10`")
    rep = reporting.before_after(run["id"])
    if args.format == "html":
        print(reporting.to_html(rep))
    elif args.format == "csv":
        print(reporting.to_csv(rep), end="")
    else:
        print(json.dumps({**rep, "triage_quality": reporting.triage_quality(run["id"])}, indent=2))


def _serve(args) -> None:
    import uvicorn
    uvicorn.run("ra.api.app:app", host=args.host, port=args.port, log_config=None)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="ra", description="Revenue Assurance")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed", help="create demo users and a machine client").set_defaults(fn=_seed)
    r = sub.add_parser("run", help="run a reconciliation")
    r.add_argument("--period", required=True)
    r.add_argument("--accounts", type=int, default=400)
    r.add_argument("--seed", type=int, default=7)
    r.add_argument("--data", choices=["synthetic", "sources"], default="synthetic")
    r.set_defaults(fn=_run)
    rp = sub.add_parser("report", help="before/after report for the latest run")
    rp.add_argument("--format", choices=["json", "html", "csv"], default="json")
    rp.set_defaults(fn=_report)
    sv = sub.add_parser("serve", help="start the API and console")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8080)
    sv.set_defaults(fn=_serve)
    sub.add_parser("verify-audit", help="check the audit hash chain").set_defaults(
        fn=lambda a: print(json.dumps(audit.verify())))
    sub.add_parser("dispatch", help="deliver queued plug-in events").set_defaults(
        fn=lambda a: print(json.dumps(plugins.dispatch())))
    sub.add_parser("plugins", help="list configured plug-ins").set_defaults(
        fn=lambda a: print(json.dumps(plugins.describe(), indent=2)))
    args = ap.parse_args(argv)
    get_settings()
    if args.cmd != "serve":
        obs.setup()
    args.fn(args)


if __name__ == "__main__":
    main()
