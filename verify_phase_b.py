"""
verify_phase_b.py
=================
Checks every NEW kind of request the Phase B features rely on, against the
real OpenAlex API, before you trust the dashboard with them.

Same discipline as verify_data.py: prove the data source answers the way the
code expects, in a plain script, before any of it is buried inside a web app.

Run it with:   python verify_phase_b.py
"""

import sys

import requests

import config
import openalex

INST = config.INSTITUTION_ID
FROM, TO = config.DEFAULT_YEAR_FROM, 2026
results = []


def check(name, fn):
    """Run one probe, print OK or FAIL, and remember the outcome."""
    try:
        detail = fn()
        print(f"  [OK]    {name}")
        if detail:
            print(f"          {detail}")
        results.append((name, True))
        return True
    except requests.HTTPError as error:
        status = error.response.status_code if error.response is not None else "?"
        print(f"  [FAIL]  {name}  (HTTP {status})")
    except Exception as error:  # noqa: BLE001 - this is a diagnostic script
        print(f"  [FAIL]  {name}  ({error.__class__.__name__}: {error})")
    results.append((name, False))
    return False


def main():
    print()
    print("=" * 72)
    print("  PHASE B - VERIFYING THE NEW REQUEST TYPES AGAINST OPENALEX")
    print("=" * 72)

    # --- 1. Research field filter ------------------------------------------
    print("\n1  Research field filter (sidebar)")
    fields = openalex.group_works_by(INST, "primary_topic.field.id", FROM, TO)
    top = max(fields, key=lambda g: g["count"])
    print(f"   using field: {top['label']}  key={top['key']}")

    # The app sends the short id. The other two spellings are tried too, so
    # if the first fails we know exactly which one to switch to.
    short = openalex._short_id(top["key"])
    spellings = {
        "short id (what the app uses)": short,
        "fields/<id>": f"fields/{short}",
        "full URL": top["key"],
    }
    for label, value in spellings.items():
        check(
            f"field filter as {label}",
            lambda v=value: f"{openalex.count_works(INST, FROM, TO, (f'primary_topic.field.id:{v}',)):,} papers",
        )

    field_extra = (openalex.field_filter(top["key"]),)
    check(
        "subfield breakdown inside that field",
        lambda: ", ".join(
            g["label"] for g in openalex.group_works_by(
                INST, "primary_topic.subfield.id", FROM, TO, field_extra)[:3]
        ),
    )

    # --- 2. Author spotlight ------------------------------------------------
    print("\n2  Author spotlight")
    authors = openalex.group_works_by(INST, "authorships.author.id", FROM, TO)
    lead = max(authors, key=lambda g: g["count"])
    print(f"   using author: {lead['label']}  key={lead['key']}")

    author_extra = (openalex.author_filter(lead["key"]),)
    check(
        "author filter (papers at CHRIST)",
        lambda: f"{openalex.count_works(INST, FROM, TO, author_extra):,} papers",
    )
    check(
        "author record (career totals)",
        lambda: (lambda a: f"{a['name']}: {a['works_count']:,} works, "
                           f"{a['cited_by_count']:,} citations, h-index {a['h_index']}, "
                           f"last known at {a['institutions'][:1]}")(
            openalex.get_author(lead["key"])),
    )
    check(
        "author's papers per year",
        lambda: f"{len(openalex.group_works_by(INST, 'publication_year', FROM, TO, author_extra))} years with papers",
    )

    # --- 3. Search ----------------------------------------------------------
    print("\n3  Search papers")
    for sort in (None, "cited_by_count:desc", "publication_date:desc"):
        check(
            f"search 'machine learning', sort={sort or 'relevance'}",
            lambda s=sort: (lambda total, rows: f"{total:,} matches, first: "
                                                f"{(rows[0].get('display_name') or '')[:60] if rows else '-'}")(
                *openalex.search_works(INST, "machine learning", FROM, TO, sort_by=s, limit=5)),
        )

    # --- 4. Year-over-year --------------------------------------------------
    print("\n4  Year-over-year (single-year windows)")
    for year in (2025, 2024):
        check(
            f"open-access split for {year} alone",
            lambda y=year: str({g['label']: g['count'] for g in openalex.group_works_by(
                INST, "open_access.is_oa", y, y)}),
        )

    # --- Summary ------------------------------------------------------------
    passed = sum(ok for _, ok in results)
    print()
    print("-" * 72)
    print(f"  {passed} of {len(results)} checks passed.")
    if passed == len(results):
        print("  Every Phase B feature has a working request behind it.")
    else:
        print("  Send me this output - each FAIL names the request to fix.")
    print("-" * 72)
    print()


if __name__ == "__main__":
    try:
        main()
    except requests.ConnectionError:
        print("\nNETWORK ERROR: could not reach api.openalex.org (VPN on?)")
        sys.exit(1)
