"""Render argument graphs as HTML or plain-text trees.

The HTML report is self-contained: the tokens, the layout and the rail drawing
are all embedded, so the file opens with no network and can be committed or
emailed without breaking. The rail is drawn in plain JavaScript from measured
row positions rather than by a library or a simulation, so the same input gives
the same picture every time.
"""

from __future__ import annotations

import html as _html
import json
from pathlib import Path

from argumentminer.fallacy import FallacyMatch
from argumentminer.graph import ArgumentGraph, ArgumentNode, RelationType
from argumentminer.segmenter import SegmentType


def render_text_tree(graph: ArgumentGraph) -> str:
    """Print the argument graph as an indented text tree."""
    lines = []
    visited = set()

    def _walk(node_id: str, indent: int = 0):
        if node_id in visited:
            return
        visited.add(node_id)
        node = graph.get_node(node_id)
        if node is None:
            return
        prefix = "  " * indent
        label  = f"[{node.segment.type.upper()}]"
        lines.append(f"{prefix}{label} {node.segment.text[:80]}")
        for child in graph.children_of(node_id):
            edge = next((e for e in graph.edges
                         if e.source_id == child.id and e.target_id == node_id), None)
            rel  = f" ({edge.relation})" if edge else ""
            lines.append(f"{prefix}  |{rel}")
            _walk(child.id, indent + 2)

    for root in graph.roots():
        _walk(root.id)
    return "\n".join(lines)


# Lane positions in the rail, left to right, so the direction of reasoning
# reads across the page: premise into claim into conclusion. Background units
# sit outside that flow, at the far left.
_LANES = {
    "background": 12,
    "premise":    38,
    "claim":      64,
    "conclusion": 90,
}
_RAIL_WIDTH = 102

_ROLE_ORDER = ("claim", "premise", "conclusion", "background")

_OUT_VERB = {
    RelationType.SUPPORT: "supports",
    RelationType.ATTACK:  "attacks",
    RelationType.NEUTRAL: "links to",
}
_IN_VERB = {
    RelationType.SUPPORT: "supported by",
    RelationType.ATTACK:  "attacked by",
    RelationType.NEUTRAL: "linked from",
}


def _role(node: ArgumentNode) -> str:
    """The node's unit type as a plain string, whatever enum flavour it holds."""
    return str(getattr(node.segment.type, "value", node.segment.type))


def _esc(text: str) -> str:
    return _html.escape(str(text), quote=True)


def _pct(value: float) -> str:
    return f"{value:.0%}"


def _mark_matches(text: str, matches: list[FallacyMatch]) -> str:
    """Escape a unit's text, underlining the phrases the detectors matched.

    Marking the span in place is the honest presentation: it shows exactly how
    much of the sentence the pattern saw.
    """
    spans: list[list[int]] = []
    lowered = text.lower()
    for match in matches:
        phrase = match.matched_text.strip()
        if not phrase:
            continue
        start = lowered.find(phrase.lower())
        if start == -1:
            continue
        spans.append([start, start + len(phrase)])
    if not spans:
        return _esc(text)

    # Two patterns can match overlapping spans; merge them so no span is
    # nested inside another.
    spans.sort()
    merged = [spans[0]]
    for start, end in spans[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])

    out, cursor = [], 0
    for start, end in merged:
        out.append(_esc(text[cursor:start]))
        out.append(f'<span class="matched">{_esc(text[start:end])}</span>')
        cursor = end
    out.append(_esc(text[cursor:]))
    return "".join(out)


def _relation_phrases(graph: ArgumentGraph, node: ArgumentNode,
                      number: dict[str, int]) -> list[str]:
    """Describe a unit's relations in words, so the rail is never the only copy."""
    grouped: dict[str, list[int]] = {}
    for edge in graph.edges:
        if edge.source_id == node.id and edge.target_id in number:
            verb = _OUT_VERB.get(edge.relation, "links to")
            grouped.setdefault(verb, []).append(number[edge.target_id])
        elif edge.target_id == node.id and edge.source_id in number:
            verb = _IN_VERB.get(edge.relation, "linked from")
            grouped.setdefault(verb, []).append(number[edge.source_id])

    phrases = []
    for verb, targets in grouped.items():
        targets = sorted(set(targets))
        noun = "unit" if len(targets) == 1 else "units"
        listed = ", ".join(str(t) for t in targets)
        phrases.append(f"{verb} {noun} {listed}")
    return phrases


