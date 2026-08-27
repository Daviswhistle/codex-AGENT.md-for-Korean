#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--repo", required=True)
args = parser.parse_args()
repo = Path(args.repo).resolve()

tests = subprocess.run(
    ["python3", "-m", "unittest", "discover", "-s", "tests", "-v"],
    cwd=repo,
    text=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
)
print(tests.stdout, end="")
if tests.returncode != 0:
    raise SystemExit(tests.returncode)

spec = importlib.util.spec_from_file_location("fixture_labels", repo / "src/labels.py")
if spec is None or spec.loader is None:
    raise SystemExit("cannot load fixture module")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
function = getattr(module, "dedupe_labels", None)
if function is None:
    raise SystemExit("dedupe_labels is missing")

expected = ["Alpha", "Beta", "Gamma"]
actual = function([" Alpha ", "alpha", "  ", "Beta", " BETA ", "Gamma"])
if actual != expected:
    raise SystemExit(f"unexpected dedupe result: {actual!r}")
if function(["Straße", "STRASSE"]) != ["Straße"]:
    raise SystemExit("dedupe_labels must compare with casefold()")

status = subprocess.run(
    ["git", "status", "--porcelain"],
    cwd=repo,
    check=True,
    text=True,
    stdout=subprocess.PIPE,
).stdout.splitlines()
changed = {line[3:] for line in status if len(line) >= 4}
required = {"src/labels.py", "tests/test_labels.py"}
if not required.issubset(changed):
    raise SystemExit(f"required task files were not both changed: {sorted(changed)}")
changed = {path for path in changed if "__pycache__" not in path and not path.endswith(".pyc")}
unexpected = changed - required
if unexpected:
    raise SystemExit(f"unexpected fixture changes: {sorted(unexpected)}")
print("fixture verification passed")
