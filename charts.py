"""
charts.py
=========
Every Plotly figure in the dashboard is built here.

Like transforms.py, this module is offline: it receives DataFrames and returns
figures. It never calls the API and never calls Streamlit.

----------------------------------------------------------------------------
DESIGN RULES THIS FILE FOLLOWS  (worth knowing for the viva)
----------------------------------------------------------------------------
1. No dual-axis charts. Publications and citations have wildly different
   scales (thousands vs tens of thousands). Putting them on one plot with two
   y-axes would invent a correlation that is not in the data, because the
   alignment of the two scales is arbitrary. They get two charts instead.

2. No value-ramp on nominal categories. Research fields have no natural
   order, so shading each bar darker-where-bigger would encode bar length
   twice and waste the colour channel. One series, one colour.

3. Colour is verified, not eyeballed. The two hues used here were checked for
   colour-blind separation against a white surface before being chosen.

4. Thin marks, hairline solid gridlines, labels only where they earn their
   place. A number on every data point goes unread.
----------------------------------------------------------------------------
"""

import plotly.graph_objects as go


# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
# Defined once, used everywhere. Changing the look of every chart means
# changing these eight lines.

SURFACE = "#FFFFFF"        # the chart background, matches the Streamlit theme
BLUE = "#2a78d6"           # primary series
BLUE_LIGHT = "#86b6ef"     # same hue, lighter - used for "incomplete" data
ORANGE = "#eb6834"         # second series, in its own chart
GRAY_QUIET = "#c3c2b7"     # de-emphasised, and the axis baseline
GRID = "#e1e0d9"           # hairline gridlines
INK = "#52514e"            # label text
INK_MUTED = "#898781"      # axis tick text


def _base_layout(fig, height=340, show_legend=False):
    """
    Apply the chrome every chart shares.

    Doing this in one function is what makes the four charts look like one
    system rather than four separate exercises.
    """
    fig.update_layout(
        height=height,
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        margin=dict(l=10, r=20, t=50, b=40),   # room for the axis band
        font=dict(
            family='system-ui, -apple-system, "Segoe UI", sans-serif',
            size=13,
            color=INK,
        ),
        showlegend=show_legend,
        hoverlabel=dict(
            bgcolor=SURFACE,
            font_size=13,
            bordercolor=GRAY_QUIET,
        ),
    )

    # Gridlines: solid hairlines one step off the surface. Never dashed -
    # dashing reads as "projection" or "threshold" when it is only a grid.
    fig.update_xaxes(
        showgrid=False,
        showline=True,
        linecolor=GRAY_QUIET,
        linewidth=1,
        tickfont=dict(color=INK_MUTED, size=12),
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor=GRID,
        gridwidth=1,
        zeroline=False,
        showline=False,
        tickfont=dict(color=INK_MUTED, size=12),
    )
    return fig


# ---------------------------------------------------------------------------
# 1. Publications per year
# ---------------------------------------------------------------------------

