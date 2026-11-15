"""
app.py
======
The dashboard itself.

Structure of this file:
    1. Page setup          - must run before any other Streamlit command
    2. Cached data loaders - every network call goes through one of these
    3. Sidebar             - the controls
    4. Header              - title and live-data banner
    5. KPI row             - the five headline numbers
    6. Charts              - added in Phase 4

Run it with:   streamlit run app.py
"""

from datetime import datetime

import requests
import streamlit as st

import charts
import config
import openalex
import transforms


# ===========================================================================
# 1. PAGE SETUP
# ===========================================================================
# st.set_page_config MUST be the first Streamlit command executed, before any
# st.write, st.title or st.sidebar call. Streamlit raises an error otherwise.

st.set_page_config(
    page_title="CHRIST Research Intelligence",
    page_icon="📊",
    layout="wide",                    # use the full browser width
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# 1b. Secrets
# ---------------------------------------------------------------------------
# OpenAlex offers a faster "polite pool" to requests that carry a contact
# email. We want that benefit without committing an email address to a public
# repository, so the value is read from Streamlit's secrets store:
#
#   locally   -> .streamlit/secrets.toml, which .gitignore excludes
#   deployed  -> the Secrets box in the Streamlit Cloud app settings
#
# Note the direction of the wiring. openalex.py never imports Streamlit; the
# app pushes the value down into it. That keeps the data layer runnable from a
# plain Python script, which is what made test_phase2.py possible.
#
# Having no secrets file at all is a perfectly normal state, not an error -
# the app simply uses the anonymous pool.
try:
    openalex.CONTACT_EMAIL = st.secrets.get("openalex_email", "")
except Exception:
    openalex.CONTACT_EMAIL = ""


# ===========================================================================
# 2. CACHED DATA LOADERS
# ===========================================================================
# Every function that touches the network is wrapped in @st.cache_data.
#
# What the decorator does:
#   Streamlit remembers the result for each distinct set of arguments. Call
#   load_group("language", 2015, 2026) twice and the second call returns
#   instantly from memory without touching OpenAlex.
#
# Why it matters here:
#   Streamlit re-runs this ENTIRE script top to bottom on every single user
#   interaction - every slider drag, every click. Without caching, dragging
#   the year slider would fire nine API calls per pixel of movement. OpenAlex
#   would rate-limit us within seconds.
#
# Why there is a TTL:
#   ttl=3600 means the cache expires after an hour, so the app re-fetches and
#   genuinely shows new data. A cache with no expiry would turn a live
#   dashboard into a static one, which defeats the whole point of the project.

@st.cache_data(ttl=config.CACHE_TTL_SECONDS, show_spinner=False)
def load_institution():
    """The institution record: totals, h-index, counts_by_year."""
    return openalex.get_institution(config.INSTITUTION_ID)


@st.cache_data(ttl=config.CACHE_TTL_SECONDS, show_spinner=False)
def load_group(group_field, year_from, year_to):
    """Any server-side aggregation. The arguments form the cache key."""
    return openalex.group_works_by(
        config.INSTITUTION_ID, group_field, year_from, year_to
    )


@st.cache_data(ttl=config.CACHE_TTL_SECONDS, show_spinner=False)
def load_count(year_from, year_to):
    """How many papers fall inside the selected window."""
    return openalex.count_works(config.INSTITUTION_ID, year_from, year_to)


@st.cache_data(ttl=config.CACHE_TTL_SECONDS, show_spinner=False)
def load_works(sort_by, limit, year_from, year_to):
    """A small slice of individual papers."""
    return openalex.fetch_top_works(
        config.INSTITUTION_ID, year_from, year_to, sort_by=sort_by, limit=limit
    )


# ===========================================================================
# 3. SIDEBAR
# ===========================================================================

current_year = datetime.now().year

with st.sidebar:
    st.markdown("### Filters")

    # A range slider returns a tuple: (lower, upper).
    year_from, year_to = st.slider(
        "Publication years",
        min_value=config.EARLIEST_YEAR,
        max_value=current_year,
        value=(config.DEFAULT_YEAR_FROM, current_year),
        step=1,
        help="Every chart on the page respects this range.",
    )

    st.divider()

    st.markdown("### Data source")
    st.markdown(
        f"""
        Live from the **OpenAlex** open scholarly index.

        - Institution: [{config.INSTITUTION_SHORT}]({config.INSTITUTION_OPENALEX})
        - ROR: [`{config.INSTITUTION_ROR.split('/')[-1]}`]({config.INSTITUTION_ROR})
        - Cache: refreshes every {config.CACHE_TTL_SECONDS // 60} minutes
        """
    )

    # Clearing the cache forces the next run to hit the API again. Useful in
    # a viva: click it and the numbers re-fetch in front of the examiner.
    if st.button("Refresh data now", width="stretch"):
        st.cache_data.clear()
        st.rerun()

    st.caption(
        "Built with Streamlit and the OpenAlex API. "
        "No API key, no scraping, no stored data."
    )


# ===========================================================================
# 4. HEADER
# ===========================================================================

st.title("CHRIST University Research Intelligence")
st.markdown(
    f"**{config.INSTITUTION_NAME}** · {config.INSTITUTION_CITY} · "
    f"showing **{year_from}–{year_to}**"
)

# Load the core record first - if this fails, nothing else can work, so we
# stop here with a readable message instead of letting the page half-render.
try:
    institution = load_institution()
except requests.RequestException as error:
    st.error(
        "Could not reach the OpenAlex API. "
        "Check your internet connection and try again."
    )
    st.caption(f"Technical detail: {error.__class__.__name__}")
    st.stop()

# The timestamp is the single most persuasive element on the page: it proves
# to anyone looking that this is live data, not a CSV committed to the repo.
if institution.get("updated_date"):
    stamp = institution["updated_date"].replace("T", " ")[:19]
    st.success(f"Live data · OpenAlex last updated this institution on {stamp} UTC")

st.markdown("")  # a little breathing room


# ===========================================================================
# 5. KPI ROW
# ===========================================================================

windowed_papers = load_count(year_from, year_to)

oa_frame = transforms.open_access_split(
    load_group("open_access.is_oa", year_from, year_to)
)
oa_share = transforms.open_access_percentage(oa_frame)

kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)

