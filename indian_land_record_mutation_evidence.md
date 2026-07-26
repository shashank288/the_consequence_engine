# Indian Land-Record Mutation: Evidence and Sample Documents

## Hackathon Pitch Research Pack

**Problem area:** Indian land-record mutation — transfer of ownership after death or sale.

This research pack contains:

1. Defensible baseline figures for a hackathon pitch.
2. Publicly available sample or specimen documents suitable for demonstrations.
3. A recommended privacy-safe demo bundle.

---

## Task 1 — Baseline Figures

### 1. Land/property cases are more likely to remain pending for over five years

- **Publisher:** DAKSH Society
- **Year:** 2016
- **Source:** [Access to Justice Survey — Decoding Delays: Civil Cases](https://www.dakshindia.org/access-justice-survey-decoding-delays-part-civil-cases/)
- **Exact sentence containing the number:**

> “More specifically, we find that ‘Land/property’ matters are 1.36 times more likely to witness pendency of over 5 years compared to all other suits.”

**Pitch-safe interpretation:**  
Land and property disputes are disproportionately likely to become long-running civil cases. This figure does **not** represent the percentage of all Indian civil litigation involving land.

---

### 2. Only 47% of mutation records had been computerised

- **Publisher:** PRS Legislative Research
- **Year:** 2017
- **Source:** [Land Records and Titles in India](https://prsindia.org/policy/discussion-papers/land-records-and-titles-india)
- **Exact sentence containing the number:**

> “However, only 47% of the mutation records (recording the transfer of ownership) have been computerised.”

**Pitch-safe interpretation:**  
This is a historical national DILRMP-progress figure. It shows that mutation-record digitisation lagged behind other land-record modernisation efforts. It should not be presented as the current 2026 national status.

---

### 3. Incorrect identity-document details were found in 155,726 registration cases

- **Publisher:** Comptroller and Auditor General of India
- **Report:** Tamil Nadu Registration Department Audit, Report No. 4 of 2022
- **Tabled:** 2023
- **Source:** [CAG Audit Report](https://cag.gov.in/en/audit-report/details/118801)
- **Exact sentence containing the number:**

> “Audit analysis revealed that the PAN, Aadhaar details & Driving licences in respect of 1,55,726 cases were found incorrect.”

**Pitch-safe interpretation:**  
This is a Tamil Nadu registration-system audit finding, not a national mismatch rate. It directly supports the need for identity reconciliation and controlled uncertainty in property-transfer workflows.

---

## Additional Current Official Dashboard Figure

Punjab’s official Land Records dashboard displayed the following values on **July 25, 2026**:

- **35,827 pending mutation cases**
- **43.99 days mean approval time**
- **18 days median approval time**

- **Publisher:** Punjab Land Records
- **Source:** [Punjab Mutation Dashboard](https://jamabandi.punjab.gov.in/Dashboard.aspx?itemPID=2)

These are dashboard fields rather than a prose sentence. For a pitch, present them as a dashboard screenshot or cite the live dashboard without quotation marks.

---

## Recommended Pitch Wording

> Land mutation is not merely an OCR problem. It requires reconciling legacy ownership records, identity documents, death and succession evidence, and current government workflows—within a system where land cases experience disproportionate long-term pendency and official audits have found large-scale identity-data errors.

### Important qualification

Do not generalise a state-specific audit or dashboard number into a national figure. Clearly distinguish:

- National historical digitisation figures.
- Survey-based litigation findings.
- State-specific audit findings.
- Live state dashboard statistics.

---

# Task 2 — Public Sample and Specimen Documents

## Document Table

| Link | What it is | Language | Handwritten? | Image quality |
|---|---|---|---|---|
| [Direct old-register image](https://wpmedia.prabhatkhabar.com/uploads/2024/09/CoverImage6ddbc64822f347cba0aa3aa5a3ca7f68138-3.jpg) · [Source article](https://www.prabhatkhabar.com/state/bihar/patna/bihar-land-survey-pages-torn-from-register-2-old-khatian-not-found-ancestral-land-of-ryots-in-danger) | Editorial close-up of an aged Bihar land register associated with old khatiyan/Register-II records. The article discusses torn and deteriorating legacy records, including Kaithi-script material. Personal details are not readable at the displayed resolution. | Script not safely identifiable from the photograph; article is in Hindi and discusses Kaithi records | Yes | Medium/low — aged paper, faded writing and physical deterioration; strong pitch visual |
| [Direct thumbnail](https://i.cdn.newsbytesapp.com/images/l144_27691773157856.jpg) · [Source page](https://www.newsbytesapp.com/news/science/this-ai-tool-digitizes-your-old-handwritten-land-records/tldr) | Low-resolution editorial thumbnail accompanying a report about digitising old, faded handwritten land records. Personal information is not readable at this size. | Not identifiable at thumbnail resolution | Appears handwritten | Low, 144 px — use for illustration only, not model evaluation |
| [BharatOCR synthetic Khatauni sample](https://bharatocr.com/) | Privacy-safe mock “Land Record – Khatauni” containing synthetic Hindi names, plot numbers and area fields. It is not an official government record but is suitable for frontend and workflow prototyping. | Hindi, Devanagari | No; printed/synthetic | High and clean — best safe fallback for an end-to-end demo |
| [Official blank 7/12-extract application PDF](https://cdn.s3waas.gov.in/s304025959b191f8f9de3f924f0940515f/uploads/2018/04/2018040684.pdf) · [Government page](https://mumbaisuburban.gov.in/en/form/7-12-extract-application/) | Official Maharashtra application form for obtaining a certified 7/12 extract. This is the application form, not the ownership record itself. It includes Taluka, village, survey and applicant fields but is blank. | Marathi | No; printed form | Medium/high — clean scanned government form |
| [Rajkot Municipal Corporation blank death certificate](https://www.rmc.gov.in/rmcwebsite/pdf_death_certificate.aspx) | Official blank Form No. 6 death-certificate layout containing registration, deceased-person, parent/spouse, place-of-death and address fields. No filled personal data. | Gujarati and English | No; digitally printed | High — clean specimen suitable for extraction tests |
| [Delhi Surviving Member Certificate template](https://edistrict.delhi.gov.in/Public/ViewUploadScanDocumentTemplate?q=jWdPxdcDpwWlm4OG%2Bipyv4FO8Jdj3ZWWjulbkp93BaM%3D) | Official e-District Delhi template for a Surviving Member Certificate, using placeholders for the deceased, surviving relatives and issuing authority. This is the closest official specimen to a legal-heir or varis certificate. | English | No; digital template | High — one-page structured PDF with placeholders |
| [SBI deceased-claim forms PDF — Annexure I-B starts on page 5](https://sbi.bank.in/documents/16012/22770835/18122025_Revised%2BDeceased%2BClaim%2BForms%2Bfor%2BDeposits%2Band%2BSafe%2BDeposit%2BLockers.pdf/719e7408-ed57-a359-2c33-ccb12ba6d362?t=1766040111244#page=5) | Official State Bank of India claim form for settlement of a deceased customer’s deposits where there is no nomination or survivorship mandate. It captures claimant, deceased-account and legal-heir details. | English | No; printed PDF | High — excellent structured downstream document for the death-transfer workflow |
| [Chandrapur District Land Branch mutation checklist](https://chanda.nic.in/en/land-branch/) | Official Maharashtra district checklist under “Mutations and Satbara Records.” For inheritance or deletion after death, it lists documents such as a death certificate, heirship certificate or notarised affidavit, relevant order and supporting records. The page also states a 25-day processing period and submission through the Talathi or e-Hakka system. | English | No; government webpage | High — clean and directly useful as a rules/checklist input |

---

## Recommended Five-Document Demo Bundle

For a privacy-safe hackathon demonstration, use:

1. **Synthetic Hindi khatauni** as the base ownership record.
2. **Blank Marathi 7/12 application** to demonstrate mixed-language form recognition.
3. **Rajkot death-certificate specimen** as proof of death.
4. **Delhi Surviving Member Certificate template** as succession evidence.
5. **SBI deceased-claim form** and the **Chandrapur mutation checklist** as downstream workflow requirements.

Use the faded editorial register photograph only as the memorable legacy-record visual.

For the actual live extraction test, create a synthetic handwritten land-record page based on a historical layout and artificially add:

- Fading
- Rubber stamps
- Overwriting
- Fold marks
- Skew
- Ink bleed
- Partial damage

This preserves privacy while still testing a difficult document-intelligence case.

---

## Suggested Problem Framing

### User

A legal heir, buyer, village-level operator, or revenue-office caseworker handling a mutation application.

### Job to be completed

Convert a mixed bundle of old land records, identity documents, sale or death evidence, and succession documents into:

- A structured mutation case file.
- A reconciled owner-and-heir table.
- A missing-document checklist.
- A list of conflicts requiring human review.
- A submission-ready application summary.

### Difficult input

A faded or handwritten regional-language land record combined with printed certificates whose:

- Names are spelled differently.
- Addresses use different formats.
- Relationship fields are incomplete.
- Plot or survey identifiers appear in multiple scripts.
- Stamps, overwriting or poor scans affect extraction.

### Final usable output

A traceable mutation-readiness report that shows:

- Extracted facts.
- Source document and page.
- Confidence score.
- Detected inconsistencies.
- Missing evidence.
- Recommended next action.
- Human-approval boundary.

---

## Source-Use Notes

- Prefer official government, institutional and audit sources in the pitch.
- Avoid describing an editorial image as an official specimen.
- Do not upload or demonstrate unredacted real ownership records.
- Do not claim that the prototype determines legal ownership.
- Position the product as document preparation, reconciliation and workflow assistance.
- Keep a human revenue official or authorised professional as the final decision-maker.
