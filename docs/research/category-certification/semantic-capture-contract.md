# Metadata needed before category re-evaluation

The user deferred category re-evaluation until the full semantic analysis is complete, followed by analysis of tags for useful groups. This document defines evidence capture for that future work. It does not introduce categories, runtime tags or grouping rules.

Current primary-placement approvals and preserved legacy tags do not establish complete semantic coverage. A primary approval certifies only its category/subtype/tab claim. The semantic baseline preserves 34,085 item identities, 1,926 legacy tag assignments and raw Wiki observations, but those imported tag/fact assessments are unassessed. Full raw pages and review notes retain more information than the structured store currently contains. Neither primary-approval counts nor successful source replay should be reported as completion of the full metadata analysis.

Each exact item/state needs a coverage record pointing to its pinned sources, reviewed passages and structured assertions. For each dimension below, record whether it was reviewed, remains unassessed, conflicts between sources, or has no available evidence. Absence of evidence is unknown; a sourced negative is a separate assertion. A reviewed dimension may contain several facts rather than a single label.

| Dimension | Preserve when documented |
| --- | --- |
| Functions and effects | Every meaningful direct use, effect, target, timing and relevant quantities; distinguish equipped benefits, actions, consumption and preparation into another state. |
| Skills and recipes | Skill role, inputs, outputs, creation requirements, use requirements and experience, with explicit units. Acquisition level requirements are separate from continued-use requirements. |
| Contents and containers | Accepted contents, actual contained outputs, empty/full/partial state, capacity, quantity, single-use package versus reusable storage, and opening/emptying transformations. |
| Acquisition and origin | Quest, holiday, minigame, boss, Slayer, shop or other documented provenance, including multiple origins. Origin does not establish a use restriction or determine placement. |
| Applicability and restrictions | Mode/activity/location/quest/target conditions; exact current restriction versus proposed, failed-poll or superseded historical restriction. Availability is separate from functional mechanics. |
| Consumption and state | Reusable versus consumed, doses, charges, degradation, repair, assembled/disassembled, active/inactive and transformations with exact endpoints where bound. Do not infer these from a name alone. |
| Competing roles | Secondary skill, quest, cosmetic, combat, transport, trade or reward uses alongside the primary function. Preserve disagreements about priority separately from the facts. |
| Bank context | Deposit eligibility and its conditions, possible existing bank copies, note conversion and observed placeholder relationship. Typed representation links never transfer raw functions or tags. |

Use the existing `semantic-item-assertion/v1` envelope for structured facts. Preserve exact numeric ID/state binding, literal source excerpt, revision/hash/path, applicable conditions, typed values/units and assessment stage. Give newly extracted facts candidate/unassessed status until their complete assertions are reviewed; category approval cannot approve a secondary fact or tag. New predicate meanings need explicit versioned definitions before rules consume them. Preserve unresolved conflicts and unknowns.

Keep placement preferences separate: Cooking precedence for Mushroom, quest precedence for zero-bonus quest wearables, holiday identity for Pumpkin/Easter egg, activity grouping for use-limited copies and contents-led placement for unopened packs are user policies. They are not universal Wiki facts. Preserve all existing approval objects and runtime tags while collecting additional research metadata.

Older approved cohorts need the same semantic coverage reconciliation as new reviews. Link their immutable source/read packets and extract omitted secondary facts rather than replacing their historical evidence. A later categorization pass should consume an explicitly measured structured dataset, with unassessed/missing coverage visible, rather than treating current tags as exhaustive. Category design and tag grouping analysis remain deferred.
