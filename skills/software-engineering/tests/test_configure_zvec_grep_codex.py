from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import tempfile
import tomllib
import unittest
from unittest import mock


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "configure_zvec_grep_codex.py"
)
SPEC = importlib.util.spec_from_file_location("configure_zvec_grep_codex", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SourceTransformTests(unittest.TestCase):
    def test_install_is_idempotent_and_check_accepts_exact_block(self) -> None:
        initial = 'model = "gpt-5.6"\n'

        installed = MODULE.install_source(initial, "zg", 600)
        repeated = MODULE.install_source(installed, "zg", 600)

        self.assertEqual(installed, repeated)
        self.assertEqual(installed.count(MODULE.START_MARKER), 1)
        self.assertEqual(installed.count(MODULE.END_MARKER), 1)
        self.assertIn('[mcp_servers.zvec_grep]', installed)
        self.assertIn(
            'args = ["server", "--stdio", "--mcp-toolset", "agent"]',
            installed,
        )
        self.assertEqual(
            tomllib.loads(installed)["mcp_servers"]["zvec_grep"]["command"],
            "zg",
        )
        MODULE.check_source(installed, "zg", 600)

    def test_uninstall_removes_only_the_managed_block(self) -> None:
        initial = (
            'model = "gpt-5.6"\n\n'
            + MODULE.render_block("zg", 600)
            + '\n\n[features]\nfast_mode = true\n'
        )

        removed = MODULE.uninstall_source(initial)

        self.assertEqual(
            removed,
            'model = "gpt-5.6"\n\n[features]\nfast_mode = true\n',
        )

    def test_unmanaged_table_is_never_overwritten_or_removed(self) -> None:
        source = (
            '[mcp_servers.zvec_grep]\n'
            'command = "custom-zg"\n'
        )

        with self.assertRaises(MODULE.ConfigError):
            MODULE.install_source(source, "zg", 600)
        with self.assertRaises(MODULE.ConfigError):
            MODULE.uninstall_source(source)

    def test_unmanaged_dotted_and_inline_config_are_rejected(self) -> None:
        unmanaged_sources = (
            'mcp_servers.zvec_grep.command = "custom-zg"\n',
            'mcp_servers = { zvec_grep = { command = "custom-zg" } }\n',
            '[mcp_servers]\nzvec_grep = { command = "custom-zg" }\n',
        )

        for source in unmanaged_sources:
            with self.subTest(source=source):
                with self.assertRaises(MODULE.ConfigError):
                    MODULE.install_source(source, "zg", 600)
                with self.assertRaises(MODULE.ConfigError):
                    MODULE.uninstall_source(source)

    def test_invalid_existing_toml_is_rejected(self) -> None:
        with self.assertRaises(MODULE.ConfigError):
            MODULE.install_source("broken = [\n", "zg", 600)

    def test_other_mcp_configuration_is_preserved(self) -> None:
        source = (
            '[mcp_servers.other]\n'
            'command = "other-server"\n'
        )

        installed = MODULE.install_source(source, "zg", 600)
        parsed = tomllib.loads(installed)

        self.assertEqual(parsed["mcp_servers"]["other"]["command"], "other-server")
        self.assertEqual(parsed["mcp_servers"]["zvec_grep"]["command"], "zg")

    def test_keys_semantically_extending_managed_table_are_rejected(self) -> None:
        source = MODULE.install_source("", "zg", 600) + (
            'env = { TOKEN = "outside-markers" }\n'
        )

        with self.assertRaises(MODULE.ConfigError):
            MODULE.install_source(source, "zg", 600)
        with self.assertRaises(MODULE.ConfigError):
            MODULE.check_source(source, "zg", 600)
        with self.assertRaises(MODULE.ConfigError):
            MODULE.uninstall_source(source)

    def test_unrelated_toml_inside_managed_markers_is_rejected(self) -> None:
        block_lines = MODULE.render_block("zg", 600).splitlines()
        unrelated_fragments = (
            '[features]\nfast_mode = true',
            '[mcp_servers.other]\ncommand = "other-server"',
            'env = { TOKEN = "inside-markers" }',
            '[mcp_servers.zvec_grep.env]\nTOKEN = "inside-markers"',
        )

        for unrelated in unrelated_fragments:
            source = "\n".join(
                [*block_lines[:-1], unrelated, block_lines[-1], ""]
            )
            with self.subTest(unrelated=unrelated):
                with self.assertRaises(MODULE.ConfigError):
                    MODULE.install_source(source, "zg", 600)
                with self.assertRaises(MODULE.ConfigError):
                    MODULE.check_source(source, "zg", 600)
                with self.assertRaises(MODULE.ConfigError):
                    MODULE.uninstall_source(source)

    def test_malformed_or_duplicate_markers_are_rejected(self) -> None:
        malformed_sources = (
            f"{MODULE.START_MARKER}\n[mcp_servers.zvec_grep]\n",
            f"{MODULE.END_MARKER}\n",
            (
                f"{MODULE.START_MARKER}\n{MODULE.END_MARKER}\n"
                f"{MODULE.START_MARKER}\n{MODULE.END_MARKER}\n"
            ),
        )

        for source in malformed_sources:
            with self.subTest(source=source):
                with self.assertRaises(MODULE.ConfigError):
                    MODULE.install_source(source, "zg", 600)

    def test_install_repairs_missing_or_drifted_owned_values(self) -> None:
        source = "\n".join(
            (
                MODULE.START_MARKER,
                "[mcp_servers.zvec_grep]",
                'command = "old-zg"',
                MODULE.END_MARKER,
                "",
            )
        )

        repaired = MODULE.install_source(source, "zg", 600)

        MODULE.check_source(repaired, "zg", 600)
        self.assertEqual(
            tomllib.loads(repaired)["mcp_servers"]["zvec_grep"]["command"],
            "zg",
        )

    def test_check_detects_configuration_drift(self) -> None:
        installed = MODULE.install_source("", "zg", 600)

        with self.assertRaises(MODULE.ConfigError):
            MODULE.check_source(installed, "zg", 601)


@unittest.skipIf(os.name == "nt", "symlink creation requires extra Windows privileges")
class FilesystemSafetyTests(unittest.TestCase):
    def test_install_preserves_agents_and_follows_config_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / ".codex"
            codex_home.mkdir()

            agents_source = root / "normative-AGENTS.md"
            agents_source.write_text("# normative\n", encoding="utf-8")
            agents_link = codex_home / "AGENTS.md"
            agents_link.symlink_to(agents_source)

            config_target = root / "actual-config.toml"
            config_target.write_text('[features]\nfast_mode = true\n', encoding="utf-8")
            config_link = codex_home / "config.toml"
            config_link.symlink_to(config_target)

            changed = MODULE.install_config(config_link, "zg", 600)

            self.assertTrue(changed)
            self.assertTrue(config_link.is_symlink())
            self.assertTrue(agents_link.is_symlink())
            self.assertEqual(
                agents_source.read_text(encoding="utf-8"),
                "# normative\n",
            )
            installed = config_target.read_text(encoding="utf-8")
            self.assertIn('[features]\nfast_mode = true', installed)
            MODULE.check_config(config_link, "zg", 600)

    def test_cli_missing_command_fails_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            status = MODULE.main(
                [
                    "install",
                    "--codex-home",
                    str(codex_home),
                    "--zg-command",
                    "definitely-missing-zvec-grep-command",
                ]
            )

            self.assertEqual(status, 1)
            self.assertFalse((codex_home / "config.toml").exists())

    def test_cli_persists_expanded_explicit_command_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            executable = home / "bin" / "zg"
            executable.parent.mkdir(parents=True)
            executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            executable.chmod(0o755)
            codex_home = root / ".codex"

            with mock.patch.dict(os.environ, {"HOME": str(home)}):
                status = MODULE.main(
                    [
                        "install",
                        "--codex-home",
                        str(codex_home),
                        "--zg-command",
                        "~/bin/zg",
                    ]
                )

            self.assertEqual(status, 0)
            installed = tomllib.loads(
                (codex_home / "config.toml").read_text(encoding="utf-8")
            )
            self.assertEqual(
                installed["mcp_servers"]["zvec_grep"]["command"],
                str(executable),
            )


if __name__ == "__main__":
    unittest.main()
