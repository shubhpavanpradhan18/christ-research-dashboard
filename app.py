"""
app.py
======
The dashboard itself. Layout only: every number comes from openalex.py and
transforms.py, every figure from charts.py, and every piece of page chrome
(banner, cards, headings) from ui.py.

Structure of this file, in the order it runs:
    1. Page setup          - must run before any other Streamlit command
    2. Cached data loaders - every network call goes through one of these
    3. Sidebar             - logo, year range, research field, refresh
    4. Hero banner         - title, logo and the live badge
    5. Headline cards      - five animated numbers with year-over-year change
    6. Tabs                - Overview / People and papers / Author spotlight /
                             Collaboration / Search papers
    7. Footer

Run it with:   streamlit run app.py
"""

from datetime import datetime

import requests
import streamlit as st

import charts
import config
import openalex
import transforms
import ui


# ===========================================================================
# 1. PAGE SETUP
# ===========================================================================
# st.set_page_config MUST be the first Streamlit command executed. The browser
# tab shows the CHRIST logo when one is in assets/, and a chart emoji if not.

_logo = ui.find_logo()

st.set_page_config(
    page_title="CHRIST Research Intelligence",
    page_icon=str(_logo) if _logo else "📊",
    layout="wide",
    # "auto" opens the sidebar on desktop and keeps it closed on phones,
    # where an open sidebar would cover the whole page.
    initial_sidebar_state="auto",
)

ui.inject_theme()

# Secrets: OpenAlex serves requests that carry a contact email from a faster
# "polite pool". The address lives in .streamlit/secrets.toml locally (which
# .gitignore excludes) and in the Secrets box on Streamlit Cloud. The app
# pushes it DOWN into openalex.py, which never imports Streamlit - that is
# what keeps the data layer runnable from a plain Python script. Having no
# secrets file at all is a normal state, not an error.
try:
    openalex.CONTACT_EMAIL = st.secrets.get("openalex_email", "")
except Exception:
    openalex.CONTACT_EMAIL = ""

# A refresh is triggered by a button, then the page reruns from the top. The
# button leaves a flag behind so the confirmation can be shown AFTER the
# rerun, once the fresh data is actually on screen.
if st.session_state.pop("just_refreshed", False):
    st.toast("Live data re-fetched from OpenAlex", icon=":material/check_circle:")


# ===========================================================================
# 2. CACHED DATA LOADERS
# ===========================================================================
# Streamlit re-runs this ENTIRE script on every interaction - every slider
# drag, every click. Without caching, dragging the year slider would fire
# a dozen API calls per frame and OpenAlex would rate-limit the app.
#
# @st.cache_data remembers each result per distinct set of arguments. The
# one-hour TTL is the deliberate half: a cache that never expired would
# quietly turn a live dashboard into a static one.
#
# `extra` is a tuple of additional filter conditions - a research field, an
# author. It is a tuple rather than a list because cache keys must not be
# able to change after they are made, and tuples cannot.

@st.cache_data(ttl=config.CACHE_TTL_SECONDS, show_spinner=False)
def load_institution():
    """The institution record: totals, h-index, counts_by_year."""
    return openalex.get_institution(config.INSTITUTION_ID)


@st.cache_data(ttl=config.CACHE_TTL_SECONDS, show_spinner=False)
def load_group(group_field, year_from, year_to, extra=()):
    """Any server-side aggregation. The arguments form the cache key."""
    return openalex.group_works_by(
        config.INSTITUTION_ID, group_field, year_from, year_to, extra
    )


@st.cache_data(ttl=config.CACHE_TTL_SECONDS, show_spinner=False)
def load_count(year_from, year_to, extra=()):
    """How many papers fall inside the selected window."""
    return openalex.count_works(config.INSTITUTION_ID, year_from, year_to, extra)


@st.cache_data(ttl=config.CACHE_TTL_SECONDS, show_spinner=False)
def load_works(sort_by, limit, year_from, year_to, extra=()):
    """A small slice of individual papers."""
    return openalex.fetch_top_works(
        config.INSTITUTION_ID, year_from, year_to,
        sort_by=sort_by, limit=limit, extra=extra,
    )


@st.cache_data(ttl=config.CACHE_TTL_SECONDS, show_spinner=False)
def load_author(author_key):
    """One author's career record, for the spotlight."""
    return openalex.get_author(author_key)


