"""feat/extraction acceptance tests.

WHAT THESE DO AND DO NOT PROVE. M0 could not make a live Sarvam call — there is
no API key on this machine — so every test here runs through SARVAM_OFFLINE=1
against the committed stand-in in src/extraction/offline_sample.json. That means
these tests do NOT prove Sarvam's Document Intelligence reads a degraded
Devanagari page. Nothing can prove that until a key lands and
`fixtures/raw/register_page.docintel.json` holds a real response — at which
point offline replay picks that file up and these same tests re-run against it.

What they DO prove is the part that is ours, and the part that fails a demo if
it is wrong: the policy layer. A field that cannot be read is refused rather
than guessed, a requirement with no verbatim quote never reaches the plan, a
deadline is never invented, and a document we cannot type goes to the unknown
bucket instead of being forced into one.
"""
from __future__ import annotations

import io
import json
import pathlib
import zipfile

import pytest

from src.config import REFUSE_BELOW
from src.contracts import Case
from src.extraction import pipeline
from src.extraction.confidence import score
from src.extraction.pipeline import extract_drafts, presence_facts
from src.sarvam_client import SarvamUnavailable, doc_intelligence_extract
from src.sequencer.core import build_plan

REAL_PAGE = pathlib.Path("fixtures/private/register_page.png")


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    """Replay mode, and an empty raw-cache so a real response cached by a
    previous live run cannot silently change what these tests assert."""
    monkeypatch.setenv("SARVAM_OFFLINE", "1")
    monkeypatch.setattr("src.sarvam_client.RAW_DIR", tmp_path / "raw")


def page(tmp_path: pathlib.Path, stem: str) -> str:
    """A stand-in file on disk. Offline replay keys off the STEM, so the bytes
    are irrelevant — what matters is which sample document it maps to."""
    p = tmp_path / f"{stem}.png"
    p.write_bytes(b"offline replay placeholder")
    return str(p)


def page_text(path: str) -> str:
    payload = doc_intelligence_extract(path)
    return pipeline._pages(payload, doc_id="d")[0].text


# --- the acceptance test ------------------------------------------------------

def test_register_page_produces_a_draft_with_no_silently_wrong_field(tmp_path):
    """The M1 acceptance claim, minus the live call: a photographed register
    page becomes a draft in which every consequence-bearing field is read with a
    confidence and a source, refused, or absent — never a bare value."""
    src = str(REAL_PAGE) if REAL_PAGE.exists() else page(tmp_path, "register_page")
    (draft,) = extract_drafts([src])

    assert draft.doc_type == "mutation_register_page"
    assert draft.unknown is False

    # The page states no deadline, so one must not appear from nowhere.
    assert draft.due is not None
    assert draft.due.status in ("read", "refused", "absent")
    if draft.due.status == "read":
        assert draft.due.confidence >= REFUSE_BELOW and draft.due.source is not None
    else:
        assert draft.due.value is None

    text = page_text(src)
    for f in draft.identity_fields:
        assert f.status in ("read", "refused", "absent")
        if f.status == "read":
            assert f.value and f.confidence >= REFUSE_BELOW
            assert f.source and f.source.quote and f.source.quote in text
        else:
            assert f.value is None, f"{f.name} kept a value it did not earn"


def test_stamp_occluded_area_cell_is_refused_with_its_evidence_intact(tmp_path):
    """The demo's headline refusal. The area column is unreadable, so it is
    refused — and the human still gets the exact characters we saw, which is
    what feat/register crops and shows in the escalation view."""
    src = str(REAL_PAGE) if REAL_PAGE.exists() else page(tmp_path, "register_page")
    (draft,) = extract_drafts([src])

    area = next(f for f in draft.identity_fields if f.name == "plot_area")
    assert area.status == "refused"
    assert area.value is None
    assert area.confidence < REFUSE_BELOW
    assert area.source is not None and area.source.quote
    assert area.source.doc_id == pathlib.Path(src).stem


def test_overwritten_owner_cell_is_refused_not_picked(tmp_path):
    """DATASET.md: row 2's owner is struck through and rewritten. Which name is
    current is not knowable from the page, so the system must pick NEITHER."""
    src = str(REAL_PAGE) if REAL_PAGE.exists() else page(tmp_path, "register_page")
    (draft,) = extract_drafts([src])

    owner = next(f for f in draft.identity_fields if f.name == "owner_name")
    assert owner.status == "refused" and owner.value is None
    # Both candidate names survive in the evidence for a human to adjudicate.
    assert owner.source is not None and owner.source.quote
    assert len(owner.source.quote.split()) > 3


