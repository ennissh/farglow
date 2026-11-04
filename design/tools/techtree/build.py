"""Render the Farglow PoC tech tree YAML into a branded single-page HTML file (printed to PDF by Chrome)."""
import html
import sys
from pathlib import Path

import yaml

SRC = Path(sys.argv[1])
OUT = Path(sys.argv[2])
data = yaml.safe_load(SRC.read_text())

LABEL = {
    "ftl_speed_ly_per_tick": ("travel speed", " ly/tick"),
    "comms_speed_ly_per_tick": ("comms speed", " ly/tick"),
    "command_lag_ticks": ("order lag", " tick"),
    "survey_range_ly": ("survey range", " ly"),
    "research_output": ("research", ""),
    "research_efficiency": ("research efficiency", ""),
    "mineral_yield": ("minerals", ""),
    "belt_mineral_yield": ("belt minerals", ""),
    "ice_mineral_yield": ("minerals per ice world", ""),
    "energy_yield": ("energy", ""),
    "star_energy_yield": ("star energy", ""),
    "gas_giant_energy": ("energy per gas giant", ""),
    "pop_growth": ("population growth", ""),
    "pop_cap_rocky": ("pop cap on rocky worlds", ""),
    "habitability_step": ("habitability step", ""),
    "verdant_peak_yield": ("verdant-world yields", ""),
    "stability": ("stability", ""),
    "cohesion": ("Cohesion", ""),
    "ac_efficiency": ("action-credit efficiency", ""),
    "policy_cooldown_ticks": ("policy cooldown", " ticks"),
    "trade_income": ("trade income", ""),
    "reputation_per_day": ("reputation per day", ""),
    "intel_on_others": ("intel on others", ""),
    "intel_leak": ("intel others hold on you", ""),
    "envoy_travel_time": ("envoy travel time", ""),
    "colonize_cost": ("colonize cost", ""),
    "admin_cost_exponent": ("admin cost exponent", ""),
    "expansion_cost": ("expansion cost", ""),
    "shipyard_throughput": ("shipyard output", ""),
    "fleet_upkeep": ("fleet upkeep", ""),
    "readiness_decay": ("readiness decay", ""),
    "readiness_decay_away": ("decay outside comms range", ""),
    "combat_attack": ("attack", ""),
    "combat_defense": ("defense", ""),
    "defense_slots_per_body": ("defense slot per world", ""),
    "siege_time": ("siege time", ""),
    "detection_range_ly": ("detection range", " ly"),
    "energy_upkeep": ("energy upkeep", ""),
    "mineral_upkeep": ("mineral upkeep", ""),
}
UNLOCK = {
    "outpost_ocean": "ocean-world colonies",
    "building_relay_station": "relay stations",
    "governance_council": "Council authority",
    "project_terraform": "terraform project",
    "corridor_travel": "fold corridors",
}
START_SUMMARY = {
    "fold_transit": "0.5 ly/tick travel",
    "lightspeed_relays": "2 ly/tick comms · 6 ly survey",
    "orbital_industry": "Shipyards, 1 t hull per mineral",
    "closed_ecologies": "Rocky and verdant outposts",
    "planetary_council": "8 governance options",
    "point_defense": "Baseline world defenses",
}
FIELDS = data["fields"]
FIELD_NAME = {
    "propulsion": "Propulsion",
    "communications": "Communications",
    "industry": "Industry",
    "life_sciences": "Life sciences",
    "society": "Society",
    "defense": "Defense",
}
MINUS = "−"


def num(v):
    s = f"{abs(v):g}"
    return s


def fmt(e):
    label, unit = LABEL[e["key"]]
    v = e["value"]
    sign = "+" if v >= 0 else MINUS
    if e["op"] == "pct":
        text = f"{sign}{num(v)}% {label}"
    else:
        if unit == " tick" and abs(v) != 1:
            unit = " ticks"
        text = f"{sign}{num(v)}{unit} {label}" if unit else f"{sign}{num(v)} {label}"
    q = []
    if e.get("per"):
        q.append("per " + e["per"].replace("_", " "))
    if e.get("while"):
        q.append("while " + e["while"])
    if e.get("per_level"):
        q.append("per level")
    if q:
        text += " " + ", ".join(q)
    return html.escape(text)


