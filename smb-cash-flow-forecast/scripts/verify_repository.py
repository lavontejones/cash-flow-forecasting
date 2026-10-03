"""Reproducibility, documented inputs, links, and public-content hygiene checks.

This bounded scan is not a guarantee that every conceivable secret is detectable.
"""

import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from smb_forecast.model import DEFAULTS, dumps, loads, run_model
from smb_forecast.report import csv_output, report_html


def verify():
    errors = []
    source = ROOT/"examples/sample-business.json"
    if source.read_bytes() != (ROOT/"smb_forecast/sample.json").read_bytes():
        errors.append("Bundled and example inputs differ")
    model = run_model(loads(source.read_text(encoding="utf-8")))
    outputs = ROOT/"examples/outputs"
    expected = {"forecast.json": dumps(model, indent=2)+"\n", "report.html": report_html(model)}
    expected.update({f"{name}.csv": csv_output(result) for name, result in model["scenarios"].items()})
    for name, content in expected.items():
        with (outputs/name).open(encoding="utf-8", newline="") as file:
            if file.read() != content:
                errors.append(f"Stale output: {name}")
    docs = (ROOT/"docs/assumptions.md").read_text()
    for field in set(DEFAULTS) | {"cogs_rate"}:
        if f"`{field}`" not in docs:
            errors.append(f"Undocumented assumption: {field}")
    patterns = [r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
                r"gh[pousr]_[A-Za-z0-9]{30,}", r"github_pat_[A-Za-z0-9_]{30,}",
                r"sk-(?:proj-)?[A-Za-z0-9_-]{24,}", r"AKIA[0-9A-Z]{16}"]
    files = [p for p in ROOT.rglob("*") if p.is_file() and not any(
        part in {".git", "__pycache__", ".venv", "build", "dist"} or part.endswith(".egg-info")
        for part in p.relative_to(ROOT).parts)]
    for path in files:
        if path.suffix in {".png", ".pyc"}:
            continue
        text = path.read_text(encoding="utf-8")
        if path.name != "verify_repository.py" and re.search("jo"+"nesys", text, re.I):
            errors.append(f"Disallowed branding: {path.relative_to(ROOT)}")
        for pattern in patterns:
            if re.search(pattern, text):
                errors.append(f"Possible credential: {path.relative_to(ROOT)}")
        if path.name != "verify_repository.py" and re.search(r"/Users/|/home/[a-zA-Z]|/root/", text):
            errors.append(f"Private absolute path: {path.relative_to(ROOT)}")
        if path.suffix == ".md":
            for target in re.findall(r"\]\(([^)]+)\)", text):
                if re.match(r"https?://|#", target):
                    continue
                target = target.split("#",1)[0]
                if target and not (path.parent/target).exists():
                    errors.append(f"Broken local link: {path.relative_to(ROOT)} → {target}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"Verified {len(files)} files; sample exports reproduce; all assumptions documented; no flagged public-content issues.")
    return 0


if __name__ == "__main__":
    raise SystemExit(verify())
