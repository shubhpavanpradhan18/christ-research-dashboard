"""
openalex.py
===========
Every conversation with the OpenAlex API happens in this file, and nowhere else.

Why keep it separate?
    This module knows about HTTP and JSON. It does not know that Streamlit
    exists, and it does not know what a chart is. That separation means you can
    test the data layer on its own (verify_data.py does exactly that), and later
    swap or extend the UI without touching the fetching logic.

OpenAlex is a free, open index of the world's scholarly research.
No API key. No sign-up. No authentication headers.
That is the single biggest reason this project deploys cleanly.
"""

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "https://api.openalex.org"

# OpenAlex runs two request pools:
#   - the "common pool"  : anonymous, slower, first to get rate-limited
#   - the "polite pool"  : for requests that identify themselves, faster/stabler
# You join the polite pool simply by sending a contact email with each request.
#
# This is OPTIONAL. Decide for yourself:
#   - Leave it as ""        -> works fine, just uses the common pool.
#   - Put your email here   -> faster and more reliable, BUT this file is going
#                              into a public GitHub repo, so your address would
#                              be publicly visible. Your call.
# (In Phase 7 I will show you how to move this into Streamlit secrets so it
#  stays out of the repo entirely while still being used when deployed.)
CONTACT_EMAIL = ""

# Seconds to wait before giving up on a request.
TIMEOUT = 30


# ---------------------------------------------------------------------------
# Internal helpers  (the leading underscore means "private to this module")
# ---------------------------------------------------------------------------

def _with_shared_params(params):
    """Add the parameters that every single request should carry."""
    merged = dict(params)
    if CONTACT_EMAIL:
        merged["mailto"] = CONTACT_EMAIL
    return merged