@st.cache_data(ttl=config.CACHE_TTL_SECONDS, show_spinner=False)
def load_search(query, sort_by, year_from, year_to, extra=()):
    """Full-text search across CHRIST's papers."""
    return openalex.search_works(
        config.INSTITUTION_ID, query, year_from, year_to,
        extra=extra, sort_by=sort_by, limit=config.TOP_PAPERS,
    )


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------
# Plotly's toolbar keeps the useful buttons (download as PNG, zoom, reset)
# but loses the Plotly logo and the lasso/box-select tools, which do nothing
# useful on these charts.

PLOTLY_CONFIG = {
    "displaylogo": False,
    "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"],
}


def download_csv(frame, name):
    """
    A "Download CSV" button for any table.

    on_click="ignore" means the download does not rerun the app: the file
    arrives and the page stays exactly as it was.
    """
    st.download_button(
        "Download CSV",
        data=frame.to_csv(index=False).encode("utf-8"),
        file_name=f"christ_{name}_{year_from}-{year_to}.csv",
        mime="text/csv",
        icon=":material/download:",
        on_click="ignore",
        key=f"download-{name}",
    )


def show_chart(figure, table=None, name=None, toolbar=True):
    """
    Draw a figure, followed by its "View as table" twin and a download.

    Every chart has a table twin: a tooltip should enhance a chart, never be
    the only way to read a value.

    toolbar=False hides Plotly's hover toolbar. The animated chart needs
    that: the toolbar appears on hover in the top-right corner, exactly where
    the Play button sits, and swallows the click.
    """
    config = PLOTLY_CONFIG if toolbar else {"displayModeBar": False}
    st.plotly_chart(figure, width="stretch", config=config)
    if table is not None:
        with st.expander("View as table", icon=":material/table_view:"):
            st.dataframe(table, width="stretch", hide_index=True)
            if name:
                download_csv(table, name)


# How each column of a papers table is rendered. Defined once and used by
# every papers table, so they cannot drift apart.
PAPER_COLUMNS = {
    "Title": st.column_config.TextColumn("Title", width="large"),
    # Without an explicit format, integer years render as "2,024".
    "Year": st.column_config.NumberColumn("Year", format="%d"),
    "Citations": st.column_config.NumberColumn("Citations"),
    "Authors": st.column_config.NumberColumn(
        "Authors",
        help=(
            "Number of listed authors. Large international collaborations "
            "can carry hundreds, which inflates their citation count "
            "relative to work led here."
        ),
    ),
    "Field": st.column_config.TextColumn("Field"),
    "First author": st.column_config.TextColumn("First author"),
    "Published in": st.column_config.TextColumn("Published in"),
    "Open access": st.column_config.TextColumn("Open", width="small"),
    "Link": st.column_config.LinkColumn("DOI", display_text="Open"),
}


def papers_table(frame, name):
    """A sortable papers table with its download button."""
    st.dataframe(frame, width="stretch", hide_index=True, column_config=PAPER_COLUMNS)
    if not frame.empty:
        download_csv(frame, name)


# ===========================================================================
# 3. SIDEBAR
# ===========================================================================

current_year = datetime.now().year
ALL_FIELDS = "All fields"

