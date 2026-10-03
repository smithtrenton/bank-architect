const fs = require("node:fs");
const path = require("node:path");

const workspace = process.cwd();
const auditRoot = path.join(workspace, "tmp", "semantic-audit");
const outputRoot = path.join(auditRoot, "reviews", "gear-cosmetics");
const joinedPath = path.join(auditRoot, "joined.jsonl");
const setPath = path.join(workspace, "src", "main", "resources", "com", "pkoka5",
	"ironmanbankarchitect", "organize", "item-set-catalog.tsv");

const evidenceCategories = [
	"Category:Equipable items",
	"Category:Clothing",
	"Category:Items storable in the costume room",
	"Category:Warm clothing",
	"Category:Random event rewards",
	"Category:Treasure Trails rewards",
	"Category:Skilling equipment",
	"Category:Ammunition",
	"Category:Arrows",
	"Category:Bolts",
	"Category:Ranged armour",
	"Category:Magic armour",
	"Category:Melee armour"
];
const combatBonusFields = [
	"stab_attack_bonus", "slash_attack_bonus", "crush_attack_bonus",
	"range_attack_bonus", "magic_attack_bonus", "stab_defence_bonus",
	"slash_defence_bonus", "crush_defence_bonus", "range_defence_bonus",
	"magic_defence_bonus", "strength_bonus", "ranged_strength_bonus",
	"prayer_bonus", "magic_damage_bonus"
];

function readSets() {
	const byId = new Map();
	for (const line of fs.readFileSync(setPath, "utf8").split(/\r?\n/)) {
		if (!line || line.startsWith("#")) continue;
		const [domain, key, name, rank, itemId] = line.split("\t");
		const id = Number(itemId);
		if (!byId.has(id)) byId.set(id, []);
		byId.get(id).push({ domain, key, name, rank: Number(rank) });
	}
	return byId;
}

function exactBonusFacts(item) {
	const slots = new Set();
	const nonzero = new Set();
	for (const match of item.bonus_matches || []) {
		if (match.status !== "UNIQUE" || match.method !== "EXACT_PAGE_SUB") continue;
		for (const record of match.records || []) {
			if (record.equipment_slot) slots.add(String(record.equipment_slot));
			for (const field of combatBonusFields) {
				if (Number(record[field] || 0) !== 0) nonzero.add(field + ":" + record[field]);
			}
		}
	}
	return { slots: [...slots].sort(), nonzero: [...nonzero].sort() };
}

function csvCell(value) {
	return "\"" + String(value ?? "").replace(/\"/g, "\"\"") + "\"";
}

