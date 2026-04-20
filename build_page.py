from __future__ import annotations

from collections import OrderedDict
from html import escape
from pathlib import Path
import re
from urllib.parse import quote

import yaml


ROOT = Path(__file__).resolve().parent
RAW_PATH = ROOT / "raw.yaml"
OUTPUT_PATH = ROOT / "index.html"
TITLE = "Warp Core Cafe Character List"
SUBTITLE = "Jeff Carlisle painting reference"
IMGUR_URL = "https://imgur.com/t/warp_core_cafe"
PROJECT_URL = "https://github.com/users/hobeika/projects/1/views/1"
GRID_IMAGE_NAME = "wpc.jpg"
GRID_IMAGE_WIDTH = 1217
GRID_IMAGE_HEIGHT = 1800
REFERENCE_IMAGE_DIR = "references"
DETAIL_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
ARTIST_NAME = "Jeff Carlisle"
IDENTIFICATION_TOTAL = 286
IDENTIFICATION_DONE = 31
ARTIST_BIO = [
    (
        "A lifelong science-fiction and fantasy fan, Jeff Carlisle traces the start of "
        "his artistic path back to seeing the original Star Wars as a child. That grew "
        "into a steady diet of classic sci-fi television, novels, role-playing games, "
        "video games, and the kind of long-term visual obsession that eventually became "
        "his profession."
    ),
    (
        'His work draws inspiration from Jean "Moebius" Giraud, Geoff Darrow, William '
        "Stout, Richard Amsel, the Hildebrandt Brothers, Ralph McQuarrie, Ron Cobb, and "
        "Syd Mead. Over the last two decades he has contributed art and design work tied "
        "to Star Wars, Star Trek, Doctor Who, Indiana Jones, Alien, Spider-Man, X-Men, "
        "The Lord of the Rings, Dungeons & Dragons, Pathfinder, and many other projects "
        "across books, magazines, comics, games, posters, maps, and screen work."
    ),
    (
        "Jeff has said he is proud to add his small part to the dreams of others, to "
        "celebrate the artists who came before him, and to keep doing that work for a "
        "long time. Jeff and his wife Lisa live in Ohio."
    ),
    "Life is Good.",
]


def asset_href(value: str) -> str:
    if re.match(r"^[a-z]+://", value, re.IGNORECASE):
        return value
    return quote(value, safe="/:#?&=%+")


def normalize_ref_image(value: str) -> str:
    if not value:
        return ""
    if re.match(r"^[a-z]+://", value, re.IGNORECASE):
        return value
    if "/" in value or "\\" in value:
        return value
    return f"{REFERENCE_IMAGE_DIR}/{value}"