with st.sidebar:
    ui.sidebar_logo()

    st.markdown("#### :material/tune: Filters")

    # A range slider returns a tuple: (lower, upper).
    year_from, year_to = st.slider(
        "Publication years",
        min_value=config.EARLIEST_YEAR,
        max_value=current_year,
        value=(config.DEFAULT_YEAR_FROM, current_year),
        step=1,
        help="Every chart and number on the page respects this range.",
    )
    span = year_to - year_from + 1
    st.caption(f"{span} year{'s' if span != 1 else ''} selected")

    # --- Research field ------------------------------------------------------
    # The list of fields comes from OpenAlex itself, so it is always the
    # fields CHRIST actually publishes in. Sorted alphabetically: an order
    # that changed with the year range would make the box jump around.
    try:
        field_groups = load_group("primary_topic.field.id", year_from, year_to)
    except requests.RequestException:
        field_groups = []
    field_keys = {group["label"]: group["key"] for group in field_groups}

    chosen_field = st.selectbox(
        "Research field",
        [ALL_FIELDS] + sorted(field_keys),
        help="Narrow every chart, table and search to one research field.",
    )

    # Prove the filter works with one cheap request before the whole page
    # depends on it. If OpenAlex rejects it, the page carries on with all
    # fields and says so, rather than every chart failing at once.
    field_extra = ()
    if chosen_field != ALL_FIELDS:
        candidate = (openalex.field_filter(field_keys[chosen_field]),)
        try:
            load_count(year_from, year_to, candidate)
            field_extra = candidate
        except requests.RequestException:
            st.warning(
                "That field filter could not be applied just now, so all "
                "fields are shown.",
                icon=":material/filter_alt_off:",
            )
    field_active = bool(field_extra)

    st.divider()

    st.markdown("#### :material/database: Data source")
    ui.side_card(
        [
            ("Index", "OpenAlex", "https://openalex.org"),
            ("Institution", config.INSTITUTION_SHORT, config.INSTITUTION_OPENALEX),
            ("ROR", config.INSTITUTION_ROR.split("/")[-1], config.INSTITUTION_ROR),
            ("Cache", f"{config.CACHE_TTL_SECONDS // 60} minutes", None),
        ]
    )

    st.markdown("")

    # Clearing the cache forces the next run to hit the API again. Useful in
    # a viva: click it and the numbers re-fetch in front of the examiner.
    if st.button(
        "Refresh data now",
        icon=":material/refresh:",
        type="primary",
        width="stretch",
    ):
        st.cache_data.clear()
        st.session_state["just_refreshed"] = True
        st.rerun()

    st.caption("No API key, no scraping, no stored data.")


# ===========================================================================
# 4. HERO BANNER
# ===========================================================================

TITLE = "CHRIST University Research Intelligence"
SUBTITLE = (
    f"{config.INSTITUTION_NAME} · {config.INSTITUTION_CITY} · "
    f"publications {year_from}–{year_to}"
    + (f" · {chosen_field}" if field_active else "")
)

# Load the core record first - if this fails, nothing else can work, so the
# page stops with a readable message instead of half-rendering.
try:
    with st.spinner("Fetching live data from OpenAlex…"):
        institution = load_institution()
except requests.RequestException as error:
    ui.hero(TITLE, SUBTITLE)
    st.error(
        "Could not reach the OpenAlex API. "
        "Check your internet connection and try again.",
        icon=":material/cloud_off:",
    )
    st.caption(f"Technical detail: {error.__class__.__name__}")
    st.stop()

# The live badge carries OpenAlex's own last-updated timestamp. It is the
# single most persuasive element on the page: nothing else so directly shows
# that this is live data and not a CSV committed to the repository.
ui.hero(TITLE, SUBTITLE, stamp=ui.format_stamp(institution.get("updated_date")))


# ===========================================================================
# 5. HEADLINE CARDS
# ===========================================================================
# Two sources feed the yearly series, deliberately:
#   publications -> group_by=publication_year: full history, and it respects
#                   the research-field filter
#   citations    -> counts_by_year from the institution record: the only
#                   place OpenAlex reports citations per year, about 13
#                   years of it, for the whole institution

publication_trend = transforms.yearly_from_groups(
    load_group("publication_year", year_from, year_to, field_extra)
)
citation_trend = transforms.yearly_trend(
    institution["counts_by_year"], year_from, year_to
)

windowed_papers = load_count(year_from, year_to, field_extra)

oa_frame = transforms.open_access_split(
    load_group("open_access.is_oa", year_from, year_to, field_extra)
)
oa_share = transforms.open_access_percentage(oa_frame)

# Year-over-year: the last COMPLETE year against the one before it. Never the
# current year - it is unfinished, so it would always look like a fall.
#
# Each change then passes two guards before it is shown as a real change
# (see transforms.py for the statistics):
#   1. both years need at least MIN_PAPERS papers, or no percentage is shown
#   2. a z-test decides whether the change is likely real (green or red) or
#      could easily be chance (grey, "likely noise")

MIN_PAPERS = config.MIN_PAPERS_FOR_CHANGE


def as_int(value):
    """Counts from pandas arrive as numpy integers; make them plain ints."""
    return None if value is None else int(value)


