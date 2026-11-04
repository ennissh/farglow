const fs = require('fs');
const { concepts, mark } = require('./logos');
const { board } = require('./board_shell');
const out = process.argv[2];

const tile = (c, theme) => `<div class="fg-root ${theme}" style="flex:1;min-width:0;background:var(--bg);border:1px solid var(--border);border-radius:4px;padding:10px;display:flex;flex-direction:column;gap:10px;align-items:center">
<div style="width:96px;height:96px">${mark(c, 96)}</div>
<div style="display:flex;gap:10px;align-items:flex-end">${mark(c, 32)}${mark(c, 24)}${mark(c, 16)}</div>
<div style="display:flex;gap:6px;align-items:center">${mark(c, 22)}<span style="font-family:var(--font-sans);font-size:19px;line-height:22px;font-weight:700;letter-spacing:-0.02em;color:var(--ink)">farglow</span></div>
</div>`;

const cards = concepts.map((c, i) => `<section class="fg-panel" style="gap:8px${c.id === 'f-horizon' ? ';border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)' : ''}">
<div style="display:flex;justify-content:space-between;align-items:baseline"><h2 class="fg-panel__title">${i + 1} · ${c.name}${c.id === 'f-horizon' ? ' <span class="fg-badge fg-badge--accent">Chosen</span>' : ''}</h2><span class="fg-meta">96 · 32 · 24 · 16 px</span></div>
<div style="display:flex;gap:6px">${tile(c, 'fg-light')}${tile(c, 'fg-dark')}</div>
<p style="margin:0;font-size:12px;line-height:17px;color:var(--ink-secondary)">${c.idea}</p>
</section>`).join('\n');

const body = `<main style="padding:16px;display:flex;flex-direction:column;gap:12px">
<header style="display:flex;justify-content:space-between;align-items:baseline;gap:16px">
<div style="display:flex;flex-direction:column;gap:2px">
<span class="fg-kicker">Brand · exploration</span>
<h1 style="margin:0;font-size:22px;line-height:28px;font-weight:700;letter-spacing:-0.01em">Farglow logo concepts</h1>
<span style="font-size:13px;line-height:18px;color:var(--ink-secondary)">Earthrise, retold with two or three suns. Each mark shown in light and dark, at hero size, app-icon sizes and favicon size, and as a lockup with the wordmark.</span>
</div>
<span class="fg-meta" style="max-width:420px;text-align:right">Gold = the brand glow (logo only, not a UI colour). Blue companion = the "you" accent, a nod to "every star counts". Run a trademark search on the chosen mark before finalising.</span>
</header>
<div style="display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px">
${cards}
</div>
</main>`;
fs.writeFileSync(out, board({ title: 'Logo concepts', body, height: 740 }));
console.log('wrote', out);
