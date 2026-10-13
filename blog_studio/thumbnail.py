"""Renders a diagram spec to an SVG thumbnail in the site's palette, matching the existing post thumbnails.

The spec places nodes on a 5 x 4 grid, so the model only decides structure and the layout stays tidy.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .config import DEFAULT_THEME

# Set per render from the blog's theme (see render); these are the defaults.
DEEP, NAVY, PAPER, PAPER_DIM, ACCENT, TAPE = (DEFAULT_THEME[k] for k in ("background", "box", "text", "box_light", "accent", "secondary"))
W, H = 800, 500
COLS, ROWS = 5, 4
X0, Y0, CW, CH = 30, 50, 148, 106  # grid origin and cell size
BW, BH = 124, 62                   # box size
FONT = "Geist, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif"
MONO = "ui-monospace, SFMono-Regular, Menlo, monospace"


class Node(BaseModel):
    id: str = Field(description="Short unique id, e.g. 'api'.")
    label: str = Field(description="One or two words, e.g. 'API node'.")
    sub: str | None = Field(default=None, description="Optional short monospace detail, e.g. 'stateless'.")
    kind: Literal["node", "hot", "store", "ghost", "paper"] = Field(
        description="node = component, hot = the component the post is about (use once or twice), store = database or cache, ghost = optional or background, paper = final output."
    )
    col: int = Field(description="Grid column, 0 to 4, left to right.")
    row: int = Field(description="Grid row, 0 to 3, top to bottom.")


class Edge(BaseModel):
    source: str
    target: str
    label: str | None = Field(default=None, description="Optional one or two words.")
    style: Literal["normal", "accent", "dashed"] = Field(description="accent = the main path, dashed = async or optional.")


class Group(BaseModel):
    label: str = Field(description="Short uppercase-able label, e.g. 'real-time plane'.")
    col: int
    row: int
    cols: int = Field(description="Columns spanned, at least 1.")
    rows: int = Field(description="Rows spanned, at least 1.")


class DiagramSpec(BaseModel):
    title: str = Field(description="One sentence describing the diagram, used as its accessible name.")
    nodes: list[Node]
    edges: list[Edge]
    groups: list[Group] = Field(default_factory=list)
    footnote: str | None = Field(default=None, description="Optional short monospace caption for the bottom-left corner.")

    @model_validator(mode="after")
    def _check(self) -> "DiagramSpec":
        ids = [n.id for n in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("node ids must be unique")
        cells = set()
        for n in self.nodes:
            n.col = min(max(n.col, 0), COLS - 1)
            n.row = min(max(n.row, 0), ROWS - 1)
            if (n.col, n.row) in cells:
                raise ValueError(f"two nodes share grid cell {n.col},{n.row}")
            cells.add((n.col, n.row))
        self.edges = [e for e in self.edges if e.source in ids and e.target in ids and e.source != e.target]
        for g in self.groups:
            g.col = min(max(g.col, 0), COLS - 1)
            g.row = min(max(g.row, 0), ROWS - 1)
            g.cols = min(max(g.cols, 1), COLS - g.col)
            g.rows = min(max(g.rows, 1), ROWS - g.row)
        return self


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _text(x: float, y: float, s: str, size: float, color: str, *, weight: int = 400, anchor: str = "middle", mono: bool = False) -> str:
    fam = MONO if mono else FONT
    return f'<text x="{x:.1f}" y="{y:.1f}" font-family="{fam}" font-size="{size}" font-weight="{weight}" fill="{color}" text-anchor="{anchor}">{_esc(s)}</text>'


def _center(n: Node) -> tuple[float, float]:
    return X0 + n.col * CW + CW / 2, Y0 + n.row * CH + CH / 2


def _clip(cx: float, cy: float, tx: float, ty: float, pad: float = 4) -> tuple[float, float]:
    """Where the line from a box centre towards (tx, ty) leaves the box."""
    dx, dy = tx - cx, ty - cy
    if dx == 0 and dy == 0:
        return cx, cy
    scale = min((BW / 2 + pad) / abs(dx) if dx else math.inf, (BH / 2 + pad) / abs(dy) if dy else math.inf)
    return cx + dx * scale, cy + dy * scale


def _box(n: Node) -> str:
    cx, cy = _center(n)
    x, y = cx - BW / 2, cy - BH / 2
    fill, stroke, tc = {
        "node": (NAVY, PAPER + "40", PAPER), "hot": (NAVY, ACCENT, PAPER), "store": (DEEP, TAPE + "aa", PAPER),
        "ghost": ("none", PAPER + "40", PAPER + "cc"), "paper": (PAPER_DIM, PAPER_DIM, DEEP),
    }[n.kind]
    parts = []
    if n.kind == "store":
        ry = 9
        parts.append(f'<path d="M{x} {y + ry} v{BH - 2 * ry} a{BW / 2} {ry} 0 0 0 {BW} 0 v-{BH - 2 * ry}" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>')
        parts.append(f'<ellipse cx="{cx}" cy="{y + ry}" rx="{BW / 2}" ry="{ry}" fill="{NAVY}" stroke="{stroke}" stroke-width="1.6"/>')
        cy += 5
    else:
        dash = ' stroke-dasharray="5 5"' if n.kind == "ghost" else ""
        width = 2 if n.kind == "hot" else 1.4
        parts.append(f'<rect x="{x}" y="{y}" width="{BW}" height="{BH}" rx="7" fill="{fill}" stroke="{stroke}" stroke-width="{width}"{dash}/>')
    label = n.label[:18]
    if n.sub:
        parts.append(_text(cx, cy - 4, label, 16, tc, weight=600))
        parts.append(_text(cx, cy + 15, n.sub[:20], 11.5, NAVY if n.kind == "paper" else TAPE, mono=True))
    else:
        parts.append(_text(cx, cy + 6, label, 16, tc, weight=600))
    return "".join(parts)


def _edge(e: Edge, by_id: dict[str, Node]) -> str:
    a, b = by_id[e.source], by_id[e.target]
    (ax, ay), (bx, by) = _center(a), _center(b)
    x1, y1 = _clip(ax, ay, bx, by)
    x2, y2 = _clip(bx, by, ax, ay, pad=6)
    color, marker = {"normal": (PAPER + "8c", "p"), "accent": (ACCENT, "a"), "dashed": (TAPE + "aa", "t")}[e.style]
    dash = ' stroke-dasharray="6 6"' if e.style == "dashed" else ""
    out = f'<path d="M{x1:.1f} {y1:.1f} L{x2:.1f} {y2:.1f}" fill="none" stroke="{color}" stroke-width="1.8"{dash} marker-end="url(#{marker})"/>'
    if e.label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        # Labels sit beside the line: above horizontal lines, to the right of vertical ones.
        horizontal = abs(x2 - x1) >= abs(y2 - y1)
        out += _text(mx, my - 7, e.label[:18], 11.5, TAPE, mono=True) if horizontal else _text(mx + 8, my + 4, e.label[:18], 11.5, TAPE, mono=True, anchor="start")
    return out


def _group(g: Group) -> str:
    x, y = X0 + g.col * CW + 6, Y0 + g.row * CH + 4
    w, h = g.cols * CW - 12, g.rows * CH - 8
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{PAPER}08" stroke="{PAPER}26" stroke-width="1.2" stroke-dasharray="4 6"/>'
        + _text(x + 12, y + 17, g.label.upper()[:28], 10.5, TAPE, weight=600, anchor="start", mono=True)
    )


def render(spec: DiagramSpec, theme: dict[str, str] | None = None) -> str:
    global DEEP, NAVY, PAPER, PAPER_DIM, ACCENT, TAPE
    t = {**DEFAULT_THEME, **(theme or {})}
    DEEP, NAVY, PAPER, PAPER_DIM, ACCENT, TAPE = (t[k] for k in ("background", "box", "text", "box_light", "accent", "secondary"))
    def marker(i: str, c: str) -> str:
        return f'<marker id="{i}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="{c}"/></marker>'

    by_id = {n.id: n for n in spec.nodes}
    head = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="{_esc(spec.title)}">'
        f"<title>{_esc(spec.title)}</title><defs>"
        f'<pattern id="g" width="32" height="32" patternUnits="userSpaceOnUse"><path d="M32 0H0V32" fill="none" stroke="{PAPER}" stroke-opacity="0.05"/></pattern>'
        f'<radialGradient id="glow" cx="0.82" cy="0.1" r="0.7"><stop offset="0" stop-color="{TAPE}" stop-opacity="0.16"/><stop offset="1" stop-color="{TAPE}" stop-opacity="0"/></radialGradient>'
        f'{marker("p", PAPER + "8c")}{marker("a", ACCENT)}{marker("t", TAPE)}</defs>'
        f'<rect width="{W}" height="{H}" fill="{DEEP}"/><rect width="{W}" height="{H}" fill="url(#g)"/><rect width="{W}" height="{H}" fill="url(#glow)"/>'
    )
    body = "".join(_group(g) for g in spec.groups) + "".join(_edge(e, by_id) for e in spec.edges) + "".join(_box(n) for n in spec.nodes)
    foot = _text(30, 482, spec.footnote[:60], 12.5, PAPER + "99", anchor="start", mono=True) if spec.footnote else ""
    return head + body + foot + "</svg>\n"
