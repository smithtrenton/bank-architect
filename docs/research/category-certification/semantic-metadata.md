# Reusable semantic metadata

The semantic store preserves item knowledge for future grouping and sorting rules. It is developer research data; the plugin does not load these files. Current runtime tags remain in `item-usage-tags.tsv` and current category approvals remain in `approved-assignments.tsv`.

`semantic-records-baseline.jsonl.gz` is a committed, UTF-8 JSONL snapshot compressed with deterministic gzip. It retains all **34,085 exact item IDs**, **1,926 current usage-tag assignments**, **16,054 suffix-resolved Wiki infobox observations**, and **712 additional literal bankability-field observations** within that universe. Every imported record is explicitly **unassessed / candidate**. This snapshot adds no category, tag, role, or exclusion approval. The existing 2,545 approved primary assignments remain a separate, authoritative ledger.

The manifest pins the compiled coverage, observation inputs, schema, importer, compressed bytes and decompressed JSONL. It identifies the source Git revision without assuming that HEAD alone proves a compiled export. Twelve bankability observations outside the frozen universe are listed separately; they do not create extra item assignments. Detailed source caches and raw research inputs stay under ignored `tmp/`; retain those immutable inputs for full source replay. A fresh checkout can validate and compare the committed records, but raw-byte replay requires the matching cache. A checksum does not reconstruct missing evidence.

## What a record preserves

The versioned schema is `tools/research/semantic-grouping-audit/certification/semantic-records.schema.json`. Each record carries an exact item ID, stable claim ID, claim type, predicate and predicate version, assessment status and review stage. Facts additionally carry a typed value, applicability/state qualifiers and evidence or raw observation provenance. New namespaced predicates and `extensions` can preserve new mechanics without changing the envelope or adding a Java field.

Keep these layers separate:

- **Raw observations** preserve source fields, their exact suffix/shared binding, original strings, revision, source hash and literal context. They are useful extraction results, not reviewed mechanics. The broad infobox snapshot preserves all selected fields, including fields current rules do not consume; infobox `No` stays the string `"No"` until interpreted in context.
- **Reviewed facts** describe effects, requirements, equipment/charge/dose state, recipe roles, storage restrictions, transformations and other actual mechanics. A predicate definition specifies its meaning, type, units, conditions and evidence requirements. Never infer sibling state facts from a name/family or transfer usage through a note/placeholder link.
- **Tag assessments** associate reviewed or pending functional roles with an exact ID. Imported legacy tags have `definitionStatus: unregistered`; their spelling is preserved, but no new definition or source validation is invented. Before a rule depends on a tag, register a versioned meaning and review its own evidence.
- **Derived tags** retain `factRefs` and the generating rule ID/version in `derivation`. Keep the input facts so another rule can recompute the result.
- **Placement and preferences** are the current category/subtype/tab and account-specific grouping policy. They do not become universal Wiki facts or automatic discard instructions.

A record ID identifies a stable claim slot, not its current value or evidence revision. Category records use the exact item's primary-placement slot, so a category move compares as a changed assignment. `category.name` is the stable runtime category identifier, not a display heading. Tag slots use exact ID and namespaced tag name. Fact slots use the predicate/version, state/qualifiers and optional stable `claimSource`; independent contradictory sources can therefore coexist. Use distinct `claimSource` values for conflicting assertions of the same predicate/context, preserve both, and record the conflict as needs-review. Do not put revision IDs or current values into `claimSource`, which would hide updates as new identities.

Quantities require explicit namespaced units, such as `osrs:hitpoints`, `osrs:game-tick`, `count:dose` or `ratio:percent`. Numeric fact values require `factUnit`; structured ranges, effects and recipe quantities must give each component its unit according to the versioned predicate definition. Formula text remains inert source text until a named, versioned evaluator supports it. Preserve activation versus creation requirements, consumed versus reusable state, target, timing, activity/mode and prerequisites as applicability qualifiers. Unknown predicate versions remain stored and must not activate a rule.

