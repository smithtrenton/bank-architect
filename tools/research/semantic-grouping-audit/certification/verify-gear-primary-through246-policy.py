from __future__ import annotations
import argparse, hashlib, importlib.util, json, tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
PACKET = ROOT / "tmp/root-review/gear-primary-through246-policy-wrapper-emitter-draft-v2-20261003"
CERT = ROOT / "tools/research/semantic-grouping-audit/certification"
V2 = PACKET / "inputs/v2/packet"
V4 = PACKET / "inputs/v4/packet"
V4_MANIFEST_SHA256 = "68ac0169bc3c701aaaf6b368da1142699e05b80cd68b6549dd03e0ceb348587a"
V2_MANIFEST_SHA256 = "d98871f0429a0b2c88905db86453600bfc6135f2d027c9fbe442dcea172db991"
CANDIDATE_HASHES = {
    "gear-primary-through246-same-approved-policy.json": "919c7337514811b436563a35d3d5de23027b35eb924d1aee4d0513aacdeb2c47",
    "gear-primary-through246-corrections-approved-policy.json": "60266f5d9b123562fa87b6d15ecbff6aa9f6c2ba1af8d2ddb6d9857e3af2331f",
}
CANDIDATE_NAMES = {
    "gear-primary-through246-same-approved-policy.json": "gear-primary-through246-same-candidate-policy.json",
    "gear-primary-through246-corrections-approved-policy.json": "gear-primary-through246-correction-candidate-policy.json",
}
EXPECTED = {
    "gear-primary-through246-same-approved-policy.json": (115, "certify"),
    "gear-primary-through246-corrections-approved-policy.json": (110, "revise"),
}
QUICK = {11136, 13103, 13118, 13123, 13125, 13128, 13129, 13132}

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def canon(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()

def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))

def source_replay() -> dict[str, Any]:
    if sha(V2 / "artifact-manifest.json") != V2_MANIFEST_SHA256:
        raise ValueError("immutable V2 artifact manifest hash differs")
    if sha(V4 / "artifact-manifest.json") != V4_MANIFEST_SHA256:
        raise ValueError("corrected V4 artifact manifest hash differs")
    for directory in (V2, V4):
        manifest = load(directory / "artifact-manifest.json")
        for relative, expected in manifest["files"].items():
            path = directory / relative
            if not path.is_file() or sha(path) != expected:
                raise ValueError(f"frozen evidence file differs: {relative}")
    verifier_path = V4 / "verify-gear-primary-through246-candidate.py"
    spec = importlib.util.spec_from_file_location("gear246_candidate_integrity", verifier_path)
    if spec is None or spec.loader is None:
        raise ValueError("cannot load pinned V4 technical verifier")
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    return verifier.verify(V2, V4)

def common_policy(official_name: str) -> dict[str, Any]:
    if official_name not in EXPECTED:
        raise ValueError("unexpected policy filename")
    replay = source_replay()
    if replay.get("status") != "PASS" or replay.get("candidateCounts") != {"same":115,"corrections":110,"holds":21}:
        raise ValueError("V4 evidence replay failed or tranche counts changed")
    source_name = CANDIDATE_NAMES[official_name]
    source_path = V4 / "policies" / source_name
    if sha(source_path) != CANDIDATE_HASHES[official_name]:
        raise ValueError("candidate policy bytes differ from fixed V4 pin")
    source = load(source_path)
    count, expected_decision = EXPECTED[official_name]
    if source.get("expectedCaseCount") != count or len(source.get("cases", [])) != count:
        raise ValueError("candidate case count changed")
    cases = []
    ids = []
    for item in source["cases"]:
        item_id = int(item["itemId"])
        ids.append(item_id)
        target = item["candidatePrimaryTarget"]
        tab = item["proposedIronmanTabKey"]
        if target != {"category":item["proposedCategory"],"subcategory":item["proposedSubcategory"],"ironmanTabKey":tab}:
            raise ValueError(f"candidate target fields disagree for {item_id}")
        if item.get("primaryOnly") is not True or item.get("proposedTags") != [] or item.get("addedRoles") != []:
            raise ValueError(f"candidate scope widened for {item_id}")
        if (item_id in QUICK) != (tab == "currency-utilities"):
            raise ValueError(f"quick-access tab exception is not exact for {item_id}")
        cases.append({
            "itemId":item_id,
            "title":item["title"],
            "proposedCategory":item["proposedCategory"],
            "proposedSubcategory":item["proposedSubcategory"],
            "proposedIronmanTabKey":tab,
            "semanticExcerpt":item["semanticExcerpt"],
            "secondaryExcerpts":item["secondaryExcerpts"],
            "sourceRevision":int(item["sourceRevision"]),
            "sourceSha256":item["sourceSha256"],
            "exactVariantFacts":item["exactVariantFacts"],
            "rationale":item["rationale"],
            "expectedDecision":expected_decision,
        })
    if ids != sorted(ids) or len(set(ids)) != count:
        raise ValueError("candidate IDs are not unique and sorted")
    return {
        "schema":1,
        "status":"research candidate; final review pending",
        "scope":"Research-only primary category/subcategory/emitter-tab candidates; no detached approval, role, tag, availability or bankability claims.",
        "license":"This research policy is derived from the pinned candidate evidence and confers no approval.",
        "expectedCaseCount":count,
        "expectedDecision":expected_decision,
        "sourceHashes":{
            "v2ArtifactManifest":V2_MANIFEST_SHA256,
            "v4ArtifactManifest":V4_MANIFEST_SHA256,
            "candidatePolicy":CANDIDATE_HASHES[official_name],
            "frozenCurrentDecisions":"4605062de476942bfffb921c8bcee7eaef245880d3c31466ac507c33d598f429",
            "frozenCurrentAfterCoverage":"4968b43a92ec9851552b485e8212ccdada955c1082c9314f9ba67ca018bb47c3",
            "frozenCurrentManifest":"f940e87caf845c2af8af4468de81a6c492a2e283780d0816c03f30da50e0de35",
            "quickAccessQualificationManifest":"08498eddef9402d0ee2bb4b06c9b16f53458d7b5dab48b8661f11c46291e8441",
            "candidateVerifierSha256":sha(Path(__file__).resolve()),
            "stagedEmitterDraftSha256":sha(PACKET/"staged/emit-root-approved-decisions.py"),
            "emitterSourceSha256":sha(PACKET/"inputs/runtime/emit-root-approved-decisions.py"),
        },
        "reviewedPrimaryRule":"Root-read exact own active equipment primary function and exact own physical slot only; follow mapper-aware V3/V4 target. Do not infer tags, secondary roles, availability, bankability, or unobserved states.",
        "primaryOnly":True,
        "explicitAdditionalHolds":[],
        "addedRoles":[],
        "proposedTags":[],
        "tagEvidence":{},
        "cases":cases,
        "reviewer":"research draft; no approval",
        "reviewRecord":{"approval":"not granted","rootReview":"pending"},
    }

