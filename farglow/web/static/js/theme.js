// Theme: the saved choice, else the OS preference (design-system README). Loaded in <head>
// so the page never flashes the wrong theme; CSP forbids inline scripts.
(function () {
  var saved = null;
  try { saved = localStorage.getItem('fg-theme'); } catch (e) { /* storage blocked */ }
  var dark = window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches;
  document.documentElement.dataset.theme = saved || (dark ? 'dark' : 'light');
  document.addEventListener('click', function (ev) {
    if (!ev.target.closest('[data-theme-toggle]')) return;
    var next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem('fg-theme', next); } catch (e) { /* storage blocked */ }
  });
})();