with kpi1:
    st.metric(
        "Publications",
        f"{windowed_papers:,}",
        help=f"Papers published between {year_from} and {year_to}.",
    )
    st.caption(f"{institution['works_count']:,} all-time")

with kpi2:
    st.metric(
        "Citations",
        f"{institution['cited_by_count']:,}",
        help="Total citations received, all years.",
    )
    st.caption("across all publications")

with kpi3:
    st.metric(
        "h-index",
        f"{institution['h_index']:,}",
        help=(
            "The institution has at least this many papers that have each "
            "been cited at least this many times."
        ),
    )
    st.caption("institutional impact")

with kpi4:
    st.metric(
        "i10-index",
        f"{institution['i10_index']:,}",
        help="Papers with 10 or more citations each.",
    )
    st.caption("papers cited 10+ times")

with kpi5:
    st.metric(
        "Open access",
        f"{oa_share}%",
        help="Share of papers in this window that are freely readable.",
    )
    st.caption("freely readable")


# A partial year would otherwise read as a collapse in output, so say so.
if year_to >= current_year:
    st.caption(
        f"Note: {current_year} is still in progress, so its totals are "
        "incomplete and will keep rising."
    )

st.divider()


# ===========================================================================
# 6. CHARTS
# ===========================================================================
# Two sources feed the two trend charts, and the reason is worth knowing:
#
#   publications -> group_by=publication_year, which covers the full history
#                   and so respects the slider however far back it is dragged.
#   citations    -> the institution's counts_by_year, which is the only place
#                   OpenAlex reports citations per year - but it only reaches
#                   back about 13 years.
#
# Using each source for what it is good at avoids a branch in the code and a
# wrong number in the chart.

