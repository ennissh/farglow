// Small behaviours that would otherwise need inline handlers (the CSP forbids them).
(function () {
  'use strict';
  document.addEventListener('htmx:afterRequest', function (e) {
    var form = e.target && e.target.closest && e.target.closest('form[data-reset-after]');
    if (form && e.detail.successful) {
      form.reset();
      var chat = document.getElementById('advisor-chat');
      if (chat && chat.lastElementChild) chat.lastElementChild.scrollIntoView({ block: 'nearest' });
    }
  });
})();
