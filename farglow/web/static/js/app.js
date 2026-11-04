// Small behaviours that would otherwise need inline handlers (the CSP forbids them).
(function () {
  'use strict';
  function icons(root) {
    if (!window.FarglowArt) return;
    (root || document).querySelectorAll('[data-icon]:empty').forEach(function (el) {
      try { el.innerHTML = window.FarglowArt.icon(el.dataset.icon, 14); } catch (e) { /* unknown icon name */ }
    });
  }
  document.addEventListener('DOMContentLoaded', function () { icons(document); });
  document.addEventListener('htmx:afterSwap', function (e) { icons(e.target); });
  document.addEventListener('htmx:afterRequest', function (e) {
    var form = e.target && e.target.closest && e.target.closest('form[data-reset-after]');
    if (form && e.detail.successful) {
      form.reset();
      var chat = document.getElementById('advisor-chat');
      if (chat && chat.lastElementChild) chat.lastElementChild.scrollIntoView({ block: 'nearest' });
    }
  });
  // one open pop-over at a time; a click outside closes it
  document.addEventListener('click', function (e) {
    document.querySelectorAll('details.fg-pop[open]').forEach(function (d) { if (!d.contains(e.target)) d.removeAttribute('open'); });
  });
})();