publication_trend = transforms.yearly_from_groups(
    load_group("publication_year", year_from, year_to)
)
citation_trend = transforms.yearly_trend(
    institution["counts_by_year"], year_from, year_to
)

# --- Row one: the two trends, side by side --------------------------------

trend_left, trend_right = st.columns(2)

with trend_left:
    st.plotly_chart(
        charts.publications_trend(publication_trend, current_year),
        width="stretch",
    )
    # Every chart has a table twin. A tooltip must enhance a chart, never be
    # the only way to read a value.
    with st.expander("View as table"):
        st.dataframe(publication_trend, width="stretch", hide_index=True)

with trend_right:
    st.plotly_chart(
        charts.citations_trend(citation_trend),
        width="stretch",
    )
    with st.expander("View as table"):
        st.dataframe(
            citation_trend[["year", "citations"]],
            width="stretch",
            hide_index=True,
        )
    if not citation_trend.empty and citation_trend["year"].min() > year_from:
        st.caption(
            f"Citation history is available from "
            f"{int(citation_trend['year'].min())} onwards."
        )

st.divider()

# --- Row two: research fields, and the open-access split -------------------

fields_column, access_column = st.columns([2, 1])

with fields_column:
    field_frame = transforms.top_groups(
        load_group("primary_topic.field.id", year_from, year_to),
        12,
        label_name="field",
    )
    st.plotly_chart(charts.field_bars(field_frame), width="stretch")
    with st.expander("View as table"):
        st.dataframe(field_frame, width="stretch", hide_index=True)

with access_column:
    st.plotly_chart(charts.open_access_bar(oa_frame), width="stretch")
    with st.expander("View as table"):
        st.dataframe(oa_frame, width="stretch", hide_index=True)

    if not oa_frame.empty:
        open_rows = oa_frame[oa_frame["access"] == "Open access"]
        open_count = int(open_rows["publications"].sum()) if not open_rows.empty else 0
        st.caption(
            f"{open_count:,} of {int(oa_frame['publications'].sum()):,} papers "
            f"in this window are free to read."
        )

st.divider()


# ===========================================================================
# 7. PEOPLE AND PAPERS
# ===========================================================================

authors_column, types_column = st.columns([3, 2])

with authors_column:
    author_frame = transforms.top_groups(
        load_group("authorships.author.id", year_from, year_to),
        config.TOP_N,
        label_name="author",
    )
    st.plotly_chart(charts.author_bars(author_frame), width="stretch")
    with st.expander("View as table"):
        st.dataframe(author_frame, width="stretch", hide_index=True)

with types_column:
    type_frame = transforms.top_groups(
        load_group("type", year_from, year_to),
        8,
        label_name="type",
    )
    st.plotly_chart(
        charts.field_bars(type_frame, title="Publication types"),
        width="stretch",
    )
    with st.expander("View as table"):
        st.dataframe(type_frame, width="stretch", hide_index=True)

st.divider()


# --- The papers themselves -------------------------------------------------

st.subheader("The papers")

# How each column of the papers table is rendered. Defined once and reused by
# both tabs, so the two tables cannot drift apart.
PAPER_COLUMNS = {
    "Title": st.column_config.TextColumn("Title", width="large"),
    # Without an explicit format, pandas' integer years render as "2,024".
    "Year": st.column_config.NumberColumn("Year", format="%d"),
    "Citations": st.column_config.NumberColumn("Citations"),
    "Authors": st.column_config.NumberColumn(
        "Authors",
        help=(
            "Number of listed authors. Large international collaborations can "
            "carry hundreds, which inflates their citation count relative to "
            "work led here."
        ),
    ),
    "Field": st.column_config.TextColumn("Field"),
    "First author": st.column_config.TextColumn("First author"),
    "Published in": st.column_config.TextColumn("Published in"),
    "Open access": st.column_config.TextColumn("Open", width="small"),
    "Link": st.column_config.LinkColumn("DOI", display_text="Open"),
}

most_cited_tab, newest_tab = st.tabs(["Most cited", "Most recent"])

