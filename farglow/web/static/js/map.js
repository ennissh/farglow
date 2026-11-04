// Farglow star map: vanilla JS + SVG. Data from /api/v1/map (fog of war applied server-side).
// Conventions (design system): your systems = filled accent circle with a ring; other
// civilizations = signal squares; unsurveyed = small muted dots; survey range = accent-soft
// fill with a dashed edge; ships under way = dashed lines; grid every 2 ly.
(function () {
  'use strict';
  var el = document.getElementById('star-map');
  if (!el) return;
  var NS = 'http://www.w3.org/2000/svg';
  var COLORS = (window.FarglowArt && window.FarglowArt.STAR_CLASSES) || {};

  function node(tag, attrs, parent) {
    var n = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (k) { n.setAttribute(k, attrs[k]); });
    if (parent) parent.appendChild(n);
    return n;
  }

  function select(id, data) {
    el.dataset.selected = id;
    draw(data);
    var url = el.dataset.panel.replace('SID', encodeURIComponent(id));
    if (window.htmx) {
      window.htmx.ajax('GET', url, { target: '#system-panel', swap: 'innerHTML' });
    } else {
      window.location = '/play?system=' + encodeURIComponent(id);
    }
    if (window.history && window.history.replaceState) window.history.replaceState(null, '', '/play?system=' + encodeURIComponent(id));
  }

  function draw(data) {
    el.textContent = '';
    var size = data.size;
    var svg = node('svg', { viewBox: '0 0 ' + size + ' ' + size, class: 'fg-map__svg', preserveAspectRatio: 'xMidYMid meet' }, el);
    var grid = node('g', { class: 'fg-map__grid' }, svg);
    for (var v = 0; v <= size; v += 2000) {
      node('line', { x1: v, y1: 0, x2: v, y2: size }, grid);
      node('line', { x1: 0, y1: v, x2: size, y2: v }, grid);
      if (v % 4000 === 0 && v > 0 && v < size) {
        var t = node('text', { x: v + 120, y: size - 200, class: 'fg-map__axis' }, grid);
        t.textContent = (v / 1000) + ' ly';
      }
    }
    var byId = {};
    data.systems.forEach(function (s) { byId[s.id] = s; });
    var range = node('g', { class: 'fg-map__range' }, svg);
    data.owned.forEach(function (id) {
      var s = byId[id];
      node('circle', { cx: s.x, cy: s.y, r: data.survey_range }, range);
    });
    var lanes = node('g', { class: 'fg-map__lanes' }, svg);
    data.missions.forEach(function (m) {
      var tgt = byId[m.target];
      var best = null, bd = Infinity;
      data.owned.forEach(function (id) {
        var o = byId[id], d = Math.hypot(o.x - tgt.x, o.y - tgt.y);
        if (d < bd) { bd = d; best = o; }
      });
      if (best) node('line', { x1: best.x, y1: best.y, x2: tgt.x, y2: tgt.y, class: 'fg-map__lane fg-map__lane--' + m.kind }, lanes);
    });
    var stars = node('g', {}, svg);
    data.systems.forEach(function (s) {
      var g = node('g', { class: 'fg-map__sys' + (s.id === el.dataset.selected ? ' is-selected' : ''), tabindex: '0',
        role: 'button', 'aria-label': s.name }, stars);
      node('circle', { cx: s.x, cy: s.y, r: 700, class: 'fg-map__hit' }, g);
      if (!s.surveyed) {
        node('circle', { cx: s.x, cy: s.y, r: 110, class: 'fg-map__dot' }, g);
      } else if (s.other) {
        node('rect', { x: s.x - 300, y: s.y - 300, width: 600, height: 600, class: 'fg-map__other' }, g);
        node('circle', { cx: s.x, cy: s.y, r: 150, fill: COLORS[s.star] || '#ccc' }, g);
      } else {
        if (s.mine) node('circle', { cx: s.x, cy: s.y, r: 420, class: 'fg-map__ring' }, g);
        node('circle', { cx: s.x, cy: s.y, r: s.mine ? 230 : 180, fill: COLORS[s.star] || '#ccc', class: 'fg-map__star' }, g);
      }
      if (s.id === el.dataset.selected) node('circle', { cx: s.x, cy: s.y, r: 620, class: 'fg-map__sel' }, g);
      var tip = node('title', {}, g);
      tip.textContent = s.name + (s.surveyed ? ' · ' + s.cls + ' · ' + s.bodies + ' bodies' : ' · unsurveyed');
      if (s.mine || s.other || s.named || s.id === el.dataset.selected) {
        var label = node('text', { x: s.x + 520, y: s.y + 160, class: 'fg-map__label' + (s.mine ? ' is-mine' : '') }, g);
        label.textContent = s.name;
        if (s.surveyed && (s.mine || s.id === el.dataset.selected)) {
          var sub = node('text', { x: s.x + 520, y: s.y + 620, class: 'fg-map__sub' }, g);
          sub.textContent = s.cls + (s.home ? ' · HOME' : '') + ' · ' + s.bodies + ' BODIES';
        }
      }
      g.addEventListener('click', function () { select(s.id, data); });
      g.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); select(s.id, data); } });
    });
  }

  fetch(el.dataset.src, { credentials: 'same-origin' })
    .then(function (r) { return r.json(); })
    .then(draw)
    .catch(function () { el.textContent = 'The star map could not load. Reload the page.'; });
})();
