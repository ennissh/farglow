// Chosen logo: F-Horizon. Writes static SVGs into the design system and marks the choice on board 17.
const fs = require('fs'), path = require('path');
const { concepts } = require('./logos');
const P = process.argv[2];
const c = concepts.find((x) => x.id === 'f-horizon');
const THEMES = { light: { ink: '#141A22', glow: '#D2790F', glow2: '#1D5BB8', bg: '#F3F4F1' }, dark: { ink: '#E6EAEF', glow: '#F5B547', glow2: '#8DB6F4', bg: '#0F1318' } };
const paint = (svg, t) => svg.replace(/var\(--ink\)/g, t.ink).replace(/var\(--glow-2\)/g, t.glow2).replace(/var\(--glow\)/g, t.glow).replace(/var\(--bg\)/g, t.bg);
const X = 'xmlns="http://www.w3.org/2000/svg"';
const w = (rel, s) => { const p = path.join(P, rel); fs.mkdirSync(path.dirname(p), { recursive: true }); fs.writeFileSync(p, s); };
for (const [k, t] of Object.entries(THEMES)) {
  w(`assets/Logo/farglow-mark-${k}.svg`, `<svg ${X} viewBox="0 0 64 64" width="64" height="64">${paint(c.svg(), t)}</svg>`);
  w(`assets/Logo/farglow-lockup-${k}.svg`, `<svg ${X} viewBox="0 0 230 64" width="230" height="64">${paint(c.svg(), t)}<text x="64" y="44" font-family="Inter Tight, Inter, system-ui, sans-serif" font-size="38" font-weight="700" letter-spacing="-0.76" fill="${t.ink}">farglow</text></svg>`);
}
// favicon follows the OS theme by itself
w('assets/Logo/favicon.svg', `<svg ${X} viewBox="0 0 64 64"><style>.i{fill:${THEMES.light.ink}}.s{stroke:${THEMES.light.ink}}.g{fill:${THEMES.light.glow}}.h{fill:${THEMES.light.glow2}}@media (prefers-color-scheme:dark){.i{fill:${THEMES.dark.ink}}.s{stroke:${THEMES.dark.ink}}.g{fill:${THEMES.dark.glow}}.h{fill:${THEMES.dark.glow2}}}</style><rect class="i" x="13" y="12" width="7.5" height="42" rx="2"/><path class="s" d="M16.5 15.5 Q34 7 52 15" fill="none" stroke-width="7" stroke-linecap="round"/><circle class="g" cx="31" cy="31" r="5"/><circle class="h" cx="43.5" cy="31" r="3"/></svg>`);
w('assets/Logo/README.md', `# Logo

**F-Horizon**, chosen Nov 2026. A monogram: the F's top stroke is a horizon arc and its crossbar is a pair of suns, a binary rising (the Earthrise idea).

- \`farglow-mark-light.svg\` / \`farglow-mark-dark.svg\`: the mark alone. Inks: light ${THEMES.light.ink}, glow ${THEMES.light.glow}, companion ${THEMES.light.glow2}; dark ${THEMES.dark.ink}, ${THEMES.dark.glow}, ${THEMES.dark.glow2}.
- \`farglow-lockup-*.svg\`: mark + lowercase wordmark in Inter Tight 700. The wordmark is live text here; convert it to outlines before print or merch.
- \`favicon.svg\`: switches itself with the OS light/dark setting.
- Gold is the **brand glow**, used only in the logo, never as a UI colour. The companion sun is the "you" accent blue.
- Smallest size: 16px (favicon). Clear space: half the mark's width on every side.
- **Before launch:** trademark search on the name and the mark.
`);
// tokens: brand glow
const tp = path.join(P, 'tokens.json'), tok = JSON.parse(fs.readFileSync(tp, 'utf8'));
if (!tok.color.tokens.some((t) => t.name === 'brand-glow')) tok.color.tokens.push({ name: 'brand-glow', value: { light: THEMES.light.glow, dark: THEMES.dark.glow }, usage: 'The larger sun in the F-Horizon logo. Logo only; never a UI colour.' });
fs.writeFileSync(tp, JSON.stringify(tok, null, 2));
// Iconography.md logo section
const ip = path.join(P, 'Iconography.md'); let doc = fs.readFileSync(ip, 'utf8');
doc = doc.replace(/## Logo[\s\S]*$/, `## Logo\n\n**F-Horizon** is the Farglow mark: the F's top stroke is a horizon arc, its crossbar a binary pair of suns rising. Files and rules are in **assets/Logo**. The other nine concepts stay on the Farglow Screens canvas (board 17) for reference. Run a trademark search before launch.\n`);
fs.writeFileSync(ip, doc);
console.log('logo assets written');
