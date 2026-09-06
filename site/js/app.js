(function () {
  'use strict';

  var LANG_KEY = 'puregram_lang';
  var THEME_KEY = 'puregram_theme';
  document.body.classList.add('has-js');

  /* ---- language ------------------------------------------------------ */
  function applyLang(lang) {
    var isAr = lang === 'ar';
    document.documentElement.lang = lang;
    document.documentElement.dir = isAr ? 'rtl' : 'ltr';
    document.body.setAttribute('data-lang', lang);
    document.querySelectorAll('[data-ar]').forEach(function (el) {
      var val = el.getAttribute(isAr ? 'data-ar' : 'data-en');
      if (val != null) el.innerHTML = val;
    });
    var label = document.getElementById('langLabel');
    if (label) label.textContent = isAr ? 'EN' : 'ع';
    try { localStorage.setItem(LANG_KEY, lang); } catch (e) {}
  }

  var savedLang = 'ar';
  try { savedLang = localStorage.getItem(LANG_KEY) || 'ar'; } catch (e) {}
  applyLang(savedLang);

  var langToggle = document.getElementById('langToggle');
  if (langToggle) langToggle.addEventListener('click', function () {
    applyLang(document.body.getAttribute('data-lang') === 'ar' ? 'en' : 'ar');
  });

  /* ---- theme (dark by default; light via the toggle) ----------------- */
  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    var tl = document.getElementById('themeLabel');
    if (tl) tl.textContent = theme === 'dark' ? '☀' : '☾';
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', theme === 'dark' ? '#070C18' : '#F6F8FD');
    try { localStorage.setItem(THEME_KEY, theme); } catch (e) {}
  }
  var savedTheme = 'dark';
  try { savedTheme = localStorage.getItem(THEME_KEY) || 'dark'; } catch (e) {}
  applyTheme(savedTheme);

  var themeToggle = document.getElementById('themeToggle');
  if (themeToggle) themeToggle.addEventListener('click', function () {
    applyTheme(document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
  });

  /* ---- mobile menu --------------------------------------------------- */
  var menuBtn = document.getElementById('menuBtn');
  var navLinks = document.getElementById('navLinks');
  if (menuBtn && navLinks) {
    menuBtn.addEventListener('click', function () {
      var open = navLinks.classList.toggle('open');
      menuBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    navLinks.querySelectorAll('a').forEach(function (a) {
      a.addEventListener('click', function () {
        navLinks.classList.remove('open');
        menuBtn.setAttribute('aria-expanded', 'false');
      });
    });
  }

  /* ---- nav scrolled state -------------------------------------------- */
  var nav = document.getElementById('nav');
  function onScroll() { if (nav) nav.classList.toggle('scrolled', window.scrollY > 16); }
  onScroll();
  window.addEventListener('scroll', onScroll, { passive: true });

  /* ---- FAQ accordion ------------------------------------------------- */
  document.querySelectorAll('.faq-item').forEach(function (item) {
    var q = item.querySelector('.faq-q');
    var a = item.querySelector('.faq-a');
    if (!q || !a) return;
    q.addEventListener('click', function () {
      var open = item.classList.toggle('open');
      q.setAttribute('aria-expanded', open ? 'true' : 'false');
      a.style.maxHeight = open ? a.scrollHeight + 'px' : 0;
    });
  });

  /* ---- reveal on scroll (with bulletproof fallbacks) ----------------- */
  var reveals = document.querySelectorAll('.reveal');
  function reveal(el) { el.classList.add('in'); }
  function revealAll() { reveals.forEach(reveal); }
  function inView(el) {
    var r = el.getBoundingClientRect();
    return r.top < window.innerHeight * 0.95 && r.bottom > 0;
  }

  if (!('IntersectionObserver' in window)) {
    revealAll();
  } else {
    reveals.forEach(function (el) { if (inView(el)) reveal(el); });
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { reveal(en.target); io.unobserve(en.target); }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -6% 0px' });
    reveals.forEach(function (el) { if (!el.classList.contains('in')) io.observe(el); });
    setTimeout(revealAll, 2200);
  }

  /* ---- year ---------------------------------------------------------- */
  var year = document.getElementById('year');
  if (year) year.textContent = new Date().getFullYear();

  /* ---- "coming soon" buttons (Desktop build, notify) ----------------- */
  function showSoon() {
    var t = document.getElementById('soon-toast');
    if (!t) { t = document.createElement('div'); t.id = 'soon-toast'; t.setAttribute('role', 'status'); document.body.appendChild(t); }
    t.textContent = 'قريباً · Coming soon';
    t.classList.add('show');
    clearTimeout(t._h);
    t._h = setTimeout(function () { t.classList.remove('show'); }, 1900);
  }
  document.querySelectorAll('[data-soon]').forEach(function (el) {
    el.addEventListener('click', function (e) { e.preventDefault(); showSoon(); });
  });
})();
