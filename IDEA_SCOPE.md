# IDEA_SCOPE.md

> This document is the control plane for the build. If a proposed change does not improve the active milestone's acceptance test or the chosen rubric strategy, place it in the parking lot.

## 0. Scope status

| Field | Value |
|---|---|
| Event | Sarvam Epoch Buildathon, Razorpay Arena, 2026-07-26 |
| Team | Solo — Shashank (backend/systems strong, Hindi fluent, frontend weak) |
| Build starts | 10:30 IST (scope locked ~12:30) |
| Submission deadline | **16:30 IST hard lock** |
| Demo duration | 3 min (30s problem · 30s workflow · 2 min live) |
| Current milestone | M0 |
| Scope owner | Shashank |
| Last updated | 2026-07-26 12:30 IST |

### Status language
**Specified** → **Implemented** → **Working locally** → **Verified** (acceptance test passed) → **Demo-ready** (reset+fallback+rehearsed).

## 1. Idea lock

| Decision | Locked answer |
|---|---|
| One-sentence product | Photograph the whole stack of papers around a land-mutation case and get one ordered, evidence-quoted plan with exactly one next action — every unreadable field refused and routed to a human, never guessed. |
| Specific user | The heir completing mutation of an inherited plot; secondarily the tehsil-counter/CSC facilitator who handles 15–25 such cases a week. |
| Situation and repeated job | After a death in the family: old handwritten record-of-rights + death certificate + tehsil checklist slip + bank succession letter + stray SMSes must be turned into a mutation application that is accepted first time. |
| Current workaround | Read each paper separately, sequence from memory, queue at the wrong counter, get rejected on a name mismatch, return another day (or pay a tout). |
| Hard input | A decades-old **handwritten regional-script mutation-register / record-of-rights page** — photographed at an angle, seals, overwriting, multiple hands — plus printed letters and an SMS screenshot. One page held back unseen for the demo. |
| Final usable output or state change | A **mutation-readiness packet** written to a mocked records endpoint: ordered plan + blocking edges with quoted evidence + cosmetic/blocking mismatch list + refusal queue with cropped field images; Hindi audio summary. |
| Sarvam parameter | **Document Intelligence** |
| Team's unfair advantage | Backend/pipeline engineer: the differentiating mechanic (dependency graph + refusal policy) is deterministic authored logic, not model luck. Hindi fluency to judge output. |
| Creativity thesis | **A sequencer, not an explainer.** Dependencies are DERIVED from the documents' own words and contradictions — every blocking edge quotes the lines it rests on. Sorting by deadline is wrong by design: the most urgent item is often the one that cannot be started yet. |
| Delight thesis | **Refusal-first honesty.** An unreadable field is named, shown as a crop, and routed — analysis is preserved, the user is told exactly what to re-photograph. No false green ticks. |
| Decisive demo proof | Judge's 4 unseen items in → one plan out: blocked edge with quoted reason, duplicate folded, vague item in unknown bucket, illegible field refused with crop. Mark blocker done → plan visibly re-sequences. |

### Why this idea
**Asymmetric fit:** solo backend builder; the scoring mechanic is pure logic wrapped around Akshar/Vision, which the dashboard already supports with duplicatable configs (KYC Document, Court Appeal, GST Registration, Bengali Notarised Land Deed). Voice field is crowded (54/82 library cards); DI is thinner and demo-safe (no mic, no latency).
**Decisive proof:** everything scoring is visible on one screen and repeatable on unseen inputs.
**Lineage:** library cards 50 (spine) + 87 (hard input) + 17 (mismatch) + 01/12/48 (field extraction, attribution, three-state verdict) + 30 (archaic register phrasing, optional).

## 2. User and job

**User:** heir/family member (Hindi-speaking, Khammam-style district context) or counter facilitator. Frequency: every inherited property; facilitator 15–25/week. Existing cost: repeat visits, months of delay, touts, wrongly rejected first submissions.

