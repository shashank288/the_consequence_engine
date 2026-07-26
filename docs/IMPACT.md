# Impact evidence — verified sources

Every figure below was fetched and checked on 2026-07-26. **Rules:** never
generalise a state figure to national; never present a historical figure as
current; quote the publisher and year on the slide.

## 1. The headline baseline (USE THIS ONE)

**Punjab Land Records official dashboard**, values read live 2026-07-26
(dashboard "latest reporting available date": 25/07/2026)
<https://jamabandi.punjab.gov.in/Dashboard.aspx?itemPID=2>

| Metric | Value |
|---|---:|
| Total mutations initiated | 3,113,246 |
| Total sanctioned | 3,077,637 |
| **Currently pending** | **35,609** |
| Pending initiation by Patwari | 31,077 |
| Pending verification by Kanungo | 17,356 |
| Pending sanction by Circle Revenue Officer | 8,938 |
| **Mean approval time** | **43.99 days** |
| **Median approval time** | **18.00 days** |

### The insight that carries the pitch
**Median 18 days. Mean 43.99 days — 2.4× the median.**

A mean that far above the median means the average case is *not* the problem:
a long tail of stuck cases drags it there. Those are the applications that got
rejected and resubmitted, or that sat waiting on a document nobody flagged up
front. **That tail is exactly what this product targets** — and it is one state's
own published number, not our estimate.

Pitch line: *"Punjab's own dashboard: half of mutations clear in 18 days, but the
average is 44. That gap is the resubmission tail. We attack the gap."*

## 2. Identity-mismatch evidence (supports the card-17 mechanic)

**Comptroller and Auditor General of India** — Tamil Nadu Registration Department
Audit, Report No. 4 of 2022 (tabled 2023)
<https://cag.gov.in/en/audit-report/details/118801>

> "Audit analysis revealed that the PAN, Aadhaar details & Driving licences in
> respect of 1,55,726 cases were found incorrect."

**Say:** a state audit found 1.55 lakh registration cases with incorrect identity
document details. **Do not say:** this is a national mismatch rate.

## 3. Why land cases stay stuck (context)

**DAKSH Society**, Access to Justice Survey, 2016
<https://www.dakshindia.org/access-justice-survey-decoding-delays-part-civil-cases/>

> "we find that 'Land/property' matters are 1.36 times more likely to witness
> pendency of over 5 years compared to all other suits."

**Do not say:** "land is X% of Indian civil litigation." That is a different claim.

## 4. Digitisation lag (historical, use with care)

**PRS Legislative Research**, Land Records and Titles in India, 2017
<https://prsindia.org/policy/discussion-papers/land-records-and-titles-india>

> "However, only 47% of the mutation records (recording the transfer of ownership)
> have been computerised."

Historical DILRMP-progress figure. **Do not present as current 2026 status.**

## 5. The requirements source (also feeds the dependency graph)

**Chandrapur District, Maharashtra — Land Branch, "Mutations and Satbara Records"**
<https://chanda.nic.in/en/land-branch/>

Official district checklist. For inheritance/deletion after death it lists a death
certificate, heirship certificate or notarised affidavit, and the relevant order;
states a 25-day processing period; submission via the Talathi or e-Hakka system.

This page is dual-use: it is our **Impact** context *and* a legitimate source of
**quotable `Requirement` text** for blocking edges — the product quotes the
checklist rather than asserting procedure from memory.

## What we claim vs what we must not

| We can say | We must not say |
|---|---|
| Punjab's dashboard shows mean 44 vs median 18 days | "Mutations take 44 days in India" |
| A TN audit found 1,55,726 cases with incorrect ID details | "1 in 3 mutations is rejected" (no source found) |
| Land matters are 1.36× more likely to be pending 5+ years (DAKSH 2016) | "Land is 66% of Indian civil cases" |
| Our own measured accuracy / refusal rate on held-out pages | Any legal validity or title-clarity claim |

## Our own number — measured live on the held-out page

`register_holdout.png` (seed 13) was generated at the start of the build and **never
opened during it**. Run live through `POST /api/case` → real Sarvam doc-digitization
job → plan. Reproduce with `py -3.12 -m scripts.live_holdout`.

| Measure | Result |
|---|---:|
| Consequence-bearing fields seen | 6 |
| Read with a confidence | 3 |
| **Refused and routed to a human** | **3** |
| Refusals carrying a crop for review | 2 |
| Contradictions flagged vs the records system | 1 |
| **Fields guessed wrong** | **0** |
| Refused fields still carrying a value | 0 |
| Wall clock, upload → plan | **72.4 s** |

**The line to say on stage:**

> "On a page this system had never seen, it read three fields, refused three, and
> guessed **zero**. The area column is under a tehsil seal — it says so, shows you
> the crop, and routes it. It does not invent a number that would get the mutation
> rejected."

Read fields: `father_name` 0.90 · `survey_no` 0.85 · `khata_no` 0.85.
Refused: `plot_area` (occluded_by_seal) · `owner_name` (low confidence — the
struck-through correction returned two names) · `deadline` (absent from the page).

⚠️ **72.4 s is a demo risk, not a product claim.** See IDEA_SCOPE §11. Do not run the
live upload cold in front of judges without starting it before you begin talking.