def test_requirements_always_carry_a_verbatim_quote(tmp_path):
    """The Creativity claim: a blocking edge quotes the line it rests on. A
    requirement whose words are not on the page must not exist."""
    src = page(tmp_path, "counter_slip")
    (draft,) = extract_drafts([src])
    text = page_text(src)

    assert draft.needs, "the checklist states requirements; none were extracted"
    for need in draft.needs:
        assert need.quote and need.quote in text
        assert need.source.quote and need.source.quote in text
        assert need.source.doc_id == "counter_slip"


def test_deadline_is_read_with_its_printed_form_as_evidence(tmp_path):
    src = page(tmp_path, "counter_slip")
    (draft,) = extract_drafts([src])

    assert draft.due is not None and draft.due.status == "read"
    assert draft.due.value == "2026-08-14"          # normalised for ordering
    assert draft.due.confidence >= REFUSE_BELOW
    assert "14/08/2026" in (draft.due.source.quote or "")   # the page's own words


def test_a_date_the_page_does_not_frame_as_a_deadline_is_not_promoted(tmp_path):
    """The register page carries mutation references (म. २००४/११) and no due
    date. Turning any of that into a deadline is the exact failure this product
    exists to prevent."""
    src = str(REAL_PAGE) if REAL_PAGE.exists() else page(tmp_path, "register_page")
    (draft,) = extract_drafts([src])
    assert draft.due.status == "absent" and draft.due.value is None


def test_unreadable_document_goes_to_the_unknown_bucket(tmp_path):
    """Never force a type."""
    src = page(tmp_path, "mystery_slip")            # falls through to "default"
    (draft,) = extract_drafts([src])
    assert draft.unknown is True and draft.doc_type == "unknown"
    assert draft.needs == []


def test_model_proposals_without_a_quote_on_the_page_are_dropped(monkeypatch, tmp_path):
    """The LLM is a proposer, never an authority. A requirement it invents —
    however plausible — dies at the gate; one it can actually point to survives."""
    real_line = "3. Name of applicant must match the record-of-rights entry exactly."
    monkeypatch.setattr(pipeline, "offline_mode", lambda: False)
    monkeypatch.setattr(pipeline, "chat_json", lambda *a, **k: {
        "doc_type": "counter_slip",
        "requirements": [
            {"key": "prior_order", "quote": "An order of the Collector is required"},
            {"key": "record_name_matches_id", "quote": real_line},
        ],
        "due": {"value_on_page": "2026-12-31", "quote": "submit before 31/12/2026"},
        "identity_fields": [{"name": "owner_name", "value": "Sushila Devi",
                             "quote": "owner: Sushila Devi"}],
    })

    src = page(tmp_path, "counter_slip")
    (draft,) = extract_drafts([src])
    text = page_text(src)

    assert "prior_order" not in {n.key for n in draft.needs}
    assert "record_name_matches_id" in {n.key for n in draft.needs}
    assert all(n.quote in text for n in draft.needs)
    # The invented deadline and the invented owner never reach the draft.
    assert draft.due.value == "2026-08-14"
    assert all(f.value != "Sushila Devi" for f in draft.identity_fields)


def test_confidence_is_never_certainty_when_the_api_gives_none():
    clean = score("survey_no", "SN-143", "| १३ | SN-143 | रामय्या |")
    assert REFUSE_BELOW <= clean.value < 1.0

    mangled = score("plot_area", "०५ गुठा", "| १३ | ०५ गुठा |")
    assert mangled.value < REFUSE_BELOW
    assert mangled.penalties and mangled.decisive == mangled.penalties[0]

    # An API-reported confidence is used as given, and still cannot reach 1.0.
    assert score("plot_area", "x", "x", api_confidence=1.0).value < 1.0


def test_no_key_and_no_offline_switch_refuses_instead_of_guessing(monkeypatch, tmp_path):
    monkeypatch.delenv("SARVAM_OFFLINE", raising=False)
    monkeypatch.setattr("src.sarvam_client.SARVAM_API_KEY", "")
    with pytest.raises(SarvamUnavailable):
        doc_intelligence_extract(page(tmp_path, "register_page"))


