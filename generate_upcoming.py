#!/usr/bin/env python3
"""
Generate upcoming.html for Run Together Radcliffe website.
Fetches the next 4 Thursdays from the Google Sheet and produces
a fast static HTML page. Commits and pushes to GitHub Pages.

Usage:
    python3 generate_upcoming.py
    python3 generate_upcoming.py --dry-run   # print HTML, don't commit
"""

import csv
import io
import os
import re
import sys
import urllib.request
from datetime import date, datetime, timedelta

SHEET_ID = "1ncT1NCbSnFsAokyFBkMWBVsk7yrJTiUfG0iBRxyUCTw"
SHEET_NAME = "Schedule"
SITE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(SITE_DIR, "upcoming.html")

# ── SVG icons ──────────────────────────────────────────────────────────────────
CHEVRON_RIGHT = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>'
EXTERNAL_LINK = '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>'
STRAVA_ICON = '<svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg"><path d="M15.387 17.944l-2.089-4.116h-3.065L15.387 24l5.15-10.172h-3.066m-7.008-5.599l2.836 5.598h4.172L10.463 0l-7 13.828h4.169"/></svg>'
PIN_ICON = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>'
BACK_ICON = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg>'


def fetch_sheet():
    url = (
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}"
        f"/export?format=csv&sheet={SHEET_NAME}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=20)
    return resp.read().decode("utf-8")


def parse_date(s):
    """Parse '2026-04-17 00:00:00' → date object."""
    s = s.strip()
    if not s:
        return None
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def terrain_badge(terrain, distance):
    """Return badge class and label text."""
    t = (terrain or "").strip().lower()
    try:
        d = int(float(distance)) if distance else 0
    except (ValueError, TypeError):
        d = 0
    label = f"{terrain.title()} {d}k" if d else terrain.title()
    cls = {"trail": "badge-trail", "road": "badge-road", "mixed": "badge-mixed"}.get(t, "badge-road")
    return cls, label


def parse_notes(notes_raw):
    """
    Returns dict with keys:
      meeting  – meeting location string (default 'Radcliffe market')
      on_tour  – bool
      special  – extra note text or ''
    """
    result = {"meeting": "Radcliffe market", "on_tour": False, "special": ""}
    if not notes_raw:
        return result
    parts = [p.strip() for p in notes_raw.split("|")]
    leftovers = []
    for part in parts:
        if part.lower().startswith("meeting:"):
            result["meeting"] = part[8:].strip()
        elif part.lower() == "rtr on tour":
            result["on_tour"] = True
        else:
            leftovers.append(part)
    result["special"] = " | ".join(leftovers)
    return result


def route_html(name, terrain, distance, strava_url, rtr_url):
    badge_cls, badge_label = terrain_badge(terrain, distance)
    links = []
    if strava_url and strava_url.startswith("http"):
        links.append(
            f'<a class="btn-strava" href="{strava_url}" target="_blank" rel="noopener">'
            f'{STRAVA_ICON} Strava {EXTERNAL_LINK}</a>'
        )
    if rtr_url and rtr_url.startswith("http"):
        links.append(
            f'<a class="btn-map" href="{rtr_url}">'
            f'View map {CHEVRON_RIGHT}</a>'
        )
    links_html = "".join(links)
    return (
        f'<div class="route-box">\n'
        f'    <span class="terrain-badge {badge_cls}">{badge_label}</span>\n'
        f'    <div class="route-name">{name}</div>\n'
        f'    <div class="route-links">{links_html}</div>\n'
        f'</div>'
    )


def week_card_html(run_date, notes_info, r1_html, r2_html, tour_map_url="", r2_faded=False):
    day_str = run_date.strftime("Thursday %-d %B")
    on_tour = notes_info["on_tour"]
    card_class = "week-card on-tour" if on_tour else "week-card"
    badge = '<span class="on-tour-badge">On tour</span>' if on_tour else ""
    special = (
        f'<div class="special-note">{notes_info["special"]}</div>'
        if notes_info["special"] else ""
    )
    r2_class = ' class="route-box faded"' if r2_faded else ""

    # Build meeting location line — add directions link for On Tour weeks
    directions_html = ""
    if on_tour and tour_map_url and tour_map_url.startswith("http"):
        directions_html = (
            f' <a class="btn-map" href="{tour_map_url}" target="_blank" rel="noopener"'
            f' style="margin-left:.35rem;">Meeting point {EXTERNAL_LINK}</a>'
        )

    return f"""<div class="{card_class}">
        <div class="week-header">
            <div>
                <div class="week-date">{day_str}</div>
                <div class="week-time">7:00pm &ndash; 8:00pm</div>
            </div>
            {badge}
        </div>
        {special}
        <div class="meeting-location">{PIN_ICON} {notes_info["meeting"]}{directions_html}</div>
        <div class="routes-pair">
            {r1_html}
            {r2_html}
        </div>
    </div>"""


