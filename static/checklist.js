/* Checklist: lo stato resta nel localStorage del browser, non sul repo. */
(function () {
  var KEY = 'cina2026:';

  function riga(el) {
    return el.closest('.check');
  }

  function aggiornaBarre() {
    document.querySelectorAll('[data-group]').forEach(function (g) {
      var box = g.querySelectorAll('input[type=checkbox]');
      var fatti = g.querySelectorAll('input[type=checkbox]:checked').length;
      var bar = g.querySelector('.progress i');
      var lab = g.querySelector('.count');
      if (bar) bar.style.width = box.length ? (fatti / box.length) * 100 + '%' : '0';
      if (lab) lab.textContent = fatti + ' / ' + box.length;
    });
    var tutti = document.querySelectorAll('input[type=checkbox]');
    var ok = document.querySelectorAll('input[type=checkbox]:checked').length;
    var tot = document.getElementById('totale');
    if (tot) tot.textContent = ok + ' di ' + tutti.length + ' completate';
  }

  document.querySelectorAll('input[type=checkbox][data-id]').forEach(function (cb) {
    var k = KEY + cb.dataset.id;
    if (localStorage.getItem(k) === '1') {
      cb.checked = true;
      riga(cb).classList.add('done');
    }
    cb.addEventListener('change', function () {
      if (cb.checked) {
        localStorage.setItem(k, '1');
        riga(cb).classList.add('done');
      } else {
        localStorage.removeItem(k);
        riga(cb).classList.remove('done');
      }
      aggiornaBarre();
    });
  });

  var reset = document.getElementById('reset');
  if (reset) {
    reset.addEventListener('click', function () {
      document.querySelectorAll('input[type=checkbox][data-id]').forEach(function (cb) {
        localStorage.removeItem(KEY + cb.dataset.id);
        cb.checked = false;
        riga(cb).classList.remove('done');
      });
      aggiornaBarre();
    });
  }

  aggiornaBarre();
})();
