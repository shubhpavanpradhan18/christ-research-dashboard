"""
find_campus.py
==============
Lists every institution in India whose name matches CHRIST, so you can see
exactly how OpenAlex has split the university across campuses and pick the
Bangalore Central Campus record.

Run it with:   python find_campus.py

Then copy the ID of the row you want into config.py (Phase 2).
"""

import sys

import requests

import openalex


def find_all_christ_records():
    """
    Search institutions, restricted to India, sorted by size.

    Three query parameters doing the work:
        search=CHRIST            -> name match
        filter=country_code:IN   -> drop the Christ Churches, Christ Colleges
                                    and Christus hospitals from other countries
        sort=works_count:desc    -> biggest record first, which is almost
                                    always the main campus
    """
    payload = openalex._get(
        "institutions",
        {
            "search": "CHRIST",
            "filter": "country_code:IN",
            "sort": "works_count:desc",
            "per_page": 25,
        },
    )
    return payload.get("results", [])


def main():
    print()
    print("=" * 78)
    print("  CHRIST RECORDS IN OPENALEX (India only, largest first)")
    print("=" * 78)

    try:
        results = find_all_christ_records()
    except requests.ConnectionError:
        print("\nNETWORK ERROR: could not reach api.openalex.org")
        print("Turn NordLayer off and try again.")
        sys.exit(1)
    except requests.RequestException as error:
        print(f"\nREQUEST FAILED: {error}")
        sys.exit(1)

    if not results:
        print("\n  Nothing matched. Tell me and we will widen the search.")
        return

    for position, item in enumerate(results, start=1):
        geo = item.get("geo") or {}
        short_id = openalex._short_id(item.get("id"))

        # Flag the rows most likely to be the Bangalore campus so they are
        # easy to spot in the list.
        city = (geo.get("city") or "").strip()
        marker = "  <-- BANGALORE" if city.lower() in ("bangalore", "bengaluru") else ""

        print(f"\n  [{position}] {item.get('display_name')}{marker}")
        print(f"      ID        : {short_id}")
        print(f"      City      : {city or '(not recorded)'}")
        print(f"      ROR       : {item.get('ror')}")
        print(f"      Homepage  : {item.get('homepage_url')}")
        print(f"      Works     : {item.get('works_count', 0):,}")
        print(f"      Citations : {item.get('cited_by_count', 0):,}")

    print()
    print("-" * 78)
    print("  Send me this list. The Bangalore Central Campus row is the one")
    print("  we will pin as the dashboard's primary institution.")
    print("-" * 78)
    print()


if __name__ == "__main__":
    main()