**Job:** When a landholder dies, the heir needs to get the record mutated into their name **accepted on the first submission**, so the family keeps proof of ownership and downstream claims (bank, crop insurance) unblock.

**Definition of completion:**
1. Every supplied item is classified, or explicitly in the unknown bucket.
2. A single ordered plan exists with exactly one next action and quoted reasons on every blocked item.
3. The mutation-readiness packet is written to the (mocked) records endpoint and re-readable.

Advice, transcription, or extraction alone do NOT count.

## 3. Product contract

### Golden path
1. Upload 4–6 photographed items (or load staged fixture).
2. Extraction → per-field readings with confidence; refusals below 0.75 on consequence-bearing fields.
3. Normalisation → ObligationDrafts (asked_what/by/when + needs WITH QUOTES + provides).
4. Sequencer → plan: dedupe, edges, unknown bucket, status-lookup drop, ONE next action.
5. Packet persisted; corrections propagate; Hindi audio plays; mark-blocker-done re-sequences.

### Inputs
| Input | Format/source | Hard characteristics | Validation |
|---|---|---|---|
| Register page | phone photo JPEG | handwritten, regional script, seal, overwriting, angle | must produce ≥1 refusal on illegible field, never a guess |
| Tehsil checklist slip | photo | printed, lists requirements | requirement quotes extracted verbatim |
| Bank letter | photo | printed | deadline read or refused |
| SMS screenshot | PNG | duplicate of bank letter | must fold into duplicate |
| Held-out page | unseen at build time | judge-supplied | processed live |

### Outputs and state changes
| Output/state change | Consumer | Required format | Proof of completion |
|---|---|---|---|
| Plan | user/judge on screen | ordered items + edges + quotes | visible re-sequence on status change |
| Mutation-readiness packet | mocked records endpoint | JSON (Case) | GET returns it after reload |
| Escalation queue | human reviewer | refused fields + crop images | crop visible, field absent from plan values |
| Hindi audio summary | non-reading user | Bulbul v3 audio | plays in demo |

### Memory boundary
Within one interaction: full case state. Across sessions: case persists by id; corrections recorded with propagation list; reload resumes. Across handoffs: packet is a concise state, not a transcript. Deliberately forget: nothing this demo; single-tenant, no auth (non-goal).

### Human review boundary
Automated: classification, extraction, sequencing, dedupe. Confirmation: corrections. Escalated: every refused field (crop shown). Uncertainty exposure: per-field confidence + explicit refused status + unknown bucket.

## 4. Creativity and Delight
**Obvious version:** upload one notice → summary in Hindi (card 01; everyone builds this).
**Structural mechanic:** cross-document dependency graph with quotable evidence; duplicate collapse; status-lookup drop; card-17 cosmetic-vs-blocking mismatch classification.
**Delight moment:** the refusal — "✋ plot_area cannot be read safely (conf 0.55) — routed to human review" with the cropped seal-covered cell, while the rest of the analysis is preserved.
**Why meaningful:** a guessed plot number creates the wrongly-rejected-farmer failure; refusal is what makes the plan safe to act on.
**Rejected:** avatars, chat UI, WhatsApp integration, voice input, multi-language UI — decoration or scope risk, zero rubric movement.

## 5. Event and sponsor dependency