def publications_trend(trend, current_year):
    """
    Columns, one per year.

    The current year is drawn in a lighter step of the same blue because it is
    the same measure, just incomplete. A different hue would say "different
    thing"; a lighter step of one hue says "less certain".
    """
    fig = go.Figure()

    if trend.empty:
        return _base_layout(fig)

    years = trend["year"].tolist()
    values = trend["publications"].tolist()

    # Same hue family throughout - lighter only where the year is unfinished.
    colours = [BLUE_LIGHT if year >= current_year else BLUE for year in years]

    fig.add_trace(
        go.Bar(
            x=years,
            y=values,
            marker=dict(
                color=colours,
                cornerradius=4,       # soft data-end, square against the baseline
            ),
            width=0.62,               # leaves air in each slot; bars never fill it
            hovertemplate="<b>%{x}</b><br>%{y:,} publications<extra></extra>",
            name="Publications",
        )
    )

    # Label selectively: the current year, and the peak. Labelling all twelve
    # columns would be noise, and the y-axis already carries the rest.
    #
    # The adjacency guard matters: research output is still climbing, so the
    # peak is usually the year right before the current one. Labelling both
    # puts two bold numbers side by side and they overlap. When they are
    # neighbours, the current year wins - it is the one carrying the caveat.
    peak_index = values.index(max(values))
    current_indices = [i for i, year in enumerate(years) if year >= current_year]

    label_indices = set(current_indices)
    if all(abs(peak_index - i) > 1 for i in current_indices):
        label_indices.add(peak_index)

    for index in sorted(label_indices):
        suffix = " so far" if years[index] >= current_year else ""
        fig.add_annotation(
            x=years[index],
            y=values[index],
            text=f"<b>{values[index]:,}</b>{suffix}",
            showarrow=False,
            yshift=14,
            font=dict(color=INK, size=12),
        )

    fig.update_layout(
        title=dict(
            text="Publications per year",
            font=dict(size=16, color="#0b0b0b"),
        ),
        bargap=0.38,
    )
    fig.update_xaxes(dtick=1, tickangle=0)
    # Under 10,000 the axis reads in full, with thousands separators.
    fig.update_yaxes(tickformat=",")
    return _base_layout(fig)


# ---------------------------------------------------------------------------
# 2. Citations per year
# ---------------------------------------------------------------------------

def citations_trend(trend):
    """
    A line with a soft fill underneath.

    Deliberately a SEPARATE chart from publications. Two measures whose scales
    differ by an order of magnitude belong on two axes - which means two
    charts, never one plot with two y-scales.
    """
    fig = go.Figure()

    if trend.empty or "citations" not in trend.columns:
        return _base_layout(fig)

    years = trend["year"].tolist()
    values = trend["citations"].tolist()

    fig.add_trace(
        go.Scatter(
            x=years,
            y=values,
            mode="lines+markers",
            line=dict(color=ORANGE, width=2, shape="linear"),
            # The area is a wash at roughly 10% opacity, never a solid block.
            fill="tozeroy",
            fillcolor="rgba(235, 104, 52, 0.10)",
            marker=dict(
                size=8,
                color=ORANGE,
                # A 2px ring in the surface colour keeps markers legible where
                # they sit on the line, instead of drawing a border.
                line=dict(width=2, color=SURFACE),
            ),
            hovertemplate="<b>%{x}</b><br>%{y:,} citations<extra></extra>",
            name="Citations",
        )
    )

    # Lines get their value at the end point only.
    fig.add_annotation(
        x=years[-1],
        y=values[-1],
        text=f"<b>{values[-1]:,}</b>",
        showarrow=False,
        yshift=18,
        font=dict(color=INK, size=12),
    )

    fig.update_layout(
        title=dict(
            text="Citations received per year",
            font=dict(size=16, color="#0b0b0b"),
        )
    )
    fig.update_xaxes(dtick=1, tickangle=0)
    return _base_layout(fig)


# ---------------------------------------------------------------------------
# 3. Research fields
# ---------------------------------------------------------------------------

def field_bars(fields, title="Publications by research field"):
    """
    Ranked horizontal bars, largest at the top.

    This replaces the treemap I originally planned. Bars sharing one baseline
    let you compare close values exactly - 972 vs 928 is obvious here and
    almost unreadable as two rectangles in a treemap.

    All bars are one colour on purpose. Shading them by size would encode
    magnitude twice, since the bar length already says it, and research fields
    have no inherent order for a ramp to represent.
    """
    fig = go.Figure()

    if fields.empty:
        return _base_layout(fig)

    label_column = fields.columns[0]

    # Plotly draws horizontal bars bottom-up, so reverse to put the biggest
    # at the top where the eye starts.
    labels = fields[label_column].tolist()[::-1]
    values = fields["publications"].tolist()[::-1]

    fig.add_trace(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker=dict(color=BLUE, cornerradius=4),
            hovertemplate="<b>%{y}</b><br>%{x:,} publications<extra></extra>",
            text=[f"{value:,}" for value in values],
            textposition="outside",      # outside the tip, so it is never clipped
            textfont=dict(color=INK, size=12),
            cliponaxis=False,
            name="Publications",
        )
    )

    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color="#0b0b0b")),
        bargap=0.34,
        margin=dict(l=10, r=70, t=50, b=30),   # right margin holds the labels
    )

    # _base_layout first, then override - see the note in author_bars. Its
    # horizontal gridlines would otherwise run through every category row.
    height = max(200, 30 * len(labels) + 90)
    fig = _base_layout(fig, height=height)
    fig.update_xaxes(visible=False, showgrid=False)
    fig.update_yaxes(
        showgrid=False,
        tickfont=dict(color=INK, size=12),
        automargin=True,                        # never clip a long field name
    )
    return fig


