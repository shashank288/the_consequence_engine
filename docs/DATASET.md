# Test dataset — what we have, where it came from, what we may claim

## The honest position (say this if a judge asks)

> "The record content is **synthetic** — no real person's land or identity data is
> in this demo, deliberately. What is real is the **difficulty**: mixed Devanagari
> and Latin script, a struck-through owner correction, a tehsil stamp occluding
> the area column, fold lines, corner fade, skew, uneven shop lighting and sensor
> noise. Public real registers at usable resolution all carry live personal data,
> so demoing one would be wrong. The supporting certificates and the tehsil
> checklist below are genuine official specimens."

Never call a generated page an official record. Never call an editorial news
photograph a specimen.

## A. Generated hard input — the card-87 page

`py -3.12 scripts/make_register_page.py --seed <n> --out fixtures/private/<name>.png`

| File | Seed | Role |
|---|---:|---|
| `fixtures/private/register_page.png` | 42 | primary demo page |
| `fixtures/private/register_page2.png` | 7 | second repeated case |
| `fixtures/private/register_holdout.png` | 13 | **held out — do not open during build** |
| `fixtures/private/blank_template.png` | — | ruled blank form, for handwriting by hand |

Deliberate difficulties baked in:
- **Mixed script** — Latin `SN-142/2` survey numbers beside Devanagari names/areas
- **Struck-through correction** — row 2 owner `सुशीला देवी` struck out, `सुशीला बाई`
  written above in red. Which is current? The system must not silently pick one.
- **Stamp occlusion** — tehsil stamp across the क्षेत्रफल (area) column, rows 2–3.
  **This is the refusal that must fire.**
- Fold lines, corner damp fade, ink bleed, ±3° skew, off-centre lighting, noise

⚠️ `fixtures/private/` is git-ignored (privacy hygiene + keeps the repo light).
Regenerate with the seeds above — output is deterministic.

### Better, if you have 10 minutes (asymmetric advantage: you write Devanagari)
1. Print `blank_template.png`.
2. **Handwrite** the rows yourself — vary the pen, strike one name out and rewrite
   it above, let one number run into the next column.
3. Optionally: tea-stain a corner, crease it, press a coin under paper for a
   stamp-like smudge.
4. Photograph at an angle in room light.

Genuine handwriting beats any font. This is a real edge you personally have and
most teams here do not.

## B. Genuine official specimens (blank / template — privacy-safe)

| Document | Source | Use |
|---|---|---|
| Death certificate, Form No. 6 | [Rajkot Municipal Corp](https://www.rmc.gov.in/rmcwebsite/pdf_death_certificate.aspx) | proof of death — satisfies `death_certificate` |
| Surviving Member Certificate | [Delhi e-District template](https://edistrict.delhi.gov.in/Public/ViewUploadScanDocumentTemplate?q=jWdPxdcDpwWlm4OG%2Bipyv4FO8Jdj3ZWWjulbkp93BaM%3D) | succession evidence — closest official legal-heir specimen |
| 7/12 extract application form (Marathi) | [Mumbai Suburban / s3waas PDF](https://cdn.s3waas.gov.in/s304025959b191f8f9de3f924f0940515f/uploads/2018/04/2018040684.pdf) | mixed-language printed form |
| SBI deceased-claim form (Annexure I-B, p.5) | [SBI PDF](https://sbi.bank.in/documents/16012/22770835/18122025_Revised%2BDeceased%2BClaim%2BForms%2Bfor%2BDeposits%2Band%2BSafe%2BDeposit%2BLockers.pdf#page=5) | downstream bank obligation — blocked by mutation |
| **Mutation checklist, Chandrapur district** | [chanda.nic.in Land Branch](https://chanda.nic.in/en/land-branch/) | **the requirements source — quotable `Requirement` text** |

**The Chandrapur checklist is the most valuable item here.** It states, officially,
that inheritance mutation needs a death certificate, heirship certificate or
notarised affidavit, and the relevant order; 25-day processing; Talathi/e-Hakka
submission. That means our blocking edges quote a **real government page** rather
than asserting procedure from memory — which is precisely what IDEA_SCOPE.md §12
forbids us from doing.

## C. Visual only — NOT extraction inputs

- [Bihar aged land register photo](https://wpmedia.prabhatkhabar.com/uploads/2024/09/CoverImage6ddbc64822f347cba0aa3aa5a3ca7f68138-3.jpg)
  ([article](https://www.prabhatkhabar.com/state/bihar/patna/bihar-land-survey-pages-torn-from-register-2-old-khatian-not-found-ancestral-land-of-ryots-in-danger)) —
  strong slide visual of real deteriorating khatiyan records. Editorial photo, not a specimen.
- A 144-px news thumbnail was also suggested by the research pass — **too low-resolution
  to extract from. Do not use.**
- [BharatOCR synthetic khatauni](https://bharatocr.com/) — clean printed synthetic;
  a soft fallback only. Clean input scores Document Intelligence L2–L3, so it does
  not serve our case.

## D. Coverage check against the plan

| Obligation in `fixtures/case_demo.json` | Backing document |
|---|---|
| O1 record correction | generated register page (A) |
| O2 mutation application | Chandrapur checklist (B) |
| O3 bank succession | SBI deceased-claim form (B) |
| O4 duplicate SMS | screenshot you take of any bank SMS |
| O5 unknown slip | photograph any faded thermal receipt |
| `death_certificate` provided fact | Rajkot Form No. 6 (B) |

Impact figures: see [IMPACT.md](IMPACT.md) — Punjab dashboard verified live today.
