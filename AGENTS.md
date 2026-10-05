# Ironman Bank Architect — agent instructions

## Identity
This is an original RuneLite plugin owned by this repository.
Package root: com.pkoka5.ironmanbankarchitect

Do not copy, import, adapt, or mirror code, UI, resources, naming, layouts, configuration, or project structure from Bank Templates or any other third-party plugin.

Standard RuneLite API usage and original code written in this repository are allowed.

## Product goal
Build an Ironman-oriented bank blueprint and organization assistant.

The plugin may:
- read the player's bank through supported RuneLite APIs;
- create and save local layout blueprints;
- show a sidebar planner, checklist, and manual organization guidance.

The plugin must not:
- automate mouse, keyboard, clicks, drags, packets, or bank actions;
- manipulate game state;
- use reflection, Runtime.exec, native code, external processes, network calls, or telemetry;
- read inventory or equipment unless a later documented feature explicitly allows it.

The player always moves bank items manually.

## Workflow
- Explain proposed files and changes before editing. This applies to the main thread; an approved delegation brief serves as the explanation for the subagent carrying it out.
- Keep changes small and focused.
- Do not commit, push, merge, or change branches unless explicitly asked.
- Only one coding agent edits production files at a time.
- Run tests after code changes (`./gradlew test`, or `gradlew.bat test` on Windows) and report warnings or failures.

## Subagents
- Launch every subagent through T3 Code's `delegate_task` (the `t3-code` MCP server), not native subagent tools such as Codex agent spawning or Claude's Agent tool.
- Exception: the main thread may use native read-only search agents (e.g. Claude's Explore/Plan) for quick lookups. Any subagent that writes files goes through `delegate_task`.
- If T3 tools are unavailable, do the work in the main thread or ask the user; do not fall back to native subagent tools.
- Call `orchestrator_capabilities` first and choose provider/model IDs from its live catalog. If a pinned model is missing from the catalog, ask the user before delegating.
- Research/design/review default: provider `codex`, model `gpt-6-luna`, `reasoningEffort` `high`.
- Implementation/tests default: provider `claudeAgent`, model `claude-opus-5-5`, `effort` `high`, `contextWindow` `1m`.
- Routine implementation and test work (small well-specified edits, applying already-approved catalog/resource rows, running suites, adding straightforward cases, fixing expectations): provider `claudeAgent`, model `claude-sonnet-5-5`, `effort` `high`. Use the Opus default for design-sensitive, cross-cutting or Plugin Hub token-budget work.
- Every delegation brief states the paths the subagent may write and the checks it must run before reporting.
- Parallel subagents must be read-only or write only to their own fresh directory (e.g. a new `tmp/root-review/<name>/` successor). At most one subagent edits `src/`, catalog resources or tracked policy files at a time.
- The launching (main) thread owns integration: it reviews each subagent's result and diff, runs tests, resolves conflicts, and is the only agent that commits, pushes, or merges — and only when the user asks.
- Subagents must not commit, push, merge, change branches, or launch further subagents; they report results to the main thread.
- Run at most 20 concurrent subagents. Prefer `mode: "async"` and end the turn; completions wake the parent thread, so do not poll.
- Keep each returned `taskId`. Each review round is a new `delegate_task` call with its own stable `clientRequestId` and the full brief, prior findings and open objections; never continue a round through the child thread.
- Use `t3_thread_launch` only when the user asks for a separate top-level thread or worktree.

## Certification research
- Start from the newest session-status/resume doc in `docs/research/category-certification/` and follow its preservation rules.
- Never rerun or edit sealed or frozen artifacts in place; write fresh successor directories.

## Plugin Hub review token budget
- Keep every Plugin Hub submission strictly below 200,000 review tokens. Treat this as a standing requirement for all future updates.
- Preserve several thousand tokens of headroom; simplify repeated code as features grow without removing functionality or necessary tests.
- Comments and JavaDoc are removed by the Hub before tokenization. Shortening them does not reduce the review token count.
- Before publishing code updates, run the development-only estimator documented in `tools/review-size/README.md` and inspect changes outside its main-Java scope separately.
- Local estimates are not the official Hub count. Use the highest estimate for planning, report uncertainty, and do not treat a passing build as token-limit approval.
- When a maintainer provides a new count, record its exact source revision and use that pair to recalibrate subsequent estimates.
