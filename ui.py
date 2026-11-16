"""
ui.py
=====
The presentation layer: the theme, the hero banner with the CHRIST logo, the
animated headline cards, section headings, notes and the footer.

Where it sits in the architecture:

    openalex.py    network          (HTTP and JSON)
    transforms.py  data             (pandas)
    charts.py      figures          (Plotly)
    ui.py          the page chrome  (HTML and CSS)     <- this file
    app.py         layout           (decides what goes where)

Like charts.py, it never touches the network. Unlike charts.py, it does
touch Streamlit, because its whole job is putting HTML on the page.

Safety:
    Several functions here insert raw HTML. Every piece of text that reaches
    the page passes through html.escape() first - including the timestamp,
    which comes from OpenAlex - so a stray "<" in the data can never turn
    into markup. Numbers are formatted by Python before they are inserted.
"""

import base64
import hashlib
import html
from datetime import datetime
from pathlib import Path

import streamlit as st


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------
# Paths are built from this file's own location, not from the folder the app
# was started in, so they work both locally and on Streamlit Cloud.

ASSETS = Path(__file__).parent / "assets"
STYLESHEET = ASSETS / "style.css"

# The logo is looked for under these names, in this order. Whichever you save
# into assets/ will be picked up; if none exists the app simply shows no logo.
LOGO_NAMES = (
    "christ_logo.png",
    "christ_logo.svg",
    "christ_logo.webp",
    "christ_logo.jpg",
    "christ_logo.jpeg",
)