# ---------------------------------------------------------------------------
# 3b. Top authors
# ---------------------------------------------------------------------------

def author_bars(authors):
    """
    Ranked horizontal bars, one per author.

    Same reasoning as the research fields chart: people are nominal
    categories with no inherent order, so every bar is the same colour and
    the length alone carries the magnitude.
    """
    fig = go.Figure()

    if authors.empty:
        return _base_layout(fig)

    label_column = authors.columns[0]

    # Reversed so the most prolific author sits at the top.
    names = authors[label_column].tolist()[::-1]
    values = authors["publications"].tolist()[::-1]

    fig.add_trace(
        go.Bar(
            x=values,
            y=names,
            orientation="h",
            marker=dict(color=BLUE, cornerradius=4),
            hovertemplate="<b>%{y}</b><br>%{x:,} publications<extra></extra>",
            text=[f"{value:,}" for value in values],
            textposition="outside",
            textfont=dict(color=INK, size=12),
            cliponaxis=False,
            name="Publications",
        )
    )

    fig.update_layout(
        title=dict(
            text="Most prolific authors",
            font=dict(size=16, color="#0b0b0b"),
        ),
        bargap=0.34,
        margin=dict(l=10, r=60, t=50, b=30),
    )

    # _base_layout is applied FIRST here, then overridden. It sets horizontal
    # gridlines, which are right for a column chart but wrong for a horizontal
    # bar chart - there they draw a line through every category row. Calling
    # it last would silently undo the overrides below.
    height = max(200, 30 * len(names) + 90)
    fig = _base_layout(fig, height=height)
    fig.update_xaxes(visible=False, showgrid=False)
    fig.update_yaxes(
        showgrid=False, tickfont=dict(color=INK, size=12), automargin=True
    )
    return fig


# ---------------------------------------------------------------------------
# 3c. Collaboration map
# ---------------------------------------------------------------------------

# A sequential ramp: ONE hue, light to dark. Never a rainbow - a multi-hue
# scale makes the reader decode an arbitrary colour order before they can read
# a magnitude, and the order is not self-evident. With one hue, darker simply
# means more.
BLUE_SCALE = [
    [0.00, "#cde2fb"],
    [0.25, "#9ec5f4"],
    [0.50, "#5598e7"],
    [0.75, "#256abf"],
    [1.00, "#0d366b"],
]


def collaboration_map(countries):
    """
    A world choropleth of co-publishing countries.

    Note on reading it: OpenAlex counts a paper once for each country among
    its author institutions, so a paper with authors in three countries is
    counted in all three. The totals therefore do not sum to the number of
    papers - they answer "how often do we publish with this country", which
    is the question the map is for.
    """
    fig = go.Figure()

    if countries.empty:
        return fig

    label_column = countries.columns[0]

    fig.add_trace(
        go.Choropleth(
            locations=countries[label_column],
            locationmode="country names",
            z=countries["publications"],
            colorscale=BLUE_SCALE,
            # Country outlines are drawn in the surface colour, so the gap
            # between neighbours separates them without adding dark ink.
            marker=dict(line=dict(color=SURFACE, width=0.6)),
            hovertemplate="<b>%{location}</b><br>%{z:,} co-authored papers<extra></extra>",
            colorbar=dict(
                title=dict(text="Papers", font=dict(size=12, color=INK)),
                thickness=12,
                len=0.7,
                outlinewidth=0,
                tickfont=dict(color=INK_MUTED, size=11),
            ),
        )
    )

    fig.update_geos(
        showframe=False,
        showcoastlines=False,
        showland=True,
        landcolor="#F3F3F0",          # countries with no data stay quiet
        showocean=False,
        showlakes=False,
        projection_type="natural earth",
        bgcolor=SURFACE,
    )

    fig.update_layout(
        title=dict(
            text="International collaboration",
            font=dict(size=16, color="#0b0b0b"),
        ),
        height=430,
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        margin=dict(l=0, r=0, t=50, b=0),
        font=dict(
            family='system-ui, -apple-system, "Segoe UI", sans-serif',
            size=13,
            color=INK,
        ),
        hoverlabel=dict(bgcolor=SURFACE, font_size=13, bordercolor=GRAY_QUIET),
    )
    return fig


