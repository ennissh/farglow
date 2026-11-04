// Adds the art library to the Farglow Design System working copy.
// node build_ds.js <ds project dir>
const fs = require('fs'), path = require('path');
const A = require('./farglow-art.js');
const P = process.argv[2];
const w = (rel, txt) => { const p = path.join(P, rel); fs.mkdirSync(path.dirname(p), { recursive: true }); fs.writeFileSync(p, txt); };

// 1. library
w('lib/farglow-art.js', fs.readFileSync(path.join(__dirname, 'farglow-art.js'), 'utf8'));

// 2. static assets (for download / other tools). Icons single-ink; emblems in their colours.
const INK = '#141A22';
for (const [g, set] of Object.entries(A.ICON_GROUPS)) for (const n of Object.keys(set)) w(`assets/Icons/${g.toLowerCase()}-${n}.svg`, A.icon(n, 24, { color: INK }).replace('<svg ', '<svg xmlns="http://www.w3.org/2000/svg" '));
w('assets/Icons/README.md', `# Icons\n\nSingle-ink SVGs on a 24px grid, 1.5px stroke, round caps and joins. The ink in these files is **${INK}** (light-theme ink). In the product, draw icons with \`FarglowArt.icon(name)\` from \`lib/farglow-art.js\` instead: it uses \`currentColor\`, so icons follow the theme and the text colour around them.\n\nSizes: 16px in dense tables, 20px default, 24px in panel headers. Never below 16px.\n`);
for (const s of A.SETS) w(`assets/Emblems/${s.id}.svg`, A.emblem(s, 64, { edge: '#8A929C' }).replace('<svg ', '<svg xmlns="http://www.w3.org/2000/svg" '));
w('assets/Emblems/README.md', `# Emblems\n\nThe 32 civilization emblems in their default colours, 64px viewBox, as static files. Each sits in one of four frames (roundel, hexagon, tile, shield). In the product, draw them with \`FarglowArt.emblem(id)\`, along with \`banner(id)\` and \`livery(id)\` for the rest of the set.\n`);

// 3. component cards
const loader = (render) => `<script>
(function(){var s=document.createElement('script');s.src='../../lib/farglow-art.js';s.onload=function(){var A=window.FarglowArt;${render}};document.head.appendChild(s);})();
</script>`;
const head = (marker) => `${marker}
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter+Tight:wght@400;500;600;700&amp;family=IBM+Plex+Mono:wght@400;500&amp;display=swap">
<style>.k{font:500 11px/14px var(--font-mono);letter-spacing:.04em;text-transform:uppercase;color:var(--ink-muted);margin:10px 0 4px}.row{display:flex;flex-wrap:wrap;gap:4px}.cell{width:70px;display:flex;flex-direction:column;align-items:center;gap:3px;font-size:10px;line-height:12px;color:var(--ink-secondary);text-align:center}</style>
</head>`;

w('components/Icon/preview.html', `${head('<!-- @dsCard group="Art" height=560 subtitle="60 game icons · 24px grid · currentColor" -->')}
<body style="margin:0">
<div class="fg-app" id="root" style="padding:16px"></div>
${loader(`var h='';Object.keys(A.ICON_GROUPS).forEach(function(g){h+='<div class="k">'+g+'</div><div class="row">';Object.keys(A.ICON_GROUPS[g]).forEach(function(n){h+='<div class="cell" title="'+n+'">'+A.icon(n,24)+'<span>'+n.replace(/_/g,' ')+'</span></div>';});h+='</div>';});document.getElementById('root').innerHTML=h;`)}
</body>
</html>
`);
w('components/Icon/README.md', `# Icon

Game icons for resources, bodies, space, buildings, fleets, status, objectives and interface. One shared set for every civilization, so any player can read any map.

- Draw with \`FarglowArt.icon(name, size)\` from \`lib/farglow-art.js\`. It returns an inline SVG that strokes in \`currentColor\`, so set the colour on the parent (\`--ink\`, \`--ink-muted\`, \`--accent\` for yours, \`--signal\` for others).
- 24px grid, 1.5px stroke, round caps and joins, no fills except tiny dots.
- Sizes: 16px in dense tables, 20px default, 24px in panel headers. Never below 16px.
- Always pair an icon with a number or a label on game screens. An icon alone is a hint, not data.
- Static single-ink copies live in **assets/Icons** for other tools.
`);

w('components/Emblem/preview.html', `${head('<!-- @dsCard group="Art" height=1220 subtitle="32 civilization sets: emblem, colours, banner, ship livery" -->')}
<body style="margin:0">
<div class="fg-app" id="root" style="padding:16px;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px"></div>
${loader(`var h='';A.SETS.forEach(function(s){h+='<div class="fg-panel" style="gap:4px;padding:8px"><div style="display:flex;gap:6px;align-items:center">'+A.emblem(s,52)+A.banner(s,52)+A.livery(s,52)+'<div style="display:flex;flex-direction:column;gap:4px;margin-left:auto">'+A.emblem(s,24)+A.emblem(s,16)+'</div></div><div style="display:flex;justify-content:space-between;align-items:baseline"><b style="font-size:13px">'+s.name+'</b><span style="display:flex;gap:3px"><i style="width:12px;height:12px;border-radius:2px;background:'+s.primary+'"></i><i style="width:12px;height:12px;border-radius:2px;background:'+s.trim+';border:1px solid var(--border)"></i></span></div><span class="fg-meta">'+s.primaryName+' / '+s.trimName+' · '+s.frame+' · '+s.livery+' · '+s.banner+'</span></div>';});document.getElementById('root').innerHTML=h;`)}
</body>
</html>
`);
w('components/Emblem/README.md', `# Emblem

A civilization set is what a player adopts at sign-up: an **emblem** (charge in a frame), a **colour pair** (field + trim), a **banner pattern** and a **ship livery**. 32 sets ship with the game.

- Draw with \`FarglowArt.emblem(id, size)\`, \`banner(id, size)\` and \`livery(id, size)\`.
- Every field colour is solved to the same brightness (relative luminance about 0.16), so one value reads at least 3.7:1 against both the light and dark backgrounds. That is why emblems need no separate dark versions; only the outline and the hull grey follow the theme (\`--border-strong\`, \`--hull\`).
- Field hues near the UI accent blue and signal orange are left out on purpose. **Civ colour is identity; blue and orange are relation.** On the map, a civ's territory uses its colour, and "you" vs "others" is still shown by the accent ring or the signal badge, never by the civ colour alone.
- Sizes: 16px map marker and table rows, 24px lists, 52-64px panels and banners.
- Motifs were screened to avoid national flags, religious, political and hate symbols (no crescents, crosses, six-point stars, swastika-like rotations, eagles, hammers, double lightning). Any new set must pass the same screen.
- Players pick from the 32 at sign-up; two civs on one server can't hold the same set.
`);