def _tick(value: float) -> str:
    """A value on a shared 0 to 1 scale, drawn as a tick rather than a bar."""
    x = 3 + max(0.0, min(1.0, value)) * 44
    return (
        '<svg class="tick" viewBox="0 0 50 14" width="50" height="14" '
        'aria-hidden="true" focusable="false">'
        '<line class="tick-axis" x1="3" y1="10.5" x2="47" y2="10.5"></line>'
        f'<line class="tick-mark" x1="{x:.1f}" y1="2.5" x2="{x:.1f}" y2="13"></line>'
        "</svg>"
    )


def _balance(support: int, attack: int) -> str:
    """A diverging mark from a centre line: attack left, support right."""
    scale = max(support, attack, 1)
    half = 104.0
    stub = 3.0
    left = max(stub, attack / scale * half)
    right = max(stub, support / scale * half)
    return (
        '<svg class="balance" viewBox="0 0 230 26" width="230" height="26" '
        'aria-hidden="true" focusable="false">'
        f'<rect class="bar-attack" x="{115 - left:.1f}" y="7" '
        f'width="{left:.1f}" height="12"></rect>'
        f'<rect class="bar-support" x="115" y="7" '
        f'width="{right:.1f}" height="12"></rect>'
        '<line class="balance-axis" x1="115" y1="2" x2="115" y2="24"></line>'
        "</svg>"
    )


def _figure(value: int, label: str) -> str:
    return (
        '<div class="fig-item">'
        f'<span class="fig">{value}</span>'
        f'<span class="label">{_esc(label)}</span>'
        "</div>"
    )


def _legend_glyph(kind: str) -> str:
    """The small mark that sits beside a legend sentence."""
    if kind == "lanes":
        dots = "".join(
            f'<circle class="dot dot-{role}" cx="{_LANES[role]}" cy="8" r="4"></circle>'
            for role in ("background", "premise", "claim", "conclusion")
        )
        return (
            f'<svg class="glyph" viewBox="0 0 {_RAIL_WIDTH} 16" width="{_RAIL_WIDTH}" '
            'height="16" aria-hidden="true" focusable="false">'
            f'<line class="lane-guide" x1="6" y1="8" x2="{_RAIL_WIDTH - 6}" y2="8">'
            f"</line>{dots}</svg>"
        )
    if kind == "support":
        return (
            f'<svg class="glyph" viewBox="0 0 {_RAIL_WIDTH} 16" width="{_RAIL_WIDTH}" '
            'height="16" aria-hidden="true" focusable="false">'
            '<path class="rel rel-support" d="M 8 8 H 84"></path>'
            '<polygon class="rel-head rel-support" points="84,4.4 84,11.6 92,8"></polygon>'
            "</svg>"
        )
    if kind == "attack":
        return (
            f'<svg class="glyph" viewBox="0 0 {_RAIL_WIDTH} 16" width="{_RAIL_WIDTH}" '
            'height="16" aria-hidden="true" focusable="false">'
            '<path class="rel rel-attack dashed" d="M 8 8 H 88"></path>'
            '<line class="rel rel-attack" x1="88" y1="3" x2="88" y2="13"></line>'
            "</svg>"
        )
    if kind == "flagged":
        return (
            f'<svg class="glyph" viewBox="0 0 {_RAIL_WIDTH} 16" width="{_RAIL_WIDTH}" '
            'height="16" aria-hidden="true" focusable="false">'
            f'<circle class="dot dot-premise" cx="{_RAIL_WIDTH // 2}" cy="8" r="4"></circle>'
            f'<circle class="dot-flag" cx="{_RAIL_WIDTH // 2}" cy="8" r="7.2"></circle>'
            "</svg>"
        )
    if kind == "role-rule":
        return '<span class="glyph glyph-rule role-tag role-claim">claim</span>'
    if kind == "matched":
        return '<span class="glyph glyph-text"><span class="matched">phrase</span></span>'
    if kind == "tick":
        return f'<span class="glyph">{_tick(0.65)}</span>'
    return '<span class="glyph"></span>'


