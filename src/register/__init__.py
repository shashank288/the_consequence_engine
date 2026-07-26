"""feat/register — card 87: the handwritten mutation-register page.

Build here:
  1. Per-field policy for handwritten pages (thresholds may differ from printed).
  2. Crop generation: bbox -> cropped field image saved under web/crops/,
     path recorded in FieldReading.source.crop_path (escalation shows the CROP,
     not the whole page).
  3. Contradiction check: mocks.prior_record(plot_no) vs extracted owner ->
     Mismatch(classification=...) surfaced in the plan.

Acceptance: a held-out handwritten page produces >=1 refused field routed with
its crop, and 1 contradiction flagged against the mocked prior record.
"""

PRIOR_RECORDS = {  # mocked records system: plot_no -> last accepted entry
    "SN-142/2": {"owner_name": "Ramaiah S.", "entry_year": "1998"},
}


def prior_record(plot_no: str) -> dict | None:
    return PRIOR_RECORDS.get(plot_no)