def count_change(now, before, note):
    """Card fields describing the change between two yearly paper counts."""
    if now is None or before is None:
        return {}
    if not transforms.enough_papers(now, before, MIN_PAPERS):
        return {
            "delta_hint": f"too few papers to compare ({now:,} vs {before:,})",
            "delta_test": (
                f"{note}: fewer than {MIN_PAPERS} papers in a year, so a "
                "percentage change would mostly be noise."
            ),
        }
    z = transforms.count_change_z(now, before)
    return {
        "delta": transforms.percent_change(now, before),
        "delta_note": note,
        "delta_significant": transforms.is_significant(z),
        "delta_test": (
            f"{now:,} vs {before:,} papers ({note}). Poisson z = {z:+.2f}. "
            "A |z| of 1.96 or more means a change this large would happen "
            "by chance less than 5% of the time."
        ),
    }


def share_change(open_now, total_now, open_before, total_before, note):
    """Card fields describing the change in the open-access share."""
    if not total_now or not total_before:
        return {}
    if not transforms.enough_papers(total_now, total_before, MIN_PAPERS):
        return {
            "delta_hint": f"too few papers to compare ({total_now:,} vs {total_before:,})",
            "delta_test": (
                f"{note}: fewer than {MIN_PAPERS} papers in a year, so the "
                "share would swing by several points per paper."
            ),
        }
    share_now = open_now / total_now * 100
    share_before = open_before / total_before * 100
    z = transforms.proportion_change_z(open_now, total_now, open_before, total_before)
    return {
        # Open access is already a percentage, so its change is measured in
        # percentage POINTS (41% -> 44% is +3 pts), not a percent of a percent.
        "delta": round(share_now - share_before, 1),
        "delta_unit": " pts",
        "delta_note": note,
        "delta_significant": transforms.is_significant(z),
        "delta_test": (
            f"{share_now:.1f}% of {total_now:,} vs {share_before:.1f}% of "
            f"{total_before:,} papers ({note}). Two-proportion z = {z:+.2f}. "
            "Note: many papers become open access months after publication, "
            "so the latest year tends to understate its final share."
        ),
    }


pub_change = cite_change = oa_change = {}
pair = transforms.comparison_years(year_from, year_to, current_year)
if pair:
    latest, earlier = pair
    note = f"{latest} vs {earlier}"

    pub_change = count_change(
        as_int(transforms.value_for_year(publication_trend, latest, "publications")),
        as_int(transforms.value_for_year(publication_trend, earlier, "publications")),
        note,
    )

    # Citations get the size of the change but no significance test. The
    # Poisson test assumes independent events of similar size; citations
    # cluster heavily on a few famous papers, so it would overstate its
    # confidence. Saying "not tested" is more honest than a misleading test.
    cites_now = transforms.value_for_year(citation_trend, latest, "citations")
    cites_before = transforms.value_for_year(citation_trend, earlier, "citations")
    if cites_now is not None and cites_before is not None:
        cite_change = {
            "delta": transforms.percent_change(cites_now, cites_before),
            "delta_note": note,
            "delta_test": (
                f"Citations received in {latest} vs {earlier}, whole institution. "
                "Not significance-tested: citations concentrate on a few "
                "highly cited papers, which breaks the test's assumptions."
            ),
        }

    open_now, total_now = transforms.open_and_total(transforms.open_access_split(
        load_group("open_access.is_oa", latest, latest, field_extra)))
    open_before, total_before = transforms.open_and_total(transforms.open_access_split(
        load_group("open_access.is_oa", earlier, earlier, field_extra)))
    oa_change = share_change(open_now, total_now, open_before, total_before, note)

# When a field is selected, the publication and open-access cards follow it,
# but citations, h-index and i10-index are institution-wide figures from
# OpenAlex - the captions say so rather than letting them look filtered.
WHOLE = "whole institution, all fields"

ui.kpi_row(
    [
        {
            "label": "Publications",
            "value": windowed_papers,
            **pub_change,
            "caption": (
                f"in {chosen_field}" if field_active
                else f"{institution['works_count']:,} all-time"
            ),
            "help": f"Papers published between {year_from} and {year_to}.",
        },
        {
            "label": "Citations",
            "value": institution["cited_by_count"],
            **cite_change,
            "caption": WHOLE if field_active else "across all publications",
            "help": "Total citations received, all years.",
        },
        {
            "label": "h-index",
            "value": institution["h_index"],
            "caption": WHOLE if field_active else "institutional impact",
            "help": (
                "The institution has at least this many papers that have each "
                "been cited at least this many times."
            ),
        },
        {
            "label": "i10-index",
            "value": institution["i10_index"],
            "caption": WHOLE if field_active else "papers cited 10+ times",
            "help": "Papers with 10 or more citations each.",
        },
        {
            "label": "Open access",
            "value": oa_share,
            "decimals": 1,
            "suffix": "%",
            **oa_change,
            "caption": "freely readable",
            "help": (
                "Share of papers in this window that are freely readable. "
                "Recent papers often become open access months later, so "
                "recent years can understate it."
            ),
        },
    ]
)