### Verified capability matrix (docs.sarvam.ai, fetched 2026-07-26)
| Required capability | Product/API/model | Exact endpoint/access | Languages/inputs | Limits | Verification source |
|---|---|---|---|---|---|
| Doc field extraction | Sarvam doc-digitization job API (Vision) | **`/doc-digitization/job/v1{,/upload-files,/{id}/start,/{id}/status,/{id}/download-files}`** — the documented `/api/document-intelligence/*` family **does not exist** | 23 langs, handwriting | input **.pdf or .zip only**, 1 file, 200 MB / 10 pages; `output_format` ∈ {html, md} (**no json**); `job_parameters` **required**; PUT needs `x-ms-blob-type: BlockBlob`; download is a **ZIP** | **VERIFIED LIVE in M0**, job `20260726_46a20ccd…`, 9.4 s |
| Config head-start | Akshar dashboard templates | dashboard (user logged in, 5100 credits) | KYC Doc, Court Appeal, GST Registration, **Bengali Notarised Land Deed (Digitize)** | 12 templates | user screenshot 11:45 |
| Normalisation | sarvam-105b | `POST /v1/chat/completions` | 11 langs | **reasoning model — thinking bills against the answer budget; at max_tokens 2048 it returns 200 with `content: null`. Hard cap 4096 (starter tier); we send 4096** | **VERIFIED LIVE in M0** |
| Hindi text | sarvam-translate | `POST /translate` | 23 langs | — | models page |
| Hindi audio | bulbul:v3 | `POST /text-to-speech` | 11 langs, 30+ voices | — | models page |
| Auth | api-subscription-key header | api.sarvam.ai | — | — | quickstart |

### Load-bearing dependency
Handwritten regional-script register page → structured entry with per-field confidence + source regions. Without Sarvam Vision's Indic handwriting this case fails outright.

### Replacement test
Generic OCR: printed letters survive (commodity); the handwritten sealed register collapses to garbage with no per-field confidence → no refusal policy possible → demo shows exactly this page.

### Unsupported assumptions (must NOT enter critical path)
Creative Studio/dubbing, voice cloning (beta), realtime/telephony, Studio automation via API, WhatsApp/SMS sending, real govt lookups. Doc-Intel request/response shapes unverified until M0.

## 6. Rubric strategy

| Rubric dimension | Mult | Current | Target | Wt pts | Observable proof | Work | Milestone |
|---|---:|---|---:|---:|---|---|---|
| JTBD completion | 2.5× | L1 | L4 | 10 | packet written+re-read; 3 repeated staged cases | pipeline+fixtures | M1–M2 |
| Memory & Context | 1× | L1 | L4 | 4 | reload-resume; correction propagates with visible list | case_store+correct | M4 |
| Creativity | 1.5× | L1 | L4 | 6 | edges with quoted reasons; dedupe; status drop; mismatch classes | sequencer+UI | M2 |
| Impact | 1.5× | **L3** | L4 | 6 | Punjab dashboard verified live: mean 43.99d vs median 18.0d, 35,609 pending — the gap IS the resubmission tail we target (docs/IMPACT.md) | add our held-out accuracy/refusal numbers | M5 |
| Delight | 1× | L1 | L4 | 4 | refusal crop + preserved analysis + retake instruction | register+UI | M3 |
| **Document Intelligence** | 2.5× | L1 | **L4–L5** | 10–12.5 | handwritten page → structure + source refs + controlled uncertainty on unseen page | extraction+register | M1,M3 |
| **Total** | | | | **38.5–42.5 /50** | | | |

**Sarvam strength:** Document Intelligence. **Competence floor:** voice output (one TTS call), UI (one page). **Traps:** flat to-do list (kills Creativity); reusing DocAI competence as Delight; asserting legal rules not on the page; a guessed field live.

## 7. Technical plan

```text
photos/screenshots → Doc-Intelligence job (Vision) → FieldReadings+confidence
      → sarvam-105b normalisation (quotes mandatory) → ObligationDrafts
      → sequencer (pure logic: refusals, dedupe, edges, unknown, status) → Plan
      → case_store persistence → web UI / Hindi TTS / mocked records endpoint
```

| Component | Responsibility | Owner branch | Critical path? |
|---|---|---|---|
| src/contracts.py | frozen pydantic contract | main | yes |
| src/sarvam_client.py + src/extraction/ | API + photo→drafts | feat/extraction | **yes (M0/M1)** |
| src/sequencer/ | drafts→plan | feat/sequencer | yes (done on main, deepen) |
| src/register/ | card-87 crops+contradiction | feat/register | yes (M3) |
| src/case_store/ | persistence+corrections | feat/case-memory | no (lite works) |
| web/ | one-page UI | feat/ui | yes (exists, deepen) |
| src/voice/ | Hindi TTS | feat/voice | **no — first cut** |