`status` assesses the complete assertion: supported false is a sourced negative; refuted true means evidence contradicts the asserted true value. Missing fields/records mean unknown, never false. Zero, empty list and explicit false are distinct observed values. An unassessed extraction is not an approval, even if its source hash replays successfully. `root-approved` can record a reviewed hold (`needs-review`); rule consumers may use only positively supported, scope-compatible assertions whose approval policy is independently replayed.

Future approvals carry the exact canonical claim hash, approval scope, reviewer and detached policy hash. Primary-placement approval cannot approve a usage tag. The offline validator checks the claim-content/scope pin, but does not grant approval or replace the existing detached-policy verifiers.

## Conditions and source fidelity

Bankability is an eligibility fact, separate from an item role and the user's ignore policy. Canopic jars 4678–4681 have a literal Wiki `bankable=No`, while their own prose permits banking during the quest and forbids it afterward. Jim's wet cloth 30808 no longer accepts deposits, but preexisting bank copies remain. Preserve those conditions and distinguish **can deposit now**, **may already occupy a bank**, and **ignore policy applies**. A single unqualified infobox boolean cannot decide all three.

The bankability adapter retains full bound infoboxes and leads. Its copied reviewer recommendations live under `extensions.candidate-advisory`; they remain proposals and may be superseded by another review. The generic infobox adapter retains suffix-resolved raw field observations and source/index references without asserting that their prose interpretation is complete. Raw pages contain additional relevant effects and recipe details not yet normalized into reviewed facts. Retain the pages for later extraction; the current store is extensible, not an exhaustive semantic interpretation of every page.

Exact Wiki evidence stores its own ID field/literal and bound infobox, revision, URL, source path/hash and excerpt. `--sources` replays direct Wiki source hashes, numeric ID fields, supplied variant fields, infobox and excerpts, including retained leads. Generic raw observations replay their source hash and collector ID membership; that is explicitly weaker than independently proving every interpretation. The source path must resolve inside the repository. The current source mode rejects other evidence kinds rather than pretending to replay typed-cache authority. Use the existing identity/policy verifiers for those records. Cache edges establish representation relationships, never function inheritance; a zero target is a sentinel, not an item ID.

The bundled standard-library validator implements only the JSON Schema keywords used by this schema and rejects unknown schema keywords. URI/date-time `format` fields are annotations; it does not claim full JSON Schema implementation or verify source titles against live pages. Immutable source revisions and local hashes take precedence over a current Wiki page.

## Compare future runs

Validate the committed snapshot without needing the raw cache:

```powershell
C:/Users/smith/.local/bin/python.exe tools/research/semantic-grouping-audit/certification/semantic-records.py validate docs/research/category-certification/semantic-records-baseline.jsonl.gz --manifest docs/research/category-certification/semantic-records-baseline-manifest.json
```

Add `--sources` when the matching pinned inputs are present. Create each new snapshot at a new path; bootstrap and comparison refuse to overwrite historical inputs or existing outputs.

```powershell
C:/Users/smith/.local/bin/python.exe tools/research/semantic-grouping-audit/certification/semantic-records.py bootstrap --coverage PATH_TO_NEW_COVERAGE --revision SOURCE_GIT_REVISION --output PATH_TO_NEW_RECORDS.jsonl.gz --manifest PATH_TO_NEW_MANIFEST.json
C:/Users/smith/.local/bin/python.exe tools/research/semantic-grouping-audit/certification/semantic-records.py compare docs/research/category-certification/semantic-records-baseline.jsonl.gz PATH_TO_NEW_RECORDS.jsonl.gz --output PATH_TO_NEW_REPORT.json
```

The optional `--wiki-observations` adapter retains normalized exact-variant field extractions; `--observations` currently accepts the literal bankability census. These adapters do not perform a fresh Wiki download. Additional extractors should emit the same versioned fact format and preserve source scope and candidate status.

Comparison reports record additions/removals, item identity labels, assertion/value/status, catalog assignment, evidence, review, definition, derivation and extension changes separately. A removed record is a coverage change, not semantic refutation; a new Wiki revision is an evidence change, not automatic permission to change a tag. Validate the input manifests first when comparing published snapshots. Applicability changes produce distinct qualified claim keys; interpret those added/removed claims alongside their preserved source context.