def _legend(has_units: bool, has_attack: bool) -> str:
    items = [
        ("lanes",
         "Lane position: the unit's role. Left to right the lanes are "
         "background, premise, claim, conclusion, so reasoning reads across "
         "the page while the text reads down it."),
        ("support",
         "Solid line into an arrowhead: a support relation, drawn from the "
         "supporting unit to the unit it supports."),
        ("role-rule",
         "Rule at a unit's leading edge: its role, repeated as a word beside "
         "the unit number."),
        ("matched",
         "Dotted underline inside a unit's text: the exact phrase a fallacy "
         "detector matched."),
        ("flagged",
         "Ring around a lane dot: at least one detector matched in that unit."),
        ("tick",
         "Tick in the left gutter of the pattern list: that detector's stated "
         "confidence on a scale from 0 to 1."),
    ]
    if has_attack:
        # Only named when the graph actually holds one, since the relation
        # builder in graph.py emits support and nothing else.
        items.insert(2, (
            "attack",
            "Dashed line into a crossbar: an attack relation. The line style "
            "and the end mark both differ from support, so the two never rely "
            "on colour to be told apart, and each is named in words on the "
            "unit as well.",
        ))
    if not has_units:
        items = [i for i in items if i[0] in ("matched", "tick")]
    rows = "".join(
        f'<li>{_legend_glyph(kind)}<span class="data">{text}</span></li>'
        for kind, text in items
    )
    return ('<p class="subhead label">What the marks mean</p>'
            f'<ul class="legend">{rows}</ul>')


def _units_section(graph: ArgumentGraph, number: dict[str, int],
                   fallacies: dict[str, list[FallacyMatch]] | None) -> str:
    if not graph.nodes:
        return (
            '<p class="prose">No unit survived segmentation. The text is split at '
            "sentence punctuation and any fragment of ten characters or fewer is "
            "dropped, so a passage of very short lines can leave nothing to lay "
            "out.</p>"
        )

    rows = []
    for node in graph.nodes:
        role = _role(node)
        num = number[node.id]
        matches = (fallacies or {}).get(node.id, [])
        # The classification confidence is a constant per role, so it belongs in
        # the method note once rather than on every row inviting comparison.
        meta = [role]
        meta += _relation_phrases(graph, node, number)
        if len(meta) == 1:
            meta.append("no relation inferred")

        flags = ""
        if matches:
            flags = '<ul class="flags">' + "".join(
                f'<li><span class="flag-name">{_esc(m.name)}</span> pattern matched '
                f'<span class="phrase">{_esc(m.matched_text.strip())}</span>, '
                f"stated confidence {_pct(m.confidence)}</li>"
                for m in matches
            ) + "</ul>"

        rows.append(
            f'<div class="unit u-{role}" id="unit-{num}">'
            f'<div class="u-num label">{num}</div>'
            '<div class="u-rail" aria-hidden="true"></div>'
            '<div class="u-body">'
            f'<p class="u-text">{_mark_matches(node.segment.text, matches)}</p>'
            f'<p class="u-meta label">{_esc("; ".join(meta))}</p>'
            f"{flags}"
            "</div></div>"
        )

    relation_count = len(graph.edges)
    if relation_count:
        note = (
            "Units are in the order they appear in the source text. The rail on "
            "the left places each one in its role's lane and draws the relations "
            "between them."
        )
    else:
        note = (
            "Units are in the order they appear in the source text, placed in "
            "their role's lane. No relation was inferred: a premise or a "
            "conclusion is only linked when a claim precedes it, and no unit "
            "matched the claim markers here."
        )

    return (
        f'<p class="prose caption">{note}</p>'
        '<div class="units-body" id="units-body">'
        f'<svg id="rail" width="{_RAIL_WIDTH}" height="0" '
        f'viewBox="0 0 {_RAIL_WIDTH} 0" aria-hidden="true" focusable="false"></svg>'
        + "".join(rows)
        + "</div>"
    )