def load_catalog(path: Path) -> list[dict[str, object]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entities = data.get("entities", {})
    tiles_by_coord: OrderedDict[str, list[dict[str, object]]] = OrderedDict()

    def build_entry(
        entity_id: str, entity: dict[str, object], note: str = ""
    ) -> dict[str, object]:
        name = str(entity.get("name", entity_id)).strip()
        aliases = [
            str(alias).strip()
            for alias in entity.get("aliases", [])
            if str(alias).strip()
        ]
        ref_url = str(entity.get("ref_url") or "").strip()
        ref_image = normalize_ref_image(str(entity.get("ref_image") or "").strip())
        coords = [
            str(coord).strip()
            for coord in entity.get("coords", [])
            if str(coord).strip()
        ]
        search_terms = " ".join([name, *aliases, note]).strip()
        return {
            "entity_id": entity_id,
            "name": name,
            "aliases": aliases,
            "note": note,
            "ref_url": ref_url,
            "ref_image": ref_image,
            "coords": coords,
            "search_terms": search_terms,
        }

    for entity_id, entity in entities.items():
        if not isinstance(entity, dict):
            continue
        note = str(entity.get("note") or "").strip()
        coords = entity.get("coords", [])
        if isinstance(coords, str):
            coords = [coords]
        for coord in coords:
            coord_str = str(coord).strip()
            if not coord_str:
                continue
            tiles_by_coord.setdefault(coord_str, []).append(
                build_entry(str(entity_id), entity, note)
            )

    tiles = [
        {"coord": coord, "items": entries}
        for coord, entries in sorted(
            tiles_by_coord.items(),
            key=lambda item: split_coord(item[0]),
        )
        if entries
    ]
    return tiles


def group_tiles(
    tiles: list[dict[str, object]]
) -> OrderedDict[str, list[dict[str, object]]]:
    rows: OrderedDict[str, list[dict[str, object]]] = OrderedDict()
    for tile in tiles:
        coord = str(tile["coord"])
        row = re.match(r"^[A-Z]+", coord).group(0)
        rows.setdefault(row, []).append(tile)
    return rows


def split_coord(coord: str) -> tuple[str, int]:
    match = re.fullmatch(r"([A-Z]+)(\d+)", coord)
    if not match:
        raise ValueError(f"Invalid coordinate: {coord}")
    return match.group(1), int(match.group(2))


def discover_detail_images(
    rows: OrderedDict[str, list[dict[str, object]]],
) -> dict[str, list[dict[str, str]]]:
    row_order = {row: index for index, row in enumerate(rows.keys())}
    detail_map: dict[str, list[dict[str, str]]] = {}

    for path in sorted(ROOT.iterdir()):
        if (
            not path.is_file()
            or path.suffix.lower() not in DETAIL_IMAGE_SUFFIXES
        ):
            continue
        if path.name in {GRID_IMAGE_NAME, "grid_ref.jpg"}:
            continue

        match = re.match(r"^([A-Z]+)(\d+)([A-Z]+)(\d+)(.*)$", path.stem)
        if not match:
            continue

        start_row, start_column = match.group(1), int(match.group(2))
        end_row, end_column = match.group(3), int(match.group(4))
        suffix = match.group(5).strip()
        if start_row not in row_order or end_row not in row_order:
            continue

        first_row = min(row_order[start_row], row_order[end_row])
        last_row = max(row_order[start_row], row_order[end_row])
        first_column = min(start_column, end_column)
        last_column = max(start_column, end_column)
        label = f"{start_row}{start_column}-{end_row}{end_column}"
        if suffix:
            label = f"{label} {suffix}"

        for row, row_index in row_order.items():
            if not first_row <= row_index <= last_row:
                continue
            for column in range(first_column, last_column + 1):
                coord = f"{row}{column}"
                detail_map.setdefault(coord, []).append(
                    {"href": path.name, "label": label}
                )

    return detail_map


def render_reference_map(
    rows: OrderedDict[str, list[dict[str, object]]],
) -> str:
    row_labels = list(rows.keys())
    max_column = max(
        int(re.search(r"\d+", str(tile["coord"])).group(0))
        for row in rows.values()
        for tile in row
    )
    column_labels = "\n".join(
        f"            <span>{column}</span>"
        for column in range(1, max_column + 1)
    )
    row_axis = "\n".join(
        f"            <span>{escape(row)}</span>" for row in row_labels
    )
    buttons: list[str] = []

    for row_index, row in enumerate(row_labels, start=1):
        for tile in rows[row]:
            coord = str(tile["coord"])
            column = int(re.search(r"\d+", coord).group(0))
            items = [str(item["name"]) for item in tile["items"]]
            count = len(items)
            label = "entry" if count == 1 else "entries"
            tooltip = f"{coord} - {count} {label}"
            if items:
                tooltip = "\n".join(
                    [tooltip, *[f"• {item}" for item in items]]
                )
            buttons.append(
                f"""            <button class="map-tile" type="button" style="grid-row:{row_index};grid-column:{column};" data-coord="{escape(coord)}" data-tooltip="{escape(tooltip)}" aria-label="Show {escape(coord)}">
              <span>{escape(coord)}</span>
            </button>"""
            )

    return f"""      <section class="reference-card">
        <div class="reference-copy">
          <div>
            <h2>Grid Reference</h2>
            <p>Hover or tap a square to preview its coordinate, then click to jump to that tile in the list.</p>
          </div>
        </div>
        <div class="map-grid-shell" style="--map-columns:{max_column}; --map-rows:{len(row_labels)};">
          <div class="map-axis map-axis-x" aria-hidden="true">
{column_labels}
          </div>
          <div class="map-axis map-axis-y" aria-hidden="true">
{row_axis}
          </div>
          <div class="map-frame">
            <img src="{escape(asset_href(GRID_IMAGE_NAME))}" alt="Warp Core Cafe painting with coordinate grid">
            <div class="map-overlay">
{chr(10).join(buttons)}
            </div>
            <div class="map-tooltip" id="map-tooltip" hidden></div>
          </div>
          <div class="map-axis map-axis-y" aria-hidden="true">
{row_axis}
          </div>
          <div class="map-axis map-axis-x" aria-hidden="true">
{column_labels}
          </div>
        </div>
      </section>"""


def render_artist_note() -> str:
    paragraphs = "\n".join(
        f"            <p>{escape(paragraph)}</p>" for paragraph in ARTIST_BIO
    )

    return f"""      <section class="artist-card">
        <details class="artist-details">
          <summary>
            <span>About The Artist</span>
            <small>{escape(ARTIST_NAME)} background and context for Warp Core Cafe</small>
          </summary>
          <div class="artist-copy">
{paragraphs}
            <p class="artist-source">Based on the Jeff Carlisle Timed Release email from Pulse Gallery that accompanied the piece, lightly edited for readability.</p>
          </div>
        </details>
      </section>"""


def render_tile_entry(entry: dict[str, object]) -> str:
    entity_id = escape(str(entry.get("entity_id", "")).strip())
    name = escape(str(entry.get("name", "")))
    note = str(entry.get("note", "")).strip()
    ref_url = str(entry.get("ref_url", "")).strip()
    ref_image = str(entry.get("ref_image", "")).strip()
    coords = [
        str(coord).strip()
        for coord in entry.get("coords", [])
        if str(coord).strip()
    ]
    coords_text = ", ".join(coords)

    links: list[str] = []
    if ref_url:
        links.append(
            f'<a class="tile-entry-link" href="{escape(asset_href(ref_url))}" target="_blank" rel="noreferrer">Source page</a>'
        )
    if ref_image:
        links.append(
            f'<a class="tile-entry-link" href="{escape(asset_href(ref_image))}" target="_blank" rel="noreferrer">Reference image</a>'
        )

    links_html = ""
    if links:
        links_html = f"""
                    <div class="tile-entry-links">
{chr(10).join(f"                      {link}" for link in links)}
                    </div>"""

    coords_html = ""
    if coords:
        coords_html = f"""
                  <p class="tile-entry-coords">Seen in: <span>{escape(coords_text)}</span></p>"""

    note_html = ""
    if note:
        note_html = f"""
                  <p class="tile-entry-note">{escape(note)}</p>"""

    media_html = ""
    if ref_image:
        preview_href = asset_href(ref_url or ref_image)
        media_html = f"""
                  <a class="tile-entry-media" href="{escape(preview_href)}" target="_blank" rel="noreferrer">
                    <img src="{escape(asset_href(ref_image))}" alt="Reference for {name}">
                  </a>"""

    return f"""              <li class="tile-entry" data-entity-id="{entity_id}" data-entity-name="{name}">
                <button class="tile-entry-trigger" type="button">
                  <span class="tile-entry-name">{name}</span>
                </button>
                <div class="tile-entry-panel" hidden>{coords_html}{note_html}{links_html}{media_html}</div>
              </li>"""


def render_rows(
    rows: OrderedDict[str, list[dict[str, object]]],
) -> str:
    sections: list[str] = []
    max_column = max(
        int(re.search(r"\d+", str(tile["coord"])).group(0))
        for row in rows.values()
        for tile in row
    )
    total_rows = len(rows)
    tile_aspect_ratio = (GRID_IMAGE_WIDTH * total_rows) / (
        GRID_IMAGE_HEIGHT * max_column
    )
    detail_images = discover_detail_images(rows)

    for row_index, (row, tiles) in enumerate(rows.items(), start=1):
        cards = []
        for tile in tiles:
            coord_raw = str(tile["coord"])
            coord = escape(coord_raw)
            column = int(re.search(r"\d+", coord_raw).group(0))
            offset_x = -(column - 1) * 100
            offset_y = -(row_index - 1) * 100
            search_text = " ".join(
                str(item.get("search_terms", item.get("name", "")))
                for item in tile["items"]
            )
            items = "\n".join(
                render_tile_entry(item) for item in tile["items"]
            )
            count = len(tile["items"])
            label = "entry" if count == 1 else "entries"
            detail_links = detail_images.get(coord_raw, [])
            detail_actions = ""
            if detail_links:
                links = "\n".join(
                    f'                <a class="detail-link" href="{escape(asset_href(detail["href"]))}" target="_blank" rel="noreferrer">Open high-detail {escape(detail["label"])}</a>'
                    for detail in detail_links
                )
                detail_actions = f"""
              <div class="tile-detail-actions">
{links}
              </div>"""
            cards.append(
                f"""          <article class="tile-card" id="tile-{coord.lower()}" data-coord="{coord}" data-search="{escape(search_text)}" style="--tile-column:{column}; --tile-row:{row_index}; --tile-columns:{max_column}; --tile-rows:{total_rows}; --tile-aspect:{tile_aspect_ratio:.6f}; --tile-offset-x:{offset_x}%; --tile-offset-y:{offset_y}%;">
            <div class="tile-head">
              <h3>{coord}</h3>
              <span>{count} {label}</span>
            </div>
            <div class="tile-body">
              <div class="tile-copy">
                <ul>
{items}
                </ul>
              </div>
              <aside class="tile-preview" aria-hidden="true">
                <div class="tile-preview-frame">
                  <img src="{escape(asset_href(GRID_IMAGE_NAME))}" alt="">
                </div>
                <p>Zoomed view of {coord}</p>
{detail_actions}
              </aside>
            </div>
          </article>"""
            )

        sections.append(
            f"""      <section class="row-section" id="row-{row.lower()}">
        <div class="row-head">
          <h2>Row {escape(row)}</h2>
          <p>{len(tiles)} filled tiles</p>
        </div>
        <div class="tile-grid">
{chr(10).join(cards)}
        </div>
      </section>"""
        )

    return "\n".join(sections)


def build_html(tiles: list[dict[str, object]]) -> str:
    rows = group_tiles(tiles)
    total_tiles = len(tiles)
    total_items = sum(len(tile["items"]) for tile in tiles)
    identification_percent = (IDENTIFICATION_DONE / IDENTIFICATION_TOTAL) * 100
    max_column = max(
        int(re.search(r"\d+", str(tile["coord"])).group(0))
        for row in rows.values()
        for tile in row
    )
    total_rows = len(rows)
    row_order_js = ", ".join(
        f'"{row}": {index}' for index, row in enumerate(rows.keys(), start=1)
    )
    artist_note = render_artist_note()
    reference_map = render_reference_map(rows)
    row_sections = render_rows(rows)
    suggestions = sorted(
        {
            str(value).strip()
            for tile in tiles
            for item in tile["items"]
            for value in [item.get("name", ""), *item.get("aliases", [])]
            if str(value).strip()
        },
        key=str.casefold,
    )
    suggestion_options = "\n".join(
        f'            <option value="{escape(suggestion)}"></option>'
        for suggestion in suggestions
    )

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{escape(TITLE)}</title>
    <meta name="theme-color" content="#7d4b2e">
    <style>
      :root {{
        --bg: #f5efe5;
        --bg-soft: #fffaf2;
        --card: rgba(255, 250, 242, 0.94);
        --card-strong: #fffdf9;
        --text: #241812;
        --muted: #6f5a4c;
        --line: rgba(72, 45, 29, 0.14);
        --accent: #7d4b2e;
        --accent-soft: #edd8c3;
        --shadow: 0 18px 40px rgba(60, 34, 18, 0.08);
      }}

      * {{
        box-sizing: border-box;
      }}

      html {{
        scroll-behavior: smooth;
      }}

      body {{
        margin: 0;
        font-family: Georgia, "Times New Roman", serif;
        color: var(--text);
        background:
          radial-gradient(circle at top, rgba(255, 255, 255, 0.5), transparent 38%),
          linear-gradient(180deg, #efe3d3 0%, var(--bg) 24%, #ebdfcf 100%);
      }}

      a {{
        color: inherit;
      }}

      .page {{
        width: min(1100px, calc(100% - 1.25rem));
        margin: 0 auto;
        padding: 1rem 0 3rem;
      }}

      .hero {{
        padding: 1.25rem 0 0.75rem;
      }}

      .hero h1 {{
        margin: 0;
        font-size: clamp(2rem, 4vw, 3.2rem);
        line-height: 0.98;
      }}

      .hero p {{
        margin: 0.5rem 0 0;
        color: var(--muted);
        font-size: 1rem;
      }}

      .progress-card {{
        margin-top: 1rem;
        padding: 0.95rem 1rem;
        border-radius: 20px;
        border: 1px solid var(--line);
        background: rgba(255, 250, 242, 0.9);
        box-shadow: var(--shadow);
      }}

      .progress-card strong {{
        display: block;
        margin-bottom: 0.35rem;
        font-size: 0.98rem;
      }}

      .progress-card p {{
        margin: 0;
        color: var(--muted);
        line-height: 1.5;
      }}

      .progress-bar {{
        margin-top: 0.8rem;
        height: 0.85rem;
        border-radius: 999px;
        background: rgba(125, 75, 46, 0.12);
        overflow: hidden;
      }}

      .progress-bar span {{
        display: block;
        height: 100%;
        width: var(--progress);
        border-radius: inherit;
        background: linear-gradient(90deg, #9c6037 0%, #7d4b2e 100%);
      }}

      .progress-meta {{
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: baseline;
        margin-top: 0.55rem;
        font-variant-numeric: tabular-nums;
      }}

      .progress-meta span {{
        color: var(--muted);
        font-size: 0.88rem;
      }}

      .progress-link {{
        display: inline-flex;
        align-items: center;
        margin-top: 0.75rem;
        color: var(--accent);
        text-decoration: none;
        font-size: 0.9rem;
      }}

      .progress-link:hover,
      .progress-link:focus-visible {{
        text-decoration: underline;
        outline: none;
      }}

      .summary {{
        display: flex;
        flex-wrap: wrap;
        gap: 0.65rem;
        margin-top: 1rem;
      }}

      .summary span {{
        display: inline-flex;
        align-items: center;
        padding: 0.5rem 0.8rem;
        border-radius: 999px;
        background: var(--card);
        border: 1px solid var(--line);
        box-shadow: var(--shadow);
        font-size: 0.95rem;
      }}

      .artist-card {{
        margin: 0 0 1rem;
      }}

      .artist-details {{
        border: 1px solid var(--line);
        border-radius: 22px;
        background: rgba(255, 252, 247, 0.88);
        box-shadow: var(--shadow);
        overflow: hidden;
      }}

      .artist-details summary {{
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: baseline;
        padding: 0.95rem 1rem;
        cursor: pointer;
        list-style: none;
      }}

      .artist-details summary::-webkit-details-marker {{
        display: none;
      }}

      .artist-details summary span {{
        font-size: 1rem;
        font-weight: 700;
      }}

      .artist-details summary small {{
        color: var(--muted);
        font-size: 0.88rem;
        text-align: right;
      }}

      .artist-details[open] summary {{
        border-bottom: 1px solid var(--line);
        background: rgba(125, 75, 46, 0.05);
      }}

      .artist-copy {{
        padding: 0.95rem 1rem 1rem;
      }}

      .artist-copy p {{
        margin: 0 0 0.8rem;
        line-height: 1.55;
      }}

      .artist-copy p:last-child {{
        margin-bottom: 0;
      }}

      .artist-source {{
        color: var(--muted);
        font-size: 0.92rem;
      }}

      .controls {{
        position: sticky;
        top: 0;
        z-index: 10;
        margin: 1rem 0 1.2rem;
        padding: 0.85rem;
        border: 1px solid var(--line);
        border-radius: 20px;
        background: rgba(255, 248, 239, 0.92);
        box-shadow: var(--shadow);
        backdrop-filter: blur(14px);
      }}

      .search-row {{
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 0.75rem;
      }}

      .search-row input {{
        width: 100%;
        min-height: 3rem;
        padding: 0.8rem 1rem;
        border: 1px solid var(--line);
        border-radius: 14px;
        background: var(--card-strong);
        font: inherit;
        color: inherit;
      }}

      .search-row button {{
        min-height: 3rem;
        padding: 0.8rem 1rem;
        border: 0;
        border-radius: 14px;
        background: var(--accent);
        color: #fff9f3;
        font: inherit;
        cursor: pointer;
      }}

      .controls-meta {{
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: center;
        margin-top: 0.85rem;
      }}

      .controls-meta p {{
        margin: 0;
        color: var(--muted);
        font-size: 0.95rem;
      }}

      .reference-card {{
        margin-bottom: 1.2rem;
        padding: 1rem;
        border-radius: 24px;
        border: 1px solid var(--line);
        background: rgba(255, 253, 249, 0.84);
        box-shadow: var(--shadow);
      }}

      .reference-copy {{
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: flex-start;
        margin-bottom: 0.9rem;
      }}

      .reference-copy h2 {{
        margin: 0;
        font-size: 1.2rem;
      }}

      .reference-copy p {{
        margin: 0.35rem 0 0;
        color: var(--muted);
      }}

      .external-link {{
        display: inline-flex;
        align-items: center;
        padding: 0.65rem 0.9rem;
        border-radius: 999px;
        background: var(--accent);
        color: #fff9f3;
        text-decoration: none;
        white-space: nowrap;
      }}

      .reference-links {{
        display: flex;
        flex-wrap: wrap;
        gap: 0.65rem;
        justify-content: flex-end;
      }}

      .secondary-link {{
        background: var(--bg-soft);
        color: var(--text);
        border: 1px solid var(--line);
      }}

      .map-grid-shell {{
        display: grid;
        grid-template-columns: clamp(1.5rem, 3vw, 2.25rem) minmax(0, 1fr) clamp(1.5rem, 3vw, 2.25rem);
        grid-template-rows: auto minmax(0, 1fr) auto;
        gap: 0.45rem;
        align-items: stretch;
      }}

      .map-axis {{
        display: grid;
        gap: 0.2rem;
        color: var(--muted);
        font-size: clamp(0.72rem, 1.4vw, 0.88rem);
        font-variant-numeric: tabular-nums;
        user-select: none;
      }}

      .map-axis span {{
        display: flex;
        align-items: center;
        justify-content: center;
        min-width: 0;
        min-height: 0;
        padding: 0.2rem 0;
        border-radius: 999px;
        background: rgba(255, 250, 242, 0.8);
      }}

      .map-axis-y span {{
        padding: 0;
      }}

      .map-axis-x {{
        grid-column: 2;
        grid-template-columns: repeat(var(--map-columns), minmax(0, 1fr));
      }}

      .map-axis-y {{
        grid-row: 2;
        grid-template-rows: repeat(var(--map-rows), minmax(0, 1fr));
      }}

      .map-frame {{
        grid-column: 2;
        grid-row: 2;
        position: relative;
        border-radius: 18px;
        overflow: hidden;
        border: 1px solid var(--line);
        background: #d9cab7;
      }}

      .map-frame img {{
        display: block;
        width: 100%;
        height: auto;
      }}

      .map-overlay {{
        position: absolute;
        inset: 0;
        display: grid;
        grid-template-columns: repeat(var(--map-columns), 1fr);
        grid-template-rows: repeat(var(--map-rows), 1fr);
      }}

      .map-tile {{
        min-width: 0;
        min-height: 0;
        padding: 0;
        border: 1px solid rgba(80, 43, 20, 0.15);
        background: rgba(125, 75, 46, 0.03);
        color: transparent;
        cursor: pointer;
        transition: background 120ms ease, box-shadow 120ms ease;
      }}

      .map-tooltip {{
        position: absolute;
        top: 0;
        left: 0;
        z-index: 2;
        max-width: min(18rem, calc(100% - 1rem));
        max-height: calc(100% - 1rem);
        padding: 0.45rem 0.65rem;
        border-radius: 12px;
        background: rgba(36, 24, 18, 0.92);
        color: #fffaf2;
        font-size: 0.82rem;
        line-height: 1.35;
        box-shadow: 0 12px 24px rgba(36, 24, 18, 0.22);
        pointer-events: none;
        overflow: auto;
        white-space: pre-line;
      }}

      .map-tile span {{
        position: absolute;
        width: 1px;
        height: 1px;
        padding: 0;
        margin: -1px;
        overflow: hidden;
        clip: rect(0, 0, 0, 0);
        white-space: nowrap;
        border: 0;
      }}

      .map-tile:hover,
      .map-tile.match,
      .map-tile:focus-visible,
      .map-tile.active {{
        background: rgba(125, 75, 46, 0.22);
        outline: none;
      }}

      .map-tile.match {{
        box-shadow: inset 0 0 0 1px rgba(255, 248, 239, 0.72);
      }}

      .map-tile:focus-visible,
      .map-tile.active {{
        box-shadow: inset 0 0 0 2px rgba(255, 248, 239, 0.92);
      }}

      .results {{
        display: grid;
        gap: 1.2rem;
      }}

      .row-section {{
        padding: 1rem;
        border-radius: 24px;
        border: 1px solid var(--line);
        background: rgba(255, 253, 249, 0.84);
        box-shadow: var(--shadow);
      }}

      .row-head {{
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: baseline;
        margin-bottom: 0.9rem;
      }}

      .row-head h2 {{
        margin: 0;
        font-size: 1.2rem;
      }}

      .row-head p {{
        margin: 0;
        color: var(--muted);
        font-size: 0.95rem;
      }}

      .tile-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(min(100%, 15rem), 1fr));
        gap: 0.85rem;
      }}

      .tile-card {{
        padding: 0.9rem;
        border-radius: 18px;
        border: 1px solid var(--line);
        background: var(--card);
        scroll-margin-top: 7rem;
      }}

      .tile-body {{
        min-width: 0;
      }}

      .tile-copy {{
        min-width: 0;
      }}

      .tile-head {{
        display: flex;
        justify-content: space-between;
        gap: 0.75rem;
        align-items: baseline;
        margin-bottom: 0.65rem;
      }}

      .tile-head h3 {{
        margin: 0;
        font-size: 1.05rem;
      }}

      .tile-head span {{
        color: var(--muted);
        font-size: 0.82rem;
        white-space: nowrap;
      }}

      .tile-card ul {{
        margin: 0;
        padding-left: 1.05rem;
        display: grid;
        gap: 0.4rem;
      }}

      .tile-card li {{
        line-height: 1.45;
      }}

      .tile-entry {{
        list-style: none;
      }}

      .tile-entry-trigger {{
        display: flex;
        align-items: center;
        width: 100%;
        padding: 0.35rem 0;
        border: 0;
        background: transparent;
        color: inherit;
        font: inherit;
        text-align: left;
        cursor: pointer;
      }}

      .tile-entry-trigger:hover,
      .tile-entry-trigger:focus-visible {{
        color: var(--accent);
        outline: none;
      }}

      .tile-entry-name {{
        min-width: 0;
      }}

      .tile-entry-panel {{
        display: grid;
        gap: 0.55rem;
        padding: 0;
      }}

      .tile-entry-coords,
      .tile-entry-note {{
        margin: 0;
        color: var(--muted);
        font-size: 0.88rem;
      }}

      .tile-entry-coords span {{
        color: var(--text);
        font-variant-numeric: tabular-nums;
      }}

      .tile-entry-links {{
        display: flex;
        flex-wrap: wrap;
        gap: 0.4rem;
      }}

      .tile-entry-link {{
        display: inline-flex;
        align-items: center;
        padding: 0.2rem 0.55rem;
        border-radius: 999px;
        border: 1px solid rgba(125, 75, 46, 0.2);
        background: rgba(125, 75, 46, 0.08);
        text-decoration: none;
        font-size: 0.76rem;
        white-space: nowrap;
      }}

      .tile-entry-media {{
        display: none;
        overflow: hidden;
        border-radius: 14px;
        border: 1px solid var(--line);
        background: rgba(255, 252, 247, 0.9);
      }}

      .tile-entry-media img {{
        display: block;
        width: 100%;
        height: auto;
      }}

      .tile-preview {{
        display: none;
      }}

      .tile-preview-frame {{
        aspect-ratio: var(--tile-aspect);
        position: relative;
        overflow: hidden;
        border-radius: 16px;
        border: 1px solid var(--line);
        background-color: #d9cab7;
        box-shadow: inset 0 0 0 1px rgba(255, 248, 239, 0.45);
      }}

      .tile-preview-frame img {{
        display: block;
        position: absolute;
        left: var(--tile-offset-x);
        top: var(--tile-offset-y);
        width: calc(var(--tile-columns) * 100%);
        height: calc(var(--tile-rows) * 100%);
      }}

      #entity-focus-preview img {{
        width: var(--focus-image-width, calc(var(--tile-columns) * 100%));
        height: var(--focus-image-height, calc(var(--tile-rows) * 100%));
      }}

      .tile-preview p {{
        margin: 0;
        color: var(--muted);
        font-size: 0.82rem;
        text-align: center;
      }}

      .tile-detail-actions {{
        display: grid;
        gap: 0.45rem;
      }}

      .detail-link {{
        display: inline-flex;
        justify-content: center;
        align-items: center;
        min-height: 2.5rem;
        padding: 0.6rem 0.8rem;
        border-radius: 12px;
        background: rgba(125, 75, 46, 0.1);
        border: 1px solid rgba(125, 75, 46, 0.22);
        text-decoration: none;
        font-size: 0.88rem;
        line-height: 1.3;
        text-align: center;
      }}

      .tile-card.targeted {{
        border-color: rgba(125, 75, 46, 0.6);
        box-shadow: 0 0 0 3px rgba(125, 75, 46, 0.14);
      }}

      .tile-card.targeted .tile-body {{
        display: grid;
        grid-template-columns: minmax(0, 1fr) minmax(9rem, 11rem);
        gap: 1rem;
        align-items: start;
      }}

      .tile-card.targeted .tile-preview {{
        display: grid;
        gap: 0.45rem;
      }}

      .empty-state {{
        padding: 1rem 1.1rem;
        border-radius: 18px;
        border: 1px dashed var(--line);
        background: rgba(255, 253, 249, 0.9);
      }}

      .entity-focus-card {{
        padding: 1rem;
        border-radius: 24px;
        border: 1px solid var(--line);
        background: rgba(255, 253, 249, 0.92);
        box-shadow: var(--shadow);
      }}

      .entity-focus-head {{
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: center;
        margin-bottom: 1rem;
      }}

      .entity-focus-back {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-height: 2.65rem;
        padding: 0.7rem 1rem;
        border: 1px solid var(--line);
        border-radius: 999px;
        background: var(--bg-soft);
        color: var(--text);
        font: inherit;
        cursor: pointer;
      }}

      .entity-focus-meta {{
        margin: 0;
        color: var(--muted);
        font-size: 0.92rem;
        text-align: right;
      }}

      .entity-focus-layout {{
        display: grid;
        grid-template-columns: minmax(0, 1.1fr) minmax(16rem, 20rem);
        gap: 1.1rem;
        align-items: start;
      }}

      .entity-focus-copy {{
        min-width: 0;
      }}

      .entity-focus-copy h2 {{
        margin: 0 0 0.8rem;
        font-size: clamp(1.35rem, 2.6vw, 1.9rem);
        line-height: 1.08;
      }}

      .entity-focus-body {{
        display: grid;
        gap: 0.7rem;
      }}

      .entity-focus-body .tile-entry-coords,
      .entity-focus-body .tile-entry-note {{
        font-size: 0.95rem;
      }}

      .entity-focus-body .tile-entry-links {{
        gap: 0.55rem;
      }}

      .entity-focus-body .tile-entry-link {{
        font-size: 0.84rem;
        padding: 0.38rem 0.72rem;
      }}

      .entity-focus-body .tile-entry-media {{
        display: block;
      }}

      .entity-focus-body .tile-entry-media img {{
        width: min(100%, 28rem);
      }}

      .entity-focus-preview {{
        display: grid;
        gap: 0.55rem;
      }}

      .entity-focus-preview-label {{
        margin: 0;
        color: var(--muted);
        font-size: 0.88rem;
        text-align: center;
      }}

      body.entity-focus-mode .row-section,
      body.entity-focus-mode #empty-state {{
        display: none !important;
      }}

      [hidden] {{
        display: none !important;
      }}

      @media (max-width: 640px) {{
        .page {{
          width: min(100% - 0.9rem, 1100px);
        }}

        .controls {{
          padding: 0.75rem;
          border-radius: 18px;
        }}

        .search-row {{
          grid-template-columns: 1fr;
        }}

        .reference-copy,
        .controls-meta,
        .artist-details summary {{
          flex-direction: column;
          align-items: stretch;
        }}

        .reference-links {{
          justify-content: flex-start;
        }}

        .map-grid-shell {{
          grid-template-columns: clamp(1.2rem, 4vw, 1.6rem) minmax(0, 1fr) clamp(1.2rem, 4vw, 1.6rem);
          gap: 0.3rem;
        }}

        .map-axis {{
          gap: 0.1rem;
          font-size: 0.7rem;
        }}

        .row-head,
        .tile-head {{
          flex-direction: column;
          align-items: flex-start;
        }}

        .tile-entry-links {{
          justify-content: flex-start;
        }}

        .tile-card.targeted .tile-body {{
          grid-template-columns: 1fr;
        }}

        .tile-card.targeted .tile-preview {{
          max-width: 14rem;
        }}

        .entity-focus-head,
        .entity-focus-layout {{
          grid-template-columns: 1fr;
          flex-direction: column;
          align-items: stretch;
        }}

        .entity-focus-meta {{
          text-align: left;
        }}
      }}
    </style>
  </head>
  <body>
    <div class="page">
      <header class="hero">
        <h1>{escape(TITLE)}</h1>
        <p>{escape(SUBTITLE)}. Search by tile, character, ship, show, or franchise.</p>
        <section class="progress-card" aria-label="Work in progress status">
          <strong>Work in progress</strong>
          <p>This catalogue is still being identified tile by tile. There are {IDENTIFICATION_TOTAL} references to document, and {IDENTIFICATION_DONE} have been properly identified so far.</p>
          <div class="progress-bar" aria-hidden="true" style="--progress:{identification_percent:.2f}%;">
            <span></span>
          </div>
          <div class="progress-meta">
            <span>{IDENTIFICATION_DONE} / {IDENTIFICATION_TOTAL} identified</span>
            <span>{identification_percent:.1f}% complete</span>
          </div>
          <a class="progress-link" href="{escape(PROJECT_URL)}" target="_blank" rel="noreferrer">Open the identification project board</a>
        </section>
      </header>

      <section class="controls">
        <div class="search-row">
          <input id="search" type="search" placeholder="Search for Yoda, Borg, A7, Babylon 5..." autocomplete="off" spellcheck="false" list="search-suggestions">
          <datalist id="search-suggestions">
{suggestion_options}
          </datalist>
          <button id="clear-search" type="button">Clear</button>
        </div>
        <div class="controls-meta">
          <p id="result-count" aria-live="polite">{total_tiles} tiles visible</p>
        </div>
      </section>

