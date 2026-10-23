"""Read-only release promotion: recompute panels and bind owner decisions to exact evidence files."""

from datetime import datetime, timezone, timedelta
import hashlib
import json
import re
from pathlib import Path
from types import SimpleNamespace

from .config import settings
from .pipeline.cases import all_cases, all_samples
from .pipeline.extract import quoted, value_quoted, metric_quoted, unit_quoted, scope_is_product_wide, model_quoted, selection_supported, revision_supported, family_member
from .pipeline.decide import decide
from .pipeline import spec_check, verify
from .pipeline.scores import scores
from .readiness import invalid_reasons, manifest
from .schemas import Event, Result, Requirement
from scripts.check_pdfs import required_documents

IDENTITY_FIELDS = ("version", "config", "config_hash", "code_hash", "checklists", "inputs")
MISS_FIELDS = ("wrong_call", "missed_problems", "false_alarm", "unnecessary_note")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_hash(folder: Path) -> str:
    paths = [folder / name for name in ("manifest.json", "events.jsonl", "attempts.json", "scores.json")]
    paths += sorted((folder / "results").glob("*.json"))
    entries = {str(path.relative_to(folder)): file_hash(path) for path in paths}
    return hashlib.sha256(json.dumps(entries, sort_keys=True).encode()).hexdigest()


