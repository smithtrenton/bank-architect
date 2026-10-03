# Category certification checkpoint — 3 October 2026

The current default preset has **not** been fully semantically certified. The earlier full-export passes and the completed 356 missing-item review do not establish correctness of every current assignment. This checkpoint applies 44 independently reviewed exact-ID corrections; all other pending reviewer findings remain outside production.

## Scope and evidence

The frozen compiled coverage export contains 34,085 assignments: 32,586 named effective records, 343 supplements, 606 cache research records and 550 null/invalid-name records. Research flags do not prove bankability, exclusion or semantic function. Runtime routes and raw catalog assignments must be distinguished, especially for placeholders.

The acquisition downloaded 11,396 pinned Wiki articles, with zero acquisition errors or requested-ID gaps after fixing an infobox parser that consumed the next field after a blank value. Article acquisition is evidence collection, not category certification. Revisions, literal excerpts, exact infobox IDs and article SHA-256 values for this checkpoint are retained in:

- `tools/research/semantic-grouping-audit/certification/cleanup-other-policy.json`: 35 exact-ID corrections independently reviewed in the main thread.
- `tools/research/semantic-grouping-audit/certification/materials-approved-policy.json`: nine additional exact-ID corrections independently reviewed in the main thread.

Current reviewer scripts and cache identity research are still being tightened. Their candidate or first-pass decisions are not approved changes. No classification is certified solely from a keyword, name family, equipment flag, zero-valued equipment table, existing tag, quest association or absent Wiki field.

## Applied changes

- 26 functional combat items leave generic Cleanup: mage’s book, Infinity pieces, two third-age pieces, four live salamander weapons, three poisoned Keris variants, brine sabre, berserker necklace, Zamorakian hasta, two charged trident states, malediction/odium wards, abyssal tentacle, katana and black wizard hat (g).
- Four repeatable Herblore inputs leave generic Cleanup: aldarium, demonic tallow, garlic and araxyte venom sac. Garlic retains Cooking/quest roles; the sac retains its edible protection roles.
- Nihil shard moves to crafting materials, retaining its equipment component and Herblore precursor roles.
- Strange fruit and spinach roll move to Food. Strange fruit restores energy and cures poison/venom; it is not described as healing Hitpoints.
- Bunny ears and highwayman mask move to Cosmetics, retaining documented storage and other uses.
- Empty vial follows its common Herblore container workflow instead of its glassblowing origin.
- Five exact burnt-fish IDs, exhausted rod dust and two ruined Camdozaal fish move from Resources to Cleanup Review. Their exact articles explicitly state they have no use. This routing is a review destination, not an instruction to discard an account’s items.

The passive obsidian and kalphite/scabarite damage roles now protect their items from automatic alchemy routing. Live user overrides were not edited; this report does not claim every correction changes the user’s current bank.

Two preference questions remain separate from factual review: edible holiday collectibles, and zero-stat wearable quest items retained as costumes. Existing behavior is preserved pending the user’s choices.

## Validation

Java 11 `check jar` passes: 1,161 existing unit tests, 150 random-bank scenarios and 1,800 aggregate scenarios. Existing unit assertions and two real-bank fixture rows were updated; no new regression suite or fixture was introduced.

Against `da7ee97`, the saved simulation review contains four changed scenario metric rows, 26 aggregate Cleanup exits and six aggregate Cleanup entries. Every changed Cleanup ID belongs to the 44 approved cases; common Cleanup rows are unchanged. Only aggregate distinct IDs and occurrence totals changed in metadata. All 1,950 scenarios complete. Baseline checksums were updated after this comparison.

A fresh compiled export confirms all 44 category/subcategory targets. The rebuilt 0.7.1 jar contains 238 Java 11 class files and exact current catalog resource bytes. The review-size estimator’s highest total is 197,036 with estimated headroom 2,964; this is not an official Plugin Hub count.

Upstream was fetched before this checkpoint; the branch contains its current `main` tip without a rebase gap. Full semantic certification remains active and incomplete.
