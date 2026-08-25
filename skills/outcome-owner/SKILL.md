---
name: outcome-owner
description: Use when the user explicitly wants Codex to own a non-trivial or long-running outcome through completion, act proactively within bounded authority, preserve the outcome across interruptions, or maintain durable local checkpoints and evidence instead of treating the request as a single disposable task.
---

# Outcome Owner

Own the user's intended outcome, not merely the next visible action. Maintain a durable local contract so that initiative remains accountable across long work, delegation, interruptions, and verification.

This skill adds procedural ownership. It does not grant broader authority, make uncertain facts true, or replace the user's control over external and irreversible actions.

## Ownership Contract

1. Keep one user-facing owner. That owner retains the objective, purpose, constraints, desired state, success criteria, authority boundary, integration decisions, verification, and final report.
2. Infer the outcome contract from the request and current evidence: objective, purpose, desired state, observable success criteria, constraints, repository root, and authority. Purpose records why the outcome matters or which decision principle should survive execution. Ask only when an ambiguity would materially change the result, authority, risk, or cost.
3. Maintain broad awareness but bounded action. Inspect what is relevant to the outcome, while acting only within `read-only` or `local-write` authority recorded for the mission.
4. Push, deployment, migration, external messages, purchases, production-data changes, destructive actions, and other external writes still require explicit authority.
5. Use temporary workers only when separation improves quality, speed, context preservation, or independent review. Do not impose arbitrary worker, turn, or cycle limits. The owner must inspect actual outputs and remains responsible for integration.
6. Treat important opportunities as observations, not silent scope expansion. Record the evidence, expected value, cost, risk, and smallest reversible experiment when useful, then continue the authorized outcome.

## Durable Ledger

Use `scripts/outcome_ledger.py` for every mission governed by this skill. The helper stores control state only. It never launches Codex, runs shell or Git commands, creates worktrees, calls a network service, or writes into the project.

The default database is `${CODEX_HOME:-~/.codex}/outcome-owner/objectives.sqlite3`. The database must resolve outside every governed repository; use `--db` with an isolated, dedicated path for tests. Before opening an existing source database read-write, the helper captures a stable private copy of its main file, rollback journal, and WAL in a reserved control temporary root outside every governed repository, independent of process temp-directory settings. POSIX uses `/tmp/.outcome-owner-preflight-<uid>` with mode `0700`; other platforms use `~/.codex/outcome-owner/preflight`. New missions whose repository would contain that root are rejected before state creation. Clone files use mode `0600`. Normal exit removes them; a process kill may leave a private clone under the reserved root, but never in the governed project. Inspect and remove stale clone directories only after confirming that no ledger process is using them. The helper recovers only the copy and verifies the effective application identity, full supported schema, persisted JSON and hashes, transition history, and row invariants in one read snapshot. A changing source fails closed after one retry. The helper initializes identity durably in rollback-journal mode before switching to WAL and must reject unrelated, unsupported, partially structured, or corrupt databases without recovering or mutating their source files. On POSIX, identified main, WAL, SHM, and rollback-journal files must each have mode `0600`; unsafe existing modes fail before the source is opened read-write. The database and its event text are local plaintext: never record secrets, tokens, credentials, private source text, or unnecessary sensitive data.

Before substantial work:

1. Define a concrete objective, purpose, desired state, one or more observable success criteria, one or more constraints, repository root, and authority.
2. Call `start` with a stable idempotency key. A replay with the same canonical contract recovers the existing mission; a changed payload must fail closed.
3. Create a unique owner identifier for this ownership execution; do not reuse an identifier from an earlier execution or recovery session. Call `claim` with the last observed `mission.lease_generation` as `--expected-generation` and `mission.version` as `--expected-version`. A successful claim returns the current transactional mission snapshot plus the fencing token in `lease.generation`; pass the token as `--lease-generation` to every `heartbeat`, `record`, `transition`, and `release`. Keep the lease alive with `heartbeat` during active work.
4. Claims enforce a repository reader/writer boundary across missions with the same persisted filesystem identity, exact canonical path, filesystem-aware case key, or ancestor/descendant path overlap: `local-write` is exclusive, while concurrent `read-only` claims may coexist. Filesystem identity includes device, inode, and a stable creation identity so immediate inode reuse cannot hide directory replacement. Prefer an opaque Linux file handle, then native birth/creation identity; persist the selected identity kind and revalidate with that same kind so changing OS capability availability cannot create a false replacement signal. Do not substitute Git metadata or a project sentinel, and fail `start` closed when the filesystem exposes no safe identity. Case detection distinguishes exact directory entries before following a case-variant alias, so a removable symlink cannot poison the persisted case contract. Inside the claim transaction, the helper re-resolves and stats both the target mission and every active mission whose authority could conflict; `heartbeat` and every new event or state mutation revalidate their target before writing. Missing paths or drift in canonical path, directory identity, creation identity, case semantics, or path key fail closed. Distinct sibling worktrees and case-only directories on a case-sensitive filesystem remain independent. Historical idempotent replays remain read-only, and a drifted lease may still be explicitly released before reconciliation.
5. Use native Codex goal mode only when the user explicitly requests it and it is available. The ledger remains the durable outcome contract; native goal execution is an optional execution surface.

