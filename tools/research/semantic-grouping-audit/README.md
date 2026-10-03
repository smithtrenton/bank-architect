# Full semantic grouping research

Offline developer research for Bank Architect's own effective catalog and Ironman preset. Nothing in this directory is imported by the plugin or included in its production source set. Public OSRS Wiki requests occur only when a developer explicitly runs the research fetcher. No account configuration or bank is required.

## Reproduce the baseline

Run from the repository root with the existing Java 11 toolchain and Python 3.10 or newer:

```powershell
.\gradlew.bat exportEffectiveItemClassifications '-PauditOutput=tmp/semantic-audit/effective.tsv' '-PauditExcludedOutput=tmp/semantic-audit/excluded.tsv' --console=plain
.\gradlew.bat -I tools/research/semantic-grouping-audit/init.gradle exportSemanticAuditTags --console=plain
python tools/research/semantic-grouping-audit/audit.py fetch
python tools/research/semantic-grouping-audit/audit.py enrich
python tools/research/semantic-grouping-audit/audit.py join
```

The initialization script adds a developer-only `semanticAudit` source set for `PresetTagExporter.java`. It exports `PresetCategoryMapper` and `BankTags` results for every effective exact ID, plus the preview's optional potion-family dose placement. Input and output default to the existing `effective.tsv` and `preset-tags.tsv` paths; pass `-PsemanticAuditInput=...` and `-PsemanticAuditOutput=...` to use separate files and preserve an earlier baseline. This is a baseline: user overrides, runtime equipment facts, owned-tool selection and account layout options can change the actual preview.

`fetch` discovers available category fields, batches Bucket data at 5,000 rows and splits category queries to avoid the Wiki database join limit. It paginates by `page_name` with a greater-than filter. For each full batch it defers the entire final page-name group and rereads that group in the next query, so tied page rows cannot be silently skipped at a boundary. If a full batch contains no earlier complete page group to advance from, it fails explicitly because the page boundary cannot be proven complete. Each completed bucket records its total and unique exact-row counts and rejects duplicate full rows. It waits at least one second between requests. `enrich` adds the reviewed clue, costume storage, crop, key, unfinished-potion and warmth categories. Existing raw packets are reused; `--refresh` fetches a new snapshot. A changed cached query or pagination schema requires a new cache directory or `--refresh`; do not mix old offset-paginated packets with new keyset packets. Core/category identity drift fails the merge. All JSON reads explicitly use UTF-8, including on Windows.

## Join semantics

* Strict numeric item IDs are trimmed; historical, interface and beta ID prefixes are not converted into live IDs.
* All exact-ID Wiki item-infobox records remain, including non-default records. Multiple matches remain explicit.
* The separate `item_id` lookup bucket is fetched too. Literal numeric ID links remain separate from item facts: some omit historical/interface/beta prefixes or originate in construction definitions. Lookup-only hits never propagate semantic roles; exact source-key and namespace warnings remain visible.
* Equipment joins use `(page_name, page_name_sub)`. A unique-page fallback is labeled separately; it is weaker variant evidence.
* Positive category fields are page-scoped facets. False or missing fields never establish absence. Aggregated positives do not erase the individual source records in `joined.jsonl`.
* Recipe edges use Wiki titles and subpage titles, with no display-name alias propagation. Input/output ID pools in the recipe export are candidates, not proof for every variant.
* Catalog family hints produce a separate weak review queue. They never propagate source facts or classifications.
* Local layout/set memberships are labeled baseline. Source-backed reviewed dose/food groups carry their source revision links separately.
* Source URLs, raw query text, retrieval dates and SHA-256 manifests stay in the local cache. Aggregate timestamps indicate generation; raw packet timestamps indicate acquisition. Category names unavailable on the Wiki remain explicit.

## Outputs

Generated files are under `tmp/semantic-audit/`, which is ignored by the repository:

| File | Purpose |
| --- | --- |
| `registry-universe.csv` | Accounts for every registry ID, including explicit cache exclusions and null/invalid names. |
| `catalog-semantic-audit.csv` | Every named effective ID, actual preset tags, source coverage, positive roles and detectors. |
| `joined.jsonl` | Complete per-ID matched Wiki records, equipment joins and recipe relations. |
| `mechanical-findings.csv` | Review signals, not confirmed defects or an automatic migration. |
| `full-grouping-audit.csv` | Full per-ID audit with domain review and exact group memberships. |
| `grouping-groups.csv`, `grouping-edges.csv` | Exact member/rank edges for the local baseline and separately labeled sourced groups. |
| `recipe-workflow-edges.csv` | All fetched recipe material/tool/facility edges and their candidate ID pools. |
| `wiki-version-family-candidates.csv` | Exact-ID explicit Wiki version pools; candidate relationships rather than proof of identical function or state transitions. |
| `unverified-family-candidates.csv` | Weak catalog family clusters; no established identity or transformation relationship. |
| `domain-evidence.jsonl` | Original domain review rows without flattening their uncertainties into a majority decision. |
| `summary.json`, `grouping-summary.json` | Coverage, counts, provenance and limitations. |

The domain builders below recreate the mechanical review artifacts. They use explicit UTF-8 and the cached public sources; Node.js is needed for the gear builder. Curated policy and grouping proposals still require review when a new source snapshot changes mechanics. Acquire the planned full articles (including a pinned Collection Log revision), then run from the repository root:

```powershell
python tools/research/semantic-grouping-audit/fetch-articles.py
python tools/research/semantic-grouping-audit/review-coverage-variants.py
python tools/research/semantic-grouping-audit/review-supplies-herblore.py
python tools/research/semantic-grouping-audit/review-farming-materials.py
python tools/research/semantic-grouping-audit/review-loot-quests-clues.py
python tools/research/semantic-grouping-audit/review-utilities-containers.py
node tools/research/semantic-grouping-audit/review-gear-cosmetics.js
python tools/research/semantic-grouping-audit/consolidate.py
python tools/research/semantic-grouping-audit/report.py
```

The six review domains are gear/cosmetics, supplies/Herblore, Farming/materials, utilities/containers, loot/quests/clues, and coverage/variants. Their scopes deliberately overlap. Domain records represent mechanical extraction and policy analysis; they must not be described as every item having been manually checked against article text.

## Grouping policy

Preserve exact identity and state. Record combat use, skill utility, ingredient or output stage, clue requirement, reward provenance, log membership and storage eligibility as separate roles. Derive bank placement from the selected workflow and player preferences. In particular, zero bonuses do not mean junk; quest association does not mean quest-only; costume storage does not mean cosmetic-only; Collection Log membership does not require a collection tab; and being an ingredient does not erase equipment or food identity.

Missing exact-ID facts require typed cache links or direct variant research before canonical-state propagation. Wiki categories and title-level recipe relations alone cannot prove those links. The offline audit may suggest focused exact-ID corrections or new semantic families; it does not alter production classifications.

## Attribution

OSRS Wiki facts and page text: [OSRS Wiki](https://oldschool.runescape.wiki/), CC BY-NC-SA 3.0. Bucket snapshots retain their query URLs and retrieval timestamps; article acquisitions and curated source metadata retain revision links where available. Bucket rows do not include per-page revision IDs. Bucket schema: [RuneScape:Bucket](https://oldschool.runescape.wiki/w/RuneScape:Bucket). Local memberships and effective classification are this repository's original baseline. Preserve attribution and confidence/scope fields when sharing derived research.