with most_cited_tab:
    cited_frame = transforms.works_to_frame(
        load_works("cited_by_count:desc", config.TOP_PAPERS, year_from, year_to)
    )
    st.dataframe(
        cited_frame,
        width="stretch",
        hide_index=True,
        column_config=PAPER_COLUMNS,
    )
    st.caption(
        "Citation counts reward large collaborations. The author column is "
        "shown so a paper with hundreds of contributors reads differently "
        "from one led at CHRIST."
    )

with newest_tab:
    newest_frame = transforms.works_to_frame(
        load_works("publication_date:desc", config.TOP_PAPERS, year_from, year_to)
    )
    st.dataframe(
        newest_frame,
        width="stretch",
        hide_index=True,
        column_config=PAPER_COLUMNS,
    )
    st.caption(
        "The newest papers OpenAlex has indexed for this institution. "
        "Re-run tomorrow and this list will have changed."
    )

st.divider()


# ===========================================================================
# 8. COLLABORATION
# ===========================================================================

st.subheader("Collaboration")

country_groups = load_group(
    "authorships.institutions.country_code", year_from, year_to
)

# India is excluded from the map on purpose. CHRIST is an Indian institution,
# so India appears on virtually every paper - roughly twenty times the next
# country. Leaving it in stretches the colour scale so far that every
# international partner collapses into the palest step and the map says
# nothing. Its figure is reported underneath instead, so the number is not
# hidden, only moved somewhere it can be read.
map_countries = transforms.top_groups(
    country_groups, 60, label_name="country", exclude=["India"]
)
india_count = next(
    (group["count"] for group in country_groups if group["label"] == "India"), 0
)

st.plotly_chart(charts.collaboration_map(map_countries), width="stretch")

map_caption, map_table = st.columns([1, 1])

with map_caption:
    if india_count:
        st.caption(
            f"India is excluded from the map so the international pattern is "
            f"visible; it appears on {india_count:,} papers in this window."
        )
    st.caption(
        "A paper is counted once per country among its author institutions, "
        "so the totals overlap rather than sum."
    )

with map_table:
    with st.expander("View as table"):
        st.dataframe(map_countries, width="stretch", hide_index=True)

# --- Who, specifically ----------------------------------------------------

partners_column, countries_column = st.columns(2)

with partners_column:
    partner_frame = transforms.top_groups(
        load_group("authorships.institutions.id", year_from, year_to),
        config.TOP_N,
        label_name="institution",
        # CHRIST co-authors every one of its own papers, so without this it
        # ranks as its own top collaborator. Both spellings are excluded
        # because OpenAlex records the campuses under different names.
        exclude=["Christ University", "CHRIST (Deemed"],
    )
    st.plotly_chart(
        charts.field_bars(partner_frame, title="Partner institutions"),
        width="stretch",
    )
    with st.expander("View as table"):
        st.dataframe(partner_frame, width="stretch", hide_index=True)

with countries_column:
    top_countries = map_countries.head(config.TOP_N)
    st.plotly_chart(
        charts.field_bars(top_countries, title="Top partner countries"),
        width="stretch",
    )
    st.caption(
        "The map shows the pattern; these bars let you compare close values "
        "exactly, which a colour scale cannot do."
    )


# ===========================================================================
# 9. FOOTER
# ===========================================================================
# Crediting the data source is not decoration. OpenAlex is released under CC0
# and asks only to be acknowledged, and an examiner should be able to see at a
# glance where every number came from.

st.divider()

st.caption(
    f"Data from [OpenAlex](https://openalex.org), a free and open index of "
    f"scholarly works, released under CC0. Retrieved live from the public API "
    f"for [{config.INSTITUTION_SHORT}]({config.INSTITUTION_OPENALEX}) "
    f"({config.INSTITUTION_ROR.split('/')[-1]}). "
    f"No data is stored by this application."
)
st.caption(
    "Built with Streamlit, pandas and Plotly · "
    "MCA411-2 Python Programming, CHRIST (Deemed to be University)"
)