function main() {
	fs.mkdirSync(outputRoot, { recursive: true });
	const setById = readSets();
	const rows = [];
	const categoryCounts = {};
	const counts = {};
	const setCounts = {};
	let catalogRows = 0;

	for (const line of fs.readFileSync(joinedPath, "utf8").split(/\r?\n/)) {
		if (!line) continue;
		catalogRows++;
		const item = JSON.parse(line);
		const sets = setById.get(item.item_id) || [];
		const categories = new Set();
		for (const page of item.wiki_records || []) {
			for (const category of evidenceCategories) {
				if (page[category] === true) categories.add(category);
			}
		}
		const bonus = exactBonusFacts(item);
		const subcategory = String(item.subcategory || "").toLowerCase();
		const tagsOfInterest = ["gear", "ammunition", "ammo-components", "skilling-outfits", "tools"];
		const inScope = sets.length > 0 || item.catalog_category === "GEAR"
			|| ["ammo", "thrown-weapon", "skilling-outfit"].includes(subcategory)
			|| tagsOfInterest.includes(item.preset_tag)
			|| categories.size > 0 || bonus.slots.length > 0;
		if (!inScope) continue;

		const categoryList = [...categories].sort();
		for (const category of categoryList) categoryCounts[category] = (categoryCounts[category] || 0) + 1;
		const domains = [...new Set(sets.map(set => set.domain))].sort();
		for (const domain of domains) setCounts[domain] = (setCounts[domain] || 0) + 1;
		const ammunitionEvidence = ["ammo", "thrown-weapon"].includes(subcategory)
			|| categoryList.some(category => ["Category:Ammunition", "Category:Arrows", "Category:Bolts"].includes(category));
		const outfitEvidence = subcategory === "skilling-outfit"
			|| domains.includes("tools") || categoryList.includes("Category:Skilling equipment");
		const clothingEvidence = categoryList.some(category => [
			"Category:Clothing", "Category:Random event rewards",
			"Category:Treasure Trails rewards", "Category:Items storable in the costume room"
		].includes(category));
		const exactPages = [...new Set((item.wiki_records || []).map(page => page.page_name).filter(Boolean))];
		const flags = [];
		if (ammunitionEvidence && !["ammunition", "ammo-components"].includes(item.preset_tag)) {
			flags.push("AMMUNITION_ROLE_ROUTE_REVIEW");
		}
		if (outfitEvidence && sets.length === 0) flags.push("SKILLING_OUTFIT_SET_COVERAGE_REVIEW");
		if (clothingEvidence && !domains.some(domain => ["cosmetics", "cosmetic-family"].includes(domain))) {
			flags.push("CLOTHING_OR_REWARD_FAMILY_REVIEW");
		}
		if (categories.has("Category:Items storable in the costume room")) {
			flags.push("COSTUME_ROOM_STORAGE_FACET_ONLY");
		}
		if (bonus.slots.length > 0 && bonus.nonzero.length === 0) {
			flags.push("ZERO_BONUS_ITEM_RETAINS_WEARABLE_IDENTITY");
		}
		if (item.wiki_join_status === "NO_EXACT_ID_FACT") flags.push("WIKI_ID_COVERAGE_GAP_UNKNOWN");
		for (const flag of flags) counts[flag] = (counts[flag] || 0) + 1;

		rows.push({
			item_id: item.item_id,
			name: item.name,
			catalog_category: item.catalog_category,
			subcategory: item.subcategory,
			preset_category: item.preset_category,
			preset_tag: item.preset_tag,
			preset_tag_by_family: item.preset_tag_by_family,
			set_domains: domains.join(" | "),
			set_memberships: sets.map(set => `${set.key} (${set.name}; rank ${set.rank})`).join(" | "),
			wiki_join_status: item.wiki_join_status,
			positive_categories: categoryList.join(" | "),
			exact_equipment_slots: bonus.slots.join(" | "),
			positive_nonzero_bonus_fields: bonus.nonzero.join(" | "),
			wiki_pages: exactPages.join(" | "),
			wiki_urls: [...new Set(item.wiki_urls || [])].join(" | "),
			review_flags: flags.join(" | ")
		});
	}

	rows.sort((left, right) => left.item_id - right.item_id);
	const columns = Object.keys(rows[0]);
	const csv = [columns.map(csvCell).join(","), ...rows.map(row => columns.map(key => csvCell(row[key])).join(","))].join("\n");
	fs.writeFileSync(path.join(outputRoot, "reviewed-items.csv"), csv, "utf8");
	const summary = {
		domain: "Combat gear, ammunition, cosmetic clothing, skilling outfits, and cosmetic variants",
		dataset: "tmp/semantic-audit/joined.jsonl",
		generatedAt: new Date().toISOString(),
		scope: {
			effectiveCatalogRows: catalogRows,
			domainRelevantRows: rows.length,
			wikiVerifiedRelevantRows: rows.filter(row => row.wiki_join_status.startsWith("EXACT_ID_")).length,
			wikiUnverifiedRelevantRows: rows.filter(row => row.wiki_join_status === "NO_EXACT_ID_FACT").length
		},
		positiveCategoryRowCounts: categoryCounts,
		setMembershipRowsByDomain: setCounts,
		reviewFlagCounts: counts,
		policy: {
			identity: "Each item ID remains distinct. An outfit, gear family, or cosmetic variant is an optional grouping edge.",
			negativeEvidence: "Missing equipment slots, combat bonuses, categories, and Wiki ID matches mean unknown. Zero bonuses do not mean cosmetic or junk.",
			pageScope: "Only exact-ID joined true category values are recorded. A positive page category supports a facet but does not establish a unique workflow.",
			ammunition: "An ammo-slot fact alone is insufficient: the slot also accepts wearable blessings and utility items. Require a documented ammunition type or compatibility.",
			variantEvidence: "Recipe title relationships and name similarity do not prove item variants. Use exact IDs and direct set or transformation statements.",
			reviewFlags: "Flags are candidates for human review; they are not automatic misclassification findings."
		},
		limitations: [
			"This is a complete mechanical review universe for the domain, not a manual verification of every row.",
			"Items storable in the costume room can be functional combat gear; the category does not identify the storage space or prove cosmetic-only status.",
			"Clothing, random-event, and treasure-trail categories can overlap with functional equipment.",
			"Wiki ID gaps remain unknown; no negative classification is inferred from missing facts."
		],
		outputs: { items: "reviewed-items.csv", proposals: "verified-group-proposals.json", conclusions: "conclusions.json" }
	};
	fs.writeFileSync(path.join(outputRoot, "audit-summary.json"), JSON.stringify(summary, null, 2), "utf8");
	console.log(JSON.stringify({ scope: summary.scope, positiveCategoryRowCounts: categoryCounts, setMembershipRowsByDomain: setCounts, reviewFlagCounts: counts }, null, 2));
}

main();
