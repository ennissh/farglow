// Founding page: draw the 32 civilization sets with the art library and keep the attribute sum honest.
(function () {
  'use strict';
  var A = window.FarglowArt;
  if (A) {
    document.querySelectorAll('[data-set]').forEach(function (el) {
      var set = A.SETS[+el.dataset.set];
      if (set) el.innerHTML = A.emblem(set, 56);
    });
    document.querySelectorAll('[data-set-name]').forEach(function (el) {
      var set = A.SETS[+el.dataset.setName];
      if (set) el.textContent = set.name;
    });
  }
  var inputs = document.querySelectorAll('[data-attr]');
  var out = document.getElementById('attr-sum');
  function sum() {
    var s = 0;
    inputs.forEach(function (i) { s += parseInt(i.value || '0', 10); });
    out.textContent = (s > 0 ? '+' : '') + s;
    out.classList.toggle('fg-danger', s !== 0);
  }
  inputs.forEach(function (i) { i.addEventListener('input', sum); });
  sum();
})();
