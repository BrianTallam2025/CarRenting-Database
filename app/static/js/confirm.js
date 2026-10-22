/* F3: one small confirm dialog for links and forms.
   Add data-confirm="Are you sure?" to a form or an <a> element. */
document.addEventListener('click', function (event) {
  var link = event.target.closest ? event.target.closest('a[data-confirm]') : null;
  if (link && !window.confirm(link.getAttribute('data-confirm'))) {
    event.preventDefault();
  }
});

document.addEventListener('submit', function (event) {
  var message = event.target.getAttribute('data-confirm');
  if (message && !window.confirm(message)) {
    event.preventDefault();
  }
});
