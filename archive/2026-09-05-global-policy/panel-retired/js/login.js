/* login.js — handles the Puregram admin login form. */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    var form = document.getElementById('login-form');
    var emailEl = document.getElementById('email');
    var passwordEl = document.getElementById('password');
    var submitBtn = document.getElementById('login-submit');
    var errorEl = document.getElementById('login-error');

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      Puregram.hideAlert(errorEl);

      var email = emailEl.value.trim();
      var password = passwordEl.value;

      if (!email || !password) {
        Puregram.showAlert(errorEl, 'error', 'يرجى إدخال البريد الإلكتروني وكلمة المرور.');
        return;
      }

      setBusy(true);

      Puregram.login(email, password)
        .then(function (profile) {
          Puregram.rememberAdmin(profile);
          // Fallback: stash the typed email if the API didn't return one.
          if (!Puregram.getAdminEmail()) {
            Puregram.rememberAdmin({ email: email });
          }
          window.location.replace(Puregram.HOME_PAGE);
        })
        .catch(function (err) {
          setBusy(false);
          var msg =
            err && err.status === 401
              ? 'بيانات الدخول غير صحيحة'
              : (err && err.message) || 'تعذّر الاتصال بالخادم. حاول مرة أخرى.';
          Puregram.showAlert(errorEl, 'error', msg);
          passwordEl.value = '';
          passwordEl.focus();
        });
    });

    function setBusy(busy) {
      submitBtn.disabled = busy;
      emailEl.disabled = busy;
      passwordEl.disabled = busy;
      submitBtn.textContent = busy ? 'جارٍ الدخول…' : 'تسجيل الدخول';
    }
  });
})();