def _fallacy_section(graph: ArgumentGraph, number: dict[str, int],
                     fallacies: dict[str, list[FallacyMatch]] | None) -> str:
    if fallacies is None:
        return (
            '<p class="prose">Fallacy detection was not run for this report, so '
            "nothing here says whether the passage contains any. That is not the "
            "same as a clean result.</p>"
        )

    listed = []
    for node in graph.nodes:
        for match in fallacies.get(node.id, []):
            listed.append((number[node.id], node, match))

    lead = (
        '<p class="prose">Each detector is one marker phrase pattern. A match '
        "means the phrase occurred, not that the argument commits the fallacy: "
        "quotation, reported speech and ordinary usage all match the same "
        "patterns, so expect false positives and read each row as somewhere to "
        "look. The confidence is a constant written into the detector, identical "
        "for every match it ever makes, so it ranks the detectors against each "
        "other and measures nothing about this passage.</p>"
    )

    if not listed:
        return lead + (
            '<p class="prose">Nothing matched. Eight patterns ran over each unit '
            "separately and none of them fired.</p>"
        )

    rows = []
    for num, node, match in listed:
        rows.append(
            '<div class="frow">'
            f'<div class="f-gutter">{_tick(match.confidence)}</div>'
            '<div class="f-body">'
            f'<p class="f-head"><span class="f-name">{_esc(match.name)}</span> '
            f'<span class="label">stated confidence {_pct(match.confidence)}</span></p>'
            f'<p class="data">Matched <span class="phrase">'
            f'{_esc(match.matched_text.strip())}</span> in '
            f'<a href="#unit-{num}">unit {num}</a>, classified '
            f"{_esc(_role(node))}.</p>"
            f'<p class="data f-desc">{_esc(match.description)}</p>'
            "</div></div>"
        )

    axis = (
        '<p class="caption label">Gutter tick: the detector\'s stated confidence, '
        "left edge 0, right edge 1.</p>"
    )
    return lead + axis + '<div class="frows">' + "".join(rows) + "</div>"


def _method_section(graph: ArgumentGraph,
                    fallacies: dict[str, list[FallacyMatch]] | None) -> str:
    detection = (
        "Detectors ran over each unit on its own, at most one match per detector "
        "per unit, so a phrase straddling two units is not seen."
        if fallacies is not None else
        "Fallacy detection was skipped for this report."
    )
    return (
        '<p class="subhead label">How this report was produced</p>'
        '<ul class="method prose">'
        "<li>Text is split at sentence punctuation. Fragments of ten characters "
        "or fewer are dropped, so the units here need not cover the whole "
        "source.</li>"
        "<li>A unit takes the role of the first marker family that matches, "
        "tried in the order conclusion, premise, claim, and falls back to "
        "background. Each role carries a fixed confidence written into the "
        "segmenter, 0.85 for conclusion, 0.80 for premise, 0.75 for claim and "
        "0.50 for background, identical for every unit of that role. It is a "
        "property of the rule that fired, not a measurement of this sentence, "
        "so it is not repeated on the units.</li>"
        "<li>A premise is attached as support to the most recent preceding "
        "claim, and a claim is attached as support to a conclusion that follows "
        "it. Nothing else creates a relation, so a passage with no claim has no "
        "relations at all. Support is the only kind the graph builder produces: "
        "attack is part of the data model, but no rule emits one.</li>"
        f"<li>{detection}</li>"
        "<li>The layout is computed from the order of the units, not by a "
        "simulation, so the same input draws the same picture every time. With "
        "JavaScript off the rail is empty and every relation is still written "
        "out in words on its unit.</li>"
        "</ul>"
    )


_DARK_TOKENS = """
    --ground:    #14171A;
    --lift:      #1C2024;
    --sink:      #0F1215;
    --ink:       #E4E8E6;
    --ink-mid:   #A6AEAB;
    --ink-soft:  #7B8582;
    --rule:      #2E343A;
    --rule-firm: #454D53;
    --mark:      #6FB3CE;
    --mark-soft: #3C6478;
    --confirm:   #6FBE93;
    --challenge: #E08472;
    --extend:    #D9B45C;
    --quiet:     #6E7773;
"""

