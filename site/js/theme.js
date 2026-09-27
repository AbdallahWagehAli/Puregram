/* Loaded in <head>, before first paint, so the page never flashes the wrong
   palette: the visitor's saved choice wins, otherwise the system setting.
   The key is new on purpose: the previous site saved "dark" for everyone on
   first visit, which would otherwise pin old visitors to dark. */
(function () {
  'use strict';
  var THEME_KEY = 'puregram_theme_choice';
  var theme = null;
  try { theme = localStorage.getItem(THEME_KEY); } catch (e) { /* storage blocked: use the system */ }
  if (theme !== 'light' && theme !== 'dark') {
    var prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    theme = prefersDark ? 'dark' : 'light';
  }
  document.documentElement.setAttribute('data-theme', theme);
})();
