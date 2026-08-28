#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path

_NAME = re.compile(r"^[A-Za-z0-9._-]+$")

parser = argparse.ArgumentParser()
parser.add_argument("--state", required=True)
parser.add_argument("--name", required=True)
parser.add_argument("--timeout-seconds", type=float, default=300.0)
args = parser.parse_args()

if not _NAME.fullmatch(args.name):
    raise SystemExit("barrier name must match [A-Za-z0-9._-]+")

state = Path(args.state).resolve()
state.mkdir(parents=True, exist_ok=True)
ready = state / f"{args.name}-ready.json"
release = state / f"{args.name}-release"
released = state / f"{args.name}-released.json"
timed_out = state / f"{args.name}-timeout.json"

payload = {
    "name": args.name,
    "pid": os.getpid(),
    "state": str(state),
}
ready.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")

deadline = time.monotonic() + args.timeout_seconds
while not release.exists():
    if time.monotonic() >= deadline:
        timed_out.write_text(
            json.dumps(payload | {"timeout_seconds": args.timeout_seconds}, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        raise SystemExit(f"barrier timed out: {args.name}")
    time.sleep(0.05)

release.unlink()
released.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