# A partial year would otherwise read as a collapse in output, so say so.
if year_to >= current_year:
    ui.note(
        f"{current_year} is still in progress, so its totals are incomplete "
        "and will keep rising until the year ends. Year-over-year changes "
        "compare complete years only; a grey change is within normal "
        "year-to-year variation. Hover a change to see the test behind it."
    )


# ===========================================================================
# 6. TABS
# ===========================================================================
# Switching tabs happens in the browser and does not rerun the script, so it
# is instant. The fixed key gives the tab bar a stable identity across the
# reruns that the filters trigger.

(tab_overview, tab_people, tab_spotlight,
 tab_collab, tab_search) = st.tabs(
    [
        ":material/insights: Overview",
        ":material/groups: People and papers",
        ":material/person_search: Author spotlight",
        ":material/public: Collaboration",
        ":material/search: Search papers",
    ],
    key="main_tabs",
)


# --- Overview ----------------------------------------------------------------

with tab_overview:
    ui.section(
        "Research output over time",
        "Papers published and citations received each year",
    )

    left, right = st.columns(2)

    with left:
        with st.container(border=True, key="card-publications"):
            show_chart(
                charts.publications_trend(publication_trend, current_year),
                publication_trend,
                "publications_per_year",
            )

    with right:
        with st.container(border=True, key="card-citations"):
            show_chart(
                charts.citations_trend(citation_trend),
                citation_trend[["year", "citations"]],
                "citations_per_year",
            )
            if field_active:
                st.caption(
                    "Citations per year are reported for the whole "
                    "institution, so this chart does not change with the "
                    "field filter."
                )
            if not citation_trend.empty and citation_trend["year"].min() > year_from:
                st.caption(
                    f"Citation history is available from "
                    f"{int(citation_trend['year'].min())} onwards."
                )

    ui.section(
        "The growth story",
        "Press Play to watch the output build, year by year",
    )

    with st.container(border=True, key="card-growth"):
        show_chart(
            charts.growth_animation(publication_trend, current_year),
            toolbar=False,
        )

    ui.section(
        "Subject mix and access",
        f"Inside {chosen_field}, and how much of it anyone can read"
        if field_active
        else "Where the research sits, and how much of it anyone can read",
    )

    fields_column, access_column = st.columns([2, 1])

    with fields_column:
        with st.container(border=True, key="card-fields"):
            if field_active:
                # One field selected: a chart of every field would show a
                # single bar, so drill down into its subfields instead.
                subfield_frame = transforms.top_groups(
                    load_group("primary_topic.subfield.id", year_from, year_to,
                               field_extra),
                    12,
                    label_name="subfield",
                )
                show_chart(
                    charts.field_bars(
                        subfield_frame, title=f"Subfields within {chosen_field}"
                    ),
                    subfield_frame,
                    "subfields",
                )
            else:
                field_frame = transforms.top_groups(field_groups, 12, label_name="field")
                show_chart(charts.field_bars(field_frame), field_frame, "research_fields")

    with access_column:
        with st.container(border=True, key="card-access"):
            show_chart(charts.open_access_bar(oa_frame), oa_frame, "open_access")
            if not oa_frame.empty:
                open_rows = oa_frame[oa_frame["access"] == "Open access"]
                open_count = int(open_rows["publications"].sum()) if not open_rows.empty else 0
                st.caption(
                    f"{open_count:,} of {int(oa_frame['publications'].sum()):,} "
                    f"papers in this window are free to read."
                )


# --- People and papers -------------------------------------------------------

author_groups = load_group(
    "authorships.author.id", year_from, year_to, field_extra
)