def verify_policy(policy: dict[str, Any], expected_policy_name: str, *, allow_draft: bool = False) -> dict[str, Any]:
    """Fail closed against frozen V2/V4 inputs; candidates are not approvals.

    For official emitter use, a separately root-pinned approval may change only
    status/reviewer/reviewRecord to the exact metadata below; all source-derived
    bytes and case fields must equal the generated normalized candidate.
    """
    draft = common_policy(expected_policy_name)
    approved = dict(draft)
    approved.update({
        "status":"root-reviewed primary assignments only",
        "scope":"Root-reviewed primary category, physical subcategory, and emitter-tab assignments only. Tags, supplemental roles, availability, and bankability remain unassessed.",
        "license":"Approval applies only to the exact primary assignments and source evidence in this pinned policy.",
        "reviewer":"root",
        "reviewRecord":{
            "decision":"approved primary category/subcategory/tab only",
            "candidatePolicySha256":CANDIDATE_HASHES[expected_policy_name],
            "v2ArtifactManifestSha256":V2_MANIFEST_SHA256,
            "v4ArtifactManifestSha256":V4_MANIFEST_SHA256,
            "scope":"Primary assignments only; tags, supplemental roles, availability, and bankability remain unassessed.",
        },
    })
    if policy == approved:
        return {"status":"PASS","policy":expected_policy_name,"caseCount":len(policy["cases"]),"metadata":"root-reviewed"}
    if allow_draft and policy == draft:
        return {"status":"PASS","policy":expected_policy_name,"caseCount":len(policy["cases"]),"metadata":"draft"}
    raise ValueError("policy differs from exact root-reviewed derivation; research drafts require explicit allow_draft=True")

def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--drafts",action="store_true",help="validate normalized research candidates, never official policies")
    parser.add_argument("--write-drafts",action="store_true",help="write drafts only into a fresh, separate directory")
    parser.add_argument("--draft-dir",type=Path,help="required fresh sibling directory under tmp/root-review when writing drafts")
    args=parser.parse_args()
    if args.write_drafts and not args.drafts:
        parser.error("--write-drafts requires explicit --drafts mode")
    if args.write_drafts and args.draft_dir is None:
        parser.error("--write-drafts requires an explicit --draft-dir")
    if args.draft_dir is not None and not args.write_drafts:
        parser.error("--draft-dir is valid only with --write-drafts")

    draft_root=None
    if args.write_drafts:
        allowed_parent=(ROOT/"tmp/root-review").resolve()
        draft_root=args.draft_dir.resolve()
        if draft_root.parent != allowed_parent:
            raise ValueError("draft output must be a direct child of tmp/root-review, outside the source packet")
        if draft_root.exists():
            raise FileExistsError(f"refusing to overwrite existing draft output: {draft_root}")
        if not allowed_parent.is_dir():
            raise ValueError("tmp/root-review must already exist; the verifier does not create output parents")

    reports=[]
    generated=[]
    for name in EXPECTED:
        if args.drafts:
            policy=common_policy(name)
            result=verify_policy(policy,name,allow_draft=True)
            if args.write_drafts:
                generated.append((name,json.dumps(policy,ensure_ascii=False,indent=2)+"\n"))
        else:
            path=CERT/name
            if not path.is_file():
                raise ValueError(f"official approved policy is missing: {path}")
            policy=load(path)
            result=verify_policy(policy,name)
        reports.append(result)

    if args.write_drafts:
        # Recheck after source validation, then build off to the side and atomically
        # rename a complete pair. Existing destinations are never replaced.
        if draft_root.exists():
            raise FileExistsError(f"refusing to overwrite existing draft output: {draft_root}")
        temp_root=Path(tempfile.mkdtemp(prefix=".gear-primary-drafts-",dir=str(draft_root.parent)))
        try:
            for name,contents in generated:
                (temp_root/name).write_text(contents,encoding="utf-8")
            if draft_root.exists():
                raise FileExistsError(f"refusing to overwrite existing draft output: {draft_root}")
            temp_root.rename(draft_root)
        except Exception:
            for child in temp_root.iterdir():
                if child.is_file(): child.unlink()
            temp_root.rmdir()
            raise

    print(json.dumps({"status":"PASS","mode":"draft" if args.drafts else "official_policy_verification","draftOutput":str(draft_root) if args.write_drafts else None,"approval":"not granted by this verifier","runtimeApplication":"not proved","policies":reports},indent=2,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())