names = {n["id"]: n["name"] for n in data["nodes"]}
names.update({n["id"]: n["name"] for n in data["known_at_start"]})


def card(n, kind=""):
    lines = []
    for e in n.get("effects", []) or []:
        lines.append(f'<li class="pro"><span class="mk" aria-hidden="true">+</span>{fmt(e)}</li>')
    for u in n.get("unlocks", []) or []:
        lines.append(f'<li class="pro"><span class="mk" aria-hidden="true">+</span>Unlocks {html.escape(UNLOCK.get(u, u))}</li>')
    for e in n.get("drawbacks", []) or []:
        lines.append(f'<li class="con"><span class="mk" aria-hidden="true">{MINUS}</span>{fmt(e)}</li>')
    req = ""
    if n.get("requires"):
        req = '<div class="req">needs ' + ", ".join(html.escape(names[r]) for r in n["requires"]) + "</div>"
    badge = ""
    if n.get("repeatable"):
        badge = '<span class="badge">repeatable</span>'
    return (
        f'<div class="card {kind}"><div class="nm">{html.escape(n["name"])}{badge}</div>'
        f'<ul>{"".join(lines)}</ul>{req}</div>'
    )


def start_card(n):
    return (
        f'<div class="card start"><div class="nm">{html.escape(n["name"])}</div>'
        f'<div class="sum">{html.escape(START_SUMMARY[n["id"]])}</div></div>'
    )


def row(label, sub, cells, cls=""):
    out = [f'<div class="rl {cls}"><div class="tier">{label}</div><div class="tsub">{sub}</div></div>']
    for f in FIELDS:
        out.append(f'<div class="cell {cls}">{"".join(cells.get(f, []))}</div>')
    return "".join(out)


def bucket(nodes, kind=""):
    d = {}
    for n in nodes:
        d.setdefault(n["field"], []).append(card(n, kind))
    return d


nodes = data["nodes"]
tier = {t["id"]: t for t in data["tiers"]}
reach = [n for n in nodes if n["tier"] == "reach"]
lat_reg = [n for n in nodes if n["tier"] == "lattice" and not n.get("exclusive_group")]
lat_doc = [n for n in nodes if n.get("exclusive_group") == "lattice_doctrine"]
con_reg = [n for n in nodes if n["tier"] == "concord" and not n.get("exclusive_group") and not n.get("repeatable")]
con_doc = [n for n in nodes if n.get("exclusive_group") == "concord_doctrine"]
rep = [n for n in nodes if n.get("repeatable")]
start = {}
for n in data["known_at_start"]:
    start.setdefault(n["field"], []).append(start_card(n))

researchable = len(nodes)
grid = "".join(
    [
        '<div class="corner"></div>'
        + "".join(f'<div class="fh">{FIELD_NAME[f]}</div>' for f in FIELDS),
        row("Known at start", "Tiers 0–3, the PoC begins here", start, "start"),
        row("Reach", f"Tier 4 · base {tier['reach']['base_cost']:,} RP", bucket(reach)),
        row("Lattice", f"Tier 5 · base {tier['lattice']['base_cost']:,} RP<br>after any 6 Reach", bucket(lat_reg)),
        row("Lattice doctrine", "Choose 1 of 3.<br>The other two lock.", bucket(lat_doc, "doc"), "doc"),
        row("Concord", f"Tier 6 · base {tier['concord']['base_cost']:,} RP<br>after any 6 Lattice", bucket(con_reg)),
        row("Concord doctrine", "Choose 1 of 3.<br>The other two lock.", bucket(con_doc, "doc"), "doc"),
        row("Repeatable", "Endless, +25% cost<br>per level", bucket(rep, "rep"), "rep"),
    ]
)

