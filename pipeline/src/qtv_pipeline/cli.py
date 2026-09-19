from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import build as build_mod
from .http import FetchError, PacedClient


def _cmd_terms_check(_args: argparse.Namespace) -> int:
    from . import terms

    with PacedClient(log=print) as client:
        check = terms.check_lezwatch_terms(client)
    print(f"ok: {check.url} still grants reuse")
    return 0


def _cmd_fetch(args: argparse.Namespace) -> int:
    try:
        build_mod.run_fetch(Path(args.cache), full=args.full, log=print)
    except (build_mod.BuildError, FetchError) as exc:
        print(f"fetch failed: {exc}", file=sys.stderr)
        return 1
    return 0


def _cmd_build(args: argparse.Namespace) -> int:
    try:
        build_mod.run_build(
            Path(args.cache),
            Path(args.out),
            git_sha=args.git_sha or os.environ.get("GITHUB_SHA"),
            workflow_run_id=args.workflow_run_id or os.environ.get("GITHUB_RUN_ID"),
            log=print,
        )
    except build_mod.BuildError as exc:
        print(f"build failed: {exc}", file=sys.stderr)
        return 1
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    import jsonschema

    schema_path = Path(args.schema) if args.schema else build_mod._find_schema_path()
    schema = json.loads(schema_path.read_text())
    doc = json.loads(Path(args.path).read_text())
    validator = jsonschema.Draft202012Validator(schema)
    errors = list(validator.iter_errors(doc))
    if errors:
        for err in errors[:20]:
            print(f"  {'/'.join(str(p) for p in err.path)}: {err.message}", file=sys.stderr)
        print(f"{len(errors)} validation error(s)", file=sys.stderr)
        return 1
    print(f"ok: {args.path} validates against {schema_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="qtv", description="queer-tv-guide pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("terms-check", help="re-read the LezWatch ToS and confirm the reuse grant")
    p.set_defaults(func=_cmd_terms_check)

    p = sub.add_parser("fetch", help="mirror LezWatch + TVmaze into the cache")
    p.add_argument("--cache", required=True, help="cache directory")
    p.add_argument("--full", action="store_true", help="ignore the incremental cursor")
    p.set_defaults(func=_cmd_fetch)

    p = sub.add_parser("build", help="normalize the cache into snapshot.v1.json")
    p.add_argument("--cache", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--git-sha", default=None)
    p.add_argument("--workflow-run-id", default=None)
    p.set_defaults(func=_cmd_build)

    p = sub.add_parser("validate", help="validate a snapshot file against the schema")
    p.add_argument("path")
    p.add_argument("--schema", default=None)
    p.set_defaults(func=_cmd_validate)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    status: int = args.func(args)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
