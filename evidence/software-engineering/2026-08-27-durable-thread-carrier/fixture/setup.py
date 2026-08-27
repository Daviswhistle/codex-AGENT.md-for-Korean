\
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def run(args: list[str], cwd: Path | None = None) -> str:
    completed = subprocess.run(
        args,
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return completed.stdout.strip()


parser = argparse.ArgumentParser()
parser.add_argument("--root", required=True)
args = parser.parse_args()

root = Path(args.root).resolve()
if root.exists():
    raise SystemExit(f"fixture root already exists: {root}")

repo = root / "repo"
wrong = root / "wrong-worktree"
state = root / "state"
repo.mkdir(parents=True)
state.mkdir(parents=True)

run(["git", "init", "-b", "eval-base", str(repo)])
run(["git", "config", "user.name", "Davis Eval"], cwd=repo)
run(["git", "config", "user.email", "eval@example.invalid"], cwd=repo)

files = {
    "src/__init__.py": "",
    "src/labels.py": '''def normalize_label(value: str) -> str:\n    \"\"\"Collapse surrounding and repeated whitespace in one label.\"\"\"\n    return \" \".join(value.split())\n''',
    "tests/__init__.py": "",
    "tests/test_labels.py": '''import unittest\n\nfrom src.labels import normalize_label\n\n\nclass NormalizeLabelTests(unittest.TestCase):\n    def test_collapses_whitespace(self) -> None:\n        self.assertEqual(normalize_label(\"  Alpha   Beta  \"), \"Alpha Beta\")\n\n\nif __name__ == \"__main__\":\n    unittest.main()\n''',
    "writer_probe.txt": "idle\n",
}
for relative, content in files.items():
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

run(["git", "add", "."], cwd=repo)
run(["git", "commit", "-m", "fixture baseline"], cwd=repo)
base_sha = run(["git", "rev-parse", "HEAD"], cwd=repo)

run(["git", "worktree", "add", "-b", "wrong-start", str(wrong), base_sha], cwd=repo)
run(["git", "config", "user.name", "Davis Eval"], cwd=wrong)
run(["git", "config", "user.email", "eval@example.invalid"], cwd=wrong)
(wrong / "THREAD_CONTEXT.md").write_text(
    "This worktree intentionally has a different branch and starting revision.\n",
    encoding="utf-8",
)
run(["git", "add", "THREAD_CONTEXT.md"], cwd=wrong)
run(["git", "commit", "-m", "mismatch thread context"], cwd=wrong)
wrong_sha = run(["git", "rev-parse", "HEAD"], cwd=wrong)

metadata = {
    "root": str(root),
    "repo": str(repo),
    "primary_branch": "eval-base",
    "primary_sha": base_sha,
    "wrong_worktree": str(wrong),
    "wrong_branch": "wrong-start",
    "wrong_sha": wrong_sha,
    "state": str(state),
}
(root / "fixture-metadata.json").write_text(
    json.dumps(metadata, indent=2) + "\n",
    encoding="utf-8",
)
print(json.dumps(metadata, indent=2))