page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Farglow PoC tech tree</title>
<style>
@font-face {{ font-family: "Inter Tight"; font-weight: 400; src: url(fonts/inter-tight-latin-400-normal.woff2) format("woff2"); }}
@font-face {{ font-family: "Inter Tight"; font-weight: 500; src: url(fonts/inter-tight-latin-500-normal.woff2) format("woff2"); }}
@font-face {{ font-family: "Inter Tight"; font-weight: 600; src: url(fonts/inter-tight-latin-600-normal.woff2) format("woff2"); }}
@font-face {{ font-family: "Inter Tight"; font-weight: 700; src: url(fonts/inter-tight-latin-700-normal.woff2) format("woff2"); }}
@font-face {{ font-family: "IBM Plex Mono"; font-weight: 400; src: url(fonts/ibm-plex-mono-latin-400-normal.woff2) format("woff2"); }}
@font-face {{ font-family: "IBM Plex Mono"; font-weight: 500; src: url(fonts/ibm-plex-mono-latin-500-normal.woff2) format("woff2"); }}
@page {{ size: 11in 8.5in; margin: 0; }}
:root {{
  --bg:#F3F4F1; --surface:#FFFFFF; --sunken:#FBFBFA; --raised:#EEF0EE; --border:#D5D9DE; --subtle:#E6E9EC; --strong:#8A929C;
  --ink:#141A22; --ink2:#3A434E; --muted:#56606C; --accent:#1D5BB8; --accent-soft:#E3ECF9;
  --signal:#B8460E; --signal-soft:#FBEADF; --positive:#1E7A4C; --positive-soft:#E2F3EA;
  --sans:"Inter Tight", system-ui, sans-serif; --mono:"IBM Plex Mono", ui-monospace, monospace;
}}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; }}
body {{ width: 11in; height: 8.5in; background: var(--bg); color: var(--ink); font-family: var(--sans);
  -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
.page {{ width: 11in; height: 8.5in; padding: 16pt 22pt 12pt; display: flex; flex-direction: column; gap: 6pt; overflow: hidden; }}
header {{ display: flex; justify-content: space-between; align-items: flex-end; border-bottom: 1px solid var(--border); padding-bottom: 5pt; }}
.brand {{ display: flex; align-items: baseline; gap: 10pt; }}
.wm {{ font-size: 20pt; font-weight: 700; letter-spacing: -0.02em; line-height: 1; }}
.ttl {{ font-size: 13pt; font-weight: 600; line-height: 1; }}
.kick {{ font-family: var(--mono); font-size: 6.5pt; font-weight: 500; letter-spacing: 0.06em; text-transform: uppercase; color: var(--muted); }}
.meta {{ text-align: right; display: flex; flex-direction: column; gap: 2pt; }}
.meta .m {{ font-family: var(--mono); font-size: 7pt; color: var(--muted); }}
.status {{ align-self: flex-end; font-family: var(--mono); font-size: 6.5pt; font-weight: 500; text-transform: uppercase; letter-spacing: 0.05em;
  color: var(--signal); background: var(--signal-soft); border-radius: 2pt; padding: 1.5pt 5pt; }}
.grid {{ flex: 1; display: grid; grid-template-columns: 70pt repeat(6, minmax(0, 1fr)); column-gap: 5pt; row-gap: 3pt; align-content: start; }}
.corner {{ }}
.fh {{ font-size: 7.5pt; font-weight: 600; color: var(--ink2); padding: 0 0 2pt 1pt; border-bottom: 1.5pt solid var(--accent); }}
.rl {{ padding: 4pt 4pt 0 0; border-top: 1px solid var(--subtle); }}
.tier {{ font-size: 9pt; font-weight: 700; line-height: 1.1; }}
.tsub {{ font-family: var(--mono); font-size: 6pt; line-height: 1.35; color: var(--muted); margin-top: 2pt; }}
.cell {{ display: flex; flex-direction: column; gap: 2.5pt; padding-top: 3pt; border-top: 1px solid var(--subtle); min-width: 0; }}
.rl.doc, .cell.doc {{ background: var(--accent-soft); border-top: 1px dashed var(--accent); }}
.rl.doc {{ padding-left: 4pt; border-radius: 0; }}
.rl.doc .tier {{ color: var(--accent); }}
.cell.doc {{ padding: 4pt 2pt 3pt; }}
.card {{ background: var(--surface); border: 0.75pt solid var(--border); border-radius: 2.5pt; padding: 2.5pt 4.5pt 3pt; }}
.card.doc {{ border: 1pt solid var(--accent); }}
.card.start {{ background: var(--raised); border-color: var(--raised); }}
.card.rep {{ border-style: dashed; border-color: var(--strong); }}
.nm {{ font-size: 7.6pt; font-weight: 600; line-height: 1.2; display: flex; justify-content: space-between; gap: 3pt; align-items: baseline; }}
.badge {{ font-family: var(--mono); font-size: 5.5pt; font-weight: 500; color: var(--ink2); background: var(--raised); border-radius: 2pt; padding: 0 3pt; text-transform: uppercase; }}
.sum {{ font-size: 6.6pt; color: var(--ink2); line-height: 1.3; margin-top: 1pt; }}
ul {{ list-style: none; margin: 1.5pt 0 0; padding: 0; }}
li {{ font-size: 6.6pt; line-height: 1.25; display: grid; grid-template-columns: 6pt 1fr; color: var(--ink2); }}
li .mk {{ font-family: var(--mono); font-weight: 500; }}
li.pro .mk {{ color: var(--positive); }}
li.con .mk {{ color: var(--signal); }}
li.con {{ color: var(--ink2); }}
.req {{ font-family: var(--mono); font-size: 5.8pt; color: var(--muted); margin-top: 1.5pt; line-height: 1.3; }}
footer {{ display: flex; justify-content: space-between; gap: 16pt; border-top: 1px solid var(--border); padding-top: 5pt; }}
.legend {{ display: flex; gap: 12pt; align-items: center; font-size: 6.6pt; color: var(--ink2); }}
.legend .k {{ display: inline-flex; gap: 4pt; align-items: center; }}
.sw {{ width: 12pt; height: 8pt; border-radius: 2pt; display: inline-block; }}
.rules {{ font-family: var(--mono); font-size: 6.2pt; color: var(--muted); text-align: right; line-height: 1.45; }}
</style></head>
<body><div class="page">
<header>
  <div>
    <div class="kick">A Generative Distractions game · Citus Technologies, LLC</div>
    <div class="brand" style="margin-top:4pt"><span class="wm">farglow</span><span class="ttl">Tech tree · proof of concept</span></div>
  </div>
  <div class="meta">
    <span class="status">Proposed · not yet balanced</span>
    <span class="m">{researchable} researchable · {len(data['known_at_start'])} known at start · 6 fields · 3 tiers</span>
  </div>
</header>
<main class="grid">{grid}</main>
<footer>
  <div class="legend">
    <span class="k"><b style="color:var(--positive);font-family:var(--mono)">+</b> benefit</span>
    <span class="k"><b style="color:var(--signal);font-family:var(--mono)">{MINUS}</b> drawback (every tech has one)</span>
    <span class="k"><span class="sw" style="background:var(--accent-soft);border:1pt solid var(--accent)"></span> doctrine: pick one, others lock forever</span>
    <span class="k"><span class="sw" style="background:var(--surface);border:1pt dashed var(--strong)"></span> repeatable</span>
  </div>
  <div class="rules">cost = base × (1 + 0.04 × techs known) · knowing more makes everything cost more<br>
  Full tree ≈ 85 days of hourly ticks (simulated) · debug builds run at 10% cost</div>
</footer>
</div></body></html>"""
OUT.write_text(page)
print("wrote", OUT)