def _get(endpoint, params):
    """
    Make one GET request to OpenAlex and return the parsed JSON body.

    requests builds the final URL for us, so instead of gluing strings
    together we hand it a dict and it handles the URL-encoding:

        _get("institutions", {"search": "CHRIST"})
        -> https://api.openalex.org/institutions?search=CHRIST

    raise_for_status() turns an HTTP error (404, 429, 500...) into a Python
    exception, so a failure is loud instead of silently returning nonsense.
    """
    url = f"{BASE_URL}/{endpoint}"
    response = requests.get(url, params=_with_shared_params(params), timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def _short_id(openalex_url):
    """
    OpenAlex gives every entity a full URL as its ID:
        "https://openalex.org/I1234567890"
    For filtering we only need the tail:
        "I1234567890"
    """
    if not openalex_url:
        return None
    return openalex_url.rsplit("/", 1)[-1]


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def search_institutions(query, limit=5):
    """
    Find universities whose name matches `query`.

    We deliberately SEARCH for CHRIST instead of hardcoding its ID.
    Two reasons:
      1. It is honest engineering - the app discovers its own data source.
      2. It is a good viva answer when the examiner asks
         "what if the ID changes?"

    Returns a list of plain dicts, already flattened - the caller never has
    to dig through nested OpenAlex JSON.
    """
    payload = _get("institutions", {"search": query, "per_page": limit})

    institutions = []
    for item in payload.get("results", []):
        geo = item.get("geo") or {}
        institutions.append(
            {
                "id": _short_id(item.get("id")),
                "name": item.get("display_name"),
                "ror": item.get("ror"),
                "country": item.get("country_code"),
                "city": geo.get("city"),
                "type": item.get("type"),
                "homepage": item.get("homepage_url"),
                "works_count": item.get("works_count", 0),
                "cited_by_count": item.get("cited_by_count", 0),
            }
        )
    return institutions


def build_filter(institution_id, year_from=None, year_to=None, extra=None):
    """
    Build the OpenAlex `filter` string.

    OpenAlex filters are comma-separated key:value pairs, where a comma means
    AND:

        institutions.id:I123456,publication_year:2015-2026

    `extra` adds more conditions on top - a research field, or one author:

        institutions.id:I123456,publication_year:2015-2026,
        primary_topic.field.id:17

    Keeping this in one function means every chart in the dashboard filters
    the data in exactly the same way - no accidental mismatches between
    "total publications" and "publications per year".
    """
    parts = [f"institutions.id:{institution_id}"]
    if year_from and year_to:
        parts.append(f"publication_year:{year_from}-{year_to}")
    if extra:
        parts.extend(extra)
    return ",".join(parts)


def field_filter(field_key):
    """
    The filter condition for one research field.

    group_by hands back each field's key as a URL such as
    "https://openalex.org/fields/17"; the filter wants the short id, "17".
    """
    return f"primary_topic.field.id:{_short_id(field_key)}"


def author_filter(author_key):
    """The filter condition for one author: authorships.author.id:A50..."""
    return f"authorships.author.id:{_short_id(author_key)}"


def count_works(institution_id, year_from=None, year_to=None, extra=None):
    """
    How many papers match our filter?

    Trick worth knowing: we ask for per_page=1 because we do not want the
    papers themselves - only the total. OpenAlex still reports the full count
    in meta.count, so this is a very cheap request.
    """
    payload = _get(
        "works",
        {
            "filter": build_filter(institution_id, year_from, year_to, extra),
            "per_page": 1,
        },
    )
    return payload.get("meta", {}).get("count", 0)


def group_works_by(institution_id, group_field, year_from=None, year_to=None,
                   extra=None):
    """
    Ask OpenAlex to do the aggregation for us.

    `group_by` is the most useful feature in this whole API. Instead of
    downloading 5,000 papers and counting them ourselves, we ask the server
    for the counts directly:

        group_by=publication_year      -> papers per year
        group_by=open_access.is_oa     -> open vs closed access
        group_by=type                  -> journal article / book chapter / ...

    One small request, fully aggregated answer. This is what makes the
    dashboard load fast.
    """
    payload = _get(
        "works",
        {
            "filter": build_filter(institution_id, year_from, year_to, extra),
            "group_by": group_field,
        },
    )

    groups = []
    for group in payload.get("group_by", []):
        groups.append(
            {
                # key_display_name is the human-readable label when there is
                # one ("Artificial Intelligence"); otherwise fall back to the
                # raw key ("2024", "true").
                "label": group.get("key_display_name") or str(group.get("key")),
                "key": group.get("key"),
                "count": group.get("count", 0),
            }
        )
    return groups


def get_institution(institution_id):
    """
    Fetch the institution's own record.

    This one call is unusually valuable. Besides the name and location, it
    carries two things we would otherwise have to compute ourselves:

      counts_by_year : works AND citations for each of the last ~13 years.
                       That single array powers the headline trend chart.
      summary_stats  : h_index, i10_index and 2yr_mean_citedness - real
                       bibliometric indicators, ready to drop into KPI tiles.

    Asking the server for numbers it has already calculated is always better
    than downloading 20,000 papers to calculate them yourself.
    """
    payload = _get(f"institutions/{institution_id}", {})
    stats = payload.get("summary_stats") or {}
    geo = payload.get("geo") or {}

    return {
        "id": _short_id(payload.get("id")),
        "name": payload.get("display_name"),
        "ror": payload.get("ror"),
        "homepage": payload.get("homepage_url"),
        "city": geo.get("city"),
        "country": geo.get("country"),
        "works_count": payload.get("works_count", 0),
        "cited_by_count": payload.get("cited_by_count", 0),
        "h_index": stats.get("h_index", 0),
        "i10_index": stats.get("i10_index", 0),
        "mean_citedness": stats.get("2yr_mean_citedness", 0.0),
        "counts_by_year": payload.get("counts_by_year", []),
        "updated_date": payload.get("updated_date"),
    }


def get_author(author_key):
    """
    Fetch one author's own record, for the Author Spotlight.

    Note what these numbers cover: an author's works_count, citations and
    h-index span their WHOLE career at every institution, not only their
    time at CHRIST. The dashboard labels them as career totals for exactly
    that reason.

    OpenAlex renamed last_known_institution (one) to last_known_institutions
    (a list); both spellings are read so either schema works.
    """
    payload = _get(f"authors/{_short_id(author_key)}", {})
    stats = payload.get("summary_stats") or {}

    places = payload.get("last_known_institutions")
    if places is None:
        single = payload.get("last_known_institution")
        places = [single] if single else []

    topics = [
        topic.get("display_name")
        for topic in (payload.get("topics") or [])[:5]
        if topic.get("display_name")
    ]

    return {
        "id": _short_id(payload.get("id")),
        "name": payload.get("display_name"),
        "orcid": payload.get("orcid"),
        "works_count": payload.get("works_count", 0),
        "cited_by_count": payload.get("cited_by_count", 0),
        "h_index": stats.get("h_index", 0),
        "i10_index": stats.get("i10_index", 0),
        "institutions": [p.get("display_name") for p in places if p and p.get("display_name")],
        "topics": topics,
        "url": payload.get("id"),
    }


# Fields we ask OpenAlex to return for individual papers.
# Requesting only what we display keeps the response small and the app fast -
# without this, each paper carries a very large block of metadata we ignore.
_WORK_FIELDS = (
    "id,doi,display_name,publication_year,publication_date,"
    "type,cited_by_count,open_access,authorships,primary_topic,primary_location"
)


def _get_works_with_select(params):
    """
    Request works with a `select` list, falling back to the full record.

    If OpenAlex rejects our `select` list (for instance after a schema change
    renames a field), retry without it rather than letting the whole
    dashboard fail over a performance tweak.
    """
    try:
        return _get("works", params)
    except requests.HTTPError:
        params = dict(params)
        params.pop("select", None)
        return _get("works", params)


def fetch_top_works(institution_id, year_from=None, year_to=None,
                    sort_by="cited_by_count:desc", limit=25, extra=None):
    """
    Download a SMALL number of individual papers.

    Design note worth remembering for the viva:
        CHRIST has over 20,000 indexed papers. We never download them all.
        Every aggregate number in this dashboard comes from `group_by`, which
        the server computes. We only download individual records for the
        tables that actually list papers - about 25 rows each.

        That is why there is no pagination code in this project. We do not
        need it, so it does not exist.

    sort_by options that are useful here:
        "cited_by_count:desc"   -> most influential papers
        "publication_date:desc" -> newest papers
    """
    payload = _get_works_with_select(
        {
            "filter": build_filter(institution_id, year_from, year_to, extra),
            "sort": sort_by,
            "per_page": min(limit, 200),
            "select": _WORK_FIELDS,
        }
    )
    return payload.get("results", [])


def search_works(institution_id, query, year_from=None, year_to=None,
                 extra=None, sort_by=None, limit=25):
    """
    Full-text search, restricted to CHRIST's own papers.

    OpenAlex's `search` parameter matches the words against each paper's
    title and abstract, and it combines with `filter` - so the same call that
    searches also applies the institution, the year window and any field.

    With no sort_by, results come back in relevance order: the best match
    first. Returns (total number of matches, the first `limit` papers).
    """
    params = {
        "search": query,
        "filter": build_filter(institution_id, year_from, year_to, extra),
        "per_page": min(limit, 200),
        "select": _WORK_FIELDS,
    }
    if sort_by:
        params["sort"] = sort_by

    payload = _get_works_with_select(params)
    total = payload.get("meta", {}).get("count", 0)
    return total, payload.get("results", [])
