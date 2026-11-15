"""
verify_data.py
==============
A one-time sanity check. This is NOT part of the dashboard - it is the script
you run BEFORE committing to the topic, to prove the data actually exists.

It answers three questions:
    1. Is CHRIST University indexed in OpenAlex at all?
    2. How much research data is there? (a few hundred = thin, thousands = great)
    3. Which `group_by` fields work? (this decides what charts we can build)

Run it with:   python verify_data.py
"""

import sys

import requests

import openalex


# A tidy separator so the output is readable in the terminal.
LINE = "-" * 68


def heading(text):
    print()
    print(LINE)
    print(text)
    print(LINE)


def step_1_find_the_university():
    """Search OpenAlex for CHRIST and show every candidate match."""
    heading("STEP 1  Searching OpenAlex for CHRIST University")

    matches = openalex.search_institutions("CHRIST Deemed to be University", limit=5)

    if not matches:
        print("  No institutions matched. Trying a looser search term...")
        matches = openalex.search_institutions("Christ University Bangalore", limit=5)

    if not matches:
        print("  FAILED: nothing matched either search term.")
        return None

    for position, inst in enumerate(matches, start=1):
        print(f"\n  [{position}] {inst['name']}")
        print(f"      OpenAlex ID : {inst['id']}")
        print(f"      ROR         : {inst['ror']}")
        print(f"      Location    : {inst['city']}, {inst['country']}")
        print(f"      Works       : {inst['works_count']:,}")
        print(f"      Citations   : {inst['cited_by_count']:,}")

    # The first result is OpenAlex's own best match, which is almost always
    # the right one for a distinctive name like this.
    chosen = matches[0]
    print(f"\n  --> Using: {chosen['name']}  ({chosen['id']})")
    return chosen


def step_2_check_volume(institution):
    """Confirm there is enough data for a dashboard to be interesting."""
    heading("STEP 2  How much research data is there?")

    inst_id = institution["id"]

    total = openalex.count_works(inst_id)
    recent = openalex.count_works(inst_id, year_from=2016, year_to=2026)

    print(f"  Total papers (all time)   : {total:,}")
    print(f"  Papers from 2016 onwards  : {recent:,}")

    if total >= 2000:
        verdict = "EXCELLENT - plenty of data, go ahead with this topic"
    elif total >= 500:
        verdict = "GOOD - enough for a solid dashboard"
    elif total >= 100:
        verdict = "THIN - usable, but charts will look sparse"
    else:
        verdict = "TOO LITTLE - switch to the backup topic"

    print(f"\n  Verdict: {verdict}")
    return recent


def step_3_publications_per_year(institution):
    """The headline chart of the dashboard - prove we can build it."""
    heading("STEP 3  Publications per year (the main trend chart)")

    rows = openalex.group_works_by(
        institution["id"], "publication_year", year_from=2016, year_to=2026
    )

    if not rows:
        print("  No yearly data returned.")
        return

    # OpenAlex returns groups sorted by count; sort by year for readability.
    rows.sort(key=lambda row: str(row["label"]))

    biggest = max(row["count"] for row in rows)
    for row in rows:
        # A crude terminal bar chart, 40 characters wide at most.
        bar_width = int((row["count"] / biggest) * 40) if biggest else 0
        print(f"  {row['label']:>6}  {'#' * bar_width} {row['count']:,}")


def step_4_probe_group_fields(institution):
    """
    Test which aggregations OpenAlex will give us.

    This is the most valuable step. Each field that works = one chart we can
    build in Phases 4-6 without downloading thousands of records. Each field
    that fails, we work around now rather than discovering it on 28 Nov.
    """
    heading("STEP 4  Which group_by fields work? (decides our charts)")

    candidates = [
        ("open_access.is_oa", "Open access vs paywalled  -> donut chart"),
        ("type", "Article / chapter / book  -> breakdown chart"),
        ("primary_topic.field.id", "Research fields  -> treemap"),
        ("primary_topic.subfield.id", "Research subfields  -> treemap detail"),
        ("authorships.author.id", "Top authors  -> ranked bar chart"),
        ("authorships.institutions.country_code", "Collaborator countries  -> world map"),
        ("authorships.institutions.id", "Partner institutions  -> ranked bar chart"),
        ("language", "Publication language  -> minor stat"),
    ]

    working = []
    for field, purpose in candidates:
        try:
            rows = openalex.group_works_by(
                institution["id"], field, year_from=2016, year_to=2026
            )
        except requests.HTTPError as error:
            status = error.response.status_code if error.response else "?"
            print(f"  [FAIL {status}]  {field}")
            continue
        except requests.RequestException as error:
            print(f"  [ERROR]       {field}  ({error.__class__.__name__})")
            continue

        if not rows:
            print(f"  [EMPTY]       {field}")
            continue

        working.append(field)
        sample = rows[0]
        print(f"  [OK]          {field}")
        print(f"                {purpose}")
        print(f"                top value: {sample['label']} ({sample['count']:,})")

    print(f"\n  {len(working)} of {len(candidates)} aggregations available.")
    return working


def main():
    print()
    print("=" * 68)
    print("  CHRIST RESEARCH DASHBOARD - DATA SOURCE VERIFICATION")
    print("=" * 68)

    try:
        institution = step_1_find_the_university()
        if institution is None:
            print("\nCould not identify the university. Stopping here.")
            sys.exit(1)

        step_2_check_volume(institution)
        step_3_publications_per_year(institution)
        step_4_probe_group_fields(institution)

    except requests.ConnectionError:
        print("\nNETWORK ERROR: could not reach api.openalex.org")
        print("Check your internet connection, and turn off the VPN if it is on.")
        sys.exit(1)
    except requests.HTTPError as error:
        status = error.response.status_code if error.response else "unknown"
        print(f"\nHTTP ERROR {status} from OpenAlex.")
        print("If this is 429, you are being rate-limited - wait a minute and retry.")
        sys.exit(1)
    except requests.Timeout:
        print("\nTIMEOUT: OpenAlex did not respond within 30 seconds. Try again.")
        sys.exit(1)

    heading("DONE")
    print("  Copy this whole output and send it back, and we will start Phase 2")
    print("  using exactly the fields that worked.")
    print()


if __name__ == "__main__":
    main()
