# Category certification checkpoint — 3 October 2026

The current default preset has **not** been fully semantically certified. The earlier full-export passes and the completed 356 missing-item review do not establish correctness of every current assignment. This checkpoint applies 188 independently reviewed exact-ID corrections; all other pending reviewer findings remain outside production.

## Scope and evidence

The frozen compiled coverage export contains 34,085 assignments: 32,586 named effective records, 343 supplements, 606 cache research records and 550 null/invalid-name records. Research flags do not prove bankability, exclusion or semantic function. Runtime routes and raw catalog assignments must be distinguished, especially for placeholders.

The acquisition downloaded 11,396 pinned Wiki articles, with zero acquisition errors or requested-ID gaps after fixing an infobox parser that consumed the next field after a blank value. Article acquisition is evidence collection, not category certification. Revisions, literal excerpts, exact infobox IDs and article SHA-256 values for this checkpoint are retained in:

- `tools/research/semantic-grouping-audit/certification/cleanup-other-policy.json`: 35 exact-ID corrections independently reviewed in the main thread.
- `tools/research/semantic-grouping-audit/certification/materials-approved-policy.json`: nine additional exact-ID corrections independently reviewed in the main thread.
- `tools/research/semantic-grouping-audit/certification/gear-approved-policy.json`: 26 exact-ID corrections for records incorrectly classified as equipment.
- `tools/research/semantic-grouping-audit/certification/utility-approved-policy.json`: 12 exact-ID corrections for independent utility, consumable and ingredient functions.
- `tools/research/semantic-grouping-audit/certification/cleanup-gear-approved-policy.json`: 106 exact-ID corrections, including variant options and additional literal mechanics for usage tags. Six broken and 14 activity-only states are explicitly held unresolved.

Current reviewer scripts and cache identity research are still being tightened. Their candidate or first-pass decisions are not approved changes. No classification is certified solely from a keyword, name family, equipment flag, zero-valued equipment table, existing tag, quest association or absent Wiki field.

## Applied changes

- 26 functional combat items leave generic Cleanup: mage’s book, Infinity pieces, two third-age pieces, four live salamander weapons, three poisoned Keris variants, brine sabre, berserker necklace, Zamorakian hasta, two charged trident states, malediction/odium wards, abyssal tentacle, katana and black wizard hat (g).
- Four repeatable Herblore inputs leave generic Cleanup: aldarium, demonic tallow, garlic and araxyte venom sac. Garlic retains Cooking/quest roles; the sac retains its edible protection roles.
- Nihil shard moves to crafting materials, retaining its equipment component and Herblore precursor roles.
- Strange fruit and spinach roll move to Food. Strange fruit restores energy and cures poison/venom; it is not described as healing Hitpoints.
- Bunny ears and highwayman mask move to Cosmetics, retaining documented storage and other uses.
- Empty vial follows its common Herblore container workflow instead of its glassblowing origin.
- Five exact burnt-fish IDs, exhausted rod dust and two ruined Camdozaal fish move from Resources to Cleanup Review. Their exact articles explicitly state they have no use. This routing is a review destination, not an instruction to discard an account’s items.

- Eight prepared foods leave Gear for Food; six burnt foods leave Gear for Cleanup. Burnt egg, onion and mushroom still permit bowl recovery, so the review does not claim they have no possible interaction.
- Five animation/interface records leave Gear for Cleanup; Grip's keyring follows its quest-door function. Unstrung symbols/emblems, unstrung comp bow, sinew, kebab mix and raw rainbow crab meat move to their respective skilling inputs.
- Bullroarer and pet rock move to quest utilities because their documented functions continue beyond their original quests. Bloated toad follows its consumed hunter-bait role; dwellberries follow the Farming crop workflow while retaining Cooking and quest uses.
- Karamjan rum moves to drinks; white tree fruit, red banana, Tchiki monkey nuts/paste and stuffed snake move to Food based on documented consumption. Stuffed snake heals 20 Hitpoints.
- Keris partisan moves to weapons and gains its kalphite/scabarite passive-damage tag; magic roots moves to Herblore secondaries for antidote++ production.

The latest 106 corrections move 101 functional equipment records from generic Cleanup to Gear, including 28 black-mask charge/imbuing states, five snail-protection helmets, eight kitchen weapons, raid armour and weapons, rechargeable equipment, and documented seasonal equipment. The exact state and usable options were checked separately; the classification does not claim an empty blowpipe can currently be wielded or fire.

Five explicitly fun/social weapons move to Cosmetics: undead chicken, clueless scroll, candy cane, skeleton lantern and severed leg. Negative combat bonuses are not positive combat utility. Six broken Calamity variants remain unresolved because their own variant has Drop-only options; the shared equipable flag and shared combat table do not establish a repair workflow or current use. Fourteen Arena/Gauntlet records remain unresolved pending consistent routing for activity-only copies.

Empty Fire, Water and Earth tomes retain magic attack/defence bonuses according to their exact articles. Their catalog placement is now Gear, and the Ironman preset's explicit Loot override was removed. The new `combat-passive` usage fact protects supported passive equipment from automatic alchemy routing; each tagged exact ID has a literal mechanic excerpt in the approved policy.

Two proposed utility changes were rejected after reading the full mechanics: jewellery recharge uses the placed gilded totem pole rather than the carried gilded totem, and drift nets are consumed when harvesting. Neither item was changed by this checkpoint.

The passive obsidian and kalphite/scabarite damage roles now protect their items from automatic alchemy routing. Live user overrides were not edited; this report does not claim every correction changes the user’s current bank.

Three routing preferences remain separate from factual review: edible holiday collectibles, zero-stat wearable quest items retained as costumes, and activity-only copies such as Arena/Gauntlet equipment. Pending cases preserve existing behavior until the user chooses; their known roles are not treated as absent.

## Validation

Java 11 `check jar` passes: 1,161 existing unit tests, 150 random-bank scenarios and 1,800 aggregate scenarios. Existing unit assertions and seven real-bank fixture rows were updated; no new regression suite or fixture was introduced.

Against the verified `082b0f5` checkpoint, the latest simulation review contains 27 changed scenario metric rows, 68 aggregate Cleanup exits and no aggregate Cleanup entries. The random-bank Cleanup report has nine exits and no entries. Every changed Cleanup ID belongs to the 106 newly approved cases; common Cleanup rows are unchanged. Only aggregate distinct IDs (9,244 to 9,176) and occurrence totals (46,320 to 45,969) changed in metadata. Seeds, scenarios, item counts, outcomes and statuses are unchanged; all 1,950 scenarios complete. Baseline checksums were updated after this comparison.

A fresh compiled export confirms all 188 category/subcategory targets. The rebuilt 0.7.1 jar contains 238 Java 11 class files and exact current bytes for all 19 TSV resources. Its SHA-256 is `d641919d8cdc73091b87f188e9d94cc0a7e40d7f2e7f4351f7e1852a7cd3f342`. All 188 policy source revisions, exact IDs, hashes and literal excerpts were checked against the pinned article corpus. The review-size estimator’s highest total is 197,004 with estimated headroom 2,996; this is not an official Plugin Hub count.

The root Cleanup ledger now covers all 12,104 assigned rows: 141 approved corrections and 11,963 unresolved. Its source gate verifies 205 Wiki records, including exact variant fields and usage mechanics, and its applied-target gate passes against the fresh export. These gates cover this ledger; they do not certify the other shards.

Upstream was fetched before this checkpoint; the branch contains its current `main` tip without a rebase gap. Full semantic certification remains active and incomplete.
