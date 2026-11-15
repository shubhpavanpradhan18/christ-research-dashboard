"""
test_phase2.py
==============
Exercises the whole data layer against the real CHRIST University record,
end to end, with no Streamlit involved.

The point: if this script prints sensible tables, the dashboard in Phase 3
is just layout. Any bug found here is a bug you would otherwise be hunting
inside a running web app, which is far slower.

Run it with:   python test_phase2.py
"""

import sys

import pandas as pd
import requests

import config
import openalex
import transforms


# Make pandas print full tables instead of truncating them.
pd.set_option("display.width", 120)
pd.set_option("display.max_columns", 20)
pd.set_option("display.max_colwidth", 45)


def heading(text):
    print()
    print("=" * 76)
    print(f"  {text}")
    print("=" * 76)


def main():
    print()
    print(f"Target institution : {config.INSTITUTION_NAME}")
    print(f"OpenAlex ID        : {config.INSTITUTION_ID}")
    print(f"Window             : {config.DEFAULT_YEAR_FROM}-{config.DEFAULT_YEAR_TO}")

    year_from = config.DEFAULT_YEAR_FROM
    year_to = config.DEFAULT_YEAR_TO
    inst_id = config.INSTITUTION_ID

    # -- 1. The institution record ------------------------------------------
    heading("1  Institution record  (powers the KPI tiles)")

    institution = openalex.get_institution(inst_id)
    print(f"  Name            : {institution['name']}")
    print(f"  Location        : {institution['city']}, {institution['country']}")
    print(f"  Total papers    : {institution['works_count']:,}")
    print(f"  Total citations : {institution['cited_by_count']:,}")
    print(f"  h-index         : {institution['h_index']}")
    print(f"  i10-index       : {institution['i10_index']}")
    print(f"  Mean citedness  : {institution['mean_citedness']:.2f}")
    print(f"  Data updated    : {institution['updated_date']}")

    # -- 2. Yearly trend ----------------------------------------------------
    heading("2  Yearly trend  (headline chart)")

    trend = transforms.yearly_trend(
        institution["counts_by_year"], year_from, year_to
    )
    print(trend.to_string(index=False))

    # -- 3. Filtered totals -------------------------------------------------
    heading("3  Papers inside the selected window")

    windowed = openalex.count_works(inst_id, year_from, year_to)
    print(f"  {windowed:,} papers between {year_from} and {year_to}")

    # -- 4. Research fields -------------------------------------------------
    heading("4  Research fields  (treemap)")

    field_groups = openalex.group_works_by(
        inst_id, "primary_topic.field.id", year_from, year_to
    )
    fields = transforms.top_groups(field_groups, 12, label_name="field")
    print(fields.to_string(index=False))

    # -- 5. Open access -----------------------------------------------------
    heading("5  Open access split  (donut)")

    oa_groups = openalex.group_works_by(
        inst_id, "open_access.is_oa", year_from, year_to
    )
    oa = transforms.open_access_split(oa_groups)
    print(oa.to_string(index=False))
    print(f"\n  Open access share: {transforms.open_access_percentage(oa)}%")

    # -- 6. Top authors -----------------------------------------------------
    heading("6  Top authors  (ranked bars)")

    author_groups = openalex.group_works_by(
        inst_id, "authorships.author.id", year_from, year_to
    )
    authors = transforms.top_groups(author_groups, config.TOP_N, label_name="author")
    print(authors.to_string(index=False))

    # -- 7. Collaborating countries ----------------------------------------
    heading("7  Collaborating countries  (world map, India removed)")

    country_groups = openalex.group_works_by(
        inst_id, "authorships.institutions.country_code", year_from, year_to
    )
    countries = transforms.top_groups(
        country_groups, 15, label_name="country", exclude=["India"]
    )
    print(countries.to_string(index=False))

    # -- 8. Partner institutions -------------------------------------------
    heading("8  Partner institutions  (CHRIST itself removed)")

    partner_groups = openalex.group_works_by(
        inst_id, "authorships.institutions.id", year_from, year_to
    )
    partners = transforms.top_groups(
        partner_groups, config.TOP_N, label_name="institution",
        exclude=["Christ University", "CHRIST (Deemed"],
    )
    print(partners.to_string(index=False))

    # -- 9. Most cited papers ----------------------------------------------
    heading("9  Most cited papers  (table)")

    top_works = openalex.fetch_top_works(
        inst_id, year_from, year_to,
        sort_by="cited_by_count:desc", limit=10,
    )
    papers = transforms.works_to_frame(top_works)
    print(papers[["Title", "Year", "Citations", "Field", "Open access"]].to_string(index=False))

    # -- 10. Newest papers --------------------------------------------------
    heading("10  Newest papers  (proves the data is live)")

    newest = openalex.fetch_top_works(
        inst_id, year_from, year_to,
        sort_by="publication_date:desc", limit=5,
    )
    recent = transforms.works_to_frame(newest)
    print(recent[["Title", "Year", "Field"]].to_string(index=False))

    heading("DATA LAYER OK")
    print("  Every chart in the dashboard now has verified data behind it.")
    print("  Phase 3 is pure layout.")
    print()


if __name__ == "__main__":
    try:
        main()
    except requests.ConnectionError:
        print("\nNETWORK ERROR: could not reach api.openalex.org (VPN on?)")
        sys.exit(1)
    except requests.HTTPError as error:
        status = error.response.status_code if error.response is not None else "?"
        print(f"\nHTTP {status} from OpenAlex.")
        print("Send me this message and the traceback and I will adjust the call.")
        raise