State: Case JSON (cases.json → SQLite optional). External deps: api.sarvam.ai only; fallback = cached raw responses in fixtures/raw/ + Akshar Studio manual export. Secrets: SARVAM_API_KEY in .env only.

## 8. Time-boxed build ladder (actual clock)

### M0 — 12:30–13:00 · Feasibility
One real photographed page through the Doc-Intel job flow; shapes recorded in sarvam_client; raw response cached. Docs sourced (GPT prompt running in parallel).
**Accept:** one real input completes the riskiest call. **Stop:** if Doc-Intel API unusable by **13:15** → fallback: Akshar Studio manual extraction → JSON → fixtures (JTBD L3 preserved); if no handwritten page sourced by **13:30** → drop card 87, Option-1 doc set (re-KYC), DI target L4.

### M1 — 13:00–13:45 · Ugly E2E (JTBD L3)
extraction/pipeline.py: photo→draft (1 doc type); wire POST /api/case; plan renders from a REAL photo.
**Accept:** unedited run: photo in → plan with ≥1 read-or-refused deadline. **Cut to:** fixture-mode demo (already green).

### M2 — 13:45–14:30 · Full sequencer on real docs (Creativity)
All 4–5 doc types through; dedupe/edges/unknown verified on real set; UI edges panel polished.
**Accept:** tests/test_sequencer.py + real-set run shows edge with quote + duplicate + unknown. **Cut to:** 3 doc types.

### M3 — 14:30–15:10 · Card 87 hard edge (DI L4→L5, Delight)
Handwritten page: thresholds, crop generation, contradiction vs mocked prior record; escalation view shows crop.
**Accept:** held-out handwritten page → ≥1 refusal WITH crop + 1 contradiction flag, live. **Cut to:** refusal without crop image (quote only).

### M4 — 15:10–15:40 · Memory + Hindi (Memory L4)
Reload-resume verified; correction propagates (list visible); TTS button if smooth.
**Accept:** correct owner_name once → mismatch clears, propagated_to lists items, survives reload. **Cut to:** drop TTS (voice is first cut, stated in §7).

### M5 — 15:40–16:20 · Hardening + submission
Public URL (tunnel), 3 repeated runs incl. unseen page, reset script, fallback recording, submission form, eval note (accuracy+refusal counts on held-out pages), 2 timed rehearsals. **No new features.**
**Accept:** two consecutive timed rehearsals pass, one on fallback. **16:20 hard stop → submit.**

## 9. Test plan
**Golden:** (1) fixture demo case; (2) real printed set (slip+bank+SMS+death cert); (3) real set + handwritten page. **Unseen:** one register page never opened during build; judge may supply their own photo; success = correct plan + honest refusals, zero guessed consequential fields. **Failure cases:** ambiguous slip→unknown bucket (tested in fixture); unsupported input→unknown; API timeout→cached raw responses; contradictory correction→last-write wins, logged with propagation.

## 10. Demo contract
**Setup (1 sentence):** "After a death, a family's land mutation gets rejected on a decades-old handwriting mismatch — this turns the whole paper stack into one safe next action."
**Live proof (2 min):**
| Time | What happens | Judge sees | Rubric |
|---:|---|---|---|
| 0–20s | drop 4 unseen items incl. handwritten page | ingestion, doc types | — |
| 20–50s | plan renders | ONE next action; blocked edge with quoted reason; duplicate folded; unknown bucket | Creativity, JTBD |
| 50–75s | illegible cell | ✋ refused with cropped seal-covered field, routed | **Doc Intelligence**, Delight |
| 75–95s | mark blocker done (mock tehsil) | plan re-sequences live | JTBD |
| 95–110s | correct owner_name | mismatch clears, propagation list, reload resumes | Memory |
| 110–120s | packet + Hindi audio | final artifact + spoken summary | JTBD close |
**Fallback:** fixture case + screen recording. **Claims we can prove:** field accuracy + refusal counts on our held-out pages. **Claims we must NOT make:** legal validity, title clarity, real govt integration, any rule not quoted from a page.