_CSS = """
:root {
    --ground:    #EDEFEA;
    --lift:      #F7F8F5;
    --sink:      #E3E6DF;
    --ink:       #191D1C;
    --ink-mid:   #4E5754;
    --ink-soft:  #7C8683;
    --rule:      #CFD4CC;
    --rule-firm: #A8B0AC;
    --mark:      #1D4E63;
    --mark-soft: #7FA3B2;
    --confirm:   #2F6B4F;
    --challenge: #A33B2A;
    --extend:    #8A6A1F;
    --quiet:     #8C9491;
    --measure:   68ch;
    --sans: ui-sans-serif, "Segoe UI Variable Display", "Segoe UI", Inter,
            system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif;
    --mono: ui-monospace, "Cascadia Code", "SF Mono", "Consolas",
            "Liberation Mono", monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {__DARK__}
}
:root[data-theme="dark"] {__DARK__}

* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--ground);
  color: var(--ink);
  font: 400 15px/1.6 var(--sans);
}
.page { max-width: 960px; margin: 0 auto; padding: 32px 16px 48px; }
h1, h2, p, ul, dl { margin: 0; }
ul { padding: 0; list-style: none; }
.prose { max-width: var(--measure); }
.data { font-size: 13.5px; line-height: 1.45; }
.label { font-size: 12px; line-height: 1.3; font-weight: 500; color: var(--ink-soft); }
.fig {
  font-size: 22px; line-height: 1; font-weight: 550;
  font-variant-numeric: tabular-nums;
}
.caption { color: var(--ink-mid); margin-top: 8px; }

/* header */
.masthead {
  display: flex; gap: 16px; align-items: flex-start;
  justify-content: space-between; flex-wrap: wrap;
}
h1 { font-size: 30px; line-height: 1.15; letter-spacing: -0.02em; font-weight: 600; }
.source { color: var(--ink-mid); margin-top: 8px; max-width: var(--measure); }
.figures {
  display: flex; flex-wrap: wrap; gap: 32px;
  margin-top: 24px; padding-top: 16px; border-top: 1px solid var(--rule);
}
.fig-item { display: flex; flex-direction: column; gap: 4px; }
.roles { margin-top: 16px; color: var(--ink-mid); display: flex; flex-wrap: wrap; gap: 16px; }
.role-tag { padding-left: 8px; border-left: 3px solid var(--quiet); }
.role-claim      { border-left-color: var(--mark); }
.role-premise    { border-left-color: var(--confirm); }
.role-conclusion { border-left-color: var(--extend); }
.role-background { border-left-color: var(--quiet); }
.balance-block { margin-top: 24px; }
.balance { display: block; max-width: 100%; height: auto; }
.bar-attack   { fill: var(--challenge); }
.bar-support  { fill: var(--confirm); }
.balance-axis { stroke: var(--rule-firm); stroke-width: 1; }

/* sections */
section { margin-top: 32px; }
section p + p { margin-top: 12px; }
h2 {
  font-size: 17px; line-height: 1.3; font-weight: 600;
  padding-bottom: 8px; border-bottom: 2px solid var(--rule-firm);
}

/* the argument */
.units-body { position: relative; margin-top: 16px; }
#rail { position: absolute; top: 0; left: 0; }
.lane-guide { stroke: var(--rule); stroke-width: 1; }
.dot-claim      { fill: var(--mark); }
.dot-premise    { fill: var(--confirm); }
.dot-conclusion { fill: var(--extend); }
.dot-background { fill: var(--quiet); }
.dot-flag { fill: none; stroke: var(--challenge); stroke-width: 1.4; }
.rel { fill: none; stroke-width: 1.4; }
.rel-support { stroke: var(--confirm); }
.rel-attack  { stroke: var(--challenge); }
.rel.dashed  { stroke-dasharray: 4 3; }
.rel-head.rel-support { fill: var(--confirm); stroke: none; }

.unit {
  display: flex; align-items: flex-start;
  border-top: 1px solid var(--rule);
  border-left: 3px solid var(--quiet);
  padding: 12px 0;
}
.unit:last-child { border-bottom: 1px solid var(--rule); }
.unit:target { background: var(--lift); }
.unit { scroll-margin-top: 16px; }
.u-claim      { border-left-color: var(--mark); }
.u-premise    { border-left-color: var(--confirm); }
.u-conclusion { border-left-color: var(--extend); }
.u-background { border-left-color: var(--quiet); }
.u-num {
  flex: 0 0 56px; padding: 0 8px; text-align: right;
  font-variant-numeric: tabular-nums;
}
.u-rail { flex: 0 0 __RAIL_W__px; }
.u-body { flex: 1 1 auto; min-width: 0; }
.u-text { max-width: var(--measure); }
.u-meta { margin-top: 4px; }
.matched {
  text-decoration: underline dotted var(--challenge);
  text-underline-offset: 3px;
}
.flags { margin-top: 8px; }
.flags li {
  font-size: 13.5px; line-height: 1.45; color: var(--ink-mid);
  border-left: 2px solid var(--challenge); padding: 2px 0 2px 8px;
  max-width: var(--measure);
}
.flag-name, .f-name { color: var(--ink); font-weight: 500; }
.phrase { color: var(--ink); }
.phrase::before { content: "\\201C"; }
.phrase::after  { content: "\\201D"; }

/* pattern matches */
.frows { margin-top: 16px; }
.frow {
  display: flex; align-items: flex-start; gap: 0;
  border-top: 1px solid var(--rule); padding: 12px 0;
}
.frow:last-child { border-bottom: 1px solid var(--rule); }
.f-gutter { flex: 0 0 56px; padding-top: 2px; }
.f-body { flex: 1 1 auto; min-width: 0; max-width: var(--measure); }
.f-head { display: flex; flex-wrap: wrap; gap: 8px; align-items: baseline; }
.f-desc { color: var(--ink-mid); }
.tick { display: block; }
.tick-axis { stroke: var(--rule-firm); stroke-width: 1; }
.tick-mark { stroke: var(--mark); stroke-width: 2; }
a { color: var(--mark); text-decoration-thickness: 1px; text-underline-offset: 2px; }

/* legend and method */
.subhead { margin-top: 24px; color: var(--ink-mid); }
.legend { margin-top: 8px; }
.legend li {
  display: flex; gap: 12px; align-items: flex-start;
  border-top: 1px solid var(--rule); padding: 12px 0;
}
.legend li:last-child { border-bottom: 1px solid var(--rule); }
.legend .data { max-width: var(--measure); color: var(--ink-mid); }
.glyph { flex: 0 0 __RAIL_W__px; }
.glyph-rule, .glyph-text { font-size: 12px; line-height: 1.3; color: var(--ink-mid); }
.method { margin-top: 8px; }
.method li {
  border-top: 1px solid var(--rule); padding: 12px 0;
  font-size: 13.5px; line-height: 1.45; color: var(--ink-mid);
}
.method li:last-child { border-bottom: 1px solid var(--rule); }

/* controls */
.btn {
  font: 500 12px/1.3 var(--sans); color: var(--ink);
  background: var(--lift); border: 1px solid var(--rule-firm);
  border-radius: 3px; padding: 8px 12px; cursor: pointer;
  transition: border-color 120ms ease;
}
.btn:hover { border-color: var(--mark); }
:focus-visible { outline: 2px solid var(--mark); outline-offset: 2px; }

@media (max-width: 720px) {
  /* The rail needs horizontal room it does not have here, so it is dropped
     and the relations are read from the words on each unit. */
  .u-rail, #rail { display: none; }
  .figures { gap: 24px; }
  /* Stacked, the glyph's flex basis would become its height, so it is let
     go back to its natural size. */
  .legend li { flex-direction: column; gap: 8px; }
  .legend .glyph { flex: none; }
}
@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; }
}
""".replace("__DARK__", _DARK_TOKENS)