def test_every_offline_sample_entry_declares_its_provenance():
    """The file now mixes one REAL captured response with hand-authored
    stand-ins. Guards against an entry being added — or the real one being
    edited — without the README saying which is which, because "is this actual
    model output?" is the first question a judge asks."""
    sample = json.loads(
        (pathlib.Path("src/extraction/offline_sample.json")).read_text(encoding="utf-8"))
    readme = " ".join(sample["_README"])

    assert "MIXED PROVENANCE" in readme
    assert "A REAL SARVAM RESPONSE" in readme
    for name in sample["documents"]:
        assert name in readme, f"{name} has no provenance line in _README"
    hand_authored = [n for n in sample["documents"] if n != "register_page"]
    assert readme.count("NOT a real API response") >= len(hand_authored)

    # The real capture must still look like one: unpacked pages with layout
    # blocks carrying Sarvam's own confidence.
    blocks = sample["documents"]["register_page"]["content"]["pages"][0]["blocks"]
    assert any(b["layout_tag"] == "table" and b["confidence"] > 0.9 for b in blocks)


# --- the whole chain ----------------------------------------------------------

def test_photos_to_plan_yields_one_next_action_and_a_quoted_blocking_edge(tmp_path):
    """M1 end to end: photographs in, ONE ordered plan out, every blocking edge
    resting on words that are on a page."""
    srcs = [str(REAL_PAGE) if REAL_PAGE.exists() else page(tmp_path, "register_page"),
            page(tmp_path, "counter_slip"),
            page(tmp_path, "bank_letter"),
            page(tmp_path, "mystery_slip")]
    drafts = extract_drafts(srcs)
    case = Case(id="t-extract", drafts=drafts,
                provided_facts=presence_facts(drafts))
    plan = build_plan(case)

    states = {i.obligation_id: i.state for i in plan.items}
    assert "unknown" in states.values()
    assert plan.next_single_action
    assert plan.refusals, "the register page must produce at least one refusal"

    assert plan.edges, "no dependency was derived from the documents' own words"
    texts = {pathlib.Path(s).stem: page_text(s) for s in srcs}
    for edge in plan.edges:
        assert edge.evidence, f"edge {edge.blocked_id}<-{edge.blocker_id} has no evidence"
        for ref in edge.evidence:
            if ref.quote:
                assert ref.quote in texts[ref.doc_id], "edge quotes words off the page"

    # The chain runs bank <- slip <- register: the most urgent item (the bank
    # deadline) is precisely the one that cannot be started yet.
    ordered = [i for i in plan.items if i.state == "actionable"]
    assert len(ordered) >= 1
    assert states[drafts[0].id] == "actionable"
    assert states[drafts[1].id] == "blocked"
    assert states[drafts[2].id] == "blocked"


# --- the live job flow, driven against the documented shapes ------------------

def _result_zip() -> bytes:
    """The verified download payload: a ZIP holding document.md (tables as HTML)
    plus one metadata/page_NNN.json of layout blocks with pixel coordinates."""
    table = ("<table><tbody><tr><td>१३</td><td>SN-143</td>"
             "<td>सुशीला बाई<br/>सुशीला देवी</td></tr></tbody></table>")
    meta = {"page_num": 1, "image_width": 1067, "image_height": 1373,
            "blocks": [
                {"block_id": "b0", "layout_tag": "headline", "confidence": 0.5827,
                 "reading_order": 1, "text": "अधिकार अभिलेख",
                 "coordinates": {"x1": 351.0, "y1": 49.0, "x2": 784.0, "y2": 80.0}},
                {"block_id": "b1", "layout_tag": "table", "confidence": 0.9122,
                 "reading_order": 2, "text": table,
                 "coordinates": {"x1": 27.0, "y1": 89.0, "x2": 1067.0, "y2": 1261.0}}]}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("document.md", f"## अधिकार अभिलेख\n\n{table}")
        zf.writestr("metadata/page_001.json", json.dumps(meta, ensure_ascii=False))
    return buf.getvalue()


class _FakeResponse:
    def __init__(self, payload=None, content=b"", status_code=200):
        self._payload, self.content, self.status_code = payload, content, status_code

    @property
    def text(self):
        return self.content.decode("utf-8", "replace")

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload

    def raise_for_status(self):
        return None


