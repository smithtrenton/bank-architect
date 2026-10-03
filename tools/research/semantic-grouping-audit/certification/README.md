# Current preset category certification

This developer-only audit builds immutable-input reviewer packets from the compiled current coverage export. It does not edit plugin data. It accounts for every row in `current-coverage.tsv`, including 32,586 named effective records, 343 supplemental records, 606 cache-only records, and 550 null/invalid-name records. The `auditScope` field is retained as research context, never as proof of bankability or exclusion. A source-backed explicit exclusion can be reviewed; the scope flag alone cannot justify it.

From the repository root, build the eight disjoint packets:

```powershell
C:/Users/smith/.local/bin/python.exe tools/research/semantic-grouping-audit/certification/ledger.py build
```

The default inputs are `tmp/category-certification/current-coverage.tsv`, `tmp/semantic-audit/joined.jsonl`, `tmp/category-certification/wiki-articles/article-index.json`, and the identity edge/report under `tmp/category-certification/`; output goes to a deterministic hash-versioned directory beside `tmp/category-certification/reviewer-packets/`. This prevents a new source snapshot from overwriting packets that reviewers already reference. Override inputs with `--coverage`, `--joined`, `--article-index`, `--identity-links`, `--identity-report`, and `--output` when certifying another compiled snapshot. `evidence-summary.json` contains input and packet SHA-256 hashes, full row/scope/category counts, and direct exact-match coverage.

Shard ownership is fixed by the compiled current category: `gear` (GEAR); `skilling-farming` (SKILLING, FARMING); `supplies-herblore` (POTION, HERBLORE); `tools` (TOOL); `clue-unique` (CLUE, UNIQUE); `currency-runes-teleport` (CURRENCY, RUNE, TELEPORT); and cleanup split into `cleanup-quest` (CLEANUP with subcategory other than `cleanup`) and `cleanup-other` (CLEANUP with subcategory `cleanup`). Shard IDs are disjoint and their union must equal the complete export.

Each JSONL packet row carries the exact current ID, names, scope, category, subcategory, Ironman tab key, tags, and separately labeled evidence bundles. Wiki article sources are attached by the collector's exact numeric `exactInfoboxItemIds`, including every matching source page even when the older joined file lacks that match. Each retains its pinned article revision, URL, local text path, and SHA-256. Typed cache edges touching the ID are exposed as identity evidence candidates; they never propagate semantic roles by themselves. Lookup-bucket links, recipe-title relations, and baseline role tags remain visibly separate from direct item facts. No prefix normalization, name joins, family propagation, absent-field inference, or majority vote is performed.

Reviewers return one JSONL decision per packet ID using this shape:

```json
{
  "itemId": 123,
  "shard": "gear",
  "decision": "certify",
  "proposedCategory": "GEAR",
  "proposedSubcategory": "combat-gear",
  "proposedTags": ["ammunition"],
  "proposedRoles": ["combat_equipment"],
  "proposedIronmanTabKey": "combat-gear",
  "semanticPredicate": "The exact item ID is retained and placed according to its documented combat function.",
  "rationale": "Direct item evidence establishes the listed function and retained state.",
  "evidence": [
    {
      "kind": "exact_wiki",
      "sourceTitle": "Example",
      "source": "https://oldschool.runescape.wiki/w/Special:Redirect/revision/12345678",
      "sourceRevision": 12345678,
      "sourceHash": "sha256:...",
      "itemId": 123,
      "quote": "Short supporting excerpt"
    }
  ],
  "identityLinks": [],
  "reviewer": "gear"
}
```

Allowed evidence kinds are `exact_wiki`, `typed_identity`, `local_source`, and `direct_variant`. Cite a pinned revision and the exact article-index hash. Keep quoted excerpts short and exact. A `direct_variant` record must name the reviewed numeric ID. Exact Wiki evidence for an alias may name a different canonical ID only through a typed identity link that explicitly names directed `fromItemId`/`toItemId`, relation, cache field/opcode, cache artifact path/hash/revisions, and identity-links index SHA-256. The audit matches that claim against an actual `identity-links.jsonl` row, supported cache opcode semantics, and frozen cache hashes in `identity-report.json`. Its nested exact Wiki fact must name the canonical `toItemId`; a lookup pointer cannot carry semantics. Every related ID still receives its own decision; group or family membership does not transfer facts.

`certify` means the reviewer has evidence for the semantic predicate and explicitly confirms that the proposed category, subcategory, tags, and tab key equal this compiled row. `proposedRoles` records only roles actually assessed by the decision: use a role list when the evidence supports that set, `[]` only when review supports no role, and `null` with `roleClaimScope: unassessed` when no role set was reviewed, including unresolved rows. A directly reviewed primary workflow can be certified while other roles and retained tags remain unassessed. A different proposed runtime assignment is a `revise` finding, which remains pending until the production data is changed and a fresh export is reviewed. A `revise` decision must name the target category, subcategory, tags, and tab key with supporting evidence. `exclude` requires direct source evidence that the item does not belong in the preset universe; it must be applied as a non-effective row in the fresh export. Use `unresolved` for missing, weak, conflicting, or unsupported evidence; state the evidence gap in the rationale. Current assignment alone, an existing tag, a candidate detector, a family name, a recipe title, a false Wiki facet, or another reviewer’s vote can never certify a row.