_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>__CSS__</style>
</head>
<body>
<div class="page">
<header>
  <div class="masthead">
    <div>
      <h1>__TITLE__</h1>
      <p class="source data">Source: __SOURCE__</p>
    </div>
    <button class="btn" id="theme" type="button" hidden>__THEME_LABEL__</button>
  </div>
  <div class="figures">__FIGURES__</div>
  <p class="roles data">__ROLES__</p>
  __NOTE__
  <div class="balance-block">
    __BALANCE__
    <p class="caption label">__BALANCE_CAPTION__</p>
  </div>
</header>
<section>
  <h2>The argument</h2>
  __UNITS__
</section>
<section>
  <h2>Pattern matches</h2>
  __FALLACIES__
</section>
<section>
  <h2>Reading this report</h2>
  __LEGEND__
  __METHOD__
</section>
</div>
<script id="rail-data" type="application/json">__DATA__</script>
<script>
"use strict";
var RAIL = JSON.parse(document.getElementById("rail-data").textContent);
var NS = "http://www.w3.org/2000/svg";
var svg = document.getElementById("rail");
var host = document.getElementById("units-body");

function node(name, attrs) {
  var n = document.createElementNS(NS, name);
  for (var k in attrs) { n.setAttribute(k, attrs[k]); }
  return n;
}