class _FakeClient:
    """Answers with the exact response shapes documented on docs.sarvam.ai and
    records what we sent. This is the M0 call we could not make for real: it
    locks the request sequence so the first live call is not also the first time
    this code path has ever executed."""

    def __init__(self, log):
        self.log = log
        self.status_calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def post(self, url, headers=None, json=None):
        self.log.append(("POST", url, json))
        if url.endswith("/doc-digitization/job/v1"):
            return _FakeResponse({"job_id": "JOB-1", "job_state": "Accepted",
                                  "storage_container_type": "Azure"})
        if url.endswith("/upload-files"):
            return _FakeResponse({
                "job_id": "JOB-1", "job_state": "Accepted",
                "storage_container_type": "Azure",
                "upload_urls": {json["files"][0]: {"file_url": "https://blob/up",
                                                   "file_metadata": None}}})
        if url.endswith("/start"):
            return _FakeResponse({"job_id": "JOB-1", "job_state": "Running"})
        if url.endswith("/download-files"):
            return _FakeResponse({
                "job_id": "JOB-1", "job_state": "Completed",
                "download_urls": {"document.zip": {"file_url": "https://blob/down"}}})
        raise AssertionError(f"unexpected POST {url}")

    def put(self, url, content=None, headers=None):
        self.log.append(("PUT", url, headers, len(content)))
        return _FakeResponse({})

    def get(self, url, headers=None):
        self.log.append(("GET", url, None))
        if url.endswith("/status"):
            self.status_calls += 1
            state = "Running" if self.status_calls < 2 else "Completed"
            return _FakeResponse({"job_id": "JOB-1", "job_state": state,
                                  "job_details": [{"state": "Success"}]})
        return _FakeResponse(content=_result_zip())


def test_live_job_flow_hits_the_documented_endpoints_in_order(monkeypatch, tmp_path):
    log: list = []
    monkeypatch.delenv("SARVAM_OFFLINE", raising=False)
    monkeypatch.setattr("src.sarvam_client.SARVAM_API_KEY", "test-key")
    monkeypatch.setattr("src.sarvam_client.POLL_INTERVAL_S", 0)
    monkeypatch.setattr("src.sarvam_client.httpx.Client", lambda **kw: _FakeClient(log))

    src = tmp_path / "register_page.png"
    src.write_bytes(b"\x89PNG not-really-a-png")
    payload = doc_intelligence_extract(str(src))

    calls = [(m, u.rsplit("/doc-digitization", 1)[-1] if "doc-digitization" in u else u)
             for m, u, *_ in log]
    assert calls == [
        ("POST", "/job/v1"),
        ("POST", "/job/v1/upload-files"),
        ("PUT", "https://blob/up"),
        ("POST", "/job/v1/JOB-1/start"),
        ("GET", "/job/v1/JOB-1/status"),
        ("GET", "/job/v1/JOB-1/status"),
        ("POST", "/job/v1/JOB-1/download-files"),
        ("GET", "https://blob/down"),
    ]

    # A .png is rejected by the API, so it must go up wrapped in a zip.
    upload_body = next(e[2] for e in log
                       if e[0] == "POST" and e[1].endswith("upload-files"))
    assert upload_body["files"] == ["register_page.zip"]
    put_headers = next(e[2] for e in log if e[0] == "PUT")
    assert put_headers["x-ms-blob-type"] == "BlockBlob"      # Azure presigned PUT

    assert payload["provenance"] == "sarvam-doc-digitization"
    assert payload["job_id"] == "JOB-1"

    # The download is a ZIP, and it must be unpacked into pages with blocks.
    content = payload["documents"][0]["content"]
    assert "<table>" in content["markdown"]
    page_one = content["pages"][0]
    assert page_one["page_number"] == 1
    table_block = next(b for b in page_one["blocks"] if b["layout_tag"] == "table")
    assert table_block["confidence"] == pytest.approx(0.9122)
    # Pixel coordinates are normalised 0-1 for the FROZEN SourceRef contract,
    # and kept in pixels alongside for feat/register's crops.
    assert table_block["bbox"] == pytest.approx([27 / 1067, 89 / 1373, 1.0, 1261 / 1373])
    assert table_block["bbox_px"] == [27.0, 89.0, 1067.0, 1261.0]

    # Every step's shape is on disk — that IS the M0 deliverable.
    assert (tmp_path / "raw" / "register_page.docintel.json").exists()
    assert (tmp_path / "raw" / "register_page.result.document.zip").exists()
    assert (tmp_path / "raw" / "register_page.result.metadata_page_001.json").exists()


def test_presence_of_a_death_certificate_satisfies_the_requirement(tmp_path):
    drafts = extract_drafts([page(tmp_path, "counter_slip")])
    assert presence_facts(drafts) == []
    drafts[0].doc_type = "death_certificate"
    assert presence_facts(drafts) == ["death_certificate"]
