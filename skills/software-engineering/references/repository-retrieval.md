# Repository Retrieval

Use this reference before broad repository discovery, architecture tracing, cross-file synthesis, or delegating an explorer. It chooses the narrowest evidence route that can establish the answer. It does not make zvec-grep mandatory and does not replace source inspection or validation.

## Retrieval Contract

1. Decide whether the answer should come from the current workspace before choosing a search tool. Repository implementation, local configuration, project history, and user-provided workspace material use workspace evidence. Current external facts, package behavior not established locally, and upstream contracts use the appropriate primary external source.
2. When the relevant file and region are already known, read that region directly. Do not add a search round merely because a search tool exists.
3. When an exact identifier, filename, path, configuration key, error text, literal, quotation, or regex is known and locating occurrences is sufficient, use native `rg`, grep, or the host's exact-search tool.
4. When wording or location is unknown, or the task requires semantic discovery, architecture, chronology, causality, data or control flow, or synthesis across files, use `zvec_grep_search` when it is available and the workspace is indexed.
5. For mixed tasks, use semantic retrieval to identify likely relationships, then verify decisive identifiers and call sites with exact search. Do not treat vector similarity as proof that a path is active or authoritative.
6. If the user asks whether conceptually related material exists and no exact anchor is available, make at most one focused semantic probe using the question and distinctive names or terms. Continue only when the returned evidence is relevant.
7. Before editing, inspect the authoritative source around every decisive result. A ranked snippet can establish where to look; it does not replace checking definitions, callers, surrounding conditions, generated status, and applicable project instructions.
8. Stop discovery when the evidence is sufficient to define the change and its validation. Do not widen the scan, delegate another explorer, or read whole directories without a concrete unresolved claim.

## zvec-grep Boundaries

1. Pass the daemon-visible absolute workspace root on every MCP call.
2. Use the indexed semantic route only when an index already exists. If the index is absent and exact search can answer the task, use exact search instead of creating an index.
3. Creating, rebuilding, manually forcing a refresh, dropping an index, or changing its persistent lifecycle policy requires explicit authorization. Ordinary search may use an existing index's already-configured background freshness behavior; do not change that policy or call a lifecycle tool without authorization. A software-change request alone does not authorize persistent indexing of unrelated workspaces.
4. If zvec-grep is unavailable, disconnected, stale, or returns irrelevant evidence, fall back to direct reads and native exact search. Report a material retrieval limitation; do not block a localized task or silently install software.
5. Remote embedding authorization is separate from MCP tool approval and provider credentials. Never grant it, request a secret, or send workspace content remotely without the user's explicit approval for that workspace. Prefer a local embedding model when privacy or source sensitivity matters.
6. Exclude secrets, private archives, generated model files, caches, and other irrelevant high-volume paths from indexing and broad retrieval unless the task specifically requires them and access is authorized.

## Safe Codex Setup with Davis Agent Kit

Davis Agent Kit owns `${CODEX_HOME:-$HOME/.codex}/AGENTS.md` as a symbolic link to the repository's normative `AGENTS.md`. The upstream `zg install --target codex` command writes both Codex MCP configuration and a managed guidance block into that path. Because the upstream writer follows symbolic links, running that command against a normal Davis Agent Kit installation would modify the repository source itself.

Keep guidance in this skill and configure only the MCP entry:

```bash
# zvec-grep currently requires Node.js 22 or newer.
npm install -g @zvec/zvec-grep

ZVEC_GREP_HELPER="${CODEX_HOME:-$HOME/.codex}/skills/software-engineering/scripts/configure_zvec_grep_codex.py"
python3 "$ZVEC_GREP_HELPER" install
python3 "$ZVEC_GREP_HELPER" check
```

The helper:

- edits only `${CODEX_HOME:-$HOME/.codex}/config.toml`;
- installs the stdio MCP server with the narrow `agent` toolset;
- preserves unrelated TOML and an existing `config.toml` symbolic link;
- replaces only a complete and exclusive `# ZVEC_GREP_START` / `# ZVEC_GREP_END` block, refusing unrelated keys or tables placed inside it;
- parses the surrounding TOML and refuses malformed markers, invalid TOML, any unmanaged `mcp_servers.zvec_grep` definition, or keys and nested tables that semantically extend the managed table from outside the markers;
- expands and persists explicit executable paths such as `~/bin/zg` or `./bin/zg` as absolute paths so Codex can launch them directly;
- fails before writing when `zg` is unavailable, unless `--skip-command-check` is supplied deliberately;
- never edits `AGENTS.md`, installs the npm package, starts a persistent daemon, creates an index, or grants remote embedding access.

Restart Codex or open a new session after installation. Remove only the managed MCP block with:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/software-engineering/scripts/configure_zvec_grep_codex.py" uninstall
```

Do not run `zg install --target codex` or `zg uninstall --target codex` while the kit-managed `AGENTS.md` link is active. Both commands manage that file in addition to `config.toml`.

## Workspace Indexing

Indexing is a separate, workspace-scoped decision. From the intended repository root, a local model setup can be initiated explicitly with:

```bash
zg index --embedding local/potion-retrieval-32m
```

Before indexing, confirm the root, ignore rules, source sensitivity, expected disk use, and whether generated or private paths are excluded. After material repository changes, read search freshness metadata and use exact search when current unindexed changes are decisive.

## Completion Evidence

For non-trivial discovery, retain enough evidence to explain:

1. why direct read, exact search, semantic search, or an external source was selected;
2. the focused query or anchors used;
3. which returned paths and source regions established the change boundary;
4. how decisive claims were verified exactly before editing;
5. whether the index, freshness, remote-embedding authorization, or tool availability limited confidence.
