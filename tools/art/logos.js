// Farglow logo concepts. Earthrise-style marks with binary / ternary suns.
// Theme-aware: colours come from CSS variables (--ink, --bg, --ink-muted, --glow, --glow-2).
// 64×64 grid so the marks hold up at 16px.
let uid = 0;
const dome = (r = 40) => {
  const half = 36, sag = r - Math.sqrt(r * r - half * half);
  return `<path d="M-4 64 A${r} ${r} 0 0 1 68 64Z" fill="var(--ink)"/>`;
};
const sun = (x, y, r, c = 'var(--glow)', extra = '') => `<circle cx="${x}" cy="${y}" r="${r}" fill="${c}" ${extra}/>`;
const G2 = 'var(--glow-2)';

const concepts = [
  {
    id: 'binary-rise', name: 'Binary Rise',
    idea: 'The Earthrise photo, retold: two suns climbing over a moon’s horizon. Simplest, strongest at small sizes.',
    svg: () => `${sun(26, 33, 8)}${sun(42.5, 22.5, 4.5, G2)}${dome(44)}`,
  },
  {
    id: 'syzygy', name: 'Syzygy',
    idea: 'Three suns in perfect alignment, the largest half-risen. "Syzygy" is the astronomer’s word for bodies in a line.',
    svg: () => `<path d="M19 46 A13 13 0 0 1 45 46Z" fill="var(--glow)"/>${sun(32, 27.5, 4.5, G2)}${sun(32, 16, 2.5, G2)}<path d="M5 46.5H59" stroke="var(--ink)" stroke-width="3" stroke-linecap="round"/>`,
  },
  {
    id: 'eclipse-rise', name: 'Eclipse Rise',
    idea: 'A world rising over a moon, its rim lit by a sun behind it, with a companion star above. Closest to the real Earthrise.',
    svg: () => `${sun(15, 16, 3, G2)}${sun(33, 36, 13)}<circle cx="35.6" cy="38.4" r="12.4" fill="var(--ink)"/><path d="M-4 64 A40 40 0 0 1 68 64Z" fill="var(--ink)" stroke="var(--bg)" stroke-width="2.5"/>`,
  },
  {
    id: 'twin-dawn', name: 'Twin Dawn',
    idea: 'Two suns breaking the horizon at once. Warm, optimistic, reads as "morning", which suits the daily Dispatch.',
    svg: () => `<path d="M8 50 A17 17 0 0 1 42 50Z" fill="var(--glow)"/><path d="M38 50 A10 10 0 0 1 58 50Z" fill="${G2}"/>${dome(46)}`,
  },
  {
    id: 'porthole', name: 'Porthole',
    idea: 'The binary rise seen through a ship’s viewport. The ring makes it a natural app icon and favicon.',
    svg: () => { const id = `fgp${++uid}`; return `<defs><clipPath id="${id}"><circle cx="32" cy="32" r="25"/></clipPath></defs><g clip-path="url(#${id})">${sun(27, 30, 7.5)}${sun(41, 21, 4, G2)}<path d="M-4 64 A40 40 0 0 1 68 64Z" fill="var(--ink)" transform="translate(0 -6)"/></g><circle cx="32" cy="32" r="27.5" fill="none" stroke="var(--ink)" stroke-width="4"/>`; },
  },
  {
    id: 'long-glow', name: 'Long Glow',
    idea: 'Two suns on a flat horizon with a streak of light between them: the "far glow" itself. Most minimal, most typographic.',
    svg: () => `<path d="M10 40.5H54" stroke="var(--glow)" stroke-width="2" stroke-linecap="round" opacity=".55"/>${sun(24, 34, 6.5)}${sun(41, 35.5, 3.6, G2)}<path d="M4 44.5H60" stroke="var(--ink)" stroke-width="3.2" stroke-linecap="round"/>`,
  },
  {
    id: 'trinary-arc', name: 'Trinary Arc',
    idea: 'Three suns tracing the ecliptic over a horizon. The dashed path hints at motion and orbits; busier at 16px.',
    svg: () => `<path d="M8 42 Q32 4 56 42" fill="none" stroke="var(--ink-muted)" stroke-width="1.4" stroke-dasharray="2 3"/>${sun(20.5, 28, 3.2, G2)}${sun(32, 23, 6)}${sun(43.5, 28, 2.4, G2)}${dome(44)}`,
  },
  {
    id: 'f-horizon', name: 'F-Horizon',
    idea: 'A monogram: the F’s top stroke is a horizon arc and its crossbar is a pair of suns. Works as a letter and a picture.',
    svg: () => `<rect x="13" y="12" width="7.5" height="42" rx="2" fill="var(--ink)"/><path d="M16.5 15.5 Q34 7 52 15" fill="none" stroke="var(--ink)" stroke-width="7" stroke-linecap="round"/>${sun(31, 31, 5)}${sun(43.5, 31, 3, G2)}`,
  },
  {
    id: 'lens', name: 'Lens',
    idea: 'Two overlapping suns form a bright lens where their light meets, setting over a horizon. Elegant; relies on colour.',
    svg: () => `${sun(26.5, 36, 11.5, 'var(--glow)', 'opacity=".9"')}${sun(38.5, 31, 8.5, G2, 'opacity=".85"')}${dome(42)}`,
  },
  {
    id: 'orbit', name: 'Orbit',
    idea: 'A binary pair joined by its shared orbit, rising over a horizon. Says "system" and "motion"; thin line needs ≥24px.',
    svg: () => `<ellipse cx="32" cy="27" rx="17" ry="6.5" fill="none" stroke="var(--ink)" stroke-width="1.6" transform="rotate(-16 32 27)"/>${sun(17.5, 31.5, 5.2)}${sun(46.5, 22.5, 3.2, G2)}${dome(44)}`,
  },
];

const mark = (c, size) => `<svg viewBox="0 0 64 64" width="${size}" height="${size}" style="display:block;overflow:hidden">${c.svg()}</svg>`;
module.exports = { concepts, mark };
