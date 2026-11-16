"""
transforms.py
=============
Turns the raw dicts that openalex.py returns into tidy pandas DataFrames
that Plotly can chart directly.

The split is deliberate:
    openalex.py   talks to the internet      (HTTP, JSON)
    transforms.py reshapes data              (pandas, no internet)
    app.py        displays it                (Streamlit, Plotly)

Each layer can be tested without the other two. That is the whole reason the
project is split this way, and it is a good answer if the viva asks why you
did not just write one long script.
"""

import math
import re

import pandas as pd


# ---------------------------------------------------------------------------
# Yearly trend
# ---------------------------------------------------------------------------

def yearly_trend(counts_by_year, year_from, year_to):
    """
    Build the headline chart's data from the institution's counts_by_year.

    Input is a list like:
        [{"year": 2025, "works_count": 1820, "cited_by_count": 41230}, ...]

    Returns a DataFrame with one row per year, oldest first:
        year | publications | citations
    """
    if not counts_by_year:
        return pd.DataFrame(columns=["year", "publications", "citations"])

    frame = pd.DataFrame(counts_by_year)

    frame = frame.rename(
        columns={"works_count": "publications", "cited_by_count": "citations"}
    )

    # Keep only the years the user selected in the sidebar.
    frame = frame[(frame["year"] >= year_from) & (frame["year"] <= year_to)]

    # OpenAlex returns newest first; charts read better oldest first.
    frame = frame.sort_values("year").reset_index(drop=True)

    return frame[["year", "publications", "citations"]]


def yearly_from_groups(groups):
    """
    Fallback trend builder, using group_by=publication_year instead.

    counts_by_year only goes back about 13 years. If the user drags the
    sidebar slider back to 2000, we use this instead - it covers the full
    history, though it gives publications only, with no citation figures.
    """
    frame = _groups_to_frame(groups, label_name="year")
    if frame.empty:
        return pd.DataFrame(columns=["year", "publications"])

    frame["year"] = pd.to_numeric(frame["year"], errors="coerce")
    frame = frame.dropna(subset=["year"])
    frame["year"] = frame["year"].astype(int)

    return frame.sort_values("year").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Generic group_by handling
# ---------------------------------------------------------------------------

def _groups_to_frame(groups, label_name="label"):
    """
    Convert openalex.group_works_by() output into a DataFrame.

    Every group_by response has the same shape, so every chart that is fed by
    one can share this single function.
    """
    if not groups:
        return pd.DataFrame(columns=[label_name, "publications"])

    # Build the two columns we want explicitly, rather than loading the whole
    # dict and renaming. Renaming would break whenever `label_name` happens to
    # clash with a key already present in the raw group ("key", for instance).
    return pd.DataFrame(
        {
            label_name: [group.get("label") for group in groups],
            "publications": [group.get("count", 0) for group in groups],
        }
    )


def top_groups(groups, top_n, label_name="label", exclude=None):
    """
    Take the biggest N groups, optionally dropping some labels first.

    `exclude` matters for two charts:
      - partner institutions: CHRIST co-authors every one of its own papers,
        so it would always be the number one "partner". We drop it.
      - collaborator countries: India dominates for the same reason, so the
        world map is more readable with it removed.
    """
    frame = _groups_to_frame(groups, label_name=label_name)
    if frame.empty:
        return frame

    if exclude:
        # Case-insensitive, partial match - institution names vary slightly
        # between OpenAlex records ("Christ University" vs "CHRIST (Deemed
        # to be) University").
        #
        # re.escape matters here: institution names contain brackets, and an
        # unescaped "(" would be read as the start of a regex group and raise
        # a pattern error instead of matching a literal bracket.
        pattern = "|".join(re.escape(term) for term in exclude)
        keep = ~frame[label_name].str.contains(pattern, case=False, na=False)
        frame = frame[keep]

    frame = frame.sort_values("publications", ascending=False)
    return frame.head(top_n).reset_index(drop=True)


def open_access_split(groups):
    """
    Turn the true/false open-access groups into readable labels.

    OpenAlex may return the key as a boolean or as the string "true",
    depending on the endpoint, so we handle both.
    """
    frame = _groups_to_frame(groups, label_name="key")
    if frame.empty:
        return pd.DataFrame(columns=["access", "publications"])

    def readable(value):
        text = str(value).strip().lower()
        if text in ("true", "1"):
            return "Open access"
        if text in ("false", "0"):
            return "Restricted"
        return "Unknown"

    frame["access"] = frame["key"].apply(readable)
    frame = frame.groupby("access", as_index=False)["publications"].sum()
    return frame.sort_values("publications", ascending=False).reset_index(drop=True)


def open_access_percentage(oa_frame):
    """What share of papers are freely readable? Returns a number 0-100."""
    if oa_frame.empty:
        return 0.0

    total = oa_frame["publications"].sum()
    if total == 0:
        return 0.0

    open_rows = oa_frame[oa_frame["access"] == "Open access"]
    open_count = open_rows["publications"].sum()
    return round((open_count / total) * 100, 1)


# ---------------------------------------------------------------------------
# Individual papers
# ---------------------------------------------------------------------------

