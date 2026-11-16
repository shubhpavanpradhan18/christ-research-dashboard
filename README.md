# CHRIST University Research Intelligence Dashboard

A live dashboard of CHRIST (Deemed to be University)'s research output, built
with Streamlit and powered entirely by the OpenAlex API. Nothing is hardcoded
and no data file is committed — every number is fetched from the public API
when the page loads.

**Live app:** https://christ-research-dashboard-anr6kuwdqug7puxq4go4ym.streamlit.app

---

## What it shows

| Tab | Contents |
|---|---|
| **Headline cards** | Publications, citations, h-index, i10-index and open-access share, counting up on load, with year-over-year change (last complete year against the one before) |
| **Overview** | Publications and citations per year, an animated "growth story" with Play and a year slider, research fields (subfields when one field is selected), open-access split |
| **People and papers** | The most prolific authors, publication types, most-cited and most-recent papers with DOI links |
| **Author spotlight** | Pick an author: profile, ORCID, topics, papers at CHRIST per year, their most-cited papers, career totals |
| **Collaboration** | A world map of co-publishing countries, plus ranked partner institutions and countries |
| **Search papers** | Live search across titles and abstracts, sortable by relevance, citations or date |

Two filters in the sidebar - a year range and a research field - scope every
chart, table and search on the page. Every table can be downloaded as CSV.
A **Refresh data now** button clears the cache and re-fetches from the API.

---

## Data source

[OpenAlex](https://openalex.org) is a free, open index of scholarly works,
released under CC0. It requires **no API key and no authentication**.

This dashboard reports on the main CHRIST (Deemed to be University), Bangalore record:

- OpenAlex ID: `I48018076`
- ROR: [022tv9y30](https://ror.org/022tv9y30)

CHRIST's Delhi NCR campus is indexed by OpenAlex as a **separate institution**
(`I4405253679`), so the figures here cover the Bangalore campus only.

---

## Architecture

Six modules, each with one job. Only `openalex.py` touches the network, and
only `app.py` and `ui.py` touch Streamlit, so the data and chart layers can
be tested from a plain Python script.

```
config.py        every tunable value: institution, year defaults, cache TTL
openalex.py      all API access: filters, aggregation, search, author records
transforms.py    raw JSON -> tidy DataFrames, year-over-year maths. No network
charts.py        DataFrames -> Plotly figures, incl. the animation. No network
ui.py            page chrome: banner, animated cards, headings, footer
app.py           layout, caching and filters. No data logic
assets/          style.css (the theme) and christ_logo.png (the logo)
```

The logo is optional: save the official logo as `assets/christ_logo.png` and
the app shows it in the banner, the sidebar and the browser tab. Without it,
the app runs unchanged. The university's name and logo belong to the
university; the footer states that this is a student project.

Supporting scripts, kept because they document how the project was verified:

```
find_campus.py   lists every CHRIST record in OpenAlex (how I48018076 was found)
verify_data.py   proves the data source exists and reports which aggregations work
test_phase2.py   exercises the whole data layer end to end, with no Streamlit
verify_phase_b.py  checks every request the Phase B features rely on
```

---

## Running it locally

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows PowerShell
# source .venv/bin/activate       # macOS / Linux

pip install -r requirements.txt
streamlit run app.py
```

Optionally, copy `secrets.toml.example` to `.streamlit/secrets.toml` and add a
contact email. OpenAlex serves such requests from a faster pool. The app works
without it.

To check the data layer on its own, with no web app involved:

```bash
python test_phase2.py
```

---

## Design decisions

**Aggregate on the server, not the client.** CHRIST has over 20,000 indexed
papers. The dashboard never downloads them. Every aggregate figure comes from
OpenAlex's `group_by` parameter, which returns counts the server has already
computed; individual records are fetched only for the two tables that list
papers, about 25 rows each. This is why the app loads in seconds, and why the
project contains no pagination code — it does not need any.

**Cache with an expiry, not forever.** Streamlit re-runs the whole script on
every interaction, so each network call is wrapped in `@st.cache_data`.
Without it, dragging the year slider would fire an API request per frame. The
one-hour TTL is the deliberate part: a cache that never expires would quietly
turn a live dashboard into a static one.

**No dual-axis charts.** Publications (189–3,856) and citations (706–35,065)
are shown as two separate charts rather than one plot with two y-scales.
Aligning two different scales on one plot is arbitrary, and it invents a
correlation the data does not contain.

**Ranked bars instead of a treemap.** Fields separated by small margins —
972 against 928 — are indistinguishable as rectangles and obvious as bars on
a shared baseline.

**One colour per chart.** Bars are not shaded darker-where-bigger. Research
fields and authors are nominal categories with no inherent order, and the bar
length already encodes the magnitude.

**India is excluded from the collaboration map.** As the home country it
appears on roughly twenty times more papers than the next country, which
flattens the colour scale until no international partner is distinguishable.
Its figure is reported in the caption beneath the map rather than dropped.

**Accessibility.** Chart colours were checked for colour-blind separation
against the page background rather than chosen by eye, every chart has a
table-view twin so no value is reachable only by hovering, and the two-series
chart carries a legend so identity never rests on colour alone.

---

## How to read the numbers

- **Collaboration counts overlap.** OpenAlex counts a paper once for each
  country among its author institutions, so a paper with authors in three
  countries is counted in all three. The country totals answer "how often do
  we publish with this country", and deliberately do not sum to the paper
  count.
- **The current year is incomplete.** It is drawn in a lighter shade and
  labelled "so far", because a partial year otherwise reads as a decline.
- **Citation counts reward large collaborations.** The most-cited paper is a
  several-hundred-author international collaboration. The papers table shows
  an author count per row so that context is visible.
- **Citations per year** come from the institution record, which reaches back
  about 13 years. Dragging the slider earlier than that affects the
  publications chart but not the citations chart; the app says so when it
  happens.
- **Year-over-year change compares complete years only** - for example 2025
  against 2024 - because the current year is unfinished and would always
  look like a fall. Open access changes in percentage points, not percent.
- **The research-field filter** narrows publications, open access, authors,
  papers, collaboration and search. Citations, h-index and i10-index are
  institution-wide figures in OpenAlex, so they do not change with it; their
  cards say "whole institution" when a field is selected.
- **Author career totals** (career papers, citations, h-index) cover the
  author's whole career at every institution. Only "Papers at CHRIST" is
  specific to this university.

---

## Course

Component 3 (Assignment) — **MCA411-2 Python Programming**
Department of Computer Science, CHRIST (Deemed to be University)