def generate_html(runs, generated_on):
    cards = "\n".join(runs)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Upcoming Runs &mdash; Run Together Radcliffe</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
    <style>
        *{{margin:0;padding:0;box-sizing:border-box;}}
        body{{background:#0a0a0a;color:#fff;font-family:'Inter',-apple-system,BlinkMacSystemFont,sans-serif;line-height:1.7;font-weight:300;padding:2rem;min-height:100vh;}}
        .container{{max-width:720px;margin:0 auto;padding:2rem 0;}}
        .back-link{{color:#555;font-size:.9rem;text-decoration:none;display:inline-flex;align-items:center;gap:.35rem;margin-bottom:1.5rem;transition:color .2s;}}
        .back-link:hover{{color:#f5a623;}}
        h1{{font-size:1.8rem;font-weight:500;letter-spacing:-.02em;margin-bottom:.4rem;}}
        .tagline{{color:#888;font-size:.95rem;margin-bottom:2.5rem;}}
        a{{color:#f5a623;text-decoration:none;transition:color .2s;}}
        a:hover{{color:#ffc966;}}

        .week-card{{background:#111;border:1px solid #1a1a1a;border-left:3px solid #f5a623;border-radius:0 12px 12px 0;padding:1.25rem 1.5rem;margin-bottom:1.25rem;}}
        .week-card.on-tour{{border-left-color:#ffc966;background:linear-gradient(135deg,#1a1510 0%,#111 100%);}}
        .week-header{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:.75rem;}}
        .week-date{{font-size:1.15rem;font-weight:500;}}
        .week-time{{color:#555;font-size:.85rem;margin-top:.1rem;}}
        .on-tour-badge{{background:#1a1510;border:1px solid #f5a623;color:#f5a623;font-size:.72rem;font-weight:500;padding:.2rem .6rem;border-radius:20px;white-space:nowrap;flex-shrink:0;margin-left:.75rem;text-transform:uppercase;letter-spacing:.05em;}}
        .special-note{{color:#f5a623;font-size:.875rem;margin-bottom:.6rem;font-style:italic;}}
        .meeting-location{{display:flex;align-items:center;gap:.4rem;color:#888;font-size:.875rem;margin-bottom:1rem;flex-wrap:wrap;}}
        .meeting-location svg{{flex-shrink:0;color:#555;}}

        .routes-pair{{display:grid;grid-template-columns:1fr 1fr;gap:.75rem;}}
        .route-box{{background:#0d0d0d;border:1px solid #222;border-radius:8px;padding:.875rem 1rem;display:flex;flex-direction:column;gap:.4rem;}}
        .route-box.faded{{opacity:.25;}}
        .terrain-badge{{font-size:.68rem;font-weight:600;text-transform:uppercase;letter-spacing:.07em;padding:.15rem .5rem;border-radius:8px;align-self:flex-start;}}
        .badge-trail{{background:#0d1a0d;color:#7cb87c;border:1px solid #1a3a1a;}}
        .badge-road{{background:#0d1221;color:#6b9fd4;border:1px solid #1a2a44;}}
        .badge-mixed{{background:#1a1208;color:#d4a84b;border:1px solid #3a2a0a;}}
        .route-name{{font-size:.92rem;color:#fff;line-height:1.4;flex:1;}}

        .route-links{{display:flex;gap:.5rem;margin-top:.35rem;flex-wrap:wrap;}}
        .btn-strava,.btn-map{{display:inline-flex;align-items:center;gap:.3rem;font-size:.75rem;padding:.25rem .6rem;border-radius:5px;border:1px solid;transition:all .2s;white-space:nowrap;}}
        .btn-strava{{color:#fc4c02;border-color:#3a1a0a;background:#1a0d05;}}
        .btn-strava:hover{{background:#2a1208;border-color:#fc4c02;color:#fc4c02;}}
        .btn-map{{color:#f5a623;border-color:#2a2a2a;background:transparent;}}
        .btn-map:hover{{border-color:#f5a623;background:#1a1510;color:#f5a623;}}

        .book-tip{{background:#0d1a0d;border:1px solid #1a3a1a;border-radius:8px;padding:.875rem 1.25rem;color:#7cb87c;font-size:.875rem;margin-top:.25rem;}}
        .book-tip a{{color:#7cb87c;text-decoration:underline;}}
        footer{{text-align:center;padding-top:2rem;margin-top:3rem;border-top:1px solid #1a1a1a;color:#555;font-size:.85rem;}}
        .generated{{color:#333;font-size:.75rem;text-align:center;margin-top:.5rem;}}
        @media(max-width:520px){{
            .routes-pair{{grid-template-columns:1fr;}}
            body{{padding:1rem;}}
        }}
    </style>
</head>
<body>
<!-- Generated {generated_on} from Google Sheet -->
<div class="container">
    <header>
        <a href="index.html" class="back-link">{BACK_ICON} Run Together Radcliffe</a>
        <h1>Upcoming Runs</h1>
        <p class="tagline">Every Thursday &middot; 7pm &middot; Free &middot; All welcome</p>
    </header>

    {cards}

    <div class="book-tip">
        &#128155; Book your place via the
        <a href="https://apps.apple.com/gb/app/runtogether-runner/id1447488812" target="_blank" rel="noopener">RunTogether app</a>
        &mdash; or <a href="https://play.google.com/store/apps/details?id=com.sportlabs.android.runner" target="_blank" rel="noopener">Google Play</a>
    </div>

    <footer>
        <p>Run Together Radcliffe &mdash; Part of the
        <a href="https://runtogether.co.uk" target="_blank" rel="noopener">England Athletics Run Together</a> programme</p>
    </footer>
    <p class="generated">Updated {generated_on}</p>
</div>
</body>
</html>"""


def main():
    dry_run = "--dry-run" in sys.argv

    print("Fetching schedule from Google Sheet...", flush=True)
    raw = fetch_sheet()
    reader = csv.reader(io.StringIO(raw))
    headers = next(reader)
    rows = list(reader)

    today = date.today()
    # Next Thursday on or after today
    days_until_thu = (3 - today.weekday()) % 7
    if days_until_thu == 0 and today.weekday() == 3:
        days_until_thu = 0
    first_thu = today + timedelta(days=days_until_thu)

    # Build set of the next 4 Thursdays we want
    target_dates = {first_thu + timedelta(weeks=i) for i in range(4)}
    found = {}  # date → row

    for row in rows:
        d = parse_date(row[0] if row else "")
        if d and d in target_dates:
            found[d] = row

    generated_on = today.strftime("%-d %b %Y")
    run_cards = []

    for thu in sorted(target_dates):
        if thu not in found:
            continue
        row = found[thu]
        notes_info = parse_notes(row[22] if len(row) > 22 else "")

        r1_name     = row[2]  if len(row) > 2  else ""
        r1_terrain  = row[4]  if len(row) > 4  else ""
        r1_distance = row[5]  if len(row) > 5  else ""
        r1_strava   = row[7]  if len(row) > 7  else ""
        r1_rtr      = row[34] if len(row) > 34 else ""

        r2_name     = row[12] if len(row) > 12 else ""
        r2_terrain  = row[14] if len(row) > 14 else ""
        r2_distance = row[15] if len(row) > 15 else ""
        r2_strava   = row[17] if len(row) > 17 else ""
        r2_rtr      = row[35] if len(row) > 35 else ""

        # Col AH (index 33) — Google Maps link for On Tour meeting point
        tour_map_url = row[33] if len(row) > 33 else ""

        # Skip if no run this week
        if r1_name.strip().lower() in ("no run", ""):
            continue

        r1_html = route_html(r1_name, r1_terrain, r1_distance, r1_strava, r1_rtr)
        r2_html = route_html(r2_name, r2_terrain, r2_distance, r2_strava, r2_rtr)

        run_cards.append(week_card_html(thu, notes_info, r1_html, r2_html, tour_map_url=tour_map_url))

    if not run_cards:
        print("WARNING: No upcoming Thursdays found in sheet — keeping existing file.")
        return

    html = generate_html(run_cards, generated_on)

    if dry_run:
        print(html)
        return

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Written: {OUTPUT_FILE} ({len(html):,} bytes)")

    # Push via GitHub API — bypasses git lock file issues on FUSE mounts.
    # (git uses atomic rename() for lock files, which macOS FUSE mounts don't support.)
    from github_api_push import push_files
    commit_msg = f"Update upcoming runs — {generated_on}"
    push_files(commit_msg, ["upcoming.html"])


if __name__ == "__main__":
    main()