def _stamp(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or result > datetime.now(timezone.utc):
        raise ValueError("Evidence timestamps must be aware and not in the future")
    return result


def _read(path: Path) -> dict:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("Expected an evidence object")
    return value


def _source_quotes(source: dict) -> None:
    path = (settings.raw_dir / source["file"]).resolve()
    if (not path.is_relative_to(settings.raw_dir.resolve()) or file_hash(path) != source["sha256"]
            or not source["url"].startswith("https://")):
        raise ValueError("Review source must match its frozen PDF hash and URL")
    import pymupdf
    with pymupdf.open(path) as pdf:
        if not source["quotes"] or any(not 1 <= quote["page"] <= len(pdf) or not quoted(
                quote["text"], pdf[quote["page"] - 1].get_text()) for quote in source["quotes"]):
            raise ValueError("Review quote is not on its cited page")


def _blind(folder: Path) -> tuple[dict, dict, str]:
    frozen, inputs, labels = (_read(folder / name) for name in ("manifest.json", "inputs.json", "labels.json"))
    if (frozen["version"] != 1 or not frozen["prepared_by"] or frozen["reviewed_by"].casefold() != "kyle"
            or _stamp(frozen["frozen_at"]) > _stamp(frozen["reviewed_at"])
            or frozen["inputs_sha256"] != file_hash(folder / "inputs.json")
            or frozen["labels_sha256"] != file_hash(folder / "labels.json")):
        raise ValueError("Blind set must be frozen and owner-reviewed before evaluation")
    def forbidden(value):
        if isinstance(value, dict):
            return bool({"expected", "verified", "fixture", "hint", "replaces"} & value.keys()) or any(forbidden(v) for v in value.values())
        return isinstance(value, list) and any(forbidden(v) for v in value)
    if forbidden(inputs):
        raise ValueError("Blind inputs contain labels or fixture hints")
    packages = {row["id"]: row for row in inputs["cases"]}
    answers = {row["id"]: row for row in labels["labels"]}
    if (len(packages) != 6 or len(inputs["cases"]) != 6 or set(packages) != set(answers)
            or len(labels["labels"]) != 6 or set(packages) & (all_cases().keys() | all_samples().keys())):
        raise ValueError("Exactly six new blind packages and matching labels are required")
    if any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", key) for key in packages):
        raise ValueError("Blind identifiers must be safe result filenames")
    primary_hashes = []
    for key, package in packages.items():
        if package["section"] not in {row["section"] for row in all_cases().values()} or not package["submittal"]:
            raise ValueError("Blind package must use a reviewed section and real submitted documents")
        primary_hashes.append(package["submittal"][0]["sha256"])
        expected = answers[key]["expected"]
        if (expected["decision"] not in ("approve", "approve_with_note", "send_back")
                or not isinstance(expected["problems"], list) or len(set(expected["problems"])) != len(expected["problems"])
                or any(problem not in ("spec", "currency", "currency_note", "validity", "status", "completeness") for problem in expected["problems"])):
            raise ValueError("Blind labels need a valid decision and distinct problem categories")
        for document in package["submittal"]:
            path = (settings.raw_dir / document["file"]).resolve()
            if (not path.is_relative_to(settings.raw_dir.resolve()) or file_hash(path) != document["sha256"]
                    or not path.read_bytes().startswith(b"%PDF") or not document["url"].startswith("https://")):
                raise ValueError("Blind source does not match its frozen PDF and URL")
        if not answers[key]["scope"] or not answers[key]["sources"]:
            raise ValueError("Blind labels need scope and page-grounded source evidence")
        for source in answers[key]["sources"]:
            _source_quotes(source)
    known_hashes = {row["sha256"] for row in _read(settings.data_dir / "documents.lock.json")["documents"].values()}
    if len(set(primary_hashes)) != 6 or set(primary_hashes) & known_hashes:
        raise ValueError("Blind packages need six distinct source documents outside the known demonstration set")
    catalog = {key: {**package, "expected": answers[key]["expected"]} for key, package in packages.items()}
    digest = hashlib.sha256(json.dumps({name: file_hash(folder / name) for name in
        ("manifest.json", "inputs.json", "labels.json")}, sort_keys=True).encode()).hexdigest()
    return catalog, frozen, digest


def _text_pages(path: Path) -> list[str]:
    if path.suffix == ".pdf":
        import pymupdf
        with pymupdf.open(path) as pdf:
            return [page.get_text() for page in pdf]
    return [path.read_text()]


def _archived(evidence, started: datetime, finished: datetime) -> list[str]:
    if not settings.evidence_dir or not evidence.archived_path or not evidence.retrieved_at:
        raise ValueError("Source has no timestamped archive")
    path = (settings.evidence_dir / evidence.archived_path).resolve()
    if (not path.is_relative_to(settings.evidence_dir.resolve()) or file_hash(path) != evidence.sha256
            or not started - timedelta(hours=24) <= _stamp(evidence.retrieved_at) <= finished):
        raise ValueError("Source archive is outside its freshness or integrity bound")
    return _text_pages(path)


def _citation(evidence, started: datetime, finished: datetime) -> bool:
    return bool(evidence.excerpt) and any(quoted(evidence.excerpt, text) for text in _archived(evidence, started, finished))


def _claims(extracted, claims, selection, pages: dict[int, str]) -> None:
    if extracted is None or extracted.claims != claims or extracted.selection != selection:
        raise ValueError("Saved claims must retain the complete extraction input")
    identifier = extracted.model or extracted.family or extracted.product
    if claims and not any(model_quoted(identifier, text) for text in pages.values()):
        raise ValueError("Submitted identity is absent from its pages")
    if extracted.selection and (not selection_supported(extracted.selection, pages)
            or not model_quoted(identifier, extracted.selection.model) or not model_quoted(extracted.selection.model, identifier)):
        raise ValueError("Selected configuration is not supported by its submitted page")
    if extracted.document_revision and not any(revision_supported(extracted.document_revision, text) for text in pages.values()):
        raise ValueError("Submitted revision is not quoted")
    if extracted.family and not any(quoted(extracted.family_quote, text) and family_member(extracted.family, extracted.family_quote or "")
                                    for text in pages.values()):
        raise ValueError("Submitted family is not quoted")
    if len({claim.id for claim in claims}) != len(claims):
        raise ValueError("Claim identifiers must be unique")
    for claim in claims:
        text = pages.get(claim.page, "")
        if (not quoted(claim.quote, text) or not value_quoted(claim.value, claim.quote, claim.property)
                or not metric_quoted(claim.property, claim.quote) or not unit_quoted(claim.unit, claim.quote)
                or claim.variant and not quoted(claim.variant, claim.quote or "")
                or claim.model and not (model_quoted(identifier, claim.model) and model_quoted(claim.model, identifier)
                    or selection and model_quoted(claim.model, text) and model_quoted(claim.model, selection.model))
                or not (model_quoted(identifier, claim.product) or model_quoted(claim.product, identifier) or family_member(claim.product, identifier))):
            raise ValueError("Claim identity, value and quote must survive the submitted-page gates")
        if not claim.variant and not (scope_is_product_wide(claim.scope, claim.scope_quote, claim.quote)
                                      and quoted(claim.scope_quote, text)):
            raise ValueError("A product-wide claim needs its page-grounded scope")
        if claim.selection_quote and (not claim.variant or not selection or claim.selection_quote != selection.quote
                                       or not model_quoted(claim.variant, selection.model)):
            raise ValueError("An option value needs the actual submitted selection")


def _verification(proof, extracted, started: datetime, finished: datetime):
    if proof is None or proof.submitted != extracted:
        raise ValueError("Every item needs an explicit verification outcome bound to its extraction")
    pages = [{"url":source.url, "raw_content":"\n".join(_archived(source, started, finished))} for source in proof.sources]
    output = proof.output.model_copy(deep=True)
    confirmed = verify.gate(output, pages, measure=False, submitted=proof.submitted)
    if output != proof.output:
        raise ValueError("Saved verification values do not survive the web quote gates")
    return verify.compare(proof.submitted, output, confirmed, proof.sources, pages)


def _web_finding(finding) -> dict:
    return finding.model_dump(include={"id", "check", "verdict", "severity", "claim_ids", "quote", "compare", "evidence"})


def _submitted_pages(case: dict) -> dict[int, str]:
    pages = []
    for document in case["submittal"]:
        path = (settings.raw_dir / document["file"]).resolve()
        if not path.is_relative_to(settings.raw_dir.resolve()) or path.suffix.lower() != ".pdf":
            raise ValueError("Submitted evidence must be a native local PDF")
        pages.extend(_text_pages(path))
    return dict(enumerate(pages, start=1))


def _selection_proof(candidate, selection, started: datetime, finished: datetime) -> bool:
    for evidence in candidate.documents:
        if _citation(evidence.model_copy(update={"excerpt":selection.quote}), started, finished):
            path = (settings.evidence_dir / evidence.archived_path).resolve()
            if any(selection_supported(selection, {selection.page:text}) for text in _text_pages(path)):
                return True
    return False


def _requirements(case: dict) -> list[Requirement]:
    checklist = _read(settings.data_dir / "requirements" / (case["section"].replace(" ", "_") + ".json"))
    if not checklist.get("reviewed_at"):
        raise ValueError("Replacement requirements need an owner-reviewed checklist")
    requirements = [Requirement(**row) for row in checklist["requirements"] + case.get("conditions", [])]
    return [row for row in requirements if row.property not in case.get("not_applicable", [])]


def _rescue(result: Result, investigation, started: datetime, finished: datetime) -> bool:
    if investigation.outcome != "found" or investigation.scripted is None or not investigation.steps:
        return False
    steps = investigation.steps
    final = steps[-1]
    extracted = {url for step in steps[:-1] if step.tool == "extract" and step.succeeded is True for url in step.source_urls}
    if (final.tool != "finish" or final.succeeded is not True or final.args.get("found") is not True
            or final.args.get("document_url") not in extracted):
        return False
    missing = set(verify._unambiguous(result.claims)) - set(verify._unambiguous(investigation.scripted.current_values))
    recovered = [row for row in result.comparison if row.property in missing and row.source_url in extracted and any(
        evidence.url == row.source_url and _citation(evidence.model_copy(update={"excerpt":row.quote}), started, finished)
        for finding in result.findings for evidence in finding.evidence)]
    status_recovered = investigation.scripted.status != "discontinued" and any(
        finding.check == "status" and finding.verdict == "fail" and any(evidence.url in extracted and _citation(
            evidence.model_copy(update={"excerpt":finding.quote}), started, finished) for evidence in finding.evidence)
        for finding in result.findings)
    return (bool(status_recovered or any(row.changed for row in recovered)) if investigation.resolution == "problem_found"
            else bool(recovered) and not status_recovered and not any(row.changed for row in recovered))


def _run(folder: Path, ids: set[str], catalog: dict, current: dict, *, score_ids: set[str] | None = None) -> tuple[dict, datetime]:
    identity = _read(folder / "manifest.json")
    if any(identity.get(key) != current[key] for key in IDENTITY_FIELDS):
        raise ValueError("Run does not match current code, configuration, reviewed requirements and document identities")
    if (identity["run_id"] != folder.name or len(identity["requested_ids"]) != len(ids)
            or set(identity["requested_ids"]) != ids or {p.stem for p in (folder / "results").glob("*.json")} != ids):
        raise ValueError("Run must contain exactly its required items")
    started = _stamp(identity["started_at"])
    stored = _read(folder / "scores.json")
    if stored["run_id"] != folder.name or stored["manifest"] != identity or stored["mode"] != "live":
        raise ValueError("Scoreboard must belong to this live run and manifest")
    finished = _stamp(stored["generated_at"])
    if finished < started:
        raise ValueError("Scoreboard predates its run")
    results = {key: Result.model_validate_json((folder / "results" / f"{key}.json").read_text()) for key in ids}
    if any(result.case_id != key or result.mode != "live" or not result.findings or invalid_reasons(result)
           or result.config_hash != identity["config_hash"] for key, result in results.items()):
        raise ValueError("Every release result must be valid live evidence from this configuration")
    for key, result in results.items():
        if result.decision != decide(result.findings):
            raise ValueError("Saved decision does not follow the coded findings")
        requirements = _requirements(catalog[key])
        declared = {document["role"] for document in catalog[key]["submittal"]}
        if not result.document_roles or not declared <= set(result.document_roles):
            raise ValueError("Reviewed document roles must retain submitted scope")
        _claims(result.extracted, result.claims, result.selection, _submitted_pages(catalog[key]))
        if result.document_revision != result.extracted.document_revision:
            raise ValueError("Result revision differs from its extraction")
        web_findings, web_rows = _verification(result.verification, result.extracted, started, finished)
        if ([_web_finding(finding) for finding in result.findings if finding.check in ("currency", "status")]
                != [_web_finding(finding) for finding in web_findings] or result.comparison != web_rows):
            raise ValueError("Saved web findings must match the gated verification outcome")
        expected = spec_check.check(requirements, result.claims, set(result.document_roles))
        by_requirement = {finding.requirement_id:finding for finding in result.findings if finding.requirement_id}
        if (len(by_requirement) != len(expected) or any(finding.requirement_id not in by_requirement or any(
                getattr(finding, field) != getattr(by_requirement[finding.requirement_id], field)
                for field in ("check", "verdict", "severity", "claim_ids")) for finding in expected)):
            raise ValueError("Saved spec findings must cover and match every coded requirement")
        for finding in result.findings:
            if finding.check in ("currency", "status") and finding.verdict in ("pass", "fail", "outdated"):
                proof = []
                for evidence in finding.evidence:
                    quotes = [evidence.excerpt or finding.quote]
                    if finding.compare:
                        quotes += [row.quote for row in finding.compare.rows if row.source_url == evidence.url]
                    proof += [evidence.model_copy(update={"excerpt":quote}) for quote in quotes if quote]
                if not proof or not all(_citation(e, started, finished) for e in proof):
                    raise ValueError("Web verdicts require fresh quoted archived evidence")
                if finding.check == "status" and (not finding.quote or not any(_citation(
                        e.model_copy(update={"excerpt":finding.quote}), started, finished) for e in finding.evidence)):
                    raise ValueError("The actual status quote must occur on a cited archived source")
                if finding.check == "currency" and finding.verdict in ("fail", "outdated") and (
                        not finding.compare or not finding.compare.rows or not all(row.changed and any(
                            e.url == row.source_url and _citation(e.model_copy(update={"excerpt":row.quote}), started, finished)
                            for e in finding.evidence) for row in finding.compare.rows)):
                    raise ValueError("A currency failure needs quoted changed-value rows")
            for candidate in finding.fix.candidates if finding.fix else []:
                if not candidate.passes:
                    continue
                if not candidate.extracted or not candidate.verification:
                    raise ValueError("Passing replacements need extraction and verification proof")
                page_texts = {number:"\n".join(_archived(source, started, finished))
                              for number, source in candidate.page_sources.items()}
                for number, source in candidate.page_sources.items():
                    if not any(document.url == source.url and any(quoted(page_texts[number], text)
                            for text in _archived(document, started, finished)) for document in candidate.documents):
                        raise ValueError("Replacement page is absent from its bundled source")
                _claims(candidate.extracted, candidate.claims, candidate.selection, page_texts)
                primary = candidate.verification.submitted
                _claims(primary, primary.claims, primary.selection, page_texts)
                if any(getattr(primary, field) != getattr(candidate.extracted, field) for field in
                       ("product", "manufacturer", "model", "family", "family_quote", "selection", "document_revision")):
                    raise ValueError("Replacement verification belongs to another submitted identity")
                fix_web, _ = _verification(candidate.verification, primary, started, finished)
                documents = {document.url for document in candidate.documents}
                from .pipeline.fix import _row
                for item in fix_web:
                    item.evidence = [e for e in item.evidence if e.url in documents]
                replayed_checks = [_row(item, {}) for item in fix_web]
                fields = {"check", "ok", "requirement_id", "claim_ids", "evidence"}
                if ([check.model_dump(include=fields) for check in candidate.checks if check.check in ("currency", "status")]
                        != [check.model_dump(include=fields) for check in replayed_checks]):
                    raise ValueError("Replacement currency and availability must replay from actual web proof")
                expected_fix = spec_check.check(requirements, candidate.claims, set(candidate.document_roles))
                checks = {check.requirement_id:check for check in candidate.checks if check.requirement_id}
                if (not candidate.document_roles or not declared <= set(candidate.document_roles) or not candidate.documents
                        or candidate.source_url not in documents or any(e.url not in documents for check in candidate.checks for e in check.evidence)
                        or any(row.verdict not in ("pass", "not_applicable") or row.verdict == "pass" and (
                            row.requirement_id not in checks or checks[row.requirement_id].check != row.check
                            or checks[row.requirement_id].claim_ids != row.claim_ids) for row in expected_fix)
                        or not {"currency", "status"} <= {check.check for check in candidate.checks}
                        or any(check.ok is not True or not check.evidence
                        or not all(_citation(e, started, finished) for e in check.evidence) for check in candidate.checks)):
                    raise ValueError("Passing replacements require every check and its archived quote")
                for check in candidate.checks:
                    for identifier in check.claim_ids:
                        claim = next((claim for claim in candidate.claims if claim.id == identifier), None)
                        if (not claim or not value_quoted(claim.value, claim.quote, claim.property)
                                or not metric_quoted(claim.property, claim.quote) or not unit_quoted(claim.unit, claim.quote)
                                or not any(_citation(e.model_copy(update={"excerpt":claim.quote}), started, finished) for e in check.evidence)):
                            raise ValueError("Replacement check must cite its actual claim quote")
                        if not claim.variant:
                            if (not scope_is_product_wide(claim.scope, claim.scope_quote, claim.quote) or not any(_citation(
                                    e.model_copy(update={"excerpt":claim.scope_quote}), started, finished) for e in check.evidence)):
                                raise ValueError("Replacement property-wide scope is unsupported")
                        else:
                            selection = candidate.selection
                            if (not selection or claim.selection_quote != selection.quote or not quoted(claim.variant, claim.quote or "")
                                    or not model_quoted(claim.variant, selection.model)
                                    or not _selection_proof(candidate, selection, started, finished)):
                                raise ValueError("Replacement option needs a supported selected configuration")
        if any(inv.purpose == "primary" and inv.resolution in ("problem_found", "values_confirmed")
               and not _rescue(result, inv, started, finished) for inv in result.investigations):
            raise ValueError("Primary Investigator rescue needs retrieval and attributable recovery proof")
    attempts = _read(folder / "attempts.json")
    if set(attempts) != ids or any(attempts[key]["diagnostics"] for key in ids):
        raise ValueError("Every requested attempt must have complete diagnostics")
    events = [Event.model_validate_json(line) for line in (folder / "events.jsonl").read_text().splitlines() if line]
    if (any(event.run_id != folder.name or event.case_id is not None and event.case_id not in ids
            or event.stage == "error" or event.data and event.data.get("warning") for event in events)
            or {event.case_id for event in events if event.stage == "done"} != ids
            or sum(event.stage == "done" for event in events) != len(ids)):
        raise ValueError("Run trace must finish every item without swallowed errors")
    if any(event.t_ms < 0 for event in events) or [event.t_ms for event in events] != sorted(event.t_ms for event in events):
        raise ValueError("Run trace timing must be nonnegative and ordered")
    for key, result in results.items():
        stages = [event.stage for event in events if event.case_id == key]
        required = ["queued", "ingest", "triage", "extract", "spec_check", "verify"]
        if any(inv.purpose == "primary" for inv in result.investigations):
            required.append("investigate")
        if result.decision == "send_back":
            required.append("fix")
        required += ["report", "done"]
        cursor = iter(stages)
        if not all(any(stage == wanted for stage in cursor) for wanted in required):
            raise ValueError("Run trace is missing the pipeline stages for this result")
        done = next(event for event in events if event.case_id == key and event.stage == "done")
        if not done.data or done.data.get("decision") != result.decision:
            raise ValueError("Run trace does not match the saved decision")
    run = SimpleNamespace(id=folder.name, results=results, attempts=attempts, manifest=identity,
                          ledger=SimpleNamespace(fresh_usd={key:r.fresh_model_cost_usd for key,r in results.items()},
                                                 fresh_credits={key:r.fresh_web_credits for key,r in results.items()}))
    stored_panel = scores(run, sorted(score_ids or ids), catalog=catalog)
    for key in ("rows", "right_call", "caught", "false_alarms", "fixes_passing", "unnecessary_notes", "validity",
                "quote_gate", "investigations", "fresh_model_cost_usd", "fresh_web_credits", "run_fresh_spend"):
        if stored.get(key) != stored_panel[key]:
            raise ValueError("Stored scoreboard does not match its results, attempts and original labels")
    panel = scores(run, sorted(ids), catalog=catalog)
    panel["mode"] = "live"  # Established above from every stored result, independently of this check's environment.
    panel["generated_at"] = stored["generated_at"]
    return panel, started


def check(bundle_file: Path) -> dict:
    """Never changes a recording or grants approval; missing evidence is an explicit failure."""
    bundle = _read(bundle_file)
    paths = {name: (bundle_file.parent / bundle[name]).resolve() for name in
             ("cases", "samples", "blind", "recording", "blind_set", "review")}
    current = json.loads(json.dumps(manifest()))
    issues, panels, hashes = [], {}, {}
    if not required_documents()["passed"]:
        issues.append("Required native PDFs are missing, unreadable or differ from their frozen hashes")
    try:
        blind, frozen, hashes["blind_set"] = _blind(paths["blind_set"])
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, AttributeError, IndexError):
        blind, frozen = {}, {}
        issues.append("Blind set is missing, invalid, unfrozen or not owner-reviewed")
    cases, samples = all_cases(), all_samples()
    public = {key: item for key, item in {**cases, **samples}.items() if key in cases or item.get("tray") or item.get("watch")}
    catalogs = {"cases": cases, "samples": samples, "blind": blind, "recording": public}
    finished = []
    for name, catalog in catalogs.items():
        try:
            if not catalog:
                raise ValueError("Required catalog is empty")
            panel, started = _run(paths[name], set(catalog), catalog, current, score_ids=set(cases) if name == "recording" else None)
            if name == "blind":
                identity = _read(paths[name] / "manifest.json")
                if _stamp(frozen["reviewed_at"]) > started or identity.get("validation_set_sha256") != hashes["blind_set"]:
                    raise ValueError("Blind evaluation must follow review and bind the exact frozen set")
            panels[name], hashes[name] = panel, run_hash(paths[name])
            finished.append(_stamp(panel["generated_at"]))
        except (OSError, ValueError, KeyError, TypeError, RuntimeError, AttributeError, IndexError):
            issues.append(f"{name}: complete compatible live run and trace required")
    try:
        review = _read(paths["review"])
        if (review["approved_by"].casefold() != "kyle" or review["artifact_hashes"] != hashes or len(hashes) != 5
                or _stamp(review["approved_at"]) < max(finished)):
            raise ValueError("Owner approval must bind all final artifact hashes after evaluation")
        accepted = {(row["suite"], row["id"]): row for row in review["accepted_misses"]}
        if len(accepted) != len(review["accepted_misses"]):
            raise ValueError("Duplicate release dispositions")
        for row in accepted.values():
            if (not row["reason"].strip() or not row["evidence"] or not set(row["misses"]) <= set(MISS_FIELDS)
                    or not row["misses"]):
                raise ValueError("Every accepted miss needs an explanation and source quote")
            for source in row["evidence"]:
                _source_quotes(source)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, AttributeError, IndexError):
        accepted = {}
        issues.append("Dated owner release approval and exact evidence-bound dispositions required")
    used = set()
    for name, panel in panels.items():
        for row in panel["rows"]:
            misses = {key for key, value in {"wrong_call": not row["right_call"],
                "missed_problems": row["caught"] != len(row["expected_problems"]), "false_alarm": row["false_alarm"],
                "unnecessary_note": row["unnecessary_note"]}.items() if value}
            disposition = accepted.get((name, row["id"]))
            if misses:
                if not disposition or set(disposition["misses"]) != misses:
                    issues.append(f"{name}:{row['id']}: unresolved evaluation disagreement")
                else:
                    used.add((name, row["id"]))
            if not row["valid"]:
                issues.append(f"{name}:{row['id']}: invalid evidence cannot be waived")
    if set(accepted) - used:
        issues.append("Release dispositions do not match the observed misses")
    for name in ("cases", "recording"):
        panel = panels.get(name, {})
        if panel.get("fixes_passing", {}).get("n", 0) < 1:
            issues.append(f"{name}: no evidenced passing replacement")
        if panel.get("investigations", {}).get("resolved", 0) < 1:
            issues.append(f"{name}: no demonstrated primary Investigator rescue")
    return {"passed": not issues, "issues": issues, "artifact_hashes": hashes,
            "panels": {name: {key: panel[key] for key in ("run_id", "right_call", "caught", "false_alarms",
                "fixes_passing", "unnecessary_notes", "validity", "quote_gate", "investigations")} for name,panel in panels.items()}}
