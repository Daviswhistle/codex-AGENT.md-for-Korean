#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--repo", required=True)
parser.add_argument("--state", required=True)
args = parser.parse_args()

repo = Path(args.repo).resolve()
state = Path(args.state).resolve()
state.mkdir(parents=True, exist_ok=True)
probe = repo / "writer_probe.txt"
original = probe.read_text(encoding="utf-8")
ready = state / "writer-ready.json"
release = state / "release-writer"
stopped = state / "writer-stopped.json"
ready.write_text(
    json.dumps({"pid": os.getpid(), "repo": str(repo)}) + "\n",
    encoding="utf-8",
)
counter = 0
try:
    while not release.exists():
        counter += 1
        probe.write_text(f"active-writer-{counter}\n", encoding="utf-8")
        time.sleep(0.2)
finally:
    probe.write_text(original, encoding="utf-8")
    release.unlink(missing_ok=True)
    stopped.write_text(
        json.dumps({"pid": os.getpid(), "repo": str(repo)}) + "\n",
        encoding="utf-8",
    )
