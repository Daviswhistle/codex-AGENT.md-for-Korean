\
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--root", required=True)
args = parser.parse_args()
root = Path(args.root).resolve()
if root == Path(root.anchor) or not (root / "fixture-metadata.json").is_file():
    raise SystemExit(f"refusing unsafe fixture teardown: {root}")
shutil.rmtree(root)
print(f"removed {root}")