// An elbow through a vertical channel, so every relation arrives horizontally
// and its end mark reads the same way wherever the two units sit. The channel
// is held a corner radius clear of both ends, so the run into the end mark can
// never double back on itself however close the two lanes are.
function elbow(x1, y1, x2, y2, xEnd, k, same) {
  var r = 5;
  var straight = "M " + x1 + " " + y1 + " L " + xEnd + " " + y2;
  if (Math.abs(y2 - y1) < 2 * r + 2) { return straight; }
  var channel;
  if (same) {
    channel = x1 + 20;
  } else {
    var run = Math.abs(xEnd - x1);
    if (run < 2 * r + 2) { return straight; }
    var step = xEnd > x1 ? 1 : -1;
    var off = Math.min(Math.max(run * 0.45 + ((k % 3) - 1) * 2.5, r), run - r);
    channel = x1 + step * off;
  }
  var vy = y2 > y1 ? 1 : -1;
  var sx = channel > x1 ? 1 : -1;
  var ex = xEnd > channel ? 1 : -1;
  return "M " + x1 + " " + y1 +
         " H " + (channel - sx * r) +
         " Q " + channel + " " + y1 + " " + channel + " " + (y1 + vy * r) +
         " V " + (y2 - vy * r) +
         " Q " + channel + " " + y2 + " " + (channel + ex * r) + " " + y2 +
         " H " + xEnd;
}

function draw() {
  if (!svg || !host || !RAIL.units.length) { return; }
  var slots = host.querySelectorAll(".u-rail");
  if (!slots.length || !slots[0].offsetParent) { return; }
  var base = host.getBoundingClientRect();
  var ys = [];
  for (var i = 0; i < slots.length; i++) {
    var text = slots[i].parentElement.querySelector(".u-text");
    var box = (text || slots[i]).getBoundingClientRect();
    // Sit the dot on the centre of the unit's first line of text.
    ys.push(Math.round(box.top - base.top + 12));
  }
  var height = ys[ys.length - 1] + 16;
  svg.setAttribute("viewBox", "0 0 __RAIL_W__ " + height);
  svg.setAttribute("height", height);
  svg.style.left = (slots[0].getBoundingClientRect().left - base.left) + "px";
  while (svg.firstChild) { svg.removeChild(svg.firstChild); }

  var lanes = {};
  for (var j = 0; j < RAIL.units.length; j++) {
    var lane = RAIL.units[j].lane;
    if (!lanes[lane]) { lanes[lane] = [ys[j], ys[j]]; }
    lanes[lane][1] = ys[j];
  }
  for (var key in lanes) {
    svg.appendChild(node("line", {
      "class": "lane-guide", x1: key, y1: lanes[key][0], x2: key, y2: lanes[key][1]
    }));
  }

  RAIL.edges.forEach(function (e, k) {
    var x1 = RAIL.units[e.s].lane, x2 = RAIL.units[e.t].lane;
    var y1 = ys[e.s], y2 = ys[e.t];
    var same = x1 === x2;
    var dir = same ? -1 : (x2 > x1 ? 1 : -1);
    var attack = e.relation === "attack";
    var tip = x2 - dir * 4.6;
    var xEnd = attack ? x2 - dir * 6 : tip - dir * 5;
    svg.appendChild(node("path", {
      "class": "rel " + (attack ? "rel-attack dashed" : "rel-support"),
      d: elbow(x1, y1, x2, y2, xEnd, k, same)
    }));
    if (attack) {
      svg.appendChild(node("line", {
        "class": "rel rel-attack",
        x1: xEnd, y1: y2 - 5, x2: xEnd, y2: y2 + 5
      }));
    } else {
      svg.appendChild(node("polygon", {
        "class": "rel-head rel-support",
        points: xEnd + "," + (y2 - 3.6) + " " + xEnd + "," + (y2 + 3.6) + " " + tip + "," + y2
      }));
    }
  });

  RAIL.units.forEach(function (u, i) {
    svg.appendChild(node("circle", {
      "class": "dot dot-" + u.role, cx: u.lane, cy: ys[i], r: 4
    }));
    if (u.flagged) {
      svg.appendChild(node("circle", {
        "class": "dot-flag", cx: u.lane, cy: ys[i], r: 7.2
      }));
    }
  });
}

// Nothing here animates: the geometry is read from the laid-out rows once, and
// again only when the page changes width. The second pass on load catches a
// row whose height settled after the script ran.
draw();
window.addEventListener("load", draw);
var pending = false;
window.addEventListener("resize", function () {
  if (pending) { return; }
  pending = true;
  requestAnimationFrame(function () { pending = false; draw(); });
});

// The control only appears once it can work, and it starts from the reader's
// own setting so its label says what pressing it will do.
var root = document.documentElement;
var button = document.getElementById("theme");
var startsDark = window.matchMedia &&
                 window.matchMedia("(prefers-color-scheme: dark)").matches;
