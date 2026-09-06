/* ===================================================================
   policy.js — Puregram global policy page (ADR-001).

   Server contract (under <ADMIN_BASE>/policy, see POLICY_SPEC.md §5):
     GET    policy                       → settings + entries + counts
     PUT    policy/settings              { mode?, gated_kinds?, block_restricted? }
     POST   policy/entries               { target, kind?, label? }
     POST   policy/entries/bulk          { text, kind? }
     PATCH  policy/entries/{id}          { label?, kind? }
     DELETE policy/entries/{id}

   Reuses window.Puregram helpers from api.js.
   =================================================================== */
(function () {
  'use strict';

  var P = window.Puregram;

  var POLICY = 'policy';
  var ENTRY_COLS = 6;
  var KIND_LABELS = { channel: 'قناة', bot: 'بوت', group: 'مجموعة', user: 'شخص' };
  var MODE_HINTS = {
    allow: 'سماح: القنوات والبوتات لا تُفتح إلا لو مدرجة هنا. الوضع الموصى به.',
    block: 'حظر: كل شيء يُفتح إلا ما أدرجته هنا. القنوات الجديدة تُفتح قبل أن تحظرها.',
  };

  var state = {
    policy: null,          // last payload from GET policy
    draftMode: 'allow',    // unsaved settings draft
    draftGated: [],
    draftRestricted: true,
    filterText: '',
    filterKind: '',
  };

  var els = {};

  P.initPage(function () {
    els.pageError     = document.getElementById('page-error');
    els.pageOk        = document.getElementById('page-ok');
    els.version       = document.getElementById('policy-version');
    els.refreshBtn    = document.getElementById('refresh-btn');
    els.summary       = document.getElementById('summary');

    els.modeBtns      = document.querySelectorAll('.segmented button[data-mode]');
    els.modeHint      = document.getElementById('mode-hint');
    els.gatedBoxes    = document.querySelectorAll('input[name="gated"]');
    els.blockRestricted = document.getElementById('block-restricted');
    els.saveSettings  = document.getElementById('save-settings-btn');
    els.settingsStatus = document.getElementById('settings-status');

    els.addTarget     = document.getElementById('add-target');
    els.addKind       = document.getElementById('add-kind');
    els.addLabel      = document.getElementById('add-label');
    els.addBtn        = document.getElementById('add-btn');

    els.bulkText      = document.getElementById('bulk-text');
    els.bulkKind      = document.getElementById('bulk-kind');
    els.bulkBtn       = document.getElementById('bulk-btn');
    els.bulkStatus    = document.getElementById('bulk-status');
    els.bulkErrors    = document.getElementById('bulk-errors');

    els.filter        = document.getElementById('filter');
    els.filterKind    = document.getElementById('filter-kind');
    els.entriesCount  = document.getElementById('entries-count');
    els.entriesBody   = document.getElementById('entries-body');

    els.refreshBtn.addEventListener('click', function () { loadPolicy(); });
    for (var i = 0; i < els.modeBtns.length; i++) {
      els.modeBtns[i].addEventListener('click', onModeClick);
    }
    els.saveSettings.addEventListener('click', onSaveSettings);
    els.addBtn.addEventListener('click', onAddEntry);
    els.addTarget.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') { e.preventDefault(); onAddEntry(); }
    });
    els.bulkBtn.addEventListener('click', onBulkAdd);
    els.filter.addEventListener('input', P.debounce(function () {
      state.filterText = els.filter.value.trim().toLowerCase();
      renderEntries();
    }, 140));
    els.filterKind.addEventListener('change', function () {
      state.filterKind = els.filterKind.value;
      renderEntries();
    });
    els.entriesBody.addEventListener('click', onEntriesClick);

    loadPolicy();
  });

  /* ── Loading ───────────────────────────────────────────────── */
  function loadPolicy() {
    P.hideAlert(els.pageError);
    P.tableState(els.entriesBody, ENTRY_COLS, 'loading');
    return P.http.get(POLICY)
      .then(function (policy) {
        applyPolicy(policy);
      })
      .catch(function (err) {
        if (err && err.status === 401) return;
        P.showAlert(els.pageError, 'error', (err && err.message) || 'تعذّر تحميل السياسة.');
        P.tableState(els.entriesBody, ENTRY_COLS, 'error', (err && err.message) || '');
      });
  }

  function applyPolicy(policy) {
    state.policy = policy;
    state.draftMode = policy.mode;
    state.draftGated = (policy.gated_kinds || []).slice();
    state.draftRestricted = !!policy.block_restricted;
    els.version.textContent = 'v' + (policy.version || 0);
    renderSummary();
    renderSettings();
    renderEntries();
  }

  /* ── Summary ───────────────────────────────────────────────── */
  function renderSummary() {
    var p = state.policy;
    var counts = p.counts || {};
    var modeClass = p.mode === 'block' ? 'mode-block' : 'mode-allow';
    var modeText = p.mode === 'block' ? 'حظر' : 'سماح';
    var items = [
      { k: 'الوضع الحالي', v: modeText, cls: modeClass },
      { k: 'القنوات المدرجة', v: num(counts.channel) },
      { k: 'البوتات المدرجة', v: num(counts.bot) },
      { k: 'المجموعات المدرجة', v: num(counts.group) },
      { k: 'الأشخاص المدرجون', v: num(counts.user) },
      { k: 'آخر تعديل', v: P.formatDateTime(p.updated_at), small: true },
    ];
    els.summary.innerHTML = items.map(function (it) {
      var style = it.small ? ' style="font-size:14px;font-weight:700;"' : '';
      return '<div class="sum-item"><span class="sum-k">' + P.escapeHtml(it.k) + '</span>' +
        '<span class="sum-v ' + (it.cls || '') + '"' + style + '>' + P.escapeHtml(it.v) + '</span></div>';
    }).join('');
  }

  /* ── Settings ──────────────────────────────────────────────── */
  function renderSettings() {
    for (var i = 0; i < els.modeBtns.length; i++) {
      var b = els.modeBtns[i];
      b.setAttribute('aria-pressed', b.getAttribute('data-mode') === state.draftMode ? 'true' : 'false');
    }
    els.modeHint.textContent = MODE_HINTS[state.draftMode] || '';
    for (var j = 0; j < els.gatedBoxes.length; j++) {
      els.gatedBoxes[j].checked = state.draftGated.indexOf(els.gatedBoxes[j].value) !== -1;
    }
    els.blockRestricted.checked = state.draftRestricted;
    els.settingsStatus.textContent = '';
  }

  function onModeClick(e) {
    state.draftMode = e.currentTarget.getAttribute('data-mode');
    renderSettings();
  }

  function readSettingsDraft() {
    var gated = [];
    for (var j = 0; j < els.gatedBoxes.length; j++) {
      if (els.gatedBoxes[j].checked) gated.push(els.gatedBoxes[j].value);
    }
    return {
      mode: state.draftMode,
      gated_kinds: gated,
      block_restricted: !!els.blockRestricted.checked,
    };
  }

  function onSaveSettings() {
    var body = readSettingsDraft();
    if (body.mode === 'block') {
      var ok = window.confirm(
        'وضع الحظر يفتح كل القنوات والبوتات ما عدا المدرجة. هل تريد المتابعة؟'
      );
      if (!ok) return;
    }
    els.saveSettings.disabled = true;
    els.settingsStatus.textContent = 'جارٍ الحفظ…';
    P.http.put(POLICY + '/settings', body)
      .then(function (policy) {
        applyPolicy(policy);
        els.settingsStatus.textContent = 'تم الحفظ. ستصل التغييرات للأجهزة خلال دقيقة.';
        P.showAlert(els.pageOk, 'success', 'تم حفظ الإعدادات.');
      })
      .catch(function (err) {
        if (err && err.status === 401) return;
        els.settingsStatus.textContent = '';
        P.showAlert(els.pageError, 'error', (err && err.message) || 'تعذّر الحفظ.');
      })
      .then(function () { els.saveSettings.disabled = false; });
  }

  /* ── Add one ───────────────────────────────────────────────── */
  function onAddEntry() {
    var target = els.addTarget.value.trim();
    if (!target) { els.addTarget.focus(); return; }
    var body = { target: target };
    if (els.addKind.value) body.kind = els.addKind.value;
    if (els.addLabel.value.trim()) body.label = els.addLabel.value.trim();

    els.addBtn.disabled = true;
    P.hideAlert(els.pageError);
    P.http.post(POLICY + '/entries', body)
      .then(function () {
        els.addTarget.value = '';
        els.addLabel.value = '';
        els.addTarget.focus();
        P.showAlert(els.pageOk, 'success', 'أُضيف الإدخال.');
        return loadPolicy();
      })
      .catch(function (err) {
        if (err && err.status === 401) return;
        var msg = err && err.status === 409 ? 'هذا الإدخال موجود بالفعل.' : (err && err.message) || 'تعذّرت الإضافة.';
        P.showAlert(els.pageError, 'error', msg);
      })
      .then(function () { els.addBtn.disabled = false; });
  }

  /* ── Bulk ──────────────────────────────────────────────────── */
  function onBulkAdd() {
    var text = els.bulkText.value;
    if (!text.trim()) { els.bulkText.focus(); return; }
    var body = { text: text };
    if (els.bulkKind.value) body.kind = els.bulkKind.value;

    els.bulkBtn.disabled = true;
    els.bulkStatus.textContent = 'جارٍ الإضافة…';
    els.bulkErrors.hidden = true;
    P.http.post(POLICY + '/entries/bulk', body)
      .then(function (res) {
        var added = num(res.added), skipped = num(res.skipped);
        els.bulkStatus.textContent = 'أُضيف ' + added + ' · مكرّر ' + skipped +
          (res.errors && res.errors.length ? ' · أخطاء ' + res.errors.length : '');
        if (res.errors && res.errors.length) {
          els.bulkErrors.textContent = res.errors.map(function (e) {
            return 'line ' + e.line + ': ' + e.text + ' — ' + e.reason;
          }).join('\n');
          els.bulkErrors.hidden = false;
        } else {
          els.bulkText.value = '';
        }
        return loadPolicy();
      })
      .catch(function (err) {
        if (err && err.status === 401) return;
        els.bulkStatus.textContent = '';
        P.showAlert(els.pageError, 'error', (err && err.message) || 'تعذّرت الإضافة المجمّعة.');
      })
      .then(function () { els.bulkBtn.disabled = false; });
  }

  /* ── Entries table ─────────────────────────────────────────── */
  function visibleEntries() {
    var list = (state.policy && state.policy.entries) || [];
    var q = state.filterText;
    var kind = state.filterKind;
    return list.filter(function (e) {
      if (kind && e.kind !== kind) return false;
      if (!q) return true;
      var hay = [
        e.username || '', e.chat_id != null ? String(e.chat_id) : '',
        e.label || '', e.added_by || '',
      ].join(' ').toLowerCase();
      return hay.indexOf(q) !== -1;
    });
  }

  function renderEntries() {
    var all = (state.policy && state.policy.entries) || [];
    var rows = visibleEntries();
    els.entriesCount.textContent = rows.length === all.length
      ? 'الإجمالي: ' + all.length
      : 'يظهر ' + rows.length + ' من ' + all.length;

    if (!all.length) {
      P.tableState(els.entriesBody, ENTRY_COLS, 'empty',
        state.policy && state.policy.mode === 'allow'
          ? 'القائمة فارغة: لا تُفتح أي قناة أو بوت حالياً. أضف أول إدخال أعلاه.'
          : 'القائمة فارغة.');
      return;
    }
    if (!rows.length) {
      P.tableState(els.entriesBody, ENTRY_COLS, 'empty', 'لا نتائج مطابقة.');
      return;
    }

    els.entriesBody.innerHTML = rows.map(function (e) {
      var ident = '';
      if (e.username) ident += '@' + P.escapeHtml(e.username);
      if (e.chat_id != null) {
        ident += ident ? '<span class="sub">' + P.escapeHtml(String(e.chat_id)) + '</span>'
                       : P.escapeHtml(String(e.chat_id));
      }
      var warn = e.chat_id == null
        ? ' <span class="warn-pill" title="إدخال باسم المستخدم فقط: لو غيّرت القناة اسمها لن يُطابق">بلا معرّف</span>'
        : '';
      return (
        '<tr data-id="' + e.id + '">' +
        '<td class="ident">' + ident + '</td>' +
        '<td><span class="kind-pill kind-' + P.escapeHtml(e.kind) + '">' + (KIND_LABELS[e.kind] || e.kind) + '</span>' + warn + '</td>' +
        '<td>' + (e.label ? P.escapeHtml(e.label) : '<span style="color:var(--dim)">—</span>') + '</td>' +
        '<td dir="ltr" style="text-align:left;font-size:12.5px;color:var(--muted)">' + P.escapeHtml(e.added_by || '—') + '</td>' +
        '<td style="white-space:nowrap;font-size:12.5px;color:var(--muted)">' + P.formatDateTime(e.created_at) + '</td>' +
        '<td><div class="row-actions">' +
          '<button type="button" class="btn btn-ghost btn-sm" data-action="label">الوصف</button>' +
          '<button type="button" class="btn btn-ghost btn-sm" data-action="delete" style="color:var(--danger)">حذف</button>' +
        '</div></td>' +
        '</tr>'
      );
    }).join('');
  }

  function onEntriesClick(e) {
    var btn = e.target.closest('button[data-action]');
    if (!btn) return;
    var tr = btn.closest('tr[data-id]');
    if (!tr) return;
    var id = tr.getAttribute('data-id');
    var entry = findEntry(id);
    if (!entry) return;

    if (btn.getAttribute('data-action') === 'delete') {
      var who = entry.username ? '@' + entry.username : String(entry.chat_id);
      if (!window.confirm('حذف ' + who + ' من القائمة؟')) return;
      btn.disabled = true;
      P.http.del(POLICY + '/entries/' + encodeURIComponent(id))
        .then(function () {
          P.showAlert(els.pageOk, 'success', 'حُذف الإدخال.');
          return loadPolicy();
        })
        .catch(function (err) {
          if (err && err.status === 401) return;
          btn.disabled = false;
          P.showAlert(els.pageError, 'error', (err && err.message) || 'تعذّر الحذف.');
        });
      return;
    }

    if (btn.getAttribute('data-action') === 'label') {
      var next = window.prompt('الوصف الجديد:', entry.label || '');
      if (next === null) return;
      btn.disabled = true;
      P.http.patch(POLICY + '/entries/' + encodeURIComponent(id), { label: next })
        .then(function () { return loadPolicy(); })
        .catch(function (err) {
          if (err && err.status === 401) return;
          btn.disabled = false;
          P.showAlert(els.pageError, 'error', (err && err.message) || 'تعذّر التعديل.');
        });
    }
  }

  function findEntry(id) {
    var list = (state.policy && state.policy.entries) || [];
    for (var i = 0; i < list.length; i++) {
      if (String(list[i].id) === String(id)) return list[i];
    }
    return null;
  }

  function num(v) {
    var n = Number(v);
    return isNaN(n) ? 0 : n;
  }
})();
