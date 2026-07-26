# DEMO SCRIPT — click by click

Everything below is a real thing on your screen. **Left column = what you click.
Right column = what you say.** If a step confuses you, skip it — the demo still works.

---

## SETUP (do this before you hit record)

```powershell
Get-NetTCPConnection -LocalPort 8000 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
cd c:\Projects\Hackathon_26\Sarvam
py -3.12 -m uvicorn src.app:app --port 8000
```

Open **http://localhost:8000**, press **Ctrl+Shift+R** (hard refresh).

You should see a dark page. At the **top right** there are three things:
`Resume saved case…` dropdown · `⟲ Reset case` button · **`Load demo case`** button.

**Click `⟲ Reset case` if it's enabled, then reload the page.** You want a clean screen.

### What's on the screen (so you know what you're looking at)

| Where | What it is |
|---|---|
| Top strip, full width | **Banner** — the one thing to do next. Empty until you load a case. |
| Below it | **"The plan is a chain, not a list"** — cards left to right, joined by arrows |
| Left column, top | **Escalation queue — refused, not guessed** — fields it wouldn't read |
| Left column, bottom | **Name / identity mismatches** + three text boxes and a `Correct → propagate` button |
| Right column, top | **Upload photographed stack** — drag & drop box |
| Right column, bottom | **Mock tehsil status** — `Mark record corrected ✓` button + activity log |

---

## THE RECORDING — 5 steps, ~2 minutes

### STEP 0 — start the upload FIRST (it takes 72 seconds)

**Click** the `📷 Drag & drop the paper stack here` box in the right column.
**Choose** `fixtures/private/register_holdout.png`.

Now **turn away from it and keep talking.** It runs in the background. You come back
to it at Step 5. **Do not sit and watch it.**

---

### STEP 1 — the problem *(~25 seconds, nothing to click)*

> "When someone in an Indian family dies and leaves land behind, the family has to get
> the land record changed into their name. It's called a mutation.
>
> The problem isn't reading the papers. It's that the papers contradict each other. A
> handwritten village register from decades ago spells a name one way, the person's ID
> spells it another way, and one office won't move until a different office has
> finished its step — and nobody tells you which order to do them in.
>
> So people take a day off work, stand in the wrong queue, and get sent home."

---

### STEP 2 — load the case *(~20 seconds)*

**Click `Load demo case`** (top right).

The screen fills. **Point at the big banner at the top.**

> "This is a family's actual pile: a village land record, a slip from the tehsil
> office, a letter from the bank, a text message, and one slip nobody could identify.
>
> The banner tells them the one thing to do first. Not a to-do list — one action."

**Point at the row of cards below it** (green card on the left, greyed cards to the right).

> "The green one is the only thing that can be started. The grey ones are waiting on
> it."

---

### STEP 3 — why it's blocked *(~25 seconds — this is your strongest moment)*

**Point at the second card** (grey, has a 🔒 on it). **Don't click — just point.**

> "This one is blocked. And it doesn't just say 'blocked' — it says why, using the
> document's own words:
>
> *'Name of applicant must match record-of-rights entry exactly'*
>
> That sentence is quoted off the tehsil slip, page one. We never tell the user a rule
> we haven't read off their own paperwork."

**Point at the arrow between the two cards.**

> "And notice it's not sorted by deadline. The most urgent item is the one that can't
> be started yet — so putting it at the top would send them to the wrong counter."

**Point at the two small items below the cards** (the duplicate and the unknown).

> "The text message was the same request as the bank letter — folded into one. And the
> slip we couldn't identify isn't thrown away; it's flagged for a human."

---

### STEP 4 — correct a name, then unblock *(~25 seconds)*

The three text boxes in the left column are **already filled in** — `record_page_1947`,
`owner_name`, `SUSHILA DEVI`. You don't have to type anything.

**Click `Correct → propagate`.**

A **Memory** panel appears in the middle of the screen.

> "The family corrects the spelling once. It updates everywhere that name was used, and
> the screen lists exactly which items changed.
>
> And read what it says — it did *not* unblock the next step. Because correcting a
> spelling on your own screen doesn't file anything at the tehsil. It's honest about
> that."

**Click `Mark record corrected ✓`** (right column, bottom).

> "*Now* the record is actually corrected at the office — and the plan re-sequences
> itself. The banner rewrites to the next action."

---

### STEP 5 — the live page *(~25 seconds — your closer)*

**Scroll back to the upload box.** It finished while you were talking.

> "This page went through Sarvam's document intelligence about a minute ago. It was
> generated at the start of the day and never opened — nobody here has seen it.
>
> Six fields on it carry real consequence. It read three. **It refused three. It
> guessed zero.**"

**Point at the Escalation queue** (left column) — there are cropped images in it.

> "This is the area column. Sarvam read that table at **0.91 confidence** — the model
> was sure. But we looked at the actual pixels and a tehsil office stamp is sitting on
> top of 46% of that cell's writing.
>
> So we overrule the confidence, and hand the human the cropped image so they can settle
> it in one look."

**Point at the owner name row in the same panel.**

> "And the owner's name came back as *two names* — the register has a name struck out
> and rewritten above it. We don't pick one. Both are kept for a person to decide."

---

### CLOSE *(~10 seconds)*

> "If this guessed a plot number, it wouldn't just be wrong — the mutation gets
> rejected and the family loses another month.
>
> That's why refusing is the feature. Three read. Three refused. **Zero guessed.**"

---

## If something breaks mid-recording

| Problem | Do this |
|---|---|
| Upload spins forever / network dead | Skip Step 5. Steps 1–4 need no internet. Say "I've already run the live extraction — here are the numbers" and read the three numbers below. |
| Screen looks wrong / stale | Ctrl+Shift+R, click `Load demo case` again |
| You want to re-record | Click `⟲ Reset case`, then `Load demo case`. Back to the start. |

## Three numbers, if you're asked

- **Sarvam said 0.91, we refused it** — because a stamp covers the cell
- **3 read, 3 refused, 0 guessed** — on a page the system had never seen
- **44 days vs 18 days** — *optional, only if you're comfortable:* Punjab's land records
  department publishes a live dashboard. Half of mutations finish in 18 days, but the
  average is 44 — that gap is the pile of applications that got rejected and resubmitted.
  **If you don't want to use this, don't. Skip it.**

## Never say

- That it decides who legally owns land
- That any government or bank system is really connected (they're all mocks)
- That the register page is a real official document — **it's synthetic content with
  real difficulty baked in, and saying so is a strength, not a weakness**