{reference_map}

      <main class="results">
        <section class="entity-focus-card" id="entity-focus" hidden>
          <div class="entity-focus-head">
            <button class="entity-focus-back" id="entity-focus-back" type="button">Back</button>
            <p class="entity-focus-meta" id="entity-focus-meta"></p>
          </div>
          <div class="entity-focus-layout">
            <div class="entity-focus-copy">
              <h2 id="entity-focus-title"></h2>
              <div class="entity-focus-body" id="entity-focus-body"></div>
            </div>
            <aside class="entity-focus-preview">
              <div class="tile-preview-frame" id="entity-focus-preview">
                <img src="{escape(asset_href(GRID_IMAGE_NAME))}" alt="">
              </div>
              <p class="entity-focus-preview-label" id="entity-focus-preview-label"></p>
              <div class="tile-detail-actions" id="entity-focus-actions" hidden></div>
            </aside>
          </div>
        </section>
        <div class="empty-state" id="empty-state" hidden>
          No matches found. Try a tile like <strong>B6</strong> or a title like <strong>Farscape</strong>.
        </div>
{row_sections}
      </main>

      <section class="summary">
        <span>{total_tiles} filled tiles</span>
        <span>{total_items} named entries</span>
        <span>Only non-empty coordinates are shown</span>
      </section>