Validate merged reviewer files against the exact packets before claiming completion:

```powershell
C:/Users/smith/.local/bin/python.exe tools/research/semantic-grouping-audit/certification/ledger.py validate --packets tmp/category-certification/reviewer-packets tmp/category-certification/decisions/*.jsonl
```

Reviewers can validate their own shard while other domains are still working:

```powershell
C:/Users/smith/.local/bin/python.exe tools/research/semantic-grouping-audit/certification/ledger.py validate --packets tmp/category-certification/reviewer-packets --shard supplies-herblore tmp/category-certification/reviews/supplies/decisions.jsonl
C:/Users/smith/.local/bin/python.exe tools/research/semantic-grouping-audit/certification/ledger.py audit-sources --packets tmp/category-certification/reviewer-packets --shard supplies-herblore tmp/category-certification/reviews/supplies/decisions.jsonl
```

`validate` checks shard accounting and decision schema while allowing unresolved rows; it does not mean certification succeeded. It rejects missing or duplicate IDs, wrong shard ownership, unrecognized decisions/evidence types, absent rationale/predicate/evidence/roles/tags, malformed identity links, unsupported local-only semantic claims, Wiki evidence without an exact ID and revision/hash plus either a verifiable excerpt or structured exact-variant facts, and any `certify` proposal that differs from the frozen current category/subcategory/tags/tab. After production changes, compare the approved targets against the fresh compiled export while keeping original packet ownership:

```powershell
C:/Users/smith/.local/bin/python.exe tools/research/semantic-grouping-audit/certification/ledger.py complete --coverage tmp/category-certification/current-coverage-after.tsv --article-index tmp/category-certification/wiki-articles/article-index.json tmp/category-certification/decisions/*.jsonl
```

The `audit-sources` gate can run before review is complete. It checks source hashes/revisions, excerpts or structured facts against the indexed exact-ID variant, directed typed-cache edges against the authoritative edge export/opcode/relation and frozen archive, and canonical Wiki facts. Multi-variant canonical pages are checked against their exact `id`, `id1`, `id2`, and subsequent numeric ID parameters as well as the pinned article index. Shard validation permits a typed link to a canonical ID owned by another shard while requiring each decision to belong to its frozen owner shard. It reports separate totals for decision rows, actionable rows, exact Wiki evidence records verified, typed edges verified, and unresolved rows skipped; packet accounting must never be reported as the number of certified assignments. The `complete` gate repeats those checks, then requires zero unresolved IDs and exact runtime application by ID (including category, subcategory, tags, tab and exclusions). A clean `validate` run proves only accounting and schema consistency; it does not certify decisions. Even a successful `complete` run establishes technical completeness only: independent semantic review and an approved rule or per-ID decision remain required.

Generate a reproducible priority report across the full assignment universe after reviewer decisions are available:

```powershell
C:/Users/smith/.local/bin/python.exe tools/research/semantic-grouping-audit/certification/ledger.py gap-report --packets tmp/category-certification/reviewer-packets --coverage tmp/category-certification/current-coverage.tsv --output tmp/category-certification/coverage-gap-priority.json tmp/category-certification/reviews/cleanup-other/decisions.jsonl tmp/category-certification/reviews/cleanup-quest/decisions.jsonl tmp/category-certification/reviews/collections/clue-unique-corrected.jsonl tmp/category-certification/reviews/gear-v2/decisions.jsonl tmp/category-certification/reviews/materials/skilling-farming.jsonl tmp/category-certification/reviews/supplies/decisions.jsonl tmp/category-certification/reviews/tools/decisions.jsonl tmp/category-certification/reviews/transport/decisions.jsonl
```

The JSON report retains one row per exact ID and input hashes, groups counts by shard and source scope, ranks unresolved groups, and records schema/source-audit outcomes separately. An unresolved row with an exact Wiki page or typed-link candidate identifies a review opportunity; source availability does not support a category by itself. A source-integrity pass establishes that cited evidence matches pinned artifacts, not that the proposed semantic decision is correct or root-approved.

For independent primary-source checks of the gear evidence, run:

```powershell
C:/Users/smith/.local/bin/python.exe tools/research/semantic-grouping-audit/certification/verify-gear-bonus-sources.py
```

This read-only verifier selects the 2,184 `certify` rows and 37 gear-v2 `revise` rows whose rationale addresses an equipment slot. It validates the joined snapshot and exact row hashes, follows the joined page to the pinned article revision, parses the raw `Infobox Item` and `Infobox Bonuses` templates, binds the numeric ID to its item version/label and bonus-template suffix, and compares the explicit slot and all 14 combat-stat fields. It records the exact item variant's `equipable` and `options` fields separately; bonuses alone never establish an active Wear/Wield/Equip option. Findings are written to `tmp/category-certification/reviews/gear-v2/bonus-source-proof.json` with input hashes and per-field comparisons. `consistent` means the exact pinned source and joined row agree and the selected variant has explicit active equipment evidence; it does not approve a category decision. The verifier stops if the expected 2,184 plus 37 input scope changes; `--allow-count-change` is available for a deliberately reviewed new scope.

