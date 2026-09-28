/* Puregram site: language switch and the decision simulation.
   Every translatable node carries data-ar / data-en. The markup ships in
   Arabic, so the page reads correctly before (or without) this script. */
(function () {
  'use strict';

  var LANG_KEY = 'puregram_lang';
  var COLLAPSE_MS = 500; // matches the .chat-row max-height transition, plus a frame
  var THEME_KEY = 'puregram_theme_choice'; // shared with js/theme.js
  var THEME_COLORS = { light: '#f5f7f5', dark: '#0e1511' };
  var THEME_LABELS = {
    ar: { light: 'تفعيل الوضع الداكن', dark: 'تفعيل الوضع الفاتح' },
    en: { light: 'Switch to dark mode', dark: 'Switch to light mode' }
  };
  var LANGS = { ar: { dir: 'rtl', toggle: 'English', toggleLang: 'en' },
                en: { dir: 'ltr', toggle: 'العربية', toggleLang: 'ar' } };

  function readSavedLang() {
    try {
      var saved = localStorage.getItem(LANG_KEY);
      return LANGS[saved] ? saved : 'ar';
    } catch (e) {
      return 'ar';
    }
  }

  function saveLang(lang) {
    try { localStorage.setItem(LANG_KEY, lang); } catch (e) { /* storage blocked: session-only choice */ }
  }

  var currentLang = readSavedLang();

  /* Theme */
  // js/theme.js already applied the starting theme before first paint; this
  // wires the switch and keeps following the system until the visitor chooses.
  function currentTheme() {
    return document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
  }

  function hasSavedTheme() {
    try {
      var saved = localStorage.getItem(THEME_KEY);
      return saved === 'light' || saved === 'dark';
    } catch (e) {
      return false;
    }
  }

  function renderThemeToggle() {
    var toggle = document.getElementById('themeToggle');
    if (!toggle) return;
    var label = THEME_LABELS[currentLang][currentTheme()];
    toggle.setAttribute('aria-label', label);
    toggle.setAttribute('title', label);
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', THEME_COLORS[theme]);
    renderThemeToggle();
  }

  function chooseTheme(theme) {
    applyTheme(theme);
    try { localStorage.setItem(THEME_KEY, theme); } catch (e) { /* storage blocked: session-only choice */ }
  }

  /* Language */
  // Copy is authored in this repository, never user supplied, so innerHTML is
  // safe here and lets a few strings carry inline emphasis.
  function translateNodes(lang) {
    document.querySelectorAll('[data-' + lang + ']').forEach(function (el) {
      el.innerHTML = el.getAttribute('data-' + lang);
    });
  }

  // On phones the rule table restacks into cards; each cell then shows its
  // column heading, taken from the (already translated) table head.
  function labelRuleCells() {
    document.querySelectorAll('table.rule').forEach(function (table) {
      var heads = Array.prototype.map.call(table.querySelectorAll('thead th'), function (th) {
        return th.textContent;
      });
      table.querySelectorAll('tbody tr').forEach(function (row) {
        Array.prototype.forEach.call(row.children, function (cell, index) {
          if (cell.tagName === 'TD') cell.setAttribute('data-col', heads[index] || '');
        });
      });
    });
  }

  function applyLang(lang) {
    var spec = LANGS[lang];
    currentLang = lang;
    document.documentElement.lang = lang;
    document.documentElement.dir = spec.dir;
    translateNodes(lang);
    labelRuleCells();

    var toggle = document.getElementById('langToggle');
    if (toggle) {
      toggle.textContent = spec.toggle;
      toggle.setAttribute('lang', spec.toggleLang);
    }
    saveLang(lang);
    renderThemeToggle();
    demo.render();
  }

  /* Decision simulation */
  var STRINGS = {
    ar: {
      askTitle: { channel: 'لم تسمح بهذه القناة بعد', bot: 'لم تسمح بهذا البوت بعد', group: 'لم تسمح بهذه المجموعة بعد' },
      askBody: 'لا يُفتح شيء من القنوات والبوتات والمجموعات إلا بإذنك. قرارك هنا يُحفظ مع حسابك على كل أجهزتك.',
      allow: 'السماح',
      block: 'حجب نهائي',
      confirmTitle: 'هل تريد الحجب النهائي؟',
      confirmBody: 'بعد التأكيد لن تُفتح هذه المحادثة مرة أخرى، لا على هذا الجهاز ولا على أي جهاز آخر. لا توجد طريقة للتراجع.',
      confirm: 'تأكيد الحجب النهائي',
      back: 'رجوع',
      allowedBadge: 'مسموح',
      toast: {
        person: 'المحادثات مع الناس تُفتح دائماً، دون أي سؤال.',
        allowed: 'تم السماح. تستطيع سحب السماح لاحقاً متى شئت.',
        open: 'مسموح بها، فتُفتح المحادثة مباشرة.',
        blocked: 'حُجبت نهائياً واختفت من القائمة، ولن تصلك منها إشعارات.'
      }
    },
    en: {
      askTitle: { channel: "You haven't allowed this channel yet", bot: "You haven't allowed this bot yet", group: "You haven't allowed this group yet" },
      askBody: 'No channel, bot or group opens without your permission. What you decide here is saved with your account, on every device.',
      allow: 'Allow',
      block: 'Block forever',
      confirmTitle: 'Block forever?',
      confirmBody: 'Once confirmed, this chat will never open again, on this device or any other. There is no way to undo it.',
      confirm: 'Confirm permanent block',
      back: 'Go back',
      allowedBadge: 'Allowed',
      toast: {
        person: 'Chats with people always open, with no question asked.',
        allowed: 'Allowed. You can withdraw it later whenever you like.',
        open: 'Allowed, so the chat opens directly.',
        blocked: 'Blocked forever. It left your list and will never notify you.'
      }
    }
  };

  var demo = (function () {
    var list = document.getElementById('demoList');
    var toast = document.getElementById('demoToast');
    var count = document.getElementById('tallyCount');
    var tally = document.getElementById('tally');
    var note = document.getElementById('demoNote');
    var reset = document.getElementById('demoReset');
    var enabled = Boolean(list && toast && count && tally && note && reset);

    var state = { openRow: null, step: 'ask', toastKey: null, blocked: 0 };
    var gate = document.createElement('div');
    gate.className = 'gate';

    function t() { return STRINGS[currentLang]; }

    function button(label, className, onClick) {
      var el = document.createElement('button');
      el.type = 'button';
      el.className = 'btn btn-sm ' + className;
      el.textContent = label;
      el.addEventListener('click', onClick);
      return el;
    }

    function renderGate() {
      var s = t();
      var row = state.openRow;
      var isConfirm = state.step === 'confirm';
      gate.classList.toggle('is-final', isConfirm);
      gate.textContent = '';

      var title = document.createElement('h3');
      title.id = 'gateTitle';
      title.textContent = isConfirm ? s.confirmTitle : s.askTitle[row.getAttribute('data-kind')];
      var body = document.createElement('p');
      body.textContent = isConfirm ? s.confirmBody : s.askBody;
      var actions = document.createElement('div');
      actions.className = 'actions';

      if (isConfirm) {
        actions.appendChild(button(s.confirm, 'btn-seal-solid', confirmBlock));
        actions.appendChild(button(s.back, 'btn-quiet', function () { setStep('ask', 0); }));
      } else {
        actions.appendChild(button(s.allow, 'btn-allow', allowRow));
        actions.appendChild(button(s.block, 'btn-seal', function () { setStep('confirm', 1); }));
      }
      gate.setAttribute('role', 'group');
      gate.setAttribute('aria-labelledby', 'gateTitle');
      gate.appendChild(title);
      gate.appendChild(body);
      gate.appendChild(actions);
    }

    function setStep(step, focusIndex) {
      state.step = step;
      renderGate();
      var target = gate.querySelectorAll('button')[focusIndex];
      if (target) target.focus();
    }

    function showToast(key) {
      state.toastKey = key;
      renderToast();
    }

    function renderToast() {
      toast.hidden = !state.toastKey;
      toast.setAttribute('data-tone', state.toastKey === 'blocked' ? 'seal' : 'green');
      toast.textContent = state.toastKey ? t().toast[state.toastKey] : '';
    }

    function closeGate() {
      if (!state.openRow) return;
      state.openRow.querySelector('.chat').setAttribute('aria-expanded', 'false');
      if (gate.parentNode) gate.parentNode.removeChild(gate);
      state.openRow = null;
    }

    function openGate(row) {
      closeGate();
      state.openRow = row;
      state.step = 'ask';
      row.querySelector('.chat').setAttribute('aria-expanded', 'true');
      renderGate();
      row.appendChild(gate);
    }

    function allowRow() {
      var row = state.openRow;
      var chat = row.querySelector('.chat');
      var badge = row.querySelector('.kind');
      chat.classList.add('is-allowed');
      chat.removeAttribute('aria-expanded');
      badge.setAttribute('data-ar', STRINGS.ar.allowedBadge);
      badge.setAttribute('data-en', STRINGS.en.allowedBadge);
      badge.textContent = t().allowedBadge;
      closeGate();
      showToast('allowed');
      chat.focus();
    }

    function confirmBlock() {
      var row = state.openRow;
      closeGate();
      // Pin the current height, then collapse to zero so the transition runs.
      row.style.maxHeight = row.offsetHeight + 'px';
      void row.offsetHeight;
      row.style.maxHeight = '0px';
      row.classList.add('is-gone');
      // Take it out of layout once the collapse is done, even where the
      // browser skipped the transition (background tab, reduced motion).
      setTimeout(function () { if (row.classList.contains('is-gone')) row.hidden = true; }, COLLAPSE_MS);
      row.setAttribute('aria-hidden', 'true');
      row.querySelector('.chat').tabIndex = -1;
      state.blocked += 1;
      renderTally();
      showToast('blocked');
      var next = firstVisibleChat();
      (next || reset).focus();
    }

    function firstVisibleChat() {
      var rows = list.querySelectorAll('.chat-row:not(.is-gone) .chat');
      return rows.length ? rows[0] : null;
    }

    function renderTally() {
      count.textContent = String(state.blocked);
      tally.classList.toggle('is-live', state.blocked > 0);
      note.hidden = state.blocked === 0;
      reset.hidden = state.blocked === 0;
    }

    function onChatClick(event) {
      var chat = event.target.closest('.chat');
      if (!chat || !list.contains(chat)) return;
      var row = chat.parentNode;
      if (row.getAttribute('data-kind') === 'person') {
        closeGate();
        showToast('person');
      } else if (chat.classList.contains('is-allowed')) {
        closeGate();
        showToast('open');
      } else if (state.openRow === row) {
        closeGate();
      } else {
        showToast(null);
        openGate(row);
      }
    }

    function restart() {
      closeGate();
      list.querySelectorAll('.chat-row').forEach(function (row) {
        var chat = row.querySelector('.chat');
        var badge = row.querySelector('.kind');
        row.classList.remove('is-gone');
        row.style.maxHeight = '';
        row.hidden = false;
        row.removeAttribute('aria-hidden');
        chat.removeAttribute('tabindex');
        if (chat.classList.contains('is-allowed')) {
          chat.classList.remove('is-allowed');
          chat.setAttribute('aria-expanded', 'false');
          badge.setAttribute('data-ar', badge.getAttribute('data-kind-ar'));
          badge.setAttribute('data-en', badge.getAttribute('data-kind-en'));
          badge.innerHTML = badge.getAttribute('data-' + currentLang);
        }
      });
      state.blocked = 0;
      renderTally();
      showToast(null);
      firstVisibleChat().focus();
    }

    if (enabled) {
      // Remember each row's original badge so a restart can put it back.
      list.querySelectorAll('.kind').forEach(function (badge) {
        badge.setAttribute('data-kind-ar', badge.getAttribute('data-ar'));
        badge.setAttribute('data-kind-en', badge.getAttribute('data-en'));
      });
      list.addEventListener('click', onChatClick);
      reset.addEventListener('click', restart);
    }

    return {
      render: function () {
        if (!enabled) return;
        if (state.openRow) renderGate();
        renderToast();
      }
    };
  })();

  /* Wire up */
  var toggle = document.getElementById('langToggle');
  if (toggle) {
    toggle.addEventListener('click', function () {
      applyLang(LANGS[currentLang].toggleLang);
    });
  }

  var themeToggle = document.getElementById('themeToggle');
  if (themeToggle) {
    themeToggle.addEventListener('click', function () {
      chooseTheme(currentTheme() === 'dark' ? 'light' : 'dark');
    });
  }
  if (window.matchMedia) {
    var systemDark = window.matchMedia('(prefers-color-scheme: dark)');
    var followSystem = function (event) {
      if (!hasSavedTheme()) applyTheme(event.matches ? 'dark' : 'light');
    };
    if (systemDark.addEventListener) systemDark.addEventListener('change', followSystem);
    else if (systemDark.addListener) systemDark.addListener(followSystem);
  }

  applyTheme(currentTheme());
  applyLang(currentLang);
})();
