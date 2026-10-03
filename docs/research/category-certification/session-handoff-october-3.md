# Semantic certification session handoff — 3 October 2026

The full goal remains active: certify every item category assignment using exact Wiki semantics, across the frozen **34,085 IDs**. This checkpoint does not claim completion or additional ledger approvals.

## Current authoritative state

- Published category ledger: **2,545 approvals** (2,278 certify, 267 revise), **31,540 unresolved**. Authoritative files are `docs/research/category-certification/approved-assignments.tsv` and its adjacent manifest, not older default-name manifests under `tmp/`.
- The full local decisions are `tmp/category-certification/root-approved-decisions-with-clue-scrolls.jsonl`. Decision SHA-256: `2eea806d0c1d6f977c904769df09218b3e99677ffc836498b0f8b7a6f73d300c`.
- This turn applies **40 reviewed potion/drink corrections** through the exact override table and three shadowing supplemental rows. The new compiled export changes exactly those 40 IDs; all other 34,045 rows and every existing tag are unchanged. All prior 2,545 approvals remain applied.
- Production is ahead of the certification ledger for these 40 IDs. Formal potion policies, detached approval pins, emitter support and the updated approval snapshot are **not implemented yet**. Do not report these as new published certifications.
- Current compiled export: `tmp/root-review/potion-production-application-v1/after-coverage.tsv`, SHA-256 `271ea9bb964aeff67d970ff8c9f4f81edf48b139f6c63f58e317d3a76ff1d68d`. Whole-scope delta proof is adjacent `coverage-delta-verification.json`.
- The previous published export remains `tmp/category-certification/after-coverage.tsv`, SHA-256 `1865f35dbfeef4d42f1b6703012fe6eeb4b1d4b0bb452e9259ae19480a294ce3`. Do not confuse it with the new compiled checkpoint.

## Completed validation

Java 11 (`C:/Users/smith/.jdks/temurin-11.0.32.1`) offline `check jar exportEffectiveItemClassifications` passed. All 1,161 existing tests passed; no new test methods or regression suites were added. The 150 random scenarios and 1,800 aggregate scenarios completed without failures, and all four simulation baseline files matched. Existing unit methods were extended/updated for the reviewed states and exporter expectation.

The full 34,085-ID delta check matches every one of the **387 proposed potion targets**. `ledger.py verify-applied` against the new export verifies all 2,545 published approvals. This proves application, not policy approval.

The jar is `build/libs/ironman-bank-architect-0.7.1.jar`, SHA-256 `fc3bffa93bae6f51db0cfe709468e376866cbe8d01d9d5dedc351d8cb05c55e9`. The development Hub estimator passed: highest estimate 197,004, headroom 2,996. Main Java is unchanged; the two resources and four existing unit files were inspected separately. This is not an official Hub count. Expected Git LF/CRLF warnings are present.

## First next step: potion ledger integration

Read `tmp/root-review/potion-primary-policy-draft-v1/README.md`, its policy draft and replay helper. Immutable draft SHA-256: `976bc4853125d68c2466074d39c5dcf568c04a18498406e759d48479f52dbce4`.

All 417 IDs partition exactly into **387 proposed assignments** (347 unchanged, 40 corrections), **20 holds**, and **10 no-bank candidates**. Tags and secondary roles are unassessed. The main-thread source read is complete for all 123 titles / 417 IDs, pinned by `tmp/category-certification/root-review/potion-drink-417-root-semantic-review-v3/per-title-root-review.jsonl` SHA-256 `8900d07a0c924cb46683d9d3d1fa1e789558d85d504f6ebd83782ac7e50df99e`. Earlier prep contains stale v2 enrichment; the new draft deliberately rebuilds from v3.

Independent full-source checks:

- `tmp/root-review/potion-40-revisions-adversarial-v1/`: all 40 revised states. Root resolves antifire subtype precedence consistently with ordinary antifire families: a persistent Dragon Slayer I unlock is a requirement fact, not location/mode-limited consumption. IDs 11505, 11960, 21994, 22221 retain full-dose `potion-dose-2`. Store the quest requirement explicitly; do not erase it.
- `tmp/root-review/potion-347-retained-adversarial-v1/independent-semantic-check-v1.json`, SHA-256 `95a45263fea90710c71dcfda5a3bfb0801a950cf6dc2d33f4adb169926b0f8c3`: no route change found, 110 own pages checked. Ancient brew needs its own Effects paragraph rather than a creation-only lead or Ancient mix mechanics.

Next create separate unchanged/correction policies and a provenance verifier, intentionally update `root-policy-approvals.json` and `emit-root-approved-decisions.py`, including exact metadata-derived partial-dose tab mapping. Replay independent source and scope gates; preserve all prior decisions and all other unresolved rows. Do not invent targets from the after-export. Then publish the updated snapshot. Approval is a root semantic decision, not a candidate replay or majority vote.

## Bank-ignore policy — implementation pending

The user's instruction is to ignore items that cannot be banked. Preserve every actual observed bank row, including quantity-zero valid placeholders, legacy items and exploit-created items. Notes convert at deposit; typed identity edges do not grant raw-item semantics. There is currently no general unobserved catalog-derived deposit target enumerator, so do not filter `BankSnapshotReader`, preview entries or catalog lookup. `Optional.empty()` is not a catalog tombstone.