MIME_TYPES = {
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


def find_logo():
    """Return the path of the logo file, or None if there isn't one yet."""
    for name in LOGO_NAMES:
        candidate = ASSETS / name
        if candidate.exists():
            return candidate
    return None


def _data_uri(path):
    """
    Turn an image file into text that can sit directly inside an <img> tag.

    The hero banner is plain HTML, and plain HTML cannot point at a file on
    the server's disk. Encoding the image as base64 inlines the picture into
    the page itself, so it needs no separate request and no file server.
    """
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    mime = MIME_TYPES.get(path.suffix.lower(), "image/png")
    return f"data:{mime};base64,{encoded}"


# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------

def inject_theme():
    """
    Load assets/style.css into the page.

    Given a Path to a .css file, st.html wraps it in <style> tags itself and
    places it where it takes up no room on the page.

    One trap, learned the hard way: Streamlit sanitises HTML before showing
    it, and a single angle bracket anywhere in the CSS - even inside a
    comment - is read as the start of a tag. The sanitiser then throws the
    WHOLE stylesheet away, silently. This check turns that silent failure
    into a visible warning.
    """
    if not STYLESHEET.exists():
        return
    if "<" in STYLESHEET.read_text(encoding="utf-8"):
        st.warning(
            "assets/style.css contains a '<' character, so Streamlit will "
            "discard the whole stylesheet. Remove it - comments included.",
            icon=":material/warning:",
        )
        return
    st.html(STYLESHEET)


def sidebar_logo():
    """
    Put the logo in the app's own chrome, top-left above the sidebar.

    st.logo is Streamlit's native way to brand an app: the logo stays put
    while the page scrolls, and shrinks to an icon when the sidebar closes.
    """
    logo = find_logo()
    if logo is not None:
        st.logo(str(logo), size="large")


# ---------------------------------------------------------------------------
# Hero banner
# ---------------------------------------------------------------------------

def format_stamp(raw):
    """
    "2026-11-15T18:22:16.123" -> "15 Nov 2026, 18:22"

    OpenAlex sends an ISO timestamp, sometimes with fractions of a second.
    Only the first 19 characters are parsed so either form works. If the
    format ever changes, the raw text is shown rather than crashing the page.
    """
    if not raw:
        return ""
    try:
        moment = datetime.fromisoformat(str(raw)[:19])
    except ValueError:
        return str(raw)
    return moment.strftime("%d %b %Y, %H:%M")


def hero(title, subtitle, stamp=None, eyebrow="Live research dashboard"):
    """The banner at the top of the page: logo, title, and the live badge."""
    parts = ['<section class="hero">']

    logo = find_logo()
    if logo is not None:
        parts.append(
            '<div class="hero-logo">'
            f'<img src="{_data_uri(logo)}" alt="CHRIST (Deemed to be University) logo">'
            "</div>"
        )

    # The live badge sits inside the text column, under the subtitle, so it
    # stays in a predictable place at every screen width instead of wrapping
    # to wherever the browser finds room.
    live = ""
    if stamp:
        live = (
            '<div class="hero-live">'
            '<span class="live-dot"></span>'
            f"<span><b>Live</b> · OpenAlex updated {html.escape(stamp)} UTC</span>"
            "</div>"
        )

    parts.append(
        '<div class="hero-text">'
        f'<div class="hero-eyebrow">{html.escape(eyebrow)}</div>'
        f'<div class="hero-title">{html.escape(title)}</div>'
        f'<div class="hero-sub">{html.escape(subtitle)}</div>'
        f"{live}"
        "</div>"
    )

    parts.append("</section>")
    st.html("".join(parts))


# ---------------------------------------------------------------------------
# Animated headline cards
# ---------------------------------------------------------------------------
# The count-up is progressive enhancement:
#   1. Python writes the FINAL formatted number into every card.
#   2. A small script then resets each number to zero and counts it back up.
# If the script never runs - JavaScript blocked, an older Streamlit, or the
# reader has "reduce motion" switched on - the final numbers are already
# there. The animation can fail without the data ever being wrong.

_COUNT_UP_SCRIPT = """
<script>
(function () {
  var tries = 0;
  function run() {
    var root = document.getElementById("__ROOT__");
    if (!root) {
      if (tries++ < 60) { requestAnimationFrame(run); }
      return;
    }
    if (root.getAttribute("data-animated") === "1") { return; }
    root.setAttribute("data-animated", "1");

    var reduce = window.matchMedia &&
                 window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) { return; }

    root.querySelectorAll(".num").forEach(function (el, i) {
      var target = parseFloat(el.getAttribute("data-target"));
      var places = parseInt(el.getAttribute("data-decimals") || "0", 10);
      var suffix = el.getAttribute("data-suffix") || "";
      if (!isFinite(target)) { return; }

      function show(value) {
        el.textContent = value.toLocaleString("en-US", {
          minimumFractionDigits: places,
          maximumFractionDigits: places
        }) + suffix;
      }

      var duration = 1400, delay = i * 90, start = null;
      show(0);

      function step(now) {
        if (start === null) { start = now + delay; }
        var t = Math.min(1, Math.max(0, (now - start) / duration));
        var eased = 1 - Math.pow(1 - t, 3);   /* ease-out: fast, then settles */
        show(target * eased);
        if (t < 1) { requestAnimationFrame(step); } else { show(target); }
      }
      requestAnimationFrame(step);
    });
  }
  run();
})();
</script>
"""


def _delta_html(card):
    """
    The small line under a card's number, in one of four states:

        ▲ 4.9%  2025 vs 2024                 a real rise    (green)
        ▼ 3.1 pts  2025 vs 2024              a real fall    (red)
        ▲ 14.3%  2025 vs 2024 · likely noise  too small to call (grey)
        — too few papers to compare (12 vs 9)               (grey)

    The arrow carries the direction, so it still reads for someone who
    cannot tell red from green: colour is a second signal, not the only one.
    Hovering the line shows the statistics behind it.
    """
    delta = card.get("delta")
    hint = card.get("delta_hint")
    test = html.escape(card.get("delta_test", ""))

    if delta is None:
        if not hint:
            return ""
        return f'<div class="kpi-delta muted" title="{test}">— {html.escape(hint)}</div>'

    unit = card.get("delta_unit", "%")
    note = card.get("delta_note", "")

    if abs(delta) < 0.05:
        direction, arrow = "flat", "●"
    elif delta > 0:
        direction, arrow = "up", "▲"
    else:
        direction, arrow = "down", "▼"

    # A change the significance test cannot tell apart from chance keeps its
    # arrow and number, but loses its colour: green and red are reserved for
    # changes that are probably real.
    tag = ""
    if card.get("delta_significant") is False:
        direction = "noise"
        tag = "<span>· likely noise</span>"

    # Each phrase sits in its own span, and the CSS stops a span from
    # breaking, so a narrow card wraps BETWEEN phrases ("2025 vs 2024" /
    # "· likely noise") instead of in the middle of one.
    return (
        f'<div class="kpi-delta {direction}" title="{test}">'
        f'<span class="kpi-delta-value">{arrow} {abs(delta):,.1f}{html.escape(unit)}</span>'
        f"<span>{html.escape(note)}</span>{tag}</div>"
    )


def kpi_row(cards):
    """
    Render the row of headline numbers.

    `cards` is a list of dicts:
        label       "Publications"
        value       18659
        decimals    0            (optional, default 0)
        suffix      "%"          (optional)
        caption     "20,502 all-time"
        help        shown as a tooltip when the card is hovered
        delta       4.9          (optional: change against an earlier period)
        delta_unit  "%" or " pts" (optional, default "%")
        delta_note  "2025 vs 2024"
        delta_significant  True / False / None   (None = not tested)
        delta_hint  shown instead of a change, e.g. "too few papers"
        delta_test  tooltip text explaining the statistics
    """
    # A stable id derived from the numbers themselves. When a filter changes
    # the numbers, the id changes too, the block is re-rendered, and the
    # count-up plays again with the new values.
    fingerprint = hashlib.md5(repr(cards).encode("utf-8")).hexdigest()[:10]
    root_id = f"kpi-{fingerprint}"

    blocks = []
    for position, card in enumerate(cards):
        decimals = int(card.get("decimals", 0))
        suffix = card.get("suffix", "")
        value = float(card["value"])
        final_text = f"{value:,.{decimals}f}{suffix}"

        blocks.append(
            f'<div class="kpi" style="animation-delay:{position * 90}ms" '
            f'title="{html.escape(card.get("help", ""))}">'
            f'<div class="kpi-label">{html.escape(card["label"])}</div>'
            f'<div class="kpi-value"><span class="num" data-target="{value}" '
            f'data-decimals="{decimals}" data-suffix="{html.escape(suffix)}">'
            f"{html.escape(final_text)}</span></div>"
            f"{_delta_html(card)}"
            f'<div class="kpi-caption">{html.escape(card.get("caption", ""))}</div>'
            "</div>"
        )

    markup = f'<div class="kpi-row" id="{root_id}">{"".join(blocks)}</div>'
    script = _COUNT_UP_SCRIPT.replace("__ROOT__", root_id)

    # Running JavaScript inside st.html needs a recent Streamlit. On an older
    # version the argument does not exist, so fall back to the static cards,
    # which already show the correct final numbers.
    try:
        st.html(markup + script, unsafe_allow_javascript=True)
    except TypeError:
        st.html(markup)


# ---------------------------------------------------------------------------
# Headings, notes, sidebar card, footer
# ---------------------------------------------------------------------------

def section(title, subtitle=""):
    """A section heading with the navy-to-gold accent bar."""
    sub = f'<div class="section-sub">{html.escape(subtitle)}</div>' if subtitle else ""
    st.html(
        '<div class="section-head"><span class="section-bar"></span>'
        f'<div><div class="section-title">{html.escape(title)}</div>{sub}</div></div>'
    )


def note(text, lead="Note"):
    """A soft amber callout for caveats the reader must not miss."""
    st.html(
        f'<div class="note"><span><b>{html.escape(lead)}.</b> '
        f"{html.escape(text)}</span></div>"
    )


def _safe_url(url):
    """Only ever link to http(s) addresses - never javascript: or data:."""
    if url and str(url).startswith(("https://", "http://")):
        return html.escape(str(url))
    return None


def author_card(author):
    """
    The profile header in the Author Spotlight: initials, name, links,
    last known institution, and the topics they publish on most.
    """
    name = author.get("name") or "Unknown author"
    initials = "".join(part[0] for part in name.replace(".", " ").split()[:2]).upper()

    links = []
    orcid = _safe_url(author.get("orcid"))
    if orcid:
        links.append(f'<a href="{orcid}" target="_blank" rel="noopener">ORCID</a>')
    profile = _safe_url(author.get("url"))
    if profile:
        links.append(
            f'<a href="{profile}" target="_blank" rel="noopener">OpenAlex profile</a>'
        )

    places = author.get("institutions") or []
    meta = []
    if places:
        meta.append("Last known at " + html.escape(", ".join(places[:2])))
    meta.extend(links)

    chips = "".join(
        f'<span class="chip">{html.escape(topic)}</span>'
        for topic in (author.get("topics") or [])
    )

    st.html(
        '<div class="author-card">'
        f'<div class="author-avatar">{html.escape(initials or "?")}</div>'
        "<div>"
        f'<div class="author-name">{html.escape(name)}</div>'
        f'<div class="author-meta">{" · ".join(meta)}</div>'
        f'<div class="chips">{chips}</div>'
        "</div></div>"
    )


def side_card(rows):
    """
    A compact key-value card for the sidebar.

    `rows` is a list of (label, text, url) tuples; url may be None.
    """
    lines = []
    for label, text, url in rows:
        shown = html.escape(text)
        if url:
            shown = (
                f'<a href="{html.escape(url)}" target="_blank" '
                f'rel="noopener">{shown}</a>'
            )
        lines.append(f'<div class="row"><span>{html.escape(label)}</span>{shown}</div>')
    st.html(f'<div class="side-card">{"".join(lines)}</div>')


def footer(institution_name, institution_url, ror_id):
    """Source credit, course line, and an honest disclaimer."""
    st.html(
        '<div class="footer">'
        'Data from <a href="https://openalex.org" target="_blank" rel="noopener">'
        "OpenAlex</a>, a free and open index of scholarly works released under "
        "CC0, retrieved live from its public API for "
        f'<a href="{html.escape(institution_url)}" target="_blank" rel="noopener">'
        f"{html.escape(institution_name)}</a> (ROR {html.escape(ror_id)}). "
        "No data is stored by this application.<br>"
        "Built with Streamlit, pandas and Plotly · "
        "MCA411-2 Python Programming, CHRIST (Deemed to be University)."
        '<div class="disclaimer">A student project, not an official publication '
        "of CHRIST (Deemed to be University). The university's name and logo "
        "belong to the university.</div>"
        "</div>"
    )


def result_count(total, query):
    """The "1,284 papers match 'machine learning'" line above search results."""
    st.html(
        f'<div class="result-count"><b>{total:,}</b> paper{"s" if total != 1 else ""} '
        f"match &ldquo;{html.escape(query)}&rdquo;</div>"
    )
