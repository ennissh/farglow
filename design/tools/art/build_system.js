// Board 18 · System view (MOO2-style): star and bodies in orbit order; the selected body with
// building chips around it, population pips and garrison badge; details on the right.
const fs = require('fs');
const A = require('./farglow-art.js');
const { board } = require('./board_shell');
const out = process.argv[2];
const ME = A.SETS.find((s) => s.id === 'beacon');

const B = [
  { id: 'cinder', n: 'I', name: 'Cinder', type: 'rocky', status: 'Outpost', owner: true, pop: [0, 0], size: 38,
    built: [['extraction_complex', 'Extraction complex', 'surface']], building: null, avail: ['defense_battery', 'warehouse'],
    garrison: null, yields: [['minerals', '+4.0'], ['energy', '−0.5']], note: 'Barren, tidally locked. Mines only.' },
  { id: 'hearth', n: 'II', name: 'Hearth', type: 'verdant', status: 'Capital', owner: true, pop: [14.2, 16], size: 56,
    built: [['research_station', 'Research station', 'surface'], ['civic_forum', 'Civic forum', 'surface'], ['warehouse', 'Warehouse', 'surface'], ['shipyard', 'Shipyard', 'orbital'], ['habitat_ring', 'Habitat ring', 'orbital'], ['defense_battery', 'Defense battery', 'orbital']],
    building: ['fusion_plant', 'Fusion plant', 'surface', 7, 12], avail: ['relay_station'],
    garrison: { tons: '900 t', sq: '2 squadrons', ready: '86%' }, yields: [['research', '+18.0'], ['minerals', '+6.0'], ['energy', '+3.5'], ['action_credits', '+113']], note: 'Homeworld. Temperate, 1.0 g, 71% ocean.' },
  { id: 'brin', n: 'III', name: 'Brin', type: 'ocean', status: 'Colony', owner: true, pop: [3.1, 8], size: 48,
    built: [['civic_forum', 'Civic forum', 'surface']], building: ['habitat_ring', 'Habitat ring', 'orbital', 3, 12], avail: ['research_station', 'warehouse', 'defense_battery'],
    garrison: null, yields: [['research', '+2.0'], ['action_credits', '+25']], note: 'Water world, 0.9 g. Settled tick 151.' },
  { id: 'shoals', n: '—', name: 'The Shoals', type: 'belt', status: 'Outpost', owner: true, pop: [0, 0], size: 44,
    built: [['extraction_complex', 'Extraction complex', 'surface'], ['warehouse', 'Warehouse', 'surface']], building: null, avail: ['defense_battery'],
    garrison: null, yields: [['minerals', '+5.0']], note: 'Metal-rich belt between Brin and Vast.' },
  { id: 'vast', n: 'IV', name: 'Vast', type: 'gas_giant', status: 'Outpost', owner: true, pop: [0, 0], size: 64, ring: true,
    built: [['relay_station', 'Relay station', 'orbital']], building: null, avail: ['fusion_plant', 'defense_battery'],
    garrison: { tons: '300 t', sq: '1 picket', ready: '92%' }, yields: [['energy', '+2.0']], note: 'Banded giant, 11 moons. Fuel skimming site.' },
  { id: 'rime', n: 'V', name: 'Rime', type: 'ice', status: 'Unclaimed', owner: false, pop: [0, 0], size: 40,
    built: [], building: null, avail: ['extraction_complex', 'warehouse'], garrison: null, yields: [], note: 'Frozen moon-sized world. Subsurface ice.' },
];
const SEED = (b) => `41-07-02/hearth/${b.id}`;
const art = (b, size) => (b.type === 'belt' ? A.belt(SEED(b), size) : A.planet(SEED(b), b.type, size, { ring: b.ring }));
const ic = (n, s = 16) => A.icon(n, s);

