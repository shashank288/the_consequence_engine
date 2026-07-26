# DEMO RUNBOOK — The Consequence Engine

**3 minutes: 30s problem · 30s current workflow · 2 min live.**
Print this. Do not improvise the cold open.

---

## Before you walk up (5 minutes, do it once)

```powershell
cd c:\Projects\Hackathon_26\Sarvam
py -3.12 -m scripts.smoke          # 27/27 → the demo path is intact
py -3.12 -m uvicorn src.app:app --port 8000
```
Open **http://localhost:8000**. Then:

1. Click **Load demo case** → confirm the rail renders and the banner is filled.
2. Click **⟲ Reset case** → back to as-loaded. *(Always reset before the judges arrive.)*
3. Have `fixtures/private/register_holdout.png` findable in **one click** in the file picker.
4. Have the fallback recording open in a background tab.
5. Zoom the browser so the banner + full rail sit above the fold on the projector.

**If the venue network is bad:** skip Beat 4 entirely. Beats 1–3 and 5 are all local
and need no key. Say "I've run the live extraction already — here are the numbers,"
and show `docs/IMPACT.md`. Never wait on a spinner in front of judges.

---

## ⏱ THE SEQUENCE — read the timing note first

The live Sarvam job takes **~72 seconds**. That is longer than the demo beat it
belongs to. **So it runs in the background while you talk.**

**Start the upload FIRST, before you say a word.** Click upload, select
`register_holdout.png`, hit go — *then* turn to the judges and start your 30-second
problem statement. By the time you finish Beats 1–3, the result is waiting for you.

Never click upload and then watch it. That is the one way to lose this demo.

---

## 0:00–0:30 · The problem

> "When someone in an Indian family dies and leaves land, the family has to transfer
> the record into their name — a mutation. The paperwork fights itself. The name on a
> handwritten register from decades ago never matches the spelling on a modern ID.
> One office needs another office's step finished first, and nobody tells you which.
>
> So people take a morning off, queue at the wrong counter, and get sent home."

*(Upload is running. Do not look at it.)*

## 0:30–1:00 · What happens today

> "Punjab publishes its own numbers. Half of all mutations clear in 18 days. But the
> **average is 44**. That gap is the tail — the applications that got rejected and
> resubmitted, over a name mismatch nobody caught up front.
>
> Today a clerk sequences that stack from memory. We turn the pile into one ordered
> plan — and, crucially, we refuse to guess."

## 1:00–1:30 · Beat 1–2 · The dependency is the product

**Click: Load demo case.**

> "Four papers and an SMS. One thing is doable — the banner says which. Two are
> waiting on it."

**Point at the O2 card — do not click.**

> "This one is blocked. And it tells you *why*, in the document's own words:
> *'Name of applicant must match record-of-rights entry exactly'* — quoted from the
> tehsil slip, page 1. We don't assert procedure from memory. Every blocking link is
> a sentence we can point at on a page.
>
> Note it's **not sorted by deadline**. The most urgent item is the one that can't be
> started yet. The duplicate SMS folded into the bank letter. The slip we couldn't
> classify is in an unknown bucket — surfaced, not dropped."

## 1:30–1:50 · Beat 3 · Memory + re-sequence

**Click: Correct → propagate** *(prefilled)*

> "Correct the name once. It propagates to every obligation that used it, and the
> screen says exactly where. Note it says this **did not** unblock the next step —
> because it didn't. The record still has to be filed."

**Click: Mark record corrected ✓**

> "*Now* it re-sequences. The next action rewrites itself."

## 1:50–2:20 · Beat 4 · THE CLOSER — the live unseen page

**Switch to the upload result. It finished while you were talking.**

> "This page went through Sarvam's document intelligence sixty seconds ago. Nobody
> here has seen it — it was generated at the start of the day and sealed.
>
> Six fields that carry consequence. It read three. **It refused three. It guessed
> zero.**"

**Point at the refused area cell and its crop.**

> "That's not a low confidence score. Sarvam returned that table at **0.91** — the
> model was confident. But we looked at the pixels: a tehsil seal is stamped across
> 46% of that cell's writing. So we overrule the confidence and route it, with the
> crop, so a human can settle it in one glance.
>
> And the owner's name came back as **two names** — the register has a struck-through
> correction. We don't pick one. Both survive for a human to adjudicate."

## 2:20–2:30 · Close on the consequence

> "A guessed plot number doesn't just produce a wrong answer — it produces a
> **rejected mutation** and another wasted morning. Refusing is the feature.
>
> Three fields read. Three refused. Zero guessed."

---

## Answers to the questions you will get

**"Is this a real land record?"**
> "No, and deliberately. The content is synthetic — no real person's data. The
> *difficulty* is real: mixed Devanagari and Latin, a struck-through correction, a
> seal over the figures, folds, skew, shop lighting. Public registers at usable
> resolution all carry live personal data. Demoing one would be wrong."

**"Where did that dependency come from?"**
> "The documents. Every blocking edge quotes the line it rests on, with the page.
> We never assert a legal rule we haven't read off the paper."

**"What if the OCR is wrong?"**
> "Then it should refuse, and mostly it does. We can't detect a *wrong* reading — only
> an unsupportable one. That's why a human approves before anything is filed."

**"Why refuse instead of showing low confidence?"**
> "A confidence score next to a number still puts the number in front of someone in a
> hurry. An empty field with a crop makes them look."

**"Did you use Sarvam properly?"**
> "The doc-digitization job API, live. We also found five errors in the published
> docs doing it — the documented endpoint family doesn't exist, `output_format: json`
> 400s, `job_parameters` is required, the download is a ZIP, and `sarvam-105b`
> silently returns null content at the default token limit because thinking bills
> against the answer budget."

---

## Never claim

- That it determines legal ownership or clear title
- That any government or bank system is really integrated *(all mocks — say so)*
- A national statistic from Punjab's state dashboard
- That the register page is a genuine official record

## The three numbers to have on your tongue

- **44 vs 18 days** — Punjab's own mean vs median mutation approval
- **0.91 → refused** — Sarvam's confidence on the sealed cell, overruled by pixels
- **3 read, 3 refused, 0 guessed** — the held-out page, live