with tab_people:
    ui.section("Who publishes", "The most prolific authors, and what they publish")

    authors_column, types_column = st.columns([3, 2])

    with authors_column:
        with st.container(border=True, key="card-authors"):
            author_frame = transforms.top_groups(
                author_groups, config.TOP_N, label_name="author"
            )
            show_chart(charts.author_bars(author_frame), author_frame, "top_authors")

    with types_column:
        with st.container(border=True, key="card-types"):
            type_frame = transforms.top_groups(
                load_group("type", year_from, year_to, field_extra),
                8,
                label_name="type",
            )
            show_chart(
                charts.field_bars(type_frame, title="Publication types"),
                type_frame,
                "publication_types",
            )

    ui.section("The papers", "Sortable, with links to every paper")

    with st.container(border=True, key="card-papers"):
        most_cited_tab, newest_tab = st.tabs(
            [":material/trending_up: Most cited", ":material/schedule: Most recent"]
        )

        with most_cited_tab:
            papers_table(
                transforms.works_to_frame(load_works(
                    "cited_by_count:desc", config.TOP_PAPERS,
                    year_from, year_to, field_extra)),
                "most_cited_papers",
            )
            st.caption(
                "Citation counts reward large collaborations. The author column "
                "is shown so a paper with hundreds of contributors reads "
                "differently from one led at CHRIST."
            )

        with newest_tab:
            papers_table(
                transforms.works_to_frame(load_works(
                    "publication_date:desc", config.TOP_PAPERS,
                    year_from, year_to, field_extra)),
                "newest_papers",
            )
            st.caption(
                "The newest papers OpenAlex has indexed for this institution. "
                "Re-run tomorrow and this list will have changed."
            )


# --- Author spotlight --------------------------------------------------------

with tab_spotlight:
    ui.section(
        "Author spotlight",
        "Pick one of the most prolific authors to see their record",
    )

    # The choices are the top authors for the current filters, most prolific
    # first. A name maps back to the OpenAlex id the filters need.
    top_authors = sorted(author_groups, key=lambda g: g["count"], reverse=True)
    author_keys = {group["label"]: group["key"] for group in top_authors[: config.TOP_N]}

    if not author_keys:
        st.info("No authors found for these filters.", icon=":material/person_off:")
    else:
        chosen_author = st.selectbox("Author", list(author_keys))
        author_key = author_keys[chosen_author]
        author_extra = field_extra + (openalex.author_filter(author_key),)

        try:
            author = load_author(author_key)
            at_christ = load_count(year_from, year_to, author_extra)
            author_trend = transforms.yearly_from_groups(
                load_group("publication_year", year_from, year_to, author_extra)
            )
            author_papers = transforms.works_to_frame(
                load_works("cited_by_count:desc", 10, year_from, year_to, author_extra)
            )
        except requests.RequestException:
            st.error(
                "Could not load this author's record from OpenAlex just now.",
                icon=":material/cloud_off:",
            )
        else:
            ui.author_card(author)

            # The first card is about CHRIST; the other four cover the whole
            # career at every institution, and the captions say which is which.
            ui.kpi_row(
                [
                    {
                        "label": "Papers at CHRIST",
                        "value": at_christ,
                        "caption": f"{year_from}–{year_to}"
                        + (f", {chosen_field}" if field_active else ""),
                        "help": "Papers in this window with both this author "
                                "and CHRIST on them.",
                    },
                    {
                        "label": "Career papers",
                        "value": author["works_count"],
                        "caption": "all institutions",
                        "help": "Every paper OpenAlex attributes to this author.",
                    },
                    {
                        "label": "Career citations",
                        "value": author["cited_by_count"],
                        "caption": "all institutions",
                        "help": "Citations to every paper by this author.",
                    },
                    {
                        "label": "h-index",
                        "value": author["h_index"],
                        "caption": "whole career",
                        "help": "At least this many papers cited at least "
                                "this many times each.",
                    },
                    {
                        "label": "i10-index",
                        "value": author["i10_index"],
                        "caption": "whole career",
                        "help": "Papers with 10 or more citations each.",
                    },
                ]
            )

            trend_column, papers_column = st.columns([2, 3])

            with trend_column:
                with st.container(border=True, key="card-author-trend"):
                    show_chart(
                        charts.publications_trend(
                            author_trend, current_year,
                            title="Papers at CHRIST per year",
                        ),
                        author_trend,
                        "author_publications_per_year",
                    )

            with papers_column:
                with st.container(border=True, key="card-author-papers"):
                    st.markdown("**Their most cited papers at CHRIST**")
                    papers_table(author_papers, "author_top_papers")