# ---------------------------------------------------------------------------
# 4. Open access split
# ---------------------------------------------------------------------------

def open_access_bar(oa_frame):
    """
    One whole, split into two parts, as a single segmented bar.

    Not a donut. A two-slice pie is the classic way to use a lot of space to
    say one number, and comparing two arcs is harder than comparing two blocks
    on a shared line.

    Open access is drawn in the accent blue and restricted in a quiet gray:
    the story is "how much is freely readable", so that part gets the colour
    and the other recedes.
    """
    fig = go.Figure()

    if oa_frame.empty:
        return _base_layout(fig, height=200)

    total = oa_frame["publications"].sum()
    if total == 0:
        return _base_layout(fig, height=200)

    # Fixed colours per category name - never by rank - so filtering the year
    # range can never repaint the segments.
    palette = {"Open access": BLUE, "Restricted": GRAY_QUIET, "Unknown": GRID}
    label_ink = {"Open access": "#FFFFFF", "Restricted": "#0b0b0b", "Unknown": "#0b0b0b"}

    # Draw open access first so it starts at the left edge.
    order = ["Open access", "Restricted", "Unknown"]
    rows = sorted(
        oa_frame.to_dict("records"),
        key=lambda row: order.index(row["access"]) if row["access"] in order else 99,
    )

    for row in rows:
        access = row["access"]
        value = row["publications"]
        share = value / total * 100

        # Only print the share inside the block when there is room for it.
        # A cramped label gets clipped, which is worse than no label - the
        # value still appears in the hover and in the table view.
        inside_text = f"{share:.1f}%" if share >= 12 else ""

        fig.add_trace(
            go.Bar(
                x=[value],
                y=["Open access"],
                orientation="h",
                name=access,
                marker=dict(
                    color=palette.get(access, GRID),
                    cornerradius=4,
                    # A 2px line in the surface colour renders as the gap that
                    # separates touching segments.
                    line=dict(color=SURFACE, width=2),
                ),
                text=inside_text,
                textposition="inside",
                insidetextanchor="middle",
                textfont=dict(color=label_ink.get(access, "#0b0b0b"), size=13),
                hovertemplate=(
                    f"<b>{access}</b><br>%{{x:,}} papers "
                    f"({share:.1f}%)<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        title=dict(
            text="Open access share",
            font=dict(size=16, color="#0b0b0b"),
        ),
        barmode="stack",
        bargap=0.6,
        margin=dict(l=10, r=20, t=50, b=10),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.15,
            x=0,
            font=dict(color=INK, size=12),
            # Without this the legend lists the blocks right to left, so the
            # names read in the opposite order to the bar they describe.
            traceorder="normal",
        ),
    )
    # Two series, so a legend is always present - identity never rests on
    # colour alone. Layout first, then hide both axes: a segmented bar has no
    # scale to read, so neither axis nor grid has anything to say.
    fig = _base_layout(fig, height=210, show_legend=True)
    fig.update_xaxes(visible=False, showgrid=False)
    fig.update_yaxes(visible=False, showgrid=False)
    return fig