During work:

1. Record compact `checkpoint`, `progress`, `decision`, `evidence`, `risk`, `blocker`, `opportunity`, or `recovery` events with unique idempotency keys.
2. Record facts that change the plan, authority boundary, success judgment, or safe recovery path. Avoid transcript duplication and low-value narration.
3. Reconcile the current mission contract after delegation, steering, interruption, or materially changed evidence. Mission contract fields are immutable: do not use an event as a hidden override when steering materially changes the objective, purpose, desired state, success criteria, constraints, repository, or authority. Record the replacement decision on the current mission, start the replacement with a new stable idempotency key, transition the superseded mission to `abandoned` only when the old outcome is genuinely no longer valid, then claim the replacement after the old lease is released and record the old mission ID there. On interruption, reconcile both mission IDs before continuing.
4. Supply the current claim's fencing token to every lease-authorized mutation. Supply the mission version last observed from `start`, `show`, a successful claim, or a successful transition as `--expected-version` for every claim and new transition. On generation or version conflict, reconcile the current mission and evidence before deciding again; do not blindly retry with newer numbers. An exact idempotent transition replay uses its historical generation and may return its prior event even after the version advances. In every transition response, treat `event_effect` as that historical event's effect and `mission` plus `active_lease` as the current transactional snapshot.
5. Mutation timestamps use a nondecreasing logical time anchored to the mission and current lease. Lease validity is still tested against wall time sampled after the writer lock; a backward wall-clock step may conservatively retain a lease longer, but must not create out-of-order persisted timestamps or allow early takeover.
6. Move to `waiting`, `blocked`, or `interrupted` only when the state is real. These states release the lease so another future owner can recover the mission safely.
7. Mark `blocked` only after safe in-scope checks and alternatives have been exhausted and the missing input or authority genuinely prevents meaningful progress.

## Restart And Recovery

Never blindly replay a prior command or assume an interrupted side effect did not happen.

1. Run `show` and read the mission contract, current version, lease, and ordered recent events.
2. Inspect current repository, worktree, generated artifacts, tests, and any relevant external evidence under the recorded authority.
3. Resolve whether earlier work completed, partially completed, failed, or has unknown durability.
4. Claim the mission only after the prior lease expires or is released. Generate a new owner ID for the recovery execution, pass the reconciled `mission.lease_generation` as `--expected-generation` and `mission.version` as `--expected-version`, and use only the returned fencing token. A new or takeover claim advances the lease generation, including accidental reuse of the same owner string after expiry. Record a `recovery` event describing the reconciled evidence and the next safe action.
5. Return an `interrupted` mission to `active` only after reconciliation. Do not infer success from an old checkpoint or a worker's completion statement.

## Completion

1. Transition from `active` to `verifying` with the currently observed version while retaining ownership. This establishes the evidence boundary for the verification cycle.
2. Check every success criterion against current primary evidence.
3. Record at least one fresh `evidence` event after that latest transition into `verifying` and under the current lease generation. Evidence from before verification, an earlier verification cycle, or a prior lease generation cannot satisfy completion.
4. Resolve validation failures by returning to `active`, `blocked`, or `interrupted` as the evidence requires.
5. Transition from `verifying` to `complete` only when every criterion is satisfied and provide the currently observed version plus a non-empty completion summary.
6. Report the achieved state, evidence, validation, remaining uncertainty, and any unperformed external step distinctly. `complete` and `abandoned` are terminal.

Mission transitions and lease rules are enforced by the helper. `waiting`, `blocked`, `interrupted`, `complete`, and `abandoned` release the owner lease atomically. A lease found in a nonterminal released state is valid only when its generation is newer than the generation that entered that state. To resume such a mission, claim it first and transition it back to `active` using a new idempotency key.

## Failure Boundaries

- Do not weaken success criteria to obtain completion.
- Do not equate local validation with deployment, approval, or live behavior.
- Do not conceal uncertainty, failed checks, missing evidence, or a narrowed conclusion.
- Do not place project files, shell strings, network calls, credentials, or execution logic in the ledger helper.
- Do not abandon an outcome because it is slow or difficult. Use `abandoned` only when the user directs it or the outcome is no longer valid and that conclusion is explicitly justified.

See the skill `README.md` for non-secret CLI examples and the local-state privacy boundary.