def works_to_frame(works):
    """
    Flatten paper records into a table.

    The raw JSON for one paper is deeply nested - authors inside authorships
    inside a list, the journal inside primary_location inside source. This
    function digs each value out once, defensively, so the UI layer never has
    to worry about a missing key.
    """
    rows = []

    for work in works:
        authorships = work.get("authorships") or []

        # First author's name, if anyone is listed.
        first_author = ""
        if authorships:
            author = authorships[0].get("author") or {}
            first_author = author.get("display_name") or ""

        # Journal or conference name.
        location = work.get("primary_location") or {}
        source = location.get("source") or {}
        venue = source.get("display_name") or ""

        # Research field.
        topic = work.get("primary_topic") or {}
        field = (topic.get("field") or {}).get("display_name") or ""

        open_access = work.get("open_access") or {}

        rows.append(
            {
                "Title": work.get("display_name") or "(untitled)",
                "Year": work.get("publication_year"),
                "Citations": work.get("cited_by_count", 0),
                "Field": field,
                "Authors": len(authorships),
                "First author": first_author,
                "Published in": venue,
                "Open access": "Yes" if open_access.get("is_oa") else "No",
                "Link": work.get("doi") or "",
            }
        )

    if not rows:
        return pd.DataFrame(
            columns=[
                "Title", "Year", "Citations", "Field", "Authors",
                "First author", "Published in", "Open access", "Link",
            ]
        )

    frame = pd.DataFrame(rows)

    # "Int64" with a capital I is pandas' nullable integer type. Plain int
    # cannot hold a missing value, so a single paper with no year would turn
    # the whole column into floats and print "2024.0" in the table.
    frame["Year"] = pd.to_numeric(frame["Year"], errors="coerce").astype("Int64")

    return frame


# ---------------------------------------------------------------------------
# Year-over-year comparison (for the headline cards)
# ---------------------------------------------------------------------------
# The cards compare the last COMPLETE year in the window with the year before
# it - say 2025 against 2024 - rather than the current year. The current year
# is unfinished, so comparing it with a full year would always show a fall
# that is not real.

def comparison_years(year_from, year_to, current_year):
    """
    Return (last complete year, the year before it) inside the window,
    or None when the window is too short to hold both.
    """
    latest = min(year_to, current_year - 1)
    earlier = latest - 1
    if earlier < year_from:
        return None
    return latest, earlier


def value_for_year(frame, year, column):
    """One cell from a year-indexed table, or None when that year is absent."""
    if frame.empty or column not in frame.columns:
        return None
    row = frame[frame["year"] == year]
    if row.empty:
        return None
    return row[column].iloc[0]


def percent_change(current, previous):
    """
    The change from previous to current, as a percentage.

    None when there is no fair comparison - a missing value, or a previous
    value of zero, where any growth would be "infinite percent".
    """
    if current is None or previous is None or previous == 0:
        return None
    return round((current - previous) / previous * 100, 1)


def cumulative_totals(trend):
    """Running total of publications, year by year (for the growth story)."""
    if trend.empty:
        return []
    return trend["publications"].cumsum().tolist()



# ---------------------------------------------------------------------------
# Is a change real, or just noise?
# ---------------------------------------------------------------------------
# A percentage change says how BIG a change is. It says nothing about whether
# it is REAL. Going from 22 papers to 34 is "+54.5%", yet a field that small
# swings that much from year to year by chance alone.
#
# Two guards, applied in order:
#
#   1. A minimum sample. Below it (config.MIN_PAPERS_FOR_CHANGE) the card
#      shows no percentage at all, only "too few papers to compare".
#
#   2. A significance test. Above the minimum, a z-test asks: if nothing had
#      really changed, how surprising would a difference this large be?
#      |z| >= 1.96 means a chance difference that large happens less than 5%
#      of the time, the usual 95% standard. Below that, the card still shows
#      the change, but in grey and labelled "likely noise".

Z_95 = 1.96


def enough_papers(now, before, minimum):
    """True when both years have at least `minimum` papers to compare."""
    return now is not None and before is not None and now >= minimum and before >= minimum


def count_change_z(now, before):
    """
    z-score for the change between two yearly paper COUNTS.

    Papers arriving in a year are modelled as a Poisson process, where the
    variance of a count equals the count itself. The variance of the
    difference (now - before) is therefore now + before, and

        z = (now - before) / sqrt(now + before)

    This is the standard normal approximation for comparing two Poisson
    counts over equal time periods (one year each), and it is reliable once
    both counts are around 30 or more, which the minimum-sample guard ensures.
    """
    if now is None or before is None or now + before == 0:
        return None
    return (now - before) / math.sqrt(now + before)


def proportion_change_z(open_now, total_now, open_before, total_before):
    """
    z-score for the change between two SHARES - the two-proportion z-test.

    p1 = open_now / total_now,  p2 = open_before / total_before
    Under "nothing changed", both years share one pooled rate p, and the
    standard error of p1 - p2 is sqrt(p (1 - p) (1/n1 + 1/n2)).

        z = (p1 - p2) / standard error
    """
    if not total_now or not total_before:
        return None
    pooled = (open_now + open_before) / (total_now + total_before)
    spread = math.sqrt(pooled * (1 - pooled) * (1 / total_now + 1 / total_before))
    if spread == 0:
        return None
    return (open_now / total_now - open_before / total_before) / spread


def is_significant(z):
    """True when the change would be surprising by chance alone, at 95%."""
    return z is not None and abs(z) >= Z_95


def open_and_total(oa_frame):
    """(papers that are open access, all papers) from an open-access split."""
    if oa_frame.empty:
        return 0, 0
    total = int(oa_frame["publications"].sum())
    open_rows = oa_frame[oa_frame["access"] == "Open access"]
    return int(open_rows["publications"].sum()), total
