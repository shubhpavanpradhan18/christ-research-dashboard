"""
config.py
=========
Every value you might want to change lives here, and nowhere else.

Why a config file at all?
    Constants scattered through the code are how projects rot. When the year
    range appears in four files, changing it means finding all four. Here
    there is exactly one place to look.
"""

# ---------------------------------------------------------------------------
# The institution this dashboard reports on
# ---------------------------------------------------------------------------
# Confirmed via find_campus.py on 15 Nov 2026.
# This is the Bangalore Central Campus record - 20,442 works, 262,483 citations.
# Note that OpenAlex indexes Delhi NCR (I4405253679) as a SEPARATE institution.

INSTITUTION_ID = "I48018076"
INSTITUTION_NAME = "CHRIST (Deemed to be) University"
INSTITUTION_SHORT = "CHRIST University"
INSTITUTION_CITY = "Bengaluru, India"
INSTITUTION_ROR = "https://ror.org/022tv9y30"
INSTITUTION_HOMEPAGE = "https://www.christuniversity.in"
INSTITUTION_OPENALEX = f"https://openalex.org/{INSTITUTION_ID}"


# ---------------------------------------------------------------------------
# Default time window
# ---------------------------------------------------------------------------
# The sidebar lets the user change these; these are just the starting values.

DEFAULT_YEAR_FROM = 2015
DEFAULT_YEAR_TO = 2026
EARLIEST_YEAR = 2000


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------
# How long Streamlit keeps a fetched result before asking OpenAlex again.
# One hour is a sensible balance: the data genuinely updates (so the app is
# live, not static), but a user clicking filters does not hammer the API.

CACHE_TTL_SECONDS = 60 * 60


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

TOP_N = 15          # how many bars in the "top authors" / "top partners" charts

# Below this many papers in either year, the headline cards show no
# year-over-year percentage at all. With 30 papers a single paper moves a
# count by 3% and a share by 3 points; much below that, the "change" is
# mostly noise. 30 is also roughly where the normal approximation behind the
# significance test (transforms.count_change_z) becomes reliable.
MIN_PAPERS_FOR_CHANGE = 30
TOP_PAPERS = 25     # how many rows in the most-cited papers table