## 11. Risk register
| Risk | P | Damage | Test | Mitigation | Fallback |
|---|---|---|---|---|---|
| Doc-Intel shapes ≠ assumed | M | M1 slips | 12:45 | M0 first call | Akshar Studio manual export |
| No handwritten page sourced | M | DI L5 lost | 13:30 | GPT sourcing now | Option-1 set, DI L4 |
| LLM normalisation flaky | M | edges wrong | M1 | quotes mandatory, cache raw, few-shot | hand-fix drafts JSON (staged = sanctioned) |
| Venue network | M | live fail | M5 | localhost + tunnel + recording | recording |
| Solo time | H | M3+ unfinished | each gate | cut order: voice → crops → SQLite → correction UI | fixture demo is always green |

**Pre-mortem:** (1) judge saw a to-do list → edges+quotes are the hero panel, demo leads with them; (2) a guessed field live → hard threshold + held-out rehearsal; (3) nothing e2e at 16:20 → fixture golden path locked green from 12:30.

## 12. Non-goals
1. No legal advice, no "title is clear", no asserted procedure beyond quoted pages. 2. No real government/bank integration; mocks only. 3. No voice INPUT, telephony, WhatsApp, dubbing. 4. No auth/multi-tenant. 5. No UI beyond the one page. 6. No OCR training/fine-tuning.

## 13. Parking lot
| Idea | Value | Why not now |
|---|---|---|
| WhatsApp delivery | reach | unprovisioned messaging |
| SQLite + multi-case list | Memory L5 | lite store suffices for L4 |
| English↔Telugu UI toggle | breadth | zero rubric points |
| Voice Q&A over the plan | wow | wrong Sarvam parameter |
| Real Bhulekh lookup | authenticity | unverifiable on floor |

## 14. Team execution
| Person/agent | Ownership | Current task |
|---|---|---|
| Shashank | decisions, docs sourcing, Akshar configs, demo | run GPT sourcing prompt; photograph docs |
| Claude (main) | scope, merges, M0 verify | M0 API call |
| Agent A | feat/extraction | after M0 |
| Agent B | feat/register | after M1 |
| Agent C | feat/ui, feat/voice | after M2 |
Rules: one owner per component; contracts.py frozen; golden path stays runnable; merge order extraction→sequencer→register→case-memory→ui→voice.

## 15. Current state
**Active:** M0. **Implemented:** contracts, sequencer core, fixture, tests, app, case_store lite, web UI, stubs. **Working locally:** fixture golden path (pending first `pytest` run). **Verified:** —. **Demo-ready:** —. **Blocker:** SARVAM_API_KEY into .env + document sourcing. **Next single action:** M0 Doc-Intel call with one real photographed page.

## 16. Decision log
| Time | Decision | Reason |
|---|---|---|
| 11:20 | Set A over B/C/D/E | risk shape for solo + template head-start |
| 12:05 | Reframe user to counter/heir | Impact needs payer+frequency |
| 12:10 | Option 2 (land mutation) over Option 1 | card 87 native → DI L5 reachable |
| 12:30 | Voice = first cut | DI is the scored parameter |
| 13:50 | Hard input = generated synthetic register page, real degradation | No public real handwritten register exists at usable resolution without live personal data. Content synthetic, difficulty real (mixed script, struck-through correction, stamp occlusion, fold/fade/skew). Framing in docs/DATASET.md |
| 13:55 | Impact baseline = Punjab jamabandi dashboard | Verified live today; mean 43.99d vs median 18.0d gap is a defensible, state-published number. Impact L3 secured, L4 on our own held-out numbers |