# --- Collaboration -----------------------------------------------------------

with tab_collab:
    country_groups = load_group(
        "authorships.institutions.country_code", year_from, year_to, field_extra
    )

    # India is excluded from the map on purpose: as the home country it
    # appears on roughly twenty times more papers than the next, which would
    # flatten the colour scale until no international partner was readable.
    # Its figure is reported in the caption instead - moved, not hidden.
    map_countries = transforms.top_groups(
        country_groups, 60, label_name="country", exclude=["India"]
    )
    india_count = next(
        (group["count"] for group in country_groups if group["label"] == "India"), 0
    )

    ui.section(
        "International collaboration",
        "Countries whose institutions co-author papers with CHRIST",
    )

    with st.container(border=True, key="card-map"):
        show_chart(charts.collaboration_map(map_countries), map_countries, "countries")
        if india_count:
            st.caption(
                f"India is excluded from the map so the international pattern "
                f"is visible; it appears on {india_count:,} papers in this window. "
                "A paper is counted once per country among its author "
                "institutions, so the totals overlap rather than sum."
            )

    ui.section("Partners", "The institutions and countries CHRIST works with most")

    partners_column, countries_column = st.columns(2)

    with partners_column:
        with st.container(border=True, key="card-partners"):
            partner_frame = transforms.top_groups(
                load_group("authorships.institutions.id", year_from, year_to,
                           field_extra),
                config.TOP_N,
                label_name="institution",
                # CHRIST co-authors every one of its own papers, so without
                # this it would rank as its own top collaborator.
                exclude=["Christ University", "CHRIST (Deemed"],
            )
            show_chart(
                charts.field_bars(partner_frame, title="Partner institutions"),
                partner_frame,
                "partner_institutions",
            )

    with countries_column:
        with st.container(border=True, key="card-countries"):
            top_countries = map_countries.head(config.TOP_N)
            show_chart(charts.field_bars(top_countries, title="Top partner countries"))
            st.caption(
                "The map shows the pattern; these bars let you compare close "
                "values exactly, which a colour scale cannot do."
            )


# --- Search papers -----------------------------------------------------------

SORT_OPTIONS = {
    "Best match": None,                       # OpenAlex's relevance ranking
    "Most cited": "cited_by_count:desc",
    "Newest": "publication_date:desc",
}

with tab_search:
    ui.section(
        "Search CHRIST's papers",
        "Live search across titles and abstracts, within the years and field "
        "selected in the sidebar",
    )

    query_column, sort_column = st.columns([3, 1])
    with query_column:
        query = st.text_input(
            "Search",
            placeholder="Try: machine learning, sustainability, COVID-19, blockchain",
            icon=":material/search:",
            label_visibility="collapsed",
        ).strip()
    with sort_column:
        sort_label = st.selectbox(
            "Sort by", list(SORT_OPTIONS), label_visibility="collapsed"
        )

    if len(query) < 2:
        st.caption(
            "Type at least two characters. Each search is a live request to "
            "OpenAlex, cached for an hour."
        )
    else:
        try:
            with st.spinner("Searching OpenAlex…"):
                total, found = load_search(
                    query, SORT_OPTIONS[sort_label], year_from, year_to, field_extra
                )
        except requests.RequestException:
            st.error(
                "The search could not reach OpenAlex just now. Try again.",
                icon=":material/cloud_off:",
            )
        else:
            ui.result_count(total, query)
            results = transforms.works_to_frame(found)
            if results.empty:
                st.info(
                    "No papers matched. Try a broader word, or widen the "
                    "year range.",
                    icon=":material/search_off:",
                )
            else:
                with st.container(border=True, key="card-search"):
                    papers_table(results, "search_results")
                if total > len(results):
                    st.caption(
                        f"Showing the first {len(results)} of {total:,}. "
                        "Narrow the search or the years to see others."
                    )


# ===========================================================================
# 7. FOOTER
# ===========================================================================

ui.footer(
    config.INSTITUTION_SHORT,
    config.INSTITUTION_OPENALEX,
    config.INSTITUTION_ROR.split("/")[-1],
)
