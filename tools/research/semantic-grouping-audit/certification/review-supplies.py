#!/usr/bin/env python3
"""Create conservative exact-ID source reviews for the supplies/Herblore shard.

The output is a reviewer ledger, not an automatic classification migration. The script
can certify only records with a pinned article, an exact numeric infobox identity, and
direct textual support for the present placement. Ambiguous and conflicting records
remain unresolved for item-by-item review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_PACKET = ROOT / "tmp/category-certification/reviewer-packets/supplies-herblore.jsonl"
DEFAULT_INDEX = ROOT / "tmp/category-certification/wiki-articles/article-index.json"
DEFAULT_POLICY = Path(__file__).with_name("supplies-policy.json")
DEFAULT_OUT = ROOT / "tmp/category-certification/reviews/supplies"
DOSE_RE = re.compile(r"\b([1-4])\s*[- ]?dose\b", re.I)
POTIONS = {"potion", "dose-1", "dose-2", "dose-3", "potion-dose-1", "potion-dose-2", "potion-dose-3", "potion-dose-4"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def text_excerpt(path: Path) -> str:
    """Return the article lead paragraph, never a keyword hit from a later section."""
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""
    raw = re.sub(r"\{\{Infobox Item.*?\n\}\}", " ", raw, flags=re.S | re.I)
    for paragraph in re.split(r"\n\s*\n", raw):
        clean = paragraph.strip()
        if not clean or clean.startswith("==") or clean.startswith("{{") or clean.startswith("|{"):
            continue
        clean = re.sub(r"^\[\[File:[^\]]*\]\]\s*", "", clean, count=1, flags=re.I)
        if clean and not clean.startswith("==") and not clean.startswith("{{"):
            return clean[:500]
    return ""


def short_quote(value: str, limit: int = 320) -> str:
    """Keep a literal excerpt through a sentence boundary when possible."""
    value = value.strip()
    for index, character in enumerate(value):
        if character in ".!?" and index + 1 < len(value) and value[index + 1].isspace():
            if index + 1 <= limit:
                return value[:index + 1].rstrip()
    excerpt = value[:limit]
    if len(value) > limit and " " in excerpt:
        excerpt = excerpt.rsplit(" ", 1)[0]
    return excerpt


def exact_id_quote(path: Path, item_id: int) -> str:
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            match = re.match(r"\s*\|\s*(?:id\d*|id)\s*=\s*([\d, ]+)\s*$", line, re.I)
            if match and item_id in {int(value.strip()) for value in match.group(1).split(",") if value.strip().isdigit()}:
                return line.strip()[:120]
    except (OSError, UnicodeError):
        pass
    return f"exact numeric item ID {item_id} in pinned infobox"


def category_set(item: dict) -> set[str]:
    return {key[len("Category:"):]
            for page in item.get("sourceEvidence", {}).get("wikiRecords", [])
            for key, value in page.items()
            if key.startswith("Category:") and value is True}


def exact_article(item: dict, index: dict, article_root: Path) -> tuple[dict | None, int | None]:
    item_id = int(item["itemId"])
    exact = []
    for title, meta in index.items():
        ids = {int(value) for value in meta.get("exactInfoboxItemIds", []) if str(value).isdigit()}
        if item_id in ids and str(item_id) in meta.get("variants", {}):
            exact.append((title, meta))
    # Retain ambiguity rather than choosing a title by spelling or ordering.
    if len(exact) != 1:
        return None, None
    title, meta = exact[0]
    text_path = article_root / meta["path"]
    # article-index paths are repository-relative; avoid accepting paths outside the source root.
    try:
        text_path = (ROOT / meta["path"]).resolve()
        text_path.relative_to(article_root.resolve())
    except (ValueError, OSError):
        return None, None
    if not text_path.is_file():
        return None, None
    return {"title": title, **meta, "_path": text_path}, item_id


def review_one(item: dict, index: dict, article_root: Path, policy_rules: dict[str, set[str]]) -> dict:
    current = item["current"]
    item_id = int(item["itemId"])
    exact_page, exact_id = exact_article(item, index, article_root)
    source_categories = category_set(item)
    evidence = []
    unresolved: list[str] = []
    direct_role = ""
    quote = ""
    corrected = ""
    if exact_page is None:
        unresolved.append("No unique pinned article-index record contains this exact numeric item ID; exact-ID source identity or revision is ambiguous.")
    else:
        meta = exact_page
        variant = meta.get("variants", {}).get(str(item_id), {})
        params = variant.get("params", {})
        suffix = str(variant.get("suffix", ""))
        def exact_field(prefix: str) -> str:
            if suffix and f"{prefix}{suffix}" in params:
                return str(params[f"{prefix}{suffix}"])
            return str(params.get(prefix, ""))
        exact_version = exact_field("version")
        exact_name = exact_field("name")
        exact_examine = exact_field("examine")
        version_text = " ".join(value for value in (exact_version, exact_name, exact_examine) if value)
        path = meta["_path"]
        index_quote = text_excerpt(path)
        variant_text = " ".join([version_text, exact_examine])
        source_text = " ".join(x for x in (variant_text, index_quote) if x)
        dose_match = DOSE_RE.search(version_text) or DOSE_RE.search(index_quote)
        expected_dose = None
        subcategory = current.get("subcategory", "")
        if subcategory.startswith("potion-dose-") or subcategory.startswith("dose-"):
            expected_dose = int(subcategory[-1])
        if expected_dose is not None and dose_match and int(dose_match.group(1)) != expected_dose:
            actual_dose = int(dose_match.group(1))
            prefix = "potion-dose-" if subcategory.startswith("potion-dose-") else "dose-"
            corrected = prefix + str(actual_dose)
            direct_role = f"{actual_dose}-dose potion state"
            quote = dose_match.group(0)
            unresolved.append(f"The exact item variant explicitly states {actual_dose} doses, conflicting with the current {expected_dose}-dose subcategory.")
        elif "unfinished-potion" == current.get("subcategory"):
            if ("Unfinished potions" in source_categories and
                    any(re.search(r"need(?:s)? another ingredient|incomplete|unfinished potion", text, re.I)
                        for text in (exact_examine, index_quote))):
                direct_role = "unfinished Herblore potion"
                quote = short_quote(index_quote or exact_examine)
            else:
                unresolved.append("The exact-ID source does not explicitly establish unfinished-potion stage; category facet or recipe-title relations alone are insufficient.")
        elif current.get("subcategory") in POTIONS:
            if expected_dose is not None and dose_match and int(dose_match.group(1)) == expected_dose:
                direct_role = f"{expected_dose}-dose potion state"
                quote = dose_match.group(0)
            elif (current.get("subcategory") == "potion" and
                  re.search(r"\\bcrate of potions\\b", index_quote, re.I) and
                  re.search(r"\\bcourier task\\b", index_quote, re.I)):
                direct_role = "courier-task cargo crate containing potions"
                quote = short_quote(index_quote)
                unresolved.append("The exact-ID article describes a courier cargo crate containing potions, which conflicts with an ordinary consumable-potion placement; the source does not establish a valid replacement category, subcategory, and tab.")
            elif current.get("subcategory") == "potion" and "Potions" in source_categories and re.search(r"\bpotion\b", source_text, re.I):
                direct_role = "potion"
                quote = short_quote(index_quote or exact_examine)
            else:
                unresolved.append("Exact article text does not establish the current potion/dose state for this numeric ID; family convention and article title are not proof.")
        elif current.get("subcategory") == "food":
            if "Food" in source_categories and re.search(r"\b(?:eaten?|edible|heals?|healing|restores?)\b", source_text, re.I):
                direct_role = "edible/healing food"
                quote = short_quote(index_quote or exact_examine)
            else:
                unresolved.append("Exact article text does not explicitly establish edible/healing use for this ID; potion/drink overlap remains unresolved.")
        elif current.get("subcategory") == "drink":
            if "Drinks" in source_categories and re.search(r"\b(?:drunk|drink|drinks|sip|sipped)\b", source_text, re.I):
                direct_role = "drink"
                quote = short_quote(index_quote or exact_examine)
            else:
                unresolved.append("Exact article text does not establish drink use and its distinct bank placement for this exact ID.")
        elif current.get("subcategory") in {"activity-potion", "restricted-potion"}:
            restriction_re = re.compile(
                r"\b(?:can|may)\s+only\s+be\s+used\b.{0,100}\b(?:in|within|during|at)\b.{0,80}\b(?:Wilderness|arena|raid|minigame|quest|area|activity)\b"
                r"|\bonly\s+usable\b.{0,80}\b(?:in|within|during|at)\b.{0,80}\b(?:Wilderness|arena|raid|minigame|quest|area|activity)\b"
                r"|\b(?:cannot|can't)\s+be\s+used\b.{0,80}\b(?:outside|in|within|during)\b.{0,80}\b(?:Wilderness|arena|raid|minigame|quest|area|activity)\b",
                re.I,
            )
            restriction = next((match for text in (index_quote, exact_examine)
                                if (match := restriction_re.search(text))), None)
            if "Potions" in source_categories and restriction:
                direct_role = "activity/restricted potion"
                quote = restriction.group(0)[:240]
            else:
                unresolved.append("Exact-ID article text does not state the activity or use restriction that defines this potion subcategory.")
        elif current.get("subcategory") in {"herblore", "herblore-base", "herblore-supply"}:
            # These catalog buckets intentionally combine several roles; source evidence
            # can establish a role without proving the current primary placement policy.
            role_markers = {
                "unfinished-potion": "incomplete potion stage",
                "Herblore secondaries": "Herblore secondary ingredient",
                "Herbs": "Herblore herb",
            }
            found = [(facet, role) for facet, role in role_markers.items()
                     if facet in source_categories and re.search(r"\bherblore\b", source_text, re.I)]
            if found:
                direct_role = " or ".join(role for _, role in found)
                quote = short_quote(index_quote or exact_examine)
                unresolved.append("The source documents a Herblore role but does not define which distinct role belongs in this broad current subcategory.")
            else:
                unresolved.append("The exact article does not establish the item role for this broad Herblore subcategory.")
        elif current.get("subcategory") in {"grimy-herb", "clean-herb", "herb"}:
            expected_state = "grimy" if current.get("subcategory") == "grimy-herb" else "clean"
            state_match = re.search(rf"\b{expected_state}\b", source_text, re.I)
            if "Herbs" in source_categories and re.search(r"\bherblore\b", source_text, re.I) and state_match:
                direct_role = f"{expected_state} Herblore herb" if expected_state != "clean" else "clean Herblore herb"
                quote = (index_quote or str(params.get("examine", "")))[:240]
            else:
                unresolved.append("Exact article text does not establish this exact item's clean/grimy herb state and Herblore role.")
        elif current.get("subcategory") == "secondary":
            if "Herblore secondaries" in source_categories and re.search(r"\bherblore\b", source_text, re.I):
                direct_role = "Herblore secondary ingredient"
                quote = (index_quote or str(params.get("examine", "")))[:240]
            else:
                unresolved.append("Exact article text does not establish this exact Herblore ingredient/tool/product role; recipe-title relations alone are insufficient.")
        elif current.get("subcategory") == "herblore-other":
            unresolved.append("This broad catalog subcategory contains distinct item roles; direct article evidence must establish both the item function and the intended shared placement policy.")
        else:
            unresolved.append("The current subcategory has no explicit supplies policy rule, so its placement cannot be certified by this review.")

        if exact_id is not None and direct_role and quote:
            source_hash = "sha256:" + meta["sha256"]
            evidence.append({
                "kind": "exact_wiki", "source": meta["sourceUrl"], "sourceTitle": meta["title"],
                "sourceRevision": int(meta["revid"]), "sourceHash": source_hash,
                "rawPacketPath": meta.get("packetPath", ""),
                "rawPacketHash": "sha256:" + meta.get("packetSha256", ""),
                "itemId": item_id, "quote": quote,
            })
        if not evidence:
            # Provenance is retained for unresolved records too, when exact-ID mapping exists.
            if exact_page is not None:
                evidence.append({
                    "kind": "exact_wiki",
                    "source": exact_page["sourceUrl"], "sourceTitle": exact_page["title"],
                    "sourceRevision": int(exact_page["revid"]),
                    "sourceHash": "sha256:" + exact_page["sha256"],
                    "rawPacketPath": exact_page.get("packetPath", ""),
                    "rawPacketHash": "sha256:" + exact_page.get("packetSha256", ""),
                    "itemId": item_id,
                    "quote": exact_id_quote(exact_page["_path"], item_id),
                })

    base = {
        "itemId": item_id, "shard": "supplies-herblore", "decision": "unresolved",
        "proposedCategory": current.get("category", ""),
        "proposedSubcategory": corrected or current.get("subcategory", ""),
        "proposedTags": sorted(current.get("tags", [])),
        "proposedRoles": [direct_role] if direct_role else None,
        "proposedIronmanTabKey": current.get("ironmanTabKey", ""),
        "semanticPredicate": "The exact item ID has a directly documented supplies or Herblore role that justifies this current bank placement, with overlapping functions retained as separate roles.",
        "rationale": " ".join(unresolved) if unresolved else "",
        "evidence": evidence,
        "identityLinks": [], "reviewer": "supplies-herblore",
    }
    # Policy intentionally requires a separate human taxonomy choice where a role is known
    # but the primary category/subcategory/tab convention is not proven by the article.
    if direct_role and not unresolved and current.get("subcategory") in policy_rules.get(current.get("category"), set()):
        roles = source_categories
        overlaps = ((current.get("category") == "POTION" and
                     (("Food" in roles and direct_role not in {"edible/healing food"}) or
                      ("Drinks" in roles and direct_role != "drink"))) or
                    (current.get("category") == "HERBLORE" and
                     "Potions" in roles and current.get("subcategory") not in {"unfinished-potion", "herblore-product"}))
        if not overlaps:
            base["decision"] = "certify"
            base["rationale"] = f"The pinned exact-ID item article supports {direct_role}, and the proposed category, subcategory, and Ironman tab match the compiled row."
        else:
            base["rationale"] = f"The exact-ID article supports {direct_role}, but overlapping food/drink/potion roles leave primary placement unresolved."
    elif not base["rationale"]:
        base["rationale"] = "The exact-ID article does not support a safe correction, and the current placement lacks the direct functional evidence required to certify it."
    elif corrected:
        base["decision"] = "revise"
        base["rationale"] = unresolved[-1] + " The proposed dose subcategory follows the exact-ID variant evidence."
    return base


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--article-root", type=Path, default=ROOT / "tmp/category-certification/wiki-articles")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    index = json.loads(args.index.read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in args.packet.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    args.output.mkdir(parents=True, exist_ok=True)
    policy_rules = {rule["currentCategory"]: set(rule["candidateSubcategories"])
                    for rule in policy.get("taxonomy_rules", [])}
    decisions = [review_one(row, index, args.article_root, policy_rules) for row in rows]
    ledger = args.output / "decisions.jsonl"
    with ledger.open("w", encoding="utf-8", newline="\n") as stream:
        for row in decisions:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    counts = {key: sum(row["decision"] == key for row in decisions) for key in ("certify", "revise", "unresolved")}
    summary = {
        "shard": "supplies-herblore", "packet": str(args.packet), "packetSha256": sha256(args.packet),
        "articleIndex": str(args.index), "articleIndexSha256": sha256(args.index),
        "policy": str(args.policy), "policySha256": sha256(args.policy),
        "decisionFile": str(ledger), "reviewedIds": len(decisions), "decisionCounts": counts,
        "notes": ["Only exact-ID pinned text is used for item-specific functional evidence.",
                  "This conservative extraction leaves ambiguous cases unresolved; source provenance does not itself certify a semantic claim."],
    }
    (args.output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"reviewedIds": len(decisions), "decisionCounts": counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()