Create the separate root-approved decision snapshot with:

```powershell
C:/Users/smith/.local/bin/python.exe tools/research/semantic-grouping-audit/certification/emit-root-approved-decisions.py
```

This emitter reads only the seven named root policy files, the separate `root-policy-approvals.json` record and immutable reviewer packets. It verifies each policy case's exact item ID, title, revision, article hash, literal excerpts, tag excerpts, and exact variant fields against the pinned article index and raw text. It emits all 34,085 IDs; only the 1,169 unique policy cases (230 applied corrections and 939 unchanged equipment placements) are actionable by default, while all other rows stay unresolved. The manifest records the hashes of every input packet, policy, coverage snapshot, article index, JSONL output, and compact TSV. Packet ownership stays frozen even when the approved category changes. The proposed tab comes from the approved category's explicit preset route (plus the mapper's enumerated ID-specific routes); the emitter never reads `after-coverage.tsv` to choose a target. `proposedRoles: null` with `roleClaimScope: unassessed` means no supplemental role set was assessed; a nonempty list with `supplemental_only` contains only the policy's added role claims. Unresolved `proposedTags: []` means no tag proposal is being made, not that the item has no tags. By default, the TSV and manifest names follow the JSONL output name; custom paths can be supplied with `--summary-tsv` and `--manifest`.

When the separately root-reviewed clue-scroll rule and its matching decision file are available, merge only those primary-assignment approvals with:

```powershell
C:/Users/smith/.local/bin/python.exe tools/research/semantic-grouping-audit/certification/emit-root-approved-decisions.py --certifications tmp/category-certification/reviews/root-clue-scrolls/decisions.jsonl --output tmp/category-certification/root-approved-decisions-with-clue-scrolls.jsonl --manifest tmp/category-certification/root-approved-decisions-with-clue-scrolls-manifest.json
```

The optional file must contain every ID listed by `clue-scroll-approved-rule.json`, with direct exact Wiki evidence and its fixed CLUE/treasure-trail/clues-cosmetics target; unrelated unresolved rows from the full clue shard are ignored. The emitter independently recomputes the raw clue predicate and compares all supplied proof fields against those results, rejecting substituted citations or altered semantic claims for approved IDs. It preserves the frozen packet's tags and retains only the directly reviewed `treasure_trail_step` role claim. The default output remains the distinct seven-policy, 1,169-case snapshot; merging the 637 clue placements produces 1,806 approved assignments.

After the production export has passed its build and simulation checks, validate and audit a snapshot with:

```powershell
C:/Users/smith/.local/bin/python.exe tools/research/semantic-grouping-audit/certification/ledger.py validate --packets tmp/category-certification/reviewer-packets tmp/category-certification/root-approved-decisions.jsonl
C:/Users/smith/.local/bin/python.exe tools/research/semantic-grouping-audit/certification/ledger.py audit-sources --packets tmp/category-certification/reviewer-packets tmp/category-certification/root-approved-decisions.jsonl
C:/Users/smith/.local/bin/python.exe tools/research/semantic-grouping-audit/certification/ledger.py verify-applied --coverage tmp/category-certification/after-coverage.tsv tmp/category-certification/root-approved-decisions.jsonl
```

The source audit establishes artifact integrity, not independent semantic approval. The applied gate checks only actionable exact-ID proposals against the fresh compiled export; unresolved rows remain outside that check. Record actionable-row and verified-evidence counts separately from the complete 34,085-row accounting total.

Byte-hashed approval policies, replay scripts and the durable ledger use explicit LF checkout rules in `.gitattributes`. Frozen local source artifacts retain their acquired bytes. See `docs/research/category-certification/README.md` for the authoritative 1,806-assignment snapshot and exact replay commands.

The unchanged Gear policy is checked by `verify-gear-primary-policy.py` before its cases are emitted. That helper verifies the root-recorded approval status, exact frozen source/proof/parser hashes, unique IDs, literal primary/bonus excerpts, exact active item state and compatible slot/current route. The source-proof row hash binds to all 14 independently compared combat-stat fields and slot. Existing tags are retained and supplemental roles remain unassessed. The recorded review and the source verifier are separate: positive mechanical checks do not establish the semantic premise. The root-reviewed set contains 939 cases after direct-source review rejected activity-only Castle Wars ammunition 30694/30696 from the 941-case draft.

The separate approval record pins all seven exact file hashes, canonical full contents and approved numeric-ID sets. It rejects edited policies even when the replacements cite valid source facts. The Gear helper independently enforces that pin, the source-review/filter/adversarial artifact hashes, the exact reviewed cohort after activity holds, and the full own-subject source paragraph. Intentional policy edits must be independently reviewed before updating the approval record; technical provenance checks cannot authorize them.
