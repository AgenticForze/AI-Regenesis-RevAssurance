"""Eval harness entry point. Phase 4 task T4.08 connects suites to Bedrock and datasets."""
from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run an eval suite")
    parser.add_argument("--suite", required=True)
    parser.add_argument("--subset", default="regression-100")
    parser.add_argument("--dataset", default="regression")
    parser.add_argument("--rc", default=None)
    parser.add_argument("--gate", action="store_true", help="fail on threshold breach")
    args = parser.parse_args(argv)
    print(f"[evals] suite={args.suite} subset={args.subset} dataset={args.dataset}: "
          "no suites wired yet (see task T4.08)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
