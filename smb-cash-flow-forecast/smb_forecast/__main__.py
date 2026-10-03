"""Command-line interface: forecast, validate, and serve the local dashboard."""

import argparse
from pathlib import Path
import sys

from .model import ModelError, dumps, loads, run_model
from .report import csv_output, report_html


def main(argv=None):
    parser = argparse.ArgumentParser(description="Transparent SMB monthly cash-flow and scenario model")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("forecast", "validate"):
        sub = commands.add_parser(command)
        sub.add_argument("input", type=Path, help="JSON assumption file")
        if command == "forecast":
            sub.add_argument("--out", type=Path, default=Path("output"))
    serve = commands.add_parser("serve")
    serve.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    try:
        if args.command == "serve":
            from .server import serve_dashboard
            serve_dashboard(args.port)
            return 0
        model = run_model(loads(args.input.read_text(encoding="utf-8")))
        if args.command == "validate":
            print(f"Valid: {len(model['scenarios'])} scenarios; monthly cash reconciliations passed.")
            return 0
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "forecast.json").write_text(dumps(model, indent=2) + "\n", encoding="utf-8")
        (args.out / "report.html").write_text(report_html(model), encoding="utf-8")
        for name, result in model["scenarios"].items():
            (args.out / f"{name}.csv").write_text(csv_output(result), encoding="utf-8")
        print(f"Wrote {len(model['scenarios'])} scenario CSVs, forecast.json, and report.html to {args.out}")
        return 0
    except (ModelError, OSError, UnicodeError, ValueError, RecursionError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