// ---- top strip: star + bodies in orbit order
const strip = `<div class="fg-panel" style="padding:8px 12px">
<div class="fg-panel__head"><h2 class="fg-panel__title">Hearth system · G2 + M5 binary</h2><span class="fg-meta">sector 41-07-02 · 6 bodies · 5 claimed · you hold the system</span></div>
<div style="position:relative;display:flex;align-items:center;gap:0;height:118px;background:var(--surface-sunken);border:1px solid var(--border-subtle);border-radius:3px;overflow:hidden">
<div style="position:absolute;left:96px;right:12px;top:58px;height:1px;background:var(--border)"></div>
<div style="flex:0 0 110px;margin-left:-28px">${A.star('G', 132, { companion: 'M' })}</div>
${B.map((b) => `<button type="button" onClick="{{pick_${b.id}}}" aria-pressed="{{on_${b.id}}}" class="fg-sysbody" style="flex:1;min-width:0;background:none;border:0;padding:4px 0;display:flex;flex-direction:column;align-items:center;gap:2px;cursor:pointer;color:var(--ink);font:inherit;position:relative">
<div style="height:70px;display:flex;align-items:center">${art(b, b.size)}</div>
<span style="font-size:12px;line-height:15px;font-weight:600;display:flex;gap:4px;align-items:center">${b.owner ? A.emblem(ME, 14) : ''}${b.n !== '—' ? b.n + ' · ' : ''}${b.name}</span>
<span class="fg-meta">${b.status}${b.pop[1] ? ' · ' + b.pop[0] + ' pop' : ''}</span>
</button>`).join('')}
</div></div>`;

// ---- big view per body
function chip(icon, label, where, extra = '', cls = '') {
  return `<div class="fg-chip ${cls}"><span class="fg-chip__ic">${ic(icon, 16)}</span><span style="display:flex;flex-direction:column;min-width:0"><span class="fg-chip__t">${label}</span><span class="fg-chip__m">${where}${extra}</span></span></div>`;
}
function bigView(b) {
  const items = b.built.map(([i, l, w]) => chip(i, l, w))
    .concat(b.building ? [chip(b.building[0], b.building[1], b.building[2], ` · building ${b.building[3]}/${b.building[4]}`, 'fg-chip--build')] : [])
    .concat(b.avail.map((i) => chip(i, (ICON_LABEL[i] || i), 'available · build', '', 'fg-chip--open')));
  const n = items.length, W = 760, H = 470, cx = W / 2, cy = H / 2 - 8, rx = 300, ry = 190;
  const placed = items.map((h, i) => { const a = -Math.PI / 2 + (i / n) * Math.PI * 2 + (n % 2 ? 0 : Math.PI / n); const x = cx + rx * Math.cos(a), y = cy + ry * Math.sin(a); return `<div style="position:absolute;left:${Math.round(x - 78)}px;top:${Math.round(y - 17)}px;width:156px">${h}</div>`; }).join('');
  const pips = b.pop[1] ? `<div style="position:absolute;left:0;right:0;bottom:6px;display:flex;flex-direction:column;align-items:center;gap:4px">
<div style="display:flex;gap:3px">${Array.from({ length: b.pop[1] }, (_, i) => { const fill = Math.max(0, Math.min(1, b.pop[0] - i)); return `<span class="fg-pip" style="--p:${Math.round(fill * 100)}%"></span>`; }).join('')}</div>
<span class="fg-meta" style="display:flex;gap:4px;align-items:center">${ic('population', 14)} population ${b.pop[0]} of ${b.pop[1]} · each pip is 1 million</span></div>` : '';
  const gar = b.garrison ? `<div class="fg-garrison" style="position:absolute;left:${cx - 210}px;top:${cy - 146}px">${ic('garrison', 16)}<span><b>${b.garrison.tons}</b> · ${b.garrison.sq}<br><span class="fg-meta">readiness ${b.garrison.ready}</span></span></div>` : '';
  const ps = b.type === 'gas_giant' ? 300 : b.type === 'belt' ? 240 : 220;
  return `<div style="position:relative;width:${W}px;height:${H}px;margin:0 auto">
<svg width="${W}" height="${H}" style="position:absolute;inset:0"><ellipse cx="${cx}" cy="${cy}" rx="${rx - 70}" ry="${ry - 50}" fill="none" stroke="var(--border)" stroke-dasharray="3 5"/></svg>
<div style="position:absolute;left:${cx - ps / 2}px;top:${cy - ps / 2}px;width:${ps}px;height:${ps}px">${art(b, ps)}</div>
${gar}${placed}${pips}
</div>`;
}
const ICON_LABEL = { extraction_complex: 'Extraction complex', fusion_plant: 'Fusion plant', research_station: 'Research station', habitat_ring: 'Habitat ring', civic_forum: 'Civic forum', defense_battery: 'Defense battery', warehouse: 'Warehouse', shipyard: 'Shipyard', relay_station: 'Relay station' };