w('components/Planet/preview.html', `${head('<!-- @dsCard group="Art" height=640 subtitle="Procedural planets, stars and belts from a seed" -->')}
<body style="margin:0">
<div class="fg-app" style="padding:16px">
<div style="display:flex;gap:8px;align-items:flex-end"><div class="fg-field"><label class="fg-label" for="seed">Seed</label><input id="seed" class="fg-input" value="41-07-02/hearth" style="width:220px"></div><span class="fg-meta">Same seed, same world. Change it to roll a new system.</span></div>
<div id="root"></div>
</div>
${loader(`function draw(){var seed=document.getElementById('seed').value,h='<div class="k">Stars by class</div><div class="row">';Object.keys(A.STAR_CLASSES).forEach(function(c){h+='<div class="cell">'+A.star(c,56)+'<span>'+c+'</span></div>';});h+='<div class="cell">'+A.star('K',56,{companion:'M'})+'<span>binary K+M</span></div></div>';A.TYPES.forEach(function(t){h+='<div class="k">'+t.replace('_',' ')+'</div><div class="row" style="gap:8px">';for(var i=1;i<=6;i++)h+=A.planet(seed+'/'+i,t,64);h+='</div>';});h+='<div class="k">asteroid belt</div><div class="row">'+A.belt(seed,64)+A.belt(seed+'2',64)+'</div>';document.getElementById('root').innerHTML=h;}draw();document.getElementById('seed').addEventListener('input',draw);`)}
</body>
</html>
`);
w('components/Planet/README.md', `# Planet

Planets, stars and asteroid belts are drawn procedurally, never stored as images. The galaxy has billions of bodies; each is drawn from its seed and type, so the same seed always draws the same world and the server stores nothing.

- \`FarglowArt.planet(seed, type, size)\`: type is one of verdant, ocean, super_earth, rocky, gas_giant, ice. Use the body's permanent id as the seed.
- \`FarglowArt.star(class, size, {companion})\`: class O, B, A, F, G, K or M; companion draws a binary partner.
- \`FarglowArt.belt(seed, size)\`.
- Flat vector style to match the clean scientific look: base colour, features (continents, bands, craters, cracks), clouds, then one flat terminator shadow from the upper left.
- Planet and star colours are physical, not themed; they read on both backgrounds. Lines around them use theme tokens.
- On game screens, buildings, population and garrisons are placed around a planet as icon chips (see the System view board), MOO2-style.
`);

// 4. tokens: civ palette + hull
const tokPath = path.join(P, 'tokens.json');
const tok = JSON.parse(fs.readFileSync(tokPath, 'utf8'));
const have = new Set(tok.color.tokens.map((t) => t.name));
A.PALETTE.forEach((p) => { if (!have.has('civ-' + p.name)) tok.color.tokens.push({ name: 'civ-' + p.name, value: { light: p.hex, dark: p.hex }, usage: 'Civilization field colour. Same in both themes (≥3.7:1 on either background). Identity only, never relation.' }); });
if (!have.has('hull')) tok.color.tokens.push({ name: 'hull', value: { light: '#C9CED6', dark: '#3A434E' }, usage: 'Unpainted ship hull behind a civ livery.' });
fs.writeFileSync(tokPath, JSON.stringify(tok, null, 2));

// 5. section doc
w('Iconography.md', `# Iconography and art

Farglow's art is drawn in code, not stored as pictures. One file, \`lib/farglow-art.js\`, draws every icon, civilization set, planet and star as inline SVG.

## Three kinds of art

| Kind | How many | Theme behaviour |
|---|---|---|
| **Icons** | 60, one shared set for everyone | Stroke in \`currentColor\`; follow the text colour |
| **Civilization sets** | 32: emblem, colour pair, banner, ship livery | Field colours work on both themes; outlines use tokens |
| **Bodies** | Unlimited: planets, stars, belts from a seed | Physical colours; same in both themes |

## Rules

- **Civ colour is identity; blue and orange are relation.** A civ's colour fills its emblem and territory. "You" (accent blue) and "others" (signal orange) are still shown by rings and badges.
- **Every icon on a game screen sits next to a number or label.**
- **No real-world symbols** in emblems: no flags, religious, political or hate symbols.
- **Planets are never stored.** Seed + type in, the same picture out, on every client.

## Logo

Ten concepts are on the Farglow Screens canvas (board 17). The chosen mark moves here after a trademark search.
`);

console.log('done');
