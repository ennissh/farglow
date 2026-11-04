/* Farglow art library — icons, civilization sets (emblem, colours, livery, banner), procedural planets and stars.
 * One plain script, no dependencies. Browser: window.FarglowArt. Node: require('./farglow-art.js').
 * Everything returns SVG markup strings. Theme-aware: line art uses currentColor or CSS variables
 * (--ink, --bg, --surface-raised, --border-strong), so it switches with the Farglow light/dark theme.
 * Deterministic: the same seed always draws the same planet, so the server stores nothing.
 */
(function (root) {
  'use strict';

  // ---------------------------------------------------------------- utilities
  function hash(str) { // FNV-1a 32-bit
    let h = 0x811c9dc5;
    str = String(str);
    for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 0x01000193); }
    return h >>> 0;
  }
  function rng(seed) { // mulberry32
    let a = typeof seed === 'number' ? seed >>> 0 : hash(seed);
    const r = function () { a |= 0; a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
    r.range = (lo, hi) => lo + (hi - lo) * r();
    r.int = (lo, hi) => Math.floor(r.range(lo, hi + 1));
    r.pick = (arr) => arr[Math.floor(r() * arr.length)];
    return r;
  }
  const f = (n) => Math.round(n * 100) / 100;
  let idc = 0;
  const uid = (p) => `${p}${(++idc).toString(36)}`;
  function hsl(h, s, l) { // → hex
    s /= 100; l /= 100;
    const k = (n) => (n + h / 30) % 12, a = s * Math.min(l, 1 - l);
    const c = (n) => Math.round(255 * (l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)))));
    return '#' + [c(0), c(8), c(4)].map((v) => v.toString(16).padStart(2, '0')).join('');
  }
  function lum(hex) {
    const v = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((c) => (c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)));
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2];
  }
  const contrast = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  function shade(hex, amt) { // amt < 0 darker, > 0 lighter (mix with black/white)
    const t = amt < 0 ? 0 : 255, p = Math.abs(amt);
    return '#' + [1, 3, 5].map((i) => Math.round(parseInt(hex.slice(i, i + 2), 16) * (1 - p) + t * p).toString(16).padStart(2, '0')).join('');
  }
  // smooth closed blob through points (Catmull-Rom → cubic Bézier)
  function blobPath(pts) {
    const n = pts.length; let d = `M${f(pts[0][0])} ${f(pts[0][1])}`;
    for (let i = 0; i < n; i++) {
      const p0 = pts[(i - 1 + n) % n], p1 = pts[i], p2 = pts[(i + 1) % n], p3 = pts[(i + 2) % n];
      d += `C${f(p1[0] + (p2[0] - p0[0]) / 6)} ${f(p1[1] + (p2[1] - p0[1]) / 6)} ${f(p2[0] - (p3[0] - p1[0]) / 6)} ${f(p2[1] - (p3[1] - p1[1]) / 6)} ${f(p2[0])} ${f(p2[1])}`;
    }
    return d + 'Z';
  }
  function blob(r, cx, cy, rad, pts = 8, jag = 0.35) {
    const out = [];
    for (let i = 0; i < pts; i++) { const a = (i / pts) * Math.PI * 2 + r.range(-0.2, 0.2); const k = rad * (1 - jag / 2 + r() * jag); out.push([cx + Math.cos(a) * k, cy + Math.sin(a) * k * r.range(0.75, 1)]); }
    return blobPath(out);
  }
  function polyHex(cx, cy, r, rot = 0) {
    const p = []; for (let i = 0; i < 6; i++) { const a = (Math.PI / 3) * i + rot; p.push(`${f(cx + r * Math.cos(a))} ${f(cy + r * Math.sin(a))}`); }
    return 'M' + p.join('L') + 'Z';
  }

  // ---------------------------------------------------------------- icons (24px grid, 1.5 stroke)
  const ICON_GROUPS = {
    Resources: {
      minerals: '<path d="M5 19l-1.5-6.5L8 7l3.5 5.5L10 19z"/><path d="M11.5 12.5L15 4l5 6.5L18 19h-8"/>',
      energy: '<path d="M13 3L5.5 13.5H11L10 21l7.5-10.5H12z"/>',
      research: '<path d="M9.5 3.5h5M10.5 3.5v5.5l-5 8.6A1.6 1.6 0 0 0 6.9 20h10.2a1.6 1.6 0 0 0 1.4-2.4l-5-8.6V3.5"/><path d="M7.6 14.5h8.8"/>',
      action_credits: '<path d="M12 3l7.8 4.5v9L12 21l-7.8-4.5v-9z"/><path d="M12 8l3.5 2v4L12 16l-3.5-2v-4z"/>',
      population: '<circle cx="9" cy="8" r="3"/><path d="M3.5 19.5a5.5 5.5 0 0 1 11 0"/><circle cx="16.5" cy="9" r="2.5"/><path d="M15.5 14.2a4.5 4.5 0 0 1 5.5 4.3"/>',
      stability: '<rect x="3" y="8.5" width="18" height="7" rx="3.5"/><circle cx="12" cy="12" r="1.6"/><path d="M9 8.5v7M15 8.5v7"/>',
      reputation: '<path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z"/>',
      trade: '<path d="M4 8h15l-3.5-3.5M20 16H5l3.5 3.5"/>',
    },
    Bodies: {
      verdant: '<circle cx="12" cy="12" r="8.5"/><path d="M6 8.5c2.2-.3 3.8.7 4 2.6.2 2 2.3 2.2 3 4 .5 1.3 0 2.6-.8 3.6"/><path d="M14.5 4c-.4 1.8.8 3 2.6 3.2 1.2.1 2.3.7 2.9 1.6"/>',
      ocean: '<circle cx="12" cy="12" r="8.5"/><path d="M4.5 10.5c1.5-.9 3-.9 4.5 0s3 .9 4.5 0 3-.9 4.5 0 1.4.6 2 .6"/><path d="M4.2 14.5c1.5-.9 3-.9 4.5 0s3 .9 4.5 0 3-.9 4.5 0"/>',
      super_earth: '<circle cx="11" cy="13" r="8"/><path d="M3.6 10.5c4.5 1.8 10.2 1.8 14.8 0"/><circle cx="20" cy="4.5" r="1.5"/>',
      rocky: '<circle cx="12" cy="12" r="8.5"/><circle cx="9" cy="9.5" r="1.8"/><circle cx="14.5" cy="14" r="2.3"/><circle cx="9.5" cy="16" r="1"/>',
      gas_giant: '<circle cx="12" cy="12" r="6.5"/><path d="M5.8 10.2h12.4M5.7 13.6h12.6"/><ellipse cx="12" cy="12" rx="10.5" ry="3.2" transform="rotate(-18 12 12)"/>',
      ice: '<circle cx="12" cy="12" r="8.5"/><path d="M8 6.5l2.5 4-3 3.5M10.5 10.5l4 .5 2 3.5M14.5 11l1.5-4.5M10 14l1.5 4"/>',
      belt: '<g fill="currentColor" stroke="none"><circle cx="4.5" cy="15" r="1.2"/><circle cx="8" cy="12" r="1.6"/><circle cx="12.5" cy="10.5" r="1"/><circle cx="16" cy="11.5" r="1.8"/><circle cx="20" cy="9" r="1.1"/><circle cx="10" cy="16" r="1"/><circle cx="17" cy="15.5" r="1.1"/></g>',
    },
    Space: {
      star: '<circle cx="12" cy="12" r="4.5"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M5.3 18.7l2.1-2.1M16.6 7.4l2.1-2.1"/>',
      binary_star: '<circle cx="8.5" cy="13.5" r="4.5"/><circle cx="17.5" cy="7.5" r="2.5"/><path d="M3 19.5c5 2 15-1 18.5-12" stroke-dasharray="1.5 2.5"/>',
      nebula: '<path d="M5 15c-1.5-3 1-6.5 4.5-6 1-3.5 6.5-4 8 0 3 .3 4 4 1.5 5.8 1 2.6-2 4.7-4.5 3.2-1.8 2-5.5 1.6-6-1-2.2.6-3.8-.2-3.5-2z"/><circle cx="12" cy="12" r="1" fill="currentColor" stroke="none"/>',
      anomaly: '<circle cx="12" cy="12" r="2.2"/><path d="M12 5.5a6.5 6.5 0 0 1 6.5 6.5M12 18.5A6.5 6.5 0 0 1 5.5 12M12 2.5a9.5 9.5 0 0 1 9.5 9.5M12 21.5A9.5 9.5 0 0 1 2.5 12"/>',
      survey: '<circle cx="10.5" cy="10.5" r="6"/><path d="M15 15l5.5 5.5"/><circle cx="10.5" cy="10.5" r="1.8"/>',
      comms_range: '<circle cx="12" cy="17" r="1.5"/><path d="M8.5 13.5a5 5 0 0 1 7 0M5.5 10.5a9 9 0 0 1 13 0M2.8 7.6a13 13 0 0 1 18.4 0"/>',
    },
    Buildings: {
      extraction_complex: '<path d="M8 21l4-16 4 16M9.2 16h5.6M10.3 11.5h3.4M4 21h16M12 5V3"/>',
      fusion_plant: '<ellipse cx="12" cy="12" rx="8.5" ry="4.5"/><ellipse cx="12" cy="12" rx="3.5" ry="1.6"/><path d="M12 3.5v3M12 17.5v3"/>',
      research_station: '<path d="M4 20h16M5.5 20v-5a6.5 6.5 0 0 1 13 0v5"/><path d="M12 8.5l5-4"/><path d="M9.5 20v-3h5v3"/>',
      habitat_ring: '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="5.5"/><path d="M12 3.5v3M12 17.5v3M3.5 12h3M17.5 12h3"/><circle cx="12" cy="12" r="1.3"/>',
      civic_forum: '<path d="M3.5 9L12 4l8.5 5z"/><path d="M5.5 9.5v8M10 9.5v8M14 9.5v8M18.5 9.5v8M3.5 20h17M4.5 17.5h15"/>',
      defense_battery: '<path d="M5 20h14v-4a7 7 0 0 0-14 0z"/><path d="M12 13l6-7M17 4.5l2.5 2.5"/>',
      warehouse: '<rect x="3.5" y="12" width="8" height="8" rx="1"/><rect x="12.5" y="12" width="8" height="8" rx="1"/><rect x="8" y="4" width="8" height="8" rx="1"/>',
      shipyard: '<path d="M3 20h18M5 20V6h14v14M5 9h14"/><path d="M8 17.5h8l-1.5-3.5h-5z"/>',
      relay_station: '<path d="M12 9v12M8.5 21l3.5-12 3.5 12"/><circle cx="12" cy="7" r="1.5"/><path d="M8.2 3.8a5 5 0 0 0 0 6.4M15.8 3.8a5 5 0 0 1 0 6.4"/>',
      colony: '<path d="M3 19h18"/><path d="M5.5 19a6.5 6.5 0 0 1 13 0"/><path d="M12 12.5V9M10 9h4"/>',
      outpost: '<path d="M4 20l3-5h10l3 5z"/><path d="M12 15V5M12 5.5h5l-1.5 2 1.5 2h-5"/>',
    },
    Fleet: {
      fleet: '<path d="M12 3l3 6H9zM6 12l3 6H3zM18 12l3 6h-6z"/>',
      scout: '<path d="M12 2.5l3 13-3-2.5-3 2.5z"/><path d="M12 15.5v6"/>',
      warship: '<path d="M12 2.5l4.5 9V20l-4.5-2.5L7.5 20v-8.5z"/><path d="M12 7v7M4 14l3.5-2.5M20 14l-3.5-2.5"/>',
      colony_ship: '<path d="M12 3l4 6v9l-4 3-4-3V9z"/><path d="M9.5 13a2.5 2.5 0 0 1 5 0z"/>',
      freighter: '<rect x="7" y="6" width="10" height="13" rx="2"/><path d="M12 3v3M7 11h10M7 14.5h10"/>',
      garrison: '<path d="M12 3l7.5 3v5.5c0 4.5-3.2 8-7.5 9.5-4.3-1.5-7.5-5-7.5-9.5V6z"/><path d="M8.5 11l3.5-2.5 3.5 2.5M8.5 15l3.5-2.5 3.5 2.5"/>',
    },
    Status: {
      construction: '<path d="M6 20V9l6-5 6 5v11" stroke-dasharray="2.5 2"/><path d="M4 20h16M10 20v-5h4v5"/>',
      blockade: '<path d="M3 12h5M16 12h5M9.5 8.5l5 7M14.5 8.5l-5 7"/>',
      plague: '<circle cx="12" cy="12" r="4"/><path d="M12 4.5V8M12 16v3.5M4.5 12H8M16 12h3.5M6.7 6.7l2.5 2.5M14.8 14.8l2.5 2.5M6.7 17.3l2.5-2.5M14.8 9.2l2.5-2.5"/><g fill="currentColor" stroke="none"><circle cx="12" cy="3.6" r="1.1"/><circle cx="12" cy="20.4" r="1.1"/><circle cx="3.6" cy="12" r="1.1"/><circle cx="20.4" cy="12" r="1.1"/></g>',
      quarantine: '<path d="M12 3l7.5 3v5.5c0 4.5-3.2 8-7.5 9.5-4.3-1.5-7.5-5-7.5-9.5V6z" stroke-dasharray="2.4 2"/><path d="M9 12h6"/>',
      at_war: '<path d="M4 4l11 11M20 4L9 15M14 17l3 3M10 17l-3 3M16.5 13.5l3 3M7.5 13.5l-3 3"/>',
      treaty: '<path d="M6 3h9l3 3v15H6z"/><path d="M9 8h6M9 11h6"/><circle cx="12" cy="16" r="2"/>',
      alliance: '<circle cx="9" cy="12" r="5"/><circle cx="15" cy="12" r="5"/>',
      unsurveyed: '<circle cx="12" cy="12" r="8.5" stroke-dasharray="2 2.5"/><circle cx="12" cy="12" r="1.2" fill="currentColor" stroke="none"/>',
      owned: '<path d="M6 21V4"/><path d="M6 4.5h11l-2.5 3.5 2.5 3.5H6"/>',
      contested: '<path d="M5 21V5M19 21V5"/><path d="M5 5.5h6.5l-1.5 2.5 1.5 2.5H5M19 5.5h-6.5l1.5 2.5-1.5 2.5H19"/>',
      command_lag: '<circle cx="11" cy="13" r="7.5"/><path d="M11 9v4l2.5 2M17 3.5h4v4M21 3.5l-3.5 3.5"/>',
    },
    Objectives: {
      charter: '<path d="M7 4h10a2 2 0 0 1 2 2v12a2 2 0 0 0 2 2H9a2 2 0 0 1-2-2V4z"/><path d="M7 4a2 2 0 0 0-2 2v2h2M10 9h6M10 12.5h6M10 16h3"/>',
      triumph: '<path d="M12 4l1.5 3 3.3.5-2.4 2.3.6 3.2L12 11.5 9 13l.6-3.2-2.4-2.3 3.3-.5z"/><path d="M5 9c-1 4 1 8.5 6 10.5M19 9c1 4-1 8.5-6 10.5M4.5 13l2 .5M5.8 16.3l2-.2M19.5 13l-2 .5M18.2 16.3l-2-.2"/>',
      galactic_event: '<circle cx="16" cy="8" r="3.5"/><path d="M13.5 10.5L4 20M14 12.5L8 18.5M11.5 9.8L5.5 15.8"/>',
      honor: '<circle cx="12" cy="15" r="5"/><path d="M9 3l3 6 3-6M7 3h4M13 3h4"/>',
    },
    Interface: {
      dispatch: '<rect x="3" y="5.5" width="18" height="13" rx="2"/><path d="M3.5 7l8.5 6 8.5-6"/>',
      advisor: '<path d="M4 5.5h16v10H10l-4 3.5v-3.5H4z"/><path d="M12 7.5l.9 1.8 1.9.3-1.4 1.3.3 1.9-1.7-.9-1.7.9.3-1.9-1.4-1.3 1.9-.3z"/>',
      guild: '<path d="M6 3h12v16l-6-3.5L6 19z"/><path d="M9 7.5h6"/>',
      diplomacy: '<path d="M3 5h11v7H8l-3 2.5V12H3z"/><path d="M10 14v2h6l3 2.5V16h2V9h-4"/>',
      settings: '<path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/>',
      alert: '<path d="M12 3.5l9 16H3z"/><path d="M12 10v4.5"/><circle cx="12" cy="17.2" r=".8" fill="currentColor" stroke="none"/>',
      info: '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5.5"/><circle cx="12" cy="7.8" r=".8" fill="currentColor" stroke="none"/>',
    },
  };
  const ICONS = {}; Object.values(ICON_GROUPS).forEach((g) => Object.assign(ICONS, g));
  function icon(name, size = 20, opts = {}) {
    const body = ICONS[name]; if (!body) throw new Error('unknown icon ' + name);
    const stroke = opts.color || 'currentColor';
    return `<svg viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="${stroke}" stroke-width="${opts.weight || 1.5}" stroke-linecap="round" stroke-linejoin="round"${opts.attrs ? ' ' + opts.attrs : ''}>${stroke === 'currentColor' ? body : body.replace(/currentColor/g, stroke)}</svg>`;
  }

  // ---------------------------------------------------------------- civilization colours
  // 16 mid-tone colours, each solved to relative luminance ≈ 0.16 so ONE value reads on both the light
  // background (#F3F4F1) and the dark one (#0F1318) at ≥ 3:1. Hues near the UI accent blue (216°) and
  // signal orange (21°) are left out so a civ colour is never mistaken for "you" or "others".
  const HUES = [
    ['crimson', 355, 62], ['raspberry', 335, 52], ['magenta', 312, 45], ['plum', 290, 38], ['violet', 268, 45], ['indigo', 245, 42],
    ['teal', 186, 70], ['jade', 165, 60], ['fern', 140, 45], ['leaf', 112, 40], ['olive', 75, 45], ['ochre', 48, 75],
    ['umber', 30, 35], ['brick', 8, 55], ['slate', 205, 18], ['graphite', 220, 6],
  ];
  function solveL(h, s, target = 0.16) { let lo = 5, hi = 95; for (let i = 0; i < 30; i++) { const m = (lo + hi) / 2; if (lum(hsl(h, s, m)) < target) lo = m; else hi = m; } return hsl(h, s, (lo + hi) / 2); }
  const PALETTE = HUES.map(([name, h, s]) => ({ name, hex: solveL(h, s) }));
  const TRIMS = [{ name: 'pale', hex: '#FFFFFF' }, { name: 'cream', hex: '#FFF4D6' }, { name: 'ink', hex: '#10151C' }];

  // ---------------------------------------------------------------- emblems
  // Charges are drawn on a 64 grid. {b} = trim colour, {a} = field colour (for cut-outs).
  function gear(cx, cy, ro, ri, teeth) {
    const p = []; const n = teeth * 2;
    for (let i = 0; i < n * 2; i++) { const a = (i / (n * 2)) * Math.PI * 2; const r = (Math.floor(i / 2) % 2 === 0) ? ro : ri; p.push(`${f(cx + r * Math.cos(a))} ${f(cy + r * Math.sin(a))}`); }
    return 'M' + p.join('L') + 'Z';
  }
  function spiralPath(cx, cy, turns, r0, r1, phase) {
    let d = ''; const steps = 60;
    for (let i = 0; i <= steps; i++) { const t = i / steps; const a = phase + t * turns * Math.PI * 2; const r = r0 + (r1 - r0) * t; d += (i ? 'L' : 'M') + f(cx + r * Math.cos(a)) + ' ' + f(cy + r * Math.sin(a)); }
    return d;
  }
  const S = (w) => `fill="none" stroke="{b}" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round"`;
  const CHARGES = {
    orbit: `<circle cx="30" cy="33" r="7.5" fill="{b}"/><ellipse cx="32" cy="32" rx="19" ry="7" ${S(3)} transform="rotate(-25 32 32)"/><circle cx="48" cy="24.5" r="3.2" fill="{b}"/>`,
    comet: `<circle cx="39" cy="25" r="7.5" fill="{b}"/><path d="M33.5 30.5L16 48M37 34L25 46M30.5 27.5L19 39" ${S(3.4)}/>`,
    binary: `<circle cx="25" cy="35" r="8.5" fill="{b}"/><circle cx="42" cy="26" r="5" fill="{b}"/><path d="M15 46C27 52 45 42 50 20" ${S(2.2)} stroke-dasharray="2.5 3.5"/>`,
    lattice: [0, 1, 2, 3, 4, 5].map((i) => `<path d="${polyHex(32 + 11 * Math.cos(Math.PI / 3 * i + Math.PI / 6), 32 + 11 * Math.sin(Math.PI / 3 * i + Math.PI / 6), 5.2)}" ${S(2.4)}/>`).join('') + `<path d="${polyHex(32, 32, 5.2)}" fill="{b}"/>`,
    eye: `<path d="M12 32Q32 14 52 32Q32 50 12 32Z" fill="{b}"/><circle cx="32" cy="32" r="7" fill="{a}"/><circle cx="32" cy="32" r="3" fill="{b}"/>`,
    hand: `<rect x="21" y="30" width="22" height="18" rx="7" fill="{b}"/>` + [[22, 20], [27.2, 15], [32.4, 14], [37.6, 18]].map(([x, y]) => `<rect x="${x}" y="${y}" width="4.6" height="${36 - y}" rx="2.3" fill="{b}"/>`).join('') + `<rect x="13" y="30" width="4.6" height="14" rx="2.3" fill="{b}" transform="rotate(-40 15 37)"/>`,
    flame: `<path d="M32 12C41 23 45 30 43 39C41.5 45 37 49 32 49C26.5 49 21.5 45 21.5 38.5C21.5 32 25.5 28 28 21.5C30 27 31.2 29 33.5 30.5C35 25 34 19 32 12Z" fill="{b}"/>`,
    ringed: `<circle cx="32" cy="32" r="10.5" fill="{b}"/><ellipse cx="32" cy="32" rx="21" ry="5.5" ${S(3)} transform="rotate(-15 32 32)"/>`,
    spiral: `<path d="${spiralPath(32, 32, 1.15, 2, 19, 0)}" ${S(3.4)}/><path d="${spiralPath(32, 32, 1.15, 2, 19, Math.PI)}" ${S(3.4)}/><circle cx="32" cy="32" r="3.5" fill="{b}"/>`,
    compass: `<path d="M32 11L36.5 27.5L53 32L36.5 36.5L32 53L27.5 36.5L11 32L27.5 27.5Z" fill="{b}"/>`,
    chevrons: `<path d="M17 45L32 34L47 45M17 35L32 24L47 35M17 25L32 14L47 25" ${S(4.2)}/>`,
    sprout: `<path d="M32 51V31" ${S(3.4)}/><path d="M32 36C22 36 17 28 17 21C26 21 32 26 32 36Z" fill="{b}"/><path d="M32 31C42 31 47 23 47 16C38 16 32 21 32 31Z" fill="{b}"/>`,
    wave: `<path d="M12 26q5-6 10 0t10 0 10 0 10 0M12 36q5-6 10 0t10 0 10 0 10 0M12 46q5-6 10 0t10 0 10 0 10 0" ${S(3.6)}/>`,
    peak: `<path d="M10 47L26 20L34 32L39 25L54 47Z" fill="{b}"/><path d="M26 20L30.5 27.5H21.5Z" fill="{a}"/>`,
    spire: `<path d="M32 10L37.5 30V47H26.5V30Z" fill="{b}"/><rect x="21" y="45" width="22" height="5.5" rx="1.5" fill="{b}"/><circle cx="32" cy="34" r="2.6" fill="{a}"/>`,
    gear: `<path d="${gear(32, 32, 19, 15, 8)}" fill="{b}"/><circle cx="32" cy="32" r="6.5" fill="{a}"/>`,
    wing: `<path d="M12 42C20 22 37 15 52 15C48 23 43 26 37 27C43 28 45 30 45.5 32.5C39 35 33 35 28.5 34C32 37 32 39.5 30 42C24 44 17 44 12 42Z" fill="{b}"/>`,
    feather: `<path d="M46 12C31 16 20 29 19.5 45L21.5 47C37 46.5 48 34 48 19Z" fill="{b}"/><path d="M15 52L41 21" fill="none" stroke="{a}" stroke-width="2.2" stroke-linecap="round"/>`,
    knot: `<path d="M19 32C19 23 30 23 32 32C34 41 45 41 45 32C45 23 34 23 32 32C30 41 19 41 19 32Z" ${S(4.4)}/>`,
    lantern: `<path d="M28 15.5H36M30 15.5V12.5H34V15.5" ${S(2.4)}/><path d="M23.5 20H40.5L38.5 45H25.5Z" fill="{b}"/><path d="M25.5 49.5H38.5" ${S(3)}/><circle cx="32" cy="32.5" r="4.6" fill="{a}"/>`,
    dart: `<path d="M32 10L47 49L32 40.5L17 49Z" fill="{b}"/>`,
    nautilus: `<path d="${spiralPath(33, 33, 2.1, 1.5, 19, Math.PI * 0.6)}" ${S(4)}/>`,
    crystal: `<path d="M32 10L43 26L36.5 53H27.5L21 26Z" fill="{b}"/><path d="M21.5 26H42.5M32 10.5V52" fill="none" stroke="{a}" stroke-width="1.8"/>`,
    moth: (() => { const w = `<path d="M30.5 28C21 15 11 18 13 29C14.5 34 23 35 30.5 31.5Z" fill="{b}"/><path d="M30.5 34.5C22 36 17.5 44 21 47.5C25 49.5 29.5 43 31 37.5Z" fill="{b}"/>`; return `<ellipse cx="32" cy="33" rx="2.6" ry="11" fill="{b}"/>${w}<g transform="translate(64 0) scale(-1 1)">${w}</g><path d="M31 22.5L27 16M33 22.5L37 16" ${S(1.6)}/>`; })(),
    coil: `<path d="M14 40${[0, 1, 2, 3].map((i) => `C${18 + i * 9} 22 ${24 + i * 9} 22 ${23 + i * 9} 34C${22 + i * 9} 44 ${27 + i * 9} 44 ${29 + i * 9} 36`).join('')}" ${S(3.2)}/>`,
    gate: `<path d="M17 51V30A15 15 0 0 1 47 30V51H39V31A7 7 0 0 0 25 31V51Z" fill="{b}"/>`,
    triad: `<path d="M32 19L21 39H43Z" ${S(2.2)}/><circle cx="32" cy="19" r="6.5" fill="{b}"/><circle cx="21" cy="40" r="6.5" fill="{b}"/><circle cx="43" cy="40" r="6.5" fill="{b}"/>`,
    bridge: `<path d="M10 45Q32 9 54 45" ${S(4)}/><path d="M9 45.5H55" ${S(3.4)}/><path d="M21.5 45V31M32 45V27M42.5 45V31" ${S(2.4)}/>`,
    bloom: [0, 1, 2, 3, 4].map((i) => `<ellipse cx="32" cy="19.5" rx="6" ry="11" fill="{b}" transform="rotate(${i * 72} 32 32)"/>`).join('') + `<circle cx="32" cy="32" r="5" fill="{a}"/>`,
    beacon: `<path d="M27.5 27H36.5L39 51H25Z" fill="{b}"/><path d="M25.5 21H38.5V26H25.5Z" fill="{b}"/><path d="M21 18L14 13.5M43 18L50 13.5M20.5 24.5H12.5M43.5 24.5H51.5" ${S(2.8)}/>`,
    halo: `<circle cx="32" cy="32" r="14.5" ${S(5.2)}/><circle cx="32" cy="32" r="4.5" fill="{b}"/>`,
    signal: `<path d="M21 33A10 10 0 0 1 31 43M21 25A18 18 0 0 1 39 43M21 17A26 26 0 0 1 47 43" ${S(3.6)}/><circle cx="21" cy="43" r="4.5" fill="{b}"/>`,
  };
  const FRAMES = {
    roundel: (s) => `<circle cx="32" cy="32" r="29.5" ${s}/>`,
    hexagon: (s) => `<path d="${polyHex(32, 32, 30.5, Math.PI / 6)}" ${s}/>`,
    tile: (s) => `<rect x="3" y="3" width="58" height="58" rx="14" ${s}/>`,
    shield: (s) => `<path d="M32 2.5L58 10V30C58 46 46.5 56 32 61.5C17.5 56 6 46 6 30V10Z" ${s}/>`,
  };
  const FRAME_CLIP = { roundel: 0.82, hexagon: 0.8, tile: 0.84, shield: 0.78 }; // charge scale inside each frame

  // ---------------------------------------------------------------- liveries & banners
  const HULL = 'M32 4C37.5 15 41.5 29 41.5 45L51 55.5 42 58 40 54H24L22 58 13 55.5 22.5 45C22.5 29 26.5 15 32 4Z';
  const LIVERIES = {
    nose: (A, B) => `<rect x="0" y="0" width="64" height="20" fill="${A}"/><rect x="0" y="20" width="64" height="2.2" fill="${B}"/>`,
    band: (A, B) => `<rect x="0" y="27" width="64" height="11" fill="${A}"/><rect x="0" y="25" width="64" height="1.8" fill="${B}"/><rect x="0" y="38.2" width="64" height="1.8" fill="${B}"/>`,
    twin: (A) => `<rect x="26.6" y="0" width="3.6" height="64" fill="${A}"/><rect x="33.8" y="0" width="3.6" height="64" fill="${A}"/>`,
    chevron: (A, B) => `<path d="M10 40L32 24L54 40V48L32 32L10 48Z" fill="${A}"/><path d="M10 50L32 34L54 50" fill="none" stroke="${B}" stroke-width="1.6"/>`,
    split: (A) => `<rect x="0" y="0" width="32" height="64" fill="${A}"/>`,
    spine: (A, B) => `<rect x="29" y="0" width="6" height="64" fill="${A}"/><rect x="31.2" y="0" width="1.6" height="64" fill="${B}"/>`,
    fins: (A) => `<path d="M0 44H64V64H0Z" fill="${A}"/>`,
    tail: (A, B) => `<rect x="0" y="40" width="64" height="24" fill="${A}"/><path d="M0 38.5H64" stroke="${B}" stroke-width="1.6"/><circle cx="32" cy="14" r="3" fill="${A}"/>`,
  };
  const BANNER = 'M8 2H56V52L32 62L8 52Z';
  const BANNERS = {
    plain: () => '',
    pale: (A, B, D) => `<rect x="25" y="0" width="14" height="64" fill="${D}"/>`,
    fess: (A, B, D) => `<rect x="0" y="40" width="64" height="9" fill="${D}"/>`,
    chevron: (A, B, D) => `<path d="M0 44L32 30L64 44V54L32 40L0 54Z" fill="${D}"/>`,
    bend: (A, B, D) => `<path d="M0 6L10 0L64 50V62Z" fill="${D}"/>`,
    bordure: (A, B, D) => `<path d="${BANNER}" fill="none" stroke="${D}" stroke-width="7"/>`,
    per_pale: (A, B, D) => `<rect x="32" y="0" width="32" height="64" fill="${D}"/>`,
    chief: (A, B, D) => `<rect x="0" y="0" width="64" height="12" fill="${D}"/><rect x="0" y="12" width="64" height="1.6" fill="${B}"/>`,
  };

  // ---------------------------------------------------------------- the 32 sets
  const CHARGE_ORDER = ['orbit', 'comet', 'binary', 'lattice', 'eye', 'hand', 'flame', 'ringed', 'spiral', 'compass', 'chevrons', 'sprout', 'wave', 'peak', 'spire', 'gear',
    'wing', 'feather', 'knot', 'lantern', 'dart', 'nautilus', 'crystal', 'moth', 'coil', 'gate', 'triad', 'bridge', 'bloom', 'beacon', 'halo', 'signal'];
  const SET_NAMES = ['Orbit', 'Comet', 'Binary', 'Lattice', 'Watcher', 'Open Hand', 'Hearthflame', 'Ringworld', 'Spiral', 'Compass', 'Ascent', 'Sprout', 'Tide', 'Summit', 'Spire', 'Engine',
    'Wing', 'Quill', 'Endless Knot', 'Lantern', 'Dart', 'Nautilus', 'Crystal', 'Moth', 'Coil', 'Gate', 'Triad', 'Bridge', 'Bloom', 'Beacon', 'Halo', 'Signal'];
  const FRAME_ORDER = ['roundel', 'hexagon', 'tile', 'shield'];
  const LIVERY_ORDER = Object.keys(LIVERIES), BANNER_ORDER = Object.keys(BANNERS);
  const SETS = CHARGE_ORDER.map((charge, i) => {
    const primary = PALETTE[(i * 7) % 16];               // stride 7 spreads neighbours across the wheel
    const trims = TRIMS.filter((t) => contrast(t.hex, primary.hex) >= 3);
    const trim = trims[i % trims.length];
    return {
      id: charge, name: SET_NAMES[i], charge, frame: FRAME_ORDER[i % 4],
      primary: primary.hex, primaryName: primary.name, trim: trim.hex, trimName: trim.name, deep: shade(primary.hex, -0.35),
      livery: LIVERY_ORDER[(i * 3 + Math.floor(i / 8)) % 8], banner: BANNER_ORDER[(i * 5 + 1) % 8],
    };
  });

  function chargeMarkup(set, A, B, scale) {
    const k = scale, t = 32 - 32 * k;
    return `<g transform="translate(${f(t)} ${f(t)}) scale(${f(k)})">${CHARGES[set.charge].replace(/\{b\}/g, B).replace(/\{a\}/g, A)}</g>`;
  }
  function emblem(setOrId, size = 64, opts = {}) {
    const s = typeof setOrId === 'string' ? SETS.find((x) => x.id === setOrId) : setOrId;
    const A = s.primary, B = s.trim, edge = opts.edge || 'var(--border-strong, #8A929C)';
    return `<svg viewBox="0 0 64 64" width="${size}" height="${size}">${FRAMES[s.frame](`fill="${A}" stroke="${edge}" stroke-width="1"`)}${chargeMarkup(s, A, B, FRAME_CLIP[s.frame])}</svg>`;
  }
  function livery(setOrId, size = 64) {
    const s = typeof setOrId === 'string' ? SETS.find((x) => x.id === setOrId) : setOrId;
    const id = uid('hl');
    return `<svg viewBox="0 0 64 64" width="${size}" height="${size}"><defs><clipPath id="${id}"><path d="${HULL}"/></clipPath></defs><path d="${HULL}" fill="var(--hull, #C9CED6)"/><g clip-path="url(#${id})">${LIVERIES[s.livery](s.primary, s.trim)}</g><path d="${HULL}" fill="none" stroke="var(--ink, #141A22)" stroke-width="1.2" stroke-linejoin="round"/></svg>`;
  }
  function banner(setOrId, size = 64) {
    const s = typeof setOrId === 'string' ? SETS.find((x) => x.id === setOrId) : setOrId;
    const id = uid('bn');
    return `<svg viewBox="0 0 64 64" width="${size}" height="${size}"><defs><clipPath id="${id}"><path d="${BANNER}"/></clipPath></defs><g clip-path="url(#${id})"><path d="${BANNER}" fill="${s.primary}"/>${BANNERS[s.banner](s.primary, s.trim, s.deep)}</g><path d="${BANNER}" fill="none" stroke="var(--border-strong, #8A929C)" stroke-width="1"/><circle cx="32" cy="27" r="13" fill="${s.deep}" stroke="${s.trim}" stroke-width="1.4"/>${chargeMarkup(s, s.deep, s.trim, 0.36).replace('translate(', 'translate(0 -5) translate(')}<path d="M4 2H60" stroke="var(--ink, #141A22)" stroke-width="2.4" stroke-linecap="round"/></svg>`;
  }

  // ---------------------------------------------------------------- stars
  const STAR_CLASSES = { O: '#9BB0FF', B: '#AABFFF', A: '#CAD8FF', F: '#F7F3E6', G: '#FFDF85', K: '#FFB066', M: '#FF7A4D' };
  function star(cls = 'G', size = 64, opts = {}) {
    const c = STAR_CLASSES[cls] || STAR_CLASSES.G, id = uid('sg');
    const r = { O: 15, B: 14, A: 13, F: 12.5, G: 12, K: 11, M: 9.5 }[cls] || 12;
    const companion = opts.companion ? `<circle cx="51" cy="14" r="${opts.companion === 'M' ? 4 : 5}" fill="${STAR_CLASSES[opts.companion]}"/><circle cx="51" cy="14" r="8" fill="${STAR_CLASSES[opts.companion]}" opacity=".18"/>` : '';
    return `<svg viewBox="0 0 64 64" width="${size}" height="${size}"><defs><radialGradient id="${id}"><stop offset="0" stop-color="${c}" stop-opacity=".55"/><stop offset="1" stop-color="${c}" stop-opacity="0"/></radialGradient></defs><circle cx="32" cy="32" r="31" fill="url(#${id})"/><circle cx="32" cy="32" r="${r + 4}" fill="${c}" opacity=".3"/><circle cx="32" cy="32" r="${r}" fill="${c}" stroke="var(--border-strong, #8A929C)" stroke-width=".6" stroke-opacity=".6"/>${companion}</svg>`;
  }

  // ---------------------------------------------------------------- planets
  const TYPES = ['verdant', 'ocean', 'super_earth', 'rocky', 'gas_giant', 'ice'];
  function planet(seed, type, size = 96, opts = {}) {
    const r = rng(`${seed}|${type}`);
    const R = 30, cx = 32, cy = 32, clip = uid('pc'), mask = uid('pm');
    let base, layers = '', rim = '', ring = null;
    const H = (h, s, l) => hsl(h + r.range(-8, 8), s, l + r.range(-4, 4));
    if (type === 'verdant' || type === 'ocean' || type === 'super_earth') {
      const sea = type === 'ocean' ? H(212, 62, 36) : type === 'super_earth' ? H(190, 45, 34) : H(210, 55, 40);
      base = sea;
      const land = [H(r.pick([95, 110, 125]), 38, 38), H(70, 32, 42), H(35, 30, 45)];
      const count = type === 'ocean' ? r.int(2, 4) : type === 'super_earth' ? r.int(5, 7) : r.int(4, 6);
      const size0 = type === 'ocean' ? [2.5, 5] : type === 'super_earth' ? [8, 14] : [6, 11];
      for (let i = 0; i < count; i++) {
        const x = r.range(8, 56), y = r.range(12, 52), rad = r.range(size0[0], size0[1]);
        layers += `<path d="${blob(r, x, y, rad, 9, 0.5)}" fill="${land[0]}"/>`;
        if (type !== 'ocean' && r() < 0.6) layers += `<path d="${blob(r, x + r.range(-2, 2), y + r.range(-2, 2), rad * 0.45, 7, 0.5)}" fill="${r.pick(land.slice(1))}"/>`;
      }
      if (type !== 'ocean' || r() < 0.5) layers += `<path d="${blob(r, 32, 2.5, r.range(9, 14), 8, 0.3)}" fill="#F4F7FA" opacity=".9"/><path d="${blob(r, 32, 61.5, r.range(7, 12), 8, 0.3)}" fill="#F4F7FA" opacity=".85"/>`;
      const clouds = type === 'ocean' ? r.int(5, 8) : r.int(3, 6);
      for (let i = 0; i < clouds; i++) { const y = r.range(8, 56), x = r.range(4, 50), w = r.range(10, 22); layers += `<path d="M${f(x)} ${f(y)}q${f(w / 2)} ${f(r.range(-4, 4))} ${f(w)} 0" fill="none" stroke="#FFFFFF" stroke-width="${f(r.range(1.6, 3.2))}" stroke-linecap="round" opacity=".75"/>`; }
      rim = `<circle cx="${cx}" cy="${cy}" r="${R + 0.6}" fill="none" stroke="#9CC9FF" stroke-width="1.6" opacity=".55"/>`;
    } else if (type === 'rocky') {
      const hue = r.pick([25, 35, 0, 210]), sat = hue === 210 ? 8 : 18;
      base = H(hue, sat, 52);
      for (let i = 0; i < r.int(2, 4); i++) layers += `<path d="${blob(r, r.range(10, 54), r.range(10, 54), r.range(6, 12), 8, 0.55)}" fill="${hsl(hue, sat, 40)}" opacity=".8"/>`;
      for (let i = 0; i < r.int(7, 13); i++) { const x = r.range(6, 58), y = r.range(6, 58), cr = r.range(1.2, 4.5); layers += `<circle cx="${f(x)}" cy="${f(y)}" r="${f(cr)}" fill="${hsl(hue, sat, 38)}"/><path d="M${f(x - cr)} ${f(y)}a${f(cr)} ${f(cr)} 0 0 1 ${f(cr * 2)} 0" fill="none" stroke="${hsl(hue, sat, 68)}" stroke-width=".8"/>`; }
    } else if (type === 'gas_giant') {
      const warm = r() < 0.6, hue = warm ? r.range(25, 42) : r.range(190, 215);
      base = hsl(hue, warm ? 45 : 35, 62);
      let y = 0;
      while (y < 64) { const h = r.range(3, 9); const l = r.range(42, 72); const amp = r.range(0.5, 2); layers += `<path d="M-4 ${f(y)}q8 ${f(amp)} 16 0t16 0 16 0 16 0 16 0V${f(y + h)}H-4Z" fill="${hsl(hue + r.range(-10, 10), warm ? 40 : 32, l)}" opacity=".85"/>`; y += h; }
      if (r() < 0.55) layers += `<ellipse cx="${f(r.range(18, 46))}" cy="${f(r.range(36, 48))}" rx="${f(r.range(4, 7))}" ry="${f(r.range(2, 3.2))}" fill="${hsl(warm ? 12 : 230, 50, 48)}" opacity=".85"/>`;
      if (opts.ring ?? r() < 0.45) ring = { tilt: r.range(-24, -8), col: hsl(hue, 25, 70) };
    } else if (type === 'ice') {
      base = H(200, 35, 84);
      for (let i = 0; i < r.int(2, 4); i++) layers += `<path d="${blob(r, r.range(10, 54), r.range(10, 54), r.range(6, 12), 8, 0.5)}" fill="${hsl(205, 40, 74)}"/>`;
      for (let i = 0; i < r.int(4, 7); i++) { let x = r.range(4, 60), y = r.range(4, 60), d = `M${f(x)} ${f(y)}`; for (let k = 0; k < 4; k++) { x += r.range(-9, 9); y += r.range(-9, 9); d += `L${f(x)} ${f(y)}`; } layers += `<path d="${d}" fill="none" stroke="${hsl(210, 45, 55)}" stroke-width=".9" opacity=".8"/>`; }
    } else throw new Error('unknown planet type ' + type);

    const shadow = `<mask id="${mask}"><rect x="0" y="0" width="64" height="64" fill="#fff"/><circle cx="${f(cx - R * 0.42)}" cy="${f(cy - R * 0.3)}" r="${f(R * 1.08)}" fill="#000"/></mask><rect x="0" y="0" width="64" height="64" fill="#04070C" opacity=".46" mask="url(#${mask})"/>`;
    const ringBack = ring ? `<ellipse cx="32" cy="32" rx="44" ry="9" fill="none" stroke="${ring.col}" stroke-width="3.2" opacity=".85" transform="rotate(${f(ring.tilt)} 32 32)" clip-path="url(#${clip}b)"/>` : '';
    const ringFront = ring ? `<ellipse cx="32" cy="32" rx="44" ry="9" fill="none" stroke="${ring.col}" stroke-width="3.2" transform="rotate(${f(ring.tilt)} 32 32)" clip-path="url(#${clip}f)"/>` : '';
    const ringClips = ring ? `<clipPath id="${clip}b"><rect x="-20" y="-20" width="104" height="52" transform="rotate(${f(ring.tilt)} 32 32)"/></clipPath><clipPath id="${clip}f"><rect x="-20" y="32" width="104" height="52" transform="rotate(${f(ring.tilt)} 32 32)"/></clipPath>` : '';
    const vb = ring ? '-14 -14 92 92' : '0 0 64 64';
    return `<svg viewBox="${vb}" width="${size}" height="${size}"><defs><clipPath id="${clip}"><circle cx="${cx}" cy="${cy}" r="${R}"/></clipPath>${ringClips}</defs>${ringBack}<g clip-path="url(#${clip})"><rect x="0" y="0" width="64" height="64" fill="${base}"/>${layers}${shadow}</g>${rim}${ringFront}</svg>`;
  }
  function belt(seed, size = 96) {
    const r = rng(`${seed}|belt`); let out = '';
    for (let i = 0; i < 26; i++) { const a = r.range(-0.9, 0.9), rad = r.range(24, 34); const x = 32 + Math.sin(a) * 40, y = 58 - Math.cos(a) * rad; out += `<path d="${blob(r, x, y, r.range(0.9, 2.6), 6, 0.6)}" fill="${hsl(r.range(20, 40), 14, r.range(42, 62))}"/>`; }
    return `<svg viewBox="0 0 64 64" width="${size}" height="${size}">${out}</svg>`;
  }

  const api = { version: '0.1.0', hash, rng, contrast, lum, ICON_GROUPS, ICONS, icon, PALETTE, TRIMS, SETS, FRAMES: Object.keys(FRAMES), LIVERIES: LIVERY_ORDER, BANNERS: BANNER_ORDER, emblem, livery, banner, STAR_CLASSES, star, TYPES, planet, belt };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.FarglowArt = api;
})(typeof window !== 'undefined' ? window : globalThis);
