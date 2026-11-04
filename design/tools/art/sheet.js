// Review sheet: every icon, all 32 civ sets, planets, stars. node sheet.js out.html
const fs = require('fs');
const A = require('./farglow-art.js');
const { VARS_LIGHT, VARS_DARK } = require('./board_shell');
const half = (theme) => {
  const icons = Object.entries(A.ICON_GROUPS).map(([g, set]) => `<div class="grp"><div class="k">${g}</div><div class="row">${Object.keys(set).map((n) => `<div class="ic" title="${n}">${A.icon(n, 24)}<span>${n.replace(/_/g, ' ')}</span></div>`).join('')}</div></div>`).join('');
  const sets = A.SETS.map((s) => `<div class="set"><div class="trio">${A.emblem(s, 56)}${A.banner(s, 56)}${A.livery(s, 56)}</div><div class="small">${A.emblem(s, 24)}${A.emblem(s, 16)}</div><b>${s.name}</b><span class="m">${s.primaryName}/${s.trimName} · ${s.frame} · ${s.livery} · ${s.banner}</span></div>`).join('');
  const planets = A.TYPES.map((t) => `<div class="pr"><span class="m">${t}</span>${[1, 2, 3, 4, 5].map((i) => A.planet(`hearth-${i * 37}`, t, 72)).join('')}</div>`).join('') + `<div class="pr"><span class="m">belt</span>${[1, 2, 3].map((i) => A.belt(`b${i}`, 72)).join('')}</div>`;
  const stars = Object.keys(A.STAR_CLASSES).map((c) => `<div class="ic">${A.star(c, 56)}<span>${c}</span></div>`).join('') + `<div class="ic">${A.star('G', 56, { companion: 'M' })}<span>G+M</span></div>`;
  return `<section class="${theme}"><h2>${theme}</h2>${icons}<div class="k">Stars</div><div class="row">${stars}</div><div class="k">Planets</div>${planets}<div class="k">Civilization sets (emblem · banner · livery · 24 · 16px)</div><div class="sets">${sets}</div></section>`;
};
const html = `<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;font-family:Inter Tight,system-ui,sans-serif;display:flex}
.light{${VARS_LIGHT};--hull:#C9CED6}.dark{${VARS_DARK};--hull:#3A434E}
section{flex:1;background:var(--bg);color:var(--ink);padding:14px;min-width:0}
h2{margin:0 0 6px;font-size:15px}.k{font:500 11px IBM Plex Mono,monospace;text-transform:uppercase;letter-spacing:.04em;color:var(--ink-muted);margin:10px 0 4px}
.row{display:flex;flex-wrap:wrap;gap:4px}.ic{width:62px;display:flex;flex-direction:column;align-items:center;gap:2px;font-size:9px;color:var(--ink-secondary);text-align:center}
.pr{display:flex;align-items:center;gap:6px}.pr .m{width:70px}.m{font:10px IBM Plex Mono,monospace;color:var(--ink-muted)}
.sets{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.set{border:1px solid var(--border);border-radius:4px;padding:6px;display:flex;flex-direction:column;gap:3px;font-size:12px}
.trio,.small{display:flex;gap:6px;align-items:center}
</style></head><body>${half('light')}${half('dark')}</body></html>`;
fs.writeFileSync(process.argv[2], html);
console.log('palette', A.PALETTE.map((p) => `${p.name} ${p.hex} L=${A.lum(p.hex).toFixed(3)} light:${A.contrast(p.hex, '#F3F4F1').toFixed(2)} dark:${A.contrast(p.hex, '#0F1318').toFixed(2)}`).join('\n'));
