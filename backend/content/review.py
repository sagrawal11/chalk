"""Static control-room review page.

Generates one self-contained ``index.html`` per day that shows every rendered
card next to its copy-ready caption, plus the current record, so the operator
reviews the slate and posts to Instagram manually. No server or React build
needed (matches the "render assets, post manually" decision).
"""
from __future__ import annotations

import html
from pathlib import Path
from typing import Any, Dict, List, Optional

from content import brand_config as B


def _rgb(c) -> str:
    return f"rgb({c[0]},{c[1]},{c[2]})"


def _card_block(png_name: str, caption: str, idx: int) -> str:
    cap = html.escape(caption)
    return f"""
    <div class="card">
      <img src="{png_name}" alt="{png_name}"/>
      <div class="cap">
        <div class="fn">{png_name}</div>
        <pre id="cap{idx}">{cap}</pre>
        <button onclick="navigator.clipboard.writeText(document.getElementById('cap{idx}').textContent)">Copy caption</button>
      </div>
    </div>"""


def _record_html(record: Optional[Dict[str, Any]]) -> str:
    if not record:
        return ""
    wp = record.get("win_pct")
    wp = f"{wp * 100:.0f}%" if wp is not None else "-"
    return (f'<div class="record">Record <b>{record.get("record","0-0")}</b> · '
            f'{record.get("units",0):+.1f}u · win {wp} · streak {record.get("streak",0)} '
            f'· {record.get("n_picks",0)} picks</div>')


def build_review_page(out_dir: Path, game_date: str, record: Optional[Dict[str, Any]] = None) -> Path:
    out_dir = Path(out_dir)
    cards = sorted(p.name for p in out_dir.glob("*.png"))
    blocks = []
    for i, name in enumerate(cards):
        cap_path = out_dir / (Path(name).stem + ".txt")
        caption = cap_path.read_text() if cap_path.exists() else ""
        blocks.append(_card_block(name, caption, i))

    page = f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{B.BRAND}: Review {game_date}</title>
<style>
  body {{ background:{_rgb(B.BG)}; color:{_rgb(B.TEXT)}; font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif; margin:0; padding:24px; }}
  h1 {{ color:{_rgb(B.ACCENT)}; font-size:22px; margin:0 0 4px; }}
  .sub {{ color:{_rgb(B.MUTED)}; margin-bottom:16px; }}
  .record {{ background:{_rgb(B.PANEL)}; padding:12px 16px; border-radius:12px; display:inline-block; margin-bottom:20px; }}
  .grid {{ display:flex; flex-wrap:wrap; gap:20px; }}
  .card {{ background:{_rgb(B.PANEL)}; border-radius:14px; padding:14px; width:560px; display:flex; gap:14px; }}
  .card img {{ width:240px; height:auto; border-radius:8px; }}
  .cap {{ flex:1; display:flex; flex-direction:column; gap:8px; }}
  .fn {{ color:{_rgb(B.MUTED)}; font-size:12px; }}
  pre {{ white-space:pre-wrap; font-size:13px; background:{_rgb(B.BG)}; padding:10px; border-radius:8px; margin:0; flex:1; }}
  button {{ background:{_rgb(B.ACCENT)}; color:{_rgb(B.BG)}; border:0; border-radius:8px; padding:8px 12px; font-weight:700; cursor:pointer; }}
</style></head><body>
  <h1>{B.BRAND}: content review</h1>
  <div class="sub">{game_date} · {len(cards)} cards · review, then post to {B.HANDLE}</div>
  {_record_html(record)}
  <div class="grid">{''.join(blocks)}</div>
</body></html>"""

    p = out_dir / "index.html"
    p.write_text(page)
    return p
