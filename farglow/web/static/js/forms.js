// Governor: live total of the allocation shares.
(function () {
  'use strict';
  var inputs = document.querySelectorAll('[data-alloc]');
  var out = document.getElementById('alloc-sum');
  if (!out) return;
  function sum() {
    var s = 0;
    inputs.forEach(function (i) {
      s += parseInt(i.value || '0', 10);
      var label = document.querySelector('[data-alloc-label="' + i.name + '"]');
      if (label) label.textContent = (i.value || 0) + '%';
    });
    out.textContent = s;
    out.classList.toggle('fg-danger', s !== 100);
  }
  inputs.forEach(function (i) { i.addEventListener('input', sum); });
  sum();
})();