{artist_note}
    </div>

    <script>
      const searchInput = document.querySelector("#search");
      const clearButton = document.querySelector("#clear-search");
      const resultCount = document.querySelector("#result-count");
      const emptyState = document.querySelector("#empty-state");
      const mapFrame = document.querySelector(".map-frame");
      const mapTooltip = document.querySelector("#map-tooltip");
      const cards = Array.from(document.querySelectorAll(".tile-card"));
      const sections = Array.from(document.querySelectorAll(".row-section"));
      const mapTiles = Array.from(document.querySelectorAll(".map-tile"));
      const entityFocus = document.querySelector("#entity-focus");
      const entityFocusBack = document.querySelector("#entity-focus-back");
      const entityFocusMeta = document.querySelector("#entity-focus-meta");
      const entityFocusTitle = document.querySelector("#entity-focus-title");
      const entityFocusBody = document.querySelector("#entity-focus-body");
      const entityFocusPreview = document.querySelector("#entity-focus-preview");
      const entityFocusPreviewLabel = document.querySelector("#entity-focus-preview-label");
      const entityFocusActions = document.querySelector("#entity-focus-actions");
      const totalColumns = {max_column};
      const totalRows = {total_rows};
      const rowOrder = {{{row_order_js}}};
      const prefersDirectManipulation = window.matchMedia("(pointer: coarse)").matches;
      const matchingCoords = new Set();
      let activeCoord = "";
      let entityFocusState = null;

      function updateQueryParam(value = searchInput.value.trim()) {{
        const url = new URL(window.location.href);
        if (value) {{
          url.searchParams.set("q", value);
        }} else {{
          url.searchParams.delete("q");
        }}
        url.searchParams.delete("entity");
        url.searchParams.delete("coord");
        window.history.replaceState({{}}, "", `${{url.pathname}}${{url.search}}${{url.hash}}`);
      }}

      function updateEntityParam(entityId, coord = "") {{
        const url = new URL(window.location.href);
        url.searchParams.delete("q");
        if (entityId) {{
          url.searchParams.set("entity", entityId);
        }} else {{
          url.searchParams.delete("entity");
        }}
        if (coord) {{
          url.searchParams.set("coord", coord);
        }} else {{
          url.searchParams.delete("coord");
        }}
        window.history.replaceState({{}}, "", `${{url.pathname}}${{url.search}}${{url.hash}}`);
      }}

      function applyFilter(updateUrl = true, preferredCoord = "") {{
        const query = searchInput.value.trim().toLowerCase();
        const normalizedCoord = searchInput.value.trim().toUpperCase();
        let visibleCards = 0;
        matchingCoords.clear();
        const visibleCoords = new Set();

        for (const card of cards) {{
          const matchesText = !query || (card.dataset.search || "").toLowerCase().includes(query);
          const matchesCoord = normalizedCoord && card.dataset.coord === normalizedCoord;
          const matches = matchesText || matchesCoord;
          card.hidden = !matches;
          if (matches) {{
            visibleCards += 1;
            visibleCoords.add(card.dataset.coord);
            if (query) {{
              matchingCoords.add(card.dataset.coord);
            }}
          }}
        }}

        for (const section of sections) {{
          section.hidden = !section.querySelector(".tile-card:not([hidden])");
        }}

        resultCount.textContent = query
          ? `${{visibleCards}} matching tiles`
          : `${{cards.length}} tiles visible`;
        emptyState.hidden = visibleCards !== 0;

        const exactMatch = mapTiles.some((tile) => tile.dataset.coord === normalizedCoord);
        markMatchingCoords();
        const nextActiveCoord = exactMatch
          ? normalizedCoord
          : (preferredCoord && visibleCoords.has(preferredCoord))
            ? preferredCoord
            : (activeCoord && visibleCoords.has(activeCoord))
              ? activeCoord
              : "";
        markActiveCoord(nextActiveCoord);
        if (updateUrl) {{
          updateQueryParam();
        }}
      }}

      function markMatchingCoords() {{
        for (const tile of mapTiles) {{
          tile.classList.toggle("match", matchingCoords.has(tile.dataset.coord));
        }}
      }}

      function markActiveCoord(coord) {{
        activeCoord = coord || "";
        for (const tile of mapTiles) {{
          tile.classList.toggle("active", tile.dataset.coord === activeCoord);
        }}
        for (const card of cards) {{
          card.classList.toggle("targeted", card.dataset.coord === activeCoord);
        }}
      }}

      function splitCoord(coord) {{
        const match = (coord || "").match(/^([A-Z]+)(\d+)$/);
        if (!match) {{
          return null;
        }}
        return {{
          row: match[1],
          column: Number(match[2]),
        }};
      }}

      function syncFocusPreview(card, coords) {{
        if (!entityFocusPreview) {{
          return null;
        }}

        const parts = coords
          .map(splitCoord)
          .filter((value) => value && rowOrder[value.row]);

        if (!parts.length) {{
          const styles = window.getComputedStyle(card);
          for (const name of ["--tile-aspect", "--tile-offset-x", "--tile-offset-y", "--tile-columns", "--tile-rows"]) {{
            entityFocusPreview.style.setProperty(name, styles.getPropertyValue(name));
          }}
          entityFocusPreview.style.removeProperty("--focus-image-width");
          entityFocusPreview.style.removeProperty("--focus-image-height");
          return null;
        }}

        const rowIndexes = parts.map((value) => rowOrder[value.row]);
        const columns = parts.map((value) => value.column);
        const minRow = Math.min(...rowIndexes);
        const maxRow = Math.max(...rowIndexes);
        const minColumn = Math.min(...columns);
        const maxColumn = Math.max(...columns);
        const spanRows = Math.max(1, maxRow - minRow + 1);
        const spanColumns = Math.max(1, maxColumn - minColumn + 1);
        const focusAspect = (({GRID_IMAGE_WIDTH} * totalRows * spanColumns) / ({GRID_IMAGE_HEIGHT} * totalColumns * spanRows)).toFixed(6);
        const imageWidth = ((totalColumns / spanColumns) * 100).toFixed(6);
        const imageHeight = ((totalRows / spanRows) * 100).toFixed(6);
        const offsetX = (-((minColumn - 1) / spanColumns) * 100).toFixed(6);
        const offsetY = (-((minRow - 1) / spanRows) * 100).toFixed(6);

        entityFocusPreview.style.setProperty("--tile-aspect", focusAspect);
        entityFocusPreview.style.setProperty("--tile-offset-x", `${{offsetX}}%`);
        entityFocusPreview.style.setProperty("--tile-offset-y", `${{offsetY}}%`);
        entityFocusPreview.style.setProperty("--focus-image-width", `${{imageWidth}}%`);
        entityFocusPreview.style.setProperty("--focus-image-height", `${{imageHeight}}%`);
        return {{
          startCoord: `${{Object.keys(rowOrder).find((row) => rowOrder[row] === minRow)}}${{minColumn}}`,
          endCoord: `${{Object.keys(rowOrder).find((row) => rowOrder[row] === maxRow)}}${{maxColumn}}`,
          isRegion: spanRows > 1 || spanColumns > 1,
        }};
      }}

      function leaveEntityFocus(restorePrevious = true) {{
        if (!document.body.classList.contains("entity-focus-mode")) {{
          return;
        }}

        document.body.classList.remove("entity-focus-mode");
        if (entityFocus) {{
          entityFocus.hidden = true;
        }}

        const previousState = entityFocusState;
        entityFocusState = null;

        if (!restorePrevious || !previousState) {{
          return;
        }}

        searchInput.value = previousState.query;
        applyFilter(true, previousState.activeCoord);
        if (typeof previousState.scrollY === "number") {{
          window.scrollTo({{ top: previousState.scrollY, behavior: prefersDirectManipulation ? "auto" : "smooth" }});
        }}
      }}

      function enterEntityFocus(entry, options = {{}}) {{
        const preserveState = options.preserveState !== false;
        const updateUrl = options.updateUrl !== false;
        const card = entry.closest(".tile-card");
        const panel = entry.querySelector(".tile-entry-panel");
        if (!card || !panel || !entityFocus) {{
          return;
        }}

        if (preserveState && !entityFocusState) {{
          entityFocusState = {{
            query: searchInput.value,
            activeCoord,
            scrollY: window.scrollY,
          }};
        }}

        const preferredCoord = card.dataset.coord || "";
        const entityId = entry.dataset.entityId || "";
        const entityName = entry.dataset.entityName || "";
        const coords = Array.from(new Set(
          Array.from(panel.querySelectorAll(".tile-entry-coords span"))
            .flatMap((node) => (node.textContent || "").split(","))
            .map((value) => value.trim())
            .filter(Boolean)
        ));

        entityFocusTitle.textContent = entityName;
        entityFocusBody.innerHTML = panel.innerHTML;
        const previewBounds = syncFocusPreview(card, coords);
        entityFocusPreviewLabel.textContent = preferredCoord
          ? previewBounds && previewBounds.startCoord
            ? `${{previewBounds.isRegion ? "Region" : "Tile"}} ${{previewBounds.startCoord}}${{previewBounds.endCoord !== previewBounds.startCoord ? ` to ${{previewBounds.endCoord}}` : ""}} · selected tile ${{preferredCoord}}`
            : `Selected tile ${{preferredCoord}}`
          : "";

        const detailActions = card.querySelector(".tile-detail-actions");
        entityFocusActions.innerHTML = detailActions ? detailActions.innerHTML : "";
        entityFocusActions.hidden = !detailActions;

        entityFocusMeta.textContent = coords.length
          ? `${{coords.length}} tile${{coords.length === 1 ? "" : "s"}} highlighted on the map`
          : "";

        searchInput.value = entityName;
        applyFilter(false, preferredCoord);
        if (updateUrl) {{
          updateEntityParam(entityId, preferredCoord);
        }}
        entityFocus.hidden = false;
        document.body.classList.add("entity-focus-mode");
      }}

      function openEntityById(entityId, coord = "", options = {{}}) {{
        if (!entityId) {{
          return false;
        }}

        const matches = Array.from(document.querySelectorAll(`.tile-entry[data-entity-id="${{CSS.escape(entityId)}}"]`));
        if (!matches.length) {{
          return false;
        }}

        const selectedEntry = coord
          ? matches.find((entry) => entry.closest(".tile-card")?.dataset.coord === coord) || matches[0]
          : matches[0];

        enterEntityFocus(selectedEntry, options);
        return true;
      }}

      function moveTooltip(x, y) {{
        if (!mapFrame || !mapTooltip || mapTooltip.hidden) {{
          return;
        }}

        const padding = 8;
        const frameRect = mapFrame.getBoundingClientRect();
        const tooltipRect = mapTooltip.getBoundingClientRect();
        const maxX = Math.max(padding, frameRect.width - tooltipRect.width - padding);
        const maxY = Math.max(padding, frameRect.height - tooltipRect.height - padding);
        const clampedX = Math.min(Math.max(padding, x), maxX);
        const clampedY = Math.min(Math.max(padding, y), maxY);
        mapTooltip.style.transform = `translate(${{clampedX}}px, ${{clampedY}}px)`;
      }}

      function showTooltip(tile, event) {{
        if (!mapFrame || !mapTooltip) {{
          return;
        }}

        mapTooltip.textContent = tile.dataset.tooltip || tile.dataset.coord;
        mapTooltip.hidden = false;

        if (event) {{
          moveTooltip(event.clientX - mapFrame.getBoundingClientRect().left + 12, event.clientY - mapFrame.getBoundingClientRect().top + 12);
          return;
        }}

        const tileRect = tile.getBoundingClientRect();
        const frameRect = mapFrame.getBoundingClientRect();
        moveTooltip(
          tileRect.left - frameRect.left + (tileRect.width / 2),
          tileRect.top - frameRect.top - mapTooltip.getBoundingClientRect().height - 10
        );
      }}

      function hideTooltip() {{
        if (!mapTooltip) {{
          return;
        }}

        mapTooltip.hidden = true;
        mapTooltip.style.transform = "";
      }}

      for (const tile of mapTiles) {{
        tile.addEventListener("click", () => {{
          leaveEntityFocus(false);
          const coord = tile.dataset.coord;
          searchInput.value = coord;
          applyFilter();
          const card = document.querySelector(`#tile-${{coord.toLowerCase()}}`);
          if (card && !prefersDirectManipulation) {{
            card.scrollIntoView({{ behavior: "smooth", block: "start" }});
          }}
        }});
        tile.addEventListener("mouseenter", (event) => {{
          showTooltip(tile, event);
        }});
        tile.addEventListener("mousemove", (event) => {{
          showTooltip(tile, event);
        }});
        tile.addEventListener("mouseleave", hideTooltip);
        tile.addEventListener("focus", () => {{
          showTooltip(tile);
        }});
        tile.addEventListener("blur", hideTooltip);
      }}

      for (const trigger of document.querySelectorAll(".tile-entry-trigger")) {{
        trigger.addEventListener("click", () => {{
          const entry = trigger.closest(".tile-entry");
          if (!entry) {{
            return;
          }}
          enterEntityFocus(entry);
        }});
      }}

      searchInput.addEventListener("input", () => {{
        leaveEntityFocus(false);
        applyFilter();
      }});
      clearButton.addEventListener("click", () => {{
        leaveEntityFocus(false);
        searchInput.value = "";
        applyFilter();
        markActiveCoord("");
        searchInput.focus();
      }});

      entityFocusBack.addEventListener("click", () => {{
        leaveEntityFocus(true);
      }});

      const initialUrl = new URL(window.location.href);
      const initialEntity = initialUrl.searchParams.get("entity");
      const initialCoord = initialUrl.searchParams.get("coord") || "";
      const initialQuery = initialUrl.searchParams.get("q");
      if (initialEntity) {{
        if (!openEntityById(initialEntity, initialCoord, {{ preserveState: false, updateUrl: false }})) {{
          searchInput.value = "";
          applyFilter(false);
        }}
      }} else if (initialQuery) {{
        searchInput.value = initialQuery;
        applyFilter(false);
      }}

      window.addEventListener("popstate", () => {{
        const url = new URL(window.location.href);
        const entityId = url.searchParams.get("entity");
        const coord = url.searchParams.get("coord") || "";
        const query = url.searchParams.get("q") || "";
        leaveEntityFocus(false);
        if (entityId) {{
          if (!openEntityById(entityId, coord, {{ preserveState: false, updateUrl: false }})) {{
            searchInput.value = "";
            applyFilter(false);
          }}
          return;
        }}
        searchInput.value = query;
        applyFilter(false);
      }});
    </script>
  </body>
</html>
"""


def main() -> None:
    tiles = load_catalog(RAW_PATH)
    OUTPUT_PATH.write_text(build_html(tiles), encoding="utf-8")


if __name__ == "__main__":
    main()
