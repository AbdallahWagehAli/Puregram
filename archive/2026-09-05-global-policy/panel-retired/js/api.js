/* ===================================================================
   api.js — shared fetch wrapper, auth guard, and layout helpers for
   the Puregram admin panel. Loaded by every page.
   Exposes a single global: window.Puregram.
   =================================================================== */
(function () {
  'use strict';

  /* ── Backend API base ──────────────────────────────────────────────
     The ONE place to point this panel at a backend. Wire this to the
     real Puregram deployment before going live (see panel/README.md).
     Must NOT have a trailing slash. */
  var API_BASE = 'https://puregram.app/control/v1';

  /* Admin endpoints live under <API_BASE>/admin (login, …). */
  var ADMIN_BASE = API_BASE + '/admin';
  var LOGIN_PAGE = 'login.html';
  var HOME_PAGE = 'policy.html';

  /* ── Error type so callers can branch on HTTP status ───────────── */
  function ApiError(message, status, body) {
    this.name = 'ApiError';
    this.message = message;
    this.status = status;
    this.body = body;
  }
  ApiError.prototype = Object.create(Error.prototype);

  /* ── Core request helper ───────────────────────────────────────
     - Always sends credentials so the HttpOnly JWT cookie travels.
     - Parses JSON when present; tolerates empty 204 bodies.
     - 401 → redirect to login (unless caller opts out, e.g. login itself).
  */
  function request(method, path, body, options) {
    options = options || {};
    var init = {
      method: method,
      credentials: 'include',
      headers: { Accept: 'application/json' },
    };
    if (body !== undefined && body !== null) {
      init.headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(body);
    }

    var url = path.charAt(0) === '/' ? path : ADMIN_BASE + '/' + path;

    return fetch(url, init).then(function (res) {
      if (res.status === 401 && !options.noAuthRedirect) {
        redirectToLogin();
        // Reject so callers stop; the redirect is already underway.
        throw new ApiError('غير مصرّح', 401, null);
      }
      return parseBody(res).then(function (parsed) {
        if (!res.ok) {
          throw new ApiError(extractErrorMessage(parsed, res.status), res.status, parsed);
        }
        return parsed;
      });
    });
  }

  function parseBody(res) {
    if (res.status === 204) return Promise.resolve(null);
    var ctype = res.headers.get('content-type') || '';
    if (ctype.indexOf('application/json') !== -1) {
      return res.json().catch(function () {
        return null;
      });
    }
    return res.text().then(function (t) {
      return t || null;
    });
  }

  function extractErrorMessage(parsed, status) {
    if (parsed && typeof parsed === 'object') {
      if (typeof parsed.error === 'string') return parsed.error;
      if (typeof parsed.message === 'string') return parsed.message;
      if (typeof parsed.detail === 'string') return parsed.detail;
      if (parsed.detail && parsed.detail.message) return parsed.detail.message;
    }
    if (typeof parsed === 'string' && parsed.trim()) return parsed.trim();
    return 'تعذّر تنفيذ الطلب (رمز ' + status + ').';
  }

  function redirectToLogin() {
    var here = window.location.pathname.split('/').pop();
    if (here === LOGIN_PAGE) return;
    window.location.replace(LOGIN_PAGE);
  }

  /* ── Public HTTP verbs ─────────────────────────────────────────── */
  var http = {
    get: function (path, options) {
      return request('GET', path, null, options);
    },
    post: function (path, body, options) {
      return request('POST', path, body, options);
    },
    patch: function (path, body, options) {
      return request('PATCH', path, body, options);
    },
    put: function (path, body, options) {
      return request('PUT', path, body, options);
    },
    del: function (path, body, options) {
      return request('DELETE', path, body, options);
    },
  };

  /* ── Auth session helpers ──────────────────────────────────────── */
  function login(email, password) {
    // noAuthRedirect: a 401 here is an inline "wrong credentials", not a guard trip.
    return http.post('login', { email: email, password: password }, { noAuthRedirect: true });
  }

  function logout() {
    return http
      .post('logout', null, { noAuthRedirect: true })
      .catch(function () {
        // Even if the call fails, clear the client and bounce to login.
        return null;
      })
      .then(function () {
        window.location.replace(LOGIN_PAGE);
      });
  }

  /* Best-effort admin email for the topbar. The login response may carry
     it; we cache it in sessionStorage so it survives page navigation. */
  function rememberAdmin(profile) {
    try {
      var email = '';
      if (profile && typeof profile === 'object') {
        email = profile.email || (profile.admin && profile.admin.email) || (profile.data && profile.data.email) || '';
      }
      if (email) sessionStorage.setItem('puregram_admin_email', email);
    } catch (e) {
      /* sessionStorage may be unavailable; non-fatal */
    }
  }

  function getAdminEmail() {
    try {
      return sessionStorage.getItem('puregram_admin_email') || '';
    } catch (e) {
      return '';
    }
  }

  /* ── Topbar rendering — logo image + page nav ───────────────────── */
  var NAV_PAGES = [
    { href: 'policy.html',  label: 'القائمة العامة' },
  ];

  function renderTopbar() {
    var mount = document.getElementById('topbar');
    if (!mount) return;

    var email = getAdminEmail();
    var emailEl = email
      ? '<span class="admin-email" dir="ltr" title="' + escapeHtml(email) + '">' + escapeHtml(email) + '</span>'
      : '';

    /* Detect active page by filename */
    var currentPage = window.location.pathname.split('/').pop() || 'policy.html';
    var navLinks = NAV_PAGES.map(function (p) {
      var active = (p.href === currentPage || (currentPage === '' && p.href === 'policy.html'))
        ? ' active' : '';
      return '<a href="' + p.href + '" class="' + active.trim() + '">' + escapeHtml(p.label) + '</a>';
    }).join('');

    mount.className = 'topbar';
    mount.innerHTML =
      '<div class="topbar-left">' +
        '<div class="brand-row">' +
          '<img src="img/puregram-control.png" class="logo-img" alt="Puregram Control" width="38" height="38" />' +
          '<span class="brand-name">Puregram Control</span>' +
        '</div>' +
        '<nav class="topbar-nav" aria-label="التنقل بين الصفحات">' +
          navLinks +
        '</nav>' +
      '</div>' +
      '<div class="topbar-right">' +
        emailEl +
        '<button type="button" class="btn btn-ghost btn-sm" id="logout-btn">تسجيل خروج</button>' +
      '</div>';

    var btn = document.getElementById('logout-btn');
    if (btn) {
      btn.addEventListener('click', function () {
        btn.disabled = true;
        logout();
      });
    }
  }

  /* ── Small DOM / formatting utilities ──────────────────────────── */
  function escapeHtml(value) {
    if (value === null || value === undefined) return '';
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function qs(name) {
    var params = new URLSearchParams(window.location.search);
    return params.get(name);
  }

  function formatDateTime(iso) {
    if (!iso) return '—';
    var d = new Date(iso);
    if (isNaN(d.getTime())) return String(iso);
    try {
      return new Intl.DateTimeFormat('ar-EG', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      }).format(d);
    } catch (e) {
      return d.toISOString().replace('T', ' ').slice(0, 16);
    }
  }

  /* Normalizes a list endpoint that may return either a bare array
     or an envelope like { data: [...] } / { items: [...] }. */
  function asArray(payload, key) {
    if (Array.isArray(payload)) return payload;
    if (payload && typeof payload === 'object') {
      if (key && Array.isArray(payload[key])) return payload[key];
      if (Array.isArray(payload.data)) return payload.data;
      if (Array.isArray(payload.items)) return payload.items;
      if (Array.isArray(payload.results)) return payload.results;
    }
    return [];
  }

  /* Renders a single-cell "state" row (loading/empty/error) into a tbody. */
  function tableState(tbody, colspan, kind, message) {
    var inner;
    if (kind === 'loading') {
      inner = '<span class="spinner" aria-hidden="true"></span> <span>جارٍ التحميل…</span>';
    } else if (kind === 'error') {
      inner = '<span style="color:var(--danger)">' + escapeHtml(message || 'حدث خطأ.') + '</span>';
    } else {
      inner = '<span>' + escapeHtml(message || 'لا توجد بيانات.') + '</span>';
    }
    tbody.innerHTML =
      '<tr><td colspan="' + colspan + '"><div class="state">' + inner + '</div></td></tr>';
  }

  function showAlert(el, kind, message) {
    if (!el) return;
    el.className = 'alert alert-' + (kind === 'success' ? 'success' : 'error');
    el.textContent = message;
    el.hidden = false;
  }
  function hideAlert(el) {
    if (el) el.hidden = true;
  }

  /* Debounce for search inputs. */
  function debounce(fn, wait) {
    var t;
    return function () {
      var ctx = this;
      var args = arguments;
      clearTimeout(t);
      t = setTimeout(function () {
        fn.apply(ctx, args);
      }, wait);
    };
  }

  /* ── Page bootstrap: render topbar, then run the page callback ──── */
  function initPage(run) {
    document.addEventListener('DOMContentLoaded', function () {
      renderTopbar();
      try {
        run();
      } catch (e) {
        console.error('Page init failed:', e);
      }
    });
  }

  /* ── Export ────────────────────────────────────────────────────── */
  window.Puregram = {
    API_BASE: API_BASE,
    ADMIN_BASE: ADMIN_BASE,
    HOME_PAGE: HOME_PAGE,
    ApiError: ApiError,
    http: http,
    login: login,
    logout: logout,
    rememberAdmin: rememberAdmin,
    getAdminEmail: getAdminEmail,
    renderTopbar: renderTopbar,
    initPage: initPage,
    escapeHtml: escapeHtml,
    qs: qs,
    formatDateTime: formatDateTime,
    asArray: asArray,
    tableState: tableState,
    showAlert: showAlert,
    hideAlert: hideAlert,
    debounce: debounce,
    redirectToLogin: redirectToLogin,
  };
})();