root.setAttribute("data-theme", startsDark ? "dark" : "light");
button.textContent = startsDark ? "Use light ink" : "Use dark ink";
button.hidden = false;
button.addEventListener("click", function () {
  var dark = root.getAttribute("data-theme") === "dark";
  root.setAttribute("data-theme", dark ? "light" : "dark");
  button.textContent = dark ? "Use dark ink" : "Use light ink";
});
</script>
</body>
</html>
"""


def render_html(graph: ArgumentGraph, title: str = "Argument Graph",
                output_path: Path = None,
                fallacies: dict[str, list[FallacyMatch]] | None = None,
                source: str | None = None) -> str:
    """Render a self-contained HTML report of the argument structure.

    ``fallacies`` maps a node id to the matches found in that unit, which is how
    a detector's output reaches the unit it fired on. Passing ``None`` records
    that detection was not run, which says something different from nothing
    having matched.
    """
    number = {node.id: i + 1 for i, node in enumerate(graph.nodes)}
    roles = [_role(n) for n in graph.nodes]
    counts = {role: roles.count(role) for role in _ROLE_ORDER}

    support = sum(1 for e in graph.edges if e.relation == RelationType.SUPPORT)
    attack  = sum(1 for e in graph.edges if e.relation == RelationType.ATTACK)
    other   = len(graph.edges) - support - attack

    matched = 0 if fallacies is None else sum(len(v) for v in fallacies.values())

    figures = (
        _figure(len(graph.nodes), "argument units")
        + _figure(len(graph.edges), "relations")
    )
    # No count is shown for a run that did not happen, since a zero would read
    # as a clean result.
    if fallacies is None:
        note = ('<p class="caption data">Fallacy detection was not run, so this '
                "report carries no count of pattern matches.</p>")
    else:
        figures += _figure(matched, "pattern matches")
        note = ""

    role_tags = " ".join(
        f'<span class="role-tag role-{role}">{counts[role]} {role}</span>'
        for role in _ROLE_ORDER
    )
    roles_line = f"By role: {role_tags}" if graph.nodes else "By role: no units."

    caption = (
        f"Relations from the centre line: attack to the left ({attack}), "
        f"support to the right ({support}), scale running to "
        f"{max(support, attack, 1)} either side."
    )
    if other:
        caption += f" {other} relation(s) of neither kind are not drawn here."

    html_out = (
        _TEMPLATE
        .replace("__CSS__", _CSS)
        .replace("__THEME_LABEL__", "Use dark ink")
        .replace("__FIGURES__", figures)
        .replace("__ROLES__", roles_line)
        .replace("__NOTE__", note)
        .replace("__BALANCE__", _balance(support, attack))
        .replace("__BALANCE_CAPTION__", _esc(caption))
        .replace("__UNITS__", _units_section(graph, number, fallacies))
        .replace("__FALLACIES__", _fallacy_section(graph, number, fallacies))
        .replace("__LEGEND__", _legend(bool(graph.nodes), attack > 0))
        .replace("__METHOD__", _method_section(graph, fallacies))
        .replace("__RAIL_W__", str(_RAIL_WIDTH))
        .replace("__DATA__", _rail_data(graph, number, fallacies))
        .replace("__SOURCE__", _esc(source or "not recorded"))
        .replace("__TITLE__", _esc(title))
    )

    if output_path:
        Path(output_path).write_text(html_out, encoding="utf-8")
    return html_out


def _rail_data(graph: ArgumentGraph, number: dict[str, int],
               fallacies: dict[str, list[FallacyMatch]] | None) -> str:
    """The geometry the rail needs, keyed by position so the rows match up."""
    index = {node.id: i for i, node in enumerate(graph.nodes)}
    units = []
    for node in graph.nodes:
        role = _role(node)
        units.append({
            "role": role,
            "lane": _LANES.get(role, _LANES["background"]),
            "flagged": bool((fallacies or {}).get(node.id)),
        })
    edges = [
        {"s": index[e.source_id], "t": index[e.target_id],
         "relation": str(getattr(e.relation, "value", e.relation))}
        for e in graph.edges
        if e.source_id in index and e.target_id in index
    ]
    data = json.dumps({"units": units, "edges": edges}, separators=(",", ":"))
    # A literal </script> in the data would end the block early.
    return data.replace("</", "<\\/")