// ---- detail column per body
function detail(b) {
  const rows = b.yields.length ? b.yields.map(([i, v]) => `<tr><td><span style="display:inline-flex;gap:6px;align-items:center">${ic(i, 16)}${i.replace('_', ' ')}</span></td><td class="num">${v} / tick</td></tr>`).join('') : '<tr><td colspan="2" class="fg-meta">No yields until claimed.</td></tr>';
  const queue = b.building ? `<div class="fg-meter"><div class="fg-meter__row"><span style="display:inline-flex;gap:6px;align-items:center">${ic('construction', 14)} ${b.building[1]}</span><span class="fg-meter__value">${b.building[3]} of ${b.building[4]} ticks</span></div><div class="fg-meter__track"><div class="fg-meter__fill" style="width:${Math.round(b.building[3] / b.building[4] * 100)}%"></div></div></div>` : '<span class="fg-meta">Build queue empty.</span>';
  const action = b.owner ? `<div style="display:flex;gap:6px;flex-wrap:wrap"><a class="fg-btn fg-btn--primary" href="Colony.dc.html">Manage ${b.status.toLowerCase()}</a><a class="fg-btn fg-btn--secondary" href="FleetOrders.dc.html">Fleet orders</a></div>` : `<div style="display:flex;gap:6px"><button type="button" class="fg-btn fg-btn--primary">Claim · 150 AC + 50 M</button></div><span class="fg-help">In-system claim: cheaper than a new system because Hearth already holds the star.</span>`;
  return `<section class="fg-panel">
<div class="fg-panel__head"><div style="display:flex;flex-direction:column;gap:1px"><span class="fg-kicker${b.owner ? ' fg-kicker--accent' : ''}">${b.n !== '—' ? 'Body ' + b.n + ' · ' : ''}${b.type.replace('_', ' ')}</span><h1 style="margin:0;font-size:17px;line-height:22px;font-weight:700">${b.name}</h1></div>${b.owner ? `<span style="display:flex;gap:6px;align-items:center" class="fg-meta">${A.emblem(ME, 20)}Ashenreach</span>` : '<span class="fg-badge fg-badge--neutral">Unclaimed</span>'}</div>
<p style="margin:0;font-size:12px;line-height:17px;color:var(--ink-secondary)">${b.note}</p>
<table class="fg-table"><thead><tr><th>Yield</th><th class="num">Per tick</th></tr></thead><tbody>${rows}</tbody></table>
<div style="display:flex;flex-direction:column;gap:6px"><span class="fg-kicker">Construction</span>${queue}</div>
${b.garrison ? `<table class="fg-table"><thead><tr><th>Garrison</th><th class="num">Tons</th><th class="num">Ready</th></tr></thead><tbody><tr><td><span style="display:inline-flex;gap:6px;align-items:center">${ic('warship', 16)}${b.garrison.sq}</span></td><td class="num">${b.garrison.tons}</td><td class="num">${b.garrison.ready}</td></tr></tbody></table>` : '<span class="fg-meta" style="display:inline-flex;gap:6px;align-items:center">' + ic('garrison', 14) + ' No garrison. Defended by system patrols only.</span>'}
${action}
</section>`;
}

const legend = `<section class="fg-panel"><div class="fg-panel__head"><h2 class="fg-panel__title">Reading this view</h2></div>
<ul style="margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:5px;font-size:12px;line-height:16px;color:var(--ink-secondary)">
<li style="display:flex;gap:8px;align-items:center"><span class="fg-chip" style="width:auto;padding:2px 6px"><span class="fg-chip__ic">${ic('research_station', 14)}</span></span>Built: one of each building per body</li>
<li style="display:flex;gap:8px;align-items:center"><span class="fg-chip fg-chip--build" style="width:auto;padding:2px 6px"><span class="fg-chip__ic">${ic('fusion_plant', 14)}</span></span>Under construction (12 ticks)</li>
<li style="display:flex;gap:8px;align-items:center"><span class="fg-chip fg-chip--open" style="width:auto;padding:2px 6px"><span class="fg-chip__ic">${ic('warehouse', 14)}</span></span>Available to build here</li>
<li style="display:flex;gap:8px;align-items:center"><span style="display:flex;gap:2px"><span class="fg-pip" style="--p:100%"></span><span class="fg-pip" style="--p:40%"></span><span class="fg-pip" style="--p:0%"></span></span>Population: filled, growing, room to grow</li>
<li style="display:flex;gap:8px;align-items:center">${ic('garrison', 16)}Garrison: ships stationed at this body</li>
</ul></section>`;