- Proposed gate: `tmp/category-certification/root-review/runtime-bank-ignore-gate-v1/`. It has 726 source proof cases: 724 own `bankable=No` plus two direct no-deposit blaster proofs. The old draft partitions into 720 strict candidates (708 in universe, 12 outside) and six holds (4678–4681 Canopic jars, 30808 Jim's wet cloth, 10835 Bulging taxbag). No runtime/exporter exclusions are applied.
- Integration plan: `tmp/root-review/bank-ignore-integration-plan-v2.md`. The developer exporter must retain every ID and use a distinct `EXCLUDED_NON_BANKABLE` scope after approval; it must not drop the full denominator or silently fall through to another catalog.
- Latest context audit: `tmp/root-review/bank-ignore-conditional-context-v2/`. **Read `INPUT-SET-RECONCILIATION-ADDENDUM-v1.md` first.** The audit scanned a preliminary 720-ID list: 718 match the runtime strict gate, two were already-held legacy/exploit cases, and it missed the two separately proven blasters. Do not claim its full-page review covers the gate's entire 720 set.
- Cyan crystal **6643** has explicit post-quest bank failure but unclear pre-quest scope. Reassess or quarantine this qualifier before approving a universal exclusion; absence of pre-quest evidence is not permission or prohibition.
- `tmp/root-review/activity-potion-bankability-v2/`: all 20 potion holds remain unknown-hold. Prayer enhance 20961–20972 has activity-level inference but unpinned bank-context sources; Egniol 23882–23885 and Deadman 26150–26153 lack direct bank denial. Pin stronger sources before excluding. Cannot-leave/tradeable/noteable alone do not prove bank eligibility.

## Full scope and metadata research

- Corrected full-scope research reconciliation: `tmp/category-certification/root-review/full-scope-coverage-independent-v2/`. All 34,085 IDs are retained across eight disjoint ownership shards. Research status labels and source availability are not approval counts. Older local attached manifests may still report 2,252; the committed authoritative manifest reports 2,545.
- Materials V15 is **698 IDs / 493 article groups** at `tmp/root-review/materials-v15-sourcefunction-independent-v1/sourcefunction-reading-packet-v1.json`, SHA-256 `fb5531a00c7197e274e385f4bd3f8d3a61f9f5f1475097fa3e2248d0659ff09b`. Root has not completed the full source-function review. The historical 943 residual scalar is wrong: the source-backed exact residual is 967; do not propagate 943.
- Materials 233-ID second-pass candidate facts: `tmp/root-review/materials-233-function-facts-v1/`. All 233 records passed `semantic-records.py validate --sources` in root. They remain needs-review/candidate, not approvals. Seven cohorts separate mode states, route proposals, competing uses and gaps.
- The committed extensible metadata baseline holds 52,777 unassessed records: 34,085 category, 1,926 tag, 16,766 raw fact assessments. Read `semantic-metadata.md` and the committed schema/tool before adding facts. Source replay does not grant semantics. Numeric facts require units; preserve state/conditions/requirements/effects/recipes and contradictory claim sources.
- `tmp/root-review/tag-vocabulary-candidates-v1/`: **148 tag slugs / 1,926 ID-tag pairs**, unregistered definition registry, six narrow source-backed candidate wordings. Category approval does not certify tags; do not propagate a definition example to all IDs bearing a slug.
- `tmp/root-review/wiki-field-predicate-pilot-v1/`: 98 raw field keys across 16,054 exact Wiki observations; 21 raw-string candidate facts passed source replay. Empty strings, zero and missing remain distinct.
- `tmp/root-review/semantic-format-postcommit-audit-v2/assessment.md`: final baseline/source validation passed. Remaining future-design issues: predicate-version changes appear as remove/add; claimSource must be distinct to preserve conflicts; compare does not group conflict sets; historical schema versions need retention for old manifest replay.

## Operating constraints and resume

Use up to 20 Luna (`gpt-6-luna`) agents at high effort for research; only root edits production/official approvals. Project `.codex/config.toml` requests 20 spawned agents with Luna/high defaults, committed in `fbb8100`. Current session still reports 11 total slots; restart then inspect the actual available limit, which overrides the requested allowance if lower. All review agents were asked to finish bounded checkpoints before this turn closes.

Do not follow the old Claude-only implementation workflow; the user explicitly waived it. Preserve the user's Collection Log heading. No regression suites; use existing-level unit checks. Never edit the live RuneLite config. Keep GPG signatures. Fetch upstream and rebase only if behind; upstream's actual default branch is `main`, not `master`. Avoid staging the many unrelated untracked research files or the preexisting policy stat changes with empty content diffs.

Outstanding user taxonomy choices from earlier work: Mushroom 6004, nontransport tablets 8014–8022, bankable edible holiday items, zero-stat quest wearables, and activity/mode copies. Raise a multi-choice dialog when a real unresolved preference blocks a specific reviewed rule.

The goal is incomplete. Resume from these checkpoints; do not restart the analysis or count source integrity, raw metadata, candidates or production-only application as new certifications.
