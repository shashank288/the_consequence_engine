"""Mocked records system — the "last accepted entry" for a plot.

Stands in for the tehsil/e-Hakka lookup we are not allowed to make. Deliberately
mixed-script, because a real records database is: some entries were typed in
transliterated Latin, some in Devanagari, and that inconsistency is exactly what
makes a name check hard at the counter.

Synthetic content. No real person's land or identity data (docs/DATASET.md).
"""
from __future__ import annotations

PRIOR_RECORDS: dict[str, dict] = {
    # plot/survey number -> the entry the records system currently holds
    "SN-142/2": {"owner_name": "Ramaiah S.", "entry_year": "1998",
                 "mutation_ref": "M. 1998/47"},
    "SN-143": {"owner_name": "Sushila Devi", "entry_year": "2004",
               "mutation_ref": "M. 2004/11"},
    "SN-144/1": {"owner_name": "Lakshmamma", "entry_year": "1987",
                 "mutation_ref": "M. 1987/09"},
    "SN-145": {"owner_name": "गोविंद राव", "entry_year": "2011",
               "mutation_ref": "M. 2011/03"},
}


def prior_record(plot_no: str) -> dict | None:
    """The last accepted entry for a plot, or None if the plot is not on file.

    Matching is exact on the printed plot number and then on a whitespace/case
    fold — never fuzzy. Guessing which record a half-read plot number refers to
    is precisely the error this product exists to prevent.
    """
    if plot_no is None:
        return None
    if plot_no in PRIOR_RECORDS:
        return PRIOR_RECORDS[plot_no]
    key = "".join(plot_no.split()).upper()
    for plot, rec in PRIOR_RECORDS.items():
        if "".join(plot.split()).upper() == key:
            return rec
    return None