const body = `<header style="min-height:48px;box-sizing:border-box;padding:6px 12px;display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center;justify-content:space-between;background:var(--surface);border-bottom:1px solid var(--border)">
<div style="display:flex;align-items:baseline;gap:12px"><span style="font-size:20px;line-height:24px;font-weight:700;letter-spacing:-0.02em">farglow</span><span class="fg-meta">The Ashenreach Collective · Reach tier</span></div>
<nav class="fg-tabs" aria-label="Game views"><a class="fg-tab" href="Galaxy.dc.html" aria-current="page">Galaxy</a><a class="fg-tab" href="Governor.dc.html">Governor</a><a class="fg-tab" href="Research.dc.html">Research</a><a class="fg-tab" href="Dispatch.dc.html">Dispatch <span class="fg-tab__count">3</span></a><a class="fg-tab" href="Diplomacy.dc.html">Diplomacy</a></nav>
<div class="fg-status"><span>tick <b>1,284</b></span><span>next tick <b>42 min</b></span></div>
</header>
<main style="padding:12px;display:flex;flex-direction:column;gap:12px">
<div class="fg-meta"><a href="Galaxy.dc.html">Galaxy</a> › Sector 41-07-02 › <b style="color:var(--ink)">Hearth system</b></div>
${strip}
<div style="display:flex;gap:12px;align-items:flex-start">
<section class="fg-panel" style="flex:1;min-width:0;padding:8px">
${B.map((b) => `<sc-if value="{{on_${b.id}}}" hint-placeholder-val="{{${b.id === 'hearth'}}}">${bigView(b)}</sc-if>`).join('\n')}
</section>
<aside style="flex:0 0 380px;display:flex;flex-direction:column;gap:12px">
${B.map((b) => `<sc-if value="{{on_${b.id}}}" hint-placeholder-val="{{${b.id === 'hearth'}}}">${detail(b)}</sc-if>`).join('\n')}
${legend}
</aside>
</div>
</main>`;

const extraCss = `.fg-light{--hull:#C9CED6}.fg-dark{--hull:#3A434E}
.fg-sysbody[aria-pressed="true"]{box-shadow:inset 0 -2px 0 var(--accent);background:var(--accent-soft) !important}
.fg-sysbody:hover{background:var(--surface-raised) !important}
.fg-chip{box-sizing:border-box;width:156px;display:flex;gap:6px;align-items:center;padding:4px 7px;border-radius:4px;background:var(--surface);border:1px solid var(--border);color:var(--ink)}
.fg-chip__ic{display:flex;color:var(--accent)}
.fg-chip__t{font-size:12px;line-height:15px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.fg-chip__m{font-family:var(--font-mono);font-size:10px;line-height:13px;color:var(--ink-muted)}
.fg-chip--build{border-color:var(--accent);background:var(--accent-soft)}
.fg-chip--open{border-style:dashed;background:transparent}.fg-chip--open .fg-chip__ic{color:var(--ink-muted)}.fg-chip--open .fg-chip__t{color:var(--ink-secondary);font-weight:500}
.fg-pip{width:12px;height:12px;border-radius:50%;box-sizing:border-box;border:1.5px solid var(--accent);background:linear-gradient(to top,var(--accent) var(--p),transparent var(--p))}
.fg-garrison{display:flex;gap:6px;align-items:flex-start;padding:5px 8px;border-radius:4px;background:var(--surface);border:1px solid var(--accent);font-size:12px;line-height:15px;color:var(--ink)}
.fg-garrison svg{color:var(--accent);flex:none}`;

const ids = B.map((b) => b.id);
const script = `constructor(props) { super(props); this.state = { sel: 'hearth' }; }
renderVals() {
const v = { themeClass: (this.props.theme ?? 'light') === 'dark' ? 'fg-dark' : 'fg-light' };
${JSON.stringify(ids)}.forEach((id) => { v['on_' + id] = this.state.sel === id; v['pick_' + id] = () => this.setState({ sel: id }); });
return v;
}`;
fs.writeFileSync(out, board({ title: 'System view', body, height: 1000, extraCss, script }));
console.log('wrote', out, (fs.statSync(out).size / 1024).toFixed(0) + ' KB');
