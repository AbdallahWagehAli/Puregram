/* ===================================================================
   telegram.js — Puregram Telegram whitelist control page.

   Lets admins manage per-device Telegram chat whitelists via the
   existing admin API endpoints under <ADMIN_BASE>/telegram/...

   Server contract (under <ADMIN_BASE>/telegram):
     GET    /devices                              → device list
     GET    /devices/{device_id}/chats           → known chats + whitelist + version
     PUT    /devices/{device_id}/whitelist        { chat_id, kind, label?, allowed }
     DELETE /devices/{device_id}/whitelist/{id}  → remove entry
     POST   /devices/{device_id}/bulk            { text }  → bulk add allowed

   Reuses window.Puregram helpers: http, initPage, renderTopbar,
   escapeHtml, formatDateTime, tableState, showAlert, debounce, asArray.
   =================================================================== */
(function () {
  'use strict';

  var P = window.Puregram;

  /* ── Constants ─────────────────────────────────────────────────── */
  /* Relative to ADMIN_BASE: api.js request() prepends ADMIN_BASE for any path
     that does not start with '/'. Using an absolute URL here double-prefixed it
     (…/admin/https://…/admin/telegram/devices → 404). */
  var TG_BASE     = 'telegram';
  var KNOWN_COLS  = 5;
  var WL_COLS     = 6;

  /* ── State ─────────────────────────────────────────────────────── */
  var state = {
    devices:       [],   /* raw list from /devices */
    selectedId:    null, /* device_id string of the open device */
    knownChats:    [],   /* all known chats for selected device */
    whitelist:     [],   /* whitelist rows for selected device */
    version:       0,
    loadingDetail: false,
  };

  /* ── Element cache (populated after DOMContentLoaded) ─────────── */
  var els = {};

  /* ── Bootstrap ─────────────────────────────────────────────────── */
  P.initPage(function () {
    els.devicesGrid    = document.getElementById('devices-grid');
    els.detailArea     = document.getElementById('detail-area');
    els.detailTitle    = document.getElementById('detail-title');
    els.detailVersion  = document.getElementById('detail-version');
    els.closeDetailBtn = document.getElementById('close-detail-btn');
    els.refreshBtn     = document.getElementById('refresh-devices-btn');
    els.pageError      = document.getElementById('page-error');
    els.pageOk         = document.getElementById('page-ok');

    els.knownBody      = document.getElementById('known-body');
    els.knownSearch    = document.getElementById('known-search');
    els.knownCount     = document.getElementById('known-count');

    els.wlBody         = document.getElementById('wl-body');

    els.bulkText       = document.getElementById('bulk-text');
    els.bulkSubmitBtn  = document.getElementById('bulk-submit-btn');
    els.bulkStatus     = document.getElementById('bulk-status');

    /* Tab switching */
    var tabBtns = document.querySelectorAll('.detail-tab');
    for (var i = 0; i < tabBtns.length; i++) {
      tabBtns[i].addEventListener('click', onTabClick);
    }

    els.closeDetailBtn.addEventListener('click', closeDetail);
    els.refreshBtn.addEventListener('click', function () { loadDevices(true); });

    els.knownSearch.addEventListener(
      'input',
      P.debounce(function () { renderKnownChats(); }, 160)
    );

    els.wlBody.addEventListener('click', onWlTableClick);
    els.bulkSubmitBtn.addEventListener('click', onBulkSubmit);

    loadDevices(false);
  });

  /* ── Devices ───────────────────────────────────────────────────── */
  function loadDevices(showRefreshing) {
    P.hideAlert(els.pageError);
    P.hideAlert(els.pageOk);
    if (showRefreshing) {
      els.devicesGrid.innerHTML =
        '<div class="state"><span class="spinner" aria-hidden="true"></span> <span>جارٍ التحديث…</span></div>';
    } else {
      els.devicesGrid.innerHTML =
        '<div class="state"><span class="spinner" aria-hidden="true"></span> <span>جارٍ التحميل…</span></div>';
    }

    P.http.get(TG_BASE + '/devices')
      .then(function (res) {
        state.devices = P.asArray(res, 'devices');
        renderDevices();
      })
      .catch(function (err) {
        if (err && err.status === 401) return;
        els.devicesGrid.innerHTML =
          '<div class="state"><span style="color:var(--danger)">' +
          P.escapeHtml((err && err.message) || 'تعذّر تحميل الأجهزة.') +
          '</span></div>';
      });
  }

  function renderDevices() {
    if (!state.devices.length) {
      els.devicesGrid.innerHTML =
        '<div class="state">لا توجد أجهزة لديها سجلات تليجرام.</div>';
      return;
    }

    els.devicesGrid.innerHTML = state.devices.map(function (d) {
      var isSelected = d.device_id === state.selectedId;
      return (
        '<div class="device-card' + (isSelected ? ' selected' : '') + '"' +
        '     tabindex="0" role="button"' +
        '     aria-pressed="' + (isSelected ? 'true' : 'false') + '"' +
        '     data-device-id="' + P.escapeHtml(d.device_id) + '">' +
        '  <div class="device-card-id" title="' + P.escapeHtml(d.device_id) + '">' +
             P.escapeHtml(shortId(d.device_id)) +
        '  </div>' +
        '  <div class="device-card-model">' +
             P.escapeHtml(d.model || 'جهاز غير معروف') +
        '  </div>' +
        '  <div class="device-card-counts">' +
        '    <span>معروفة: <span class="cnt-val">' + num(d.known_chats) + '</span></span>' +
        '    <span>مسموحة: <span class="cnt-val">' + num(d.allowed_chats) + '</span></span>' +
        '  </div>' +
        '  <div class="device-card-last">' +
             P.formatDateTime(d.last_seen_at) +
        '  </div>' +
        '</div>'
      );
    }).join('');

    /* Attach click + keyboard handlers */
    var cards = els.devicesGrid.querySelectorAll('.device-card');
    for (var i = 0; i < cards.length; i++) {
      cards[i].addEventListener('click',   onDeviceCardActivate);
      cards[i].addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onDeviceCardActivate.call(this, e);
        }
      });
    }
  }

  function onDeviceCardActivate() {
    var deviceId = this.getAttribute('data-device-id');
    if (!deviceId) return;
    if (state.selectedId === deviceId) {
      closeDetail();
      return;
    }
    state.selectedId = deviceId;
    renderDevices(); /* update selected highlight */
    loadDeviceDetail(deviceId);
  }

  /* ── Device detail ─────────────────────────────────────────────── */
  function loadDeviceDetail(deviceId) {
    if (state.loadingDetail) return;
    state.loadingDetail = true;

    els.detailArea.hidden = false;
    els.detailTitle.textContent = shortId(deviceId);
    els.detailVersion.textContent = 'v…';

    P.tableState(els.knownBody, KNOWN_COLS, 'loading');
    P.tableState(els.wlBody,    WL_COLS,    'loading');

    P.http.get(TG_BASE + '/devices/' + encodeURIComponent(deviceId) + '/chats')
      .then(function (res) {
        state.knownChats = P.asArray(res && res.known,     'known');
        state.whitelist  = P.asArray(res && res.whitelist, 'whitelist');
        state.version    = (res && res.version != null) ? res.version : 0;

        els.detailTitle.textContent   = shortId(deviceId);
        els.detailVersion.textContent = 'v' + state.version;

        renderKnownChats();
        renderWhitelist();
        els.detailArea.scrollIntoView({ behavior: 'smooth', block: 'start' });
      })
      .catch(function (err) {
        if (err && err.status === 401) return;
        P.tableState(els.knownBody, KNOWN_COLS, 'error', (err && err.message) || 'تعذّر التحميل.');
        P.tableState(els.wlBody,    WL_COLS,    'error', (err && err.message) || 'تعذّر التحميل.');
      })
      .then(function () {
        state.loadingDetail = false;
      });
  }

  function closeDetail() {
    state.selectedId = null;
    state.knownChats = [];
    state.whitelist  = [];
    els.detailArea.hidden = true;
    renderDevices();
  }

  /* ── Known chats tab ───────────────────────────────────────────── */
  function renderKnownChats() {
    var q = (els.knownSearch.value || '').trim().toLowerCase();
    var list = q ? state.knownChats.filter(function (c) {
      return matchChat(c, q);
    }) : state.knownChats;

    els.knownCount.textContent = q
      ? list.length + ' نتيجة'
      : state.knownChats.length + ' محادثة';

    if (!list.length) {
      P.tableState(els.knownBody, KNOWN_COLS, 'empty',
        q ? 'لا نتائج للبحث.' : 'لا توجد محادثات معروفة لهذا الجهاز.');
      return;
    }

    els.knownBody.innerHTML = list.map(function (c) {
      return knownRowHtml(c);
    }).join('');
  }

  function matchChat(c, q) {
    var hay = [c.title, c.username, c.kind, String(c.id)].join(' ').toLowerCase();
    return hay.indexOf(q) !== -1;
  }

  function knownRowHtml(c) {
    var titleCell = P.escapeHtml(c.title || '—');
    var usernameCell = c.username
      ? '<span class="cell-ltr">@' + P.escapeHtml(c.username) + '</span>'
      : '<span class="cell-muted">—</span>';
    var kindCell = kindPill(c.kind);
    var lastCell = '<span class="cell-muted">' + P.formatDateTime(c.last_seen_at) + '</span>';

    /* Toggle control — optimistic */
    var checked   = c.allowed ? ' checked' : '';
    var toggleId  = 'toggle-' + String(c.id).replace(/[^a-z0-9]/gi, '_');
    var toggleEl  =
      '<label class="toggle-wrap" title="' + (c.allowed ? 'مسموح — انقر للإلغاء' : 'محظور — انقر للسماح') + '">' +
      '<input type="checkbox" id="' + toggleId + '"' + checked +
      '       data-chat-id="' + P.escapeHtml(String(c.id)) + '"' +
      '       data-kind="'    + P.escapeHtml(c.kind || 'private') + '"' +
      '       aria-label="السماح لـ ' + P.escapeHtml(c.title || String(c.id)) + '"' +
      ' />' +
      '</label>';

    return (
      '<tr data-chat-id="' + P.escapeHtml(String(c.id)) + '">' +
      '  <td>' + titleCell + '</td>' +
      '  <td>' + usernameCell + '</td>' +
      '  <td>' + kindCell + '</td>' +
      '  <td>' + lastCell + '</td>' +
      '  <td>' + toggleEl + '</td>' +
      '</tr>'
    );
  }

  /* Delegate toggle changes on the known-chats tbody */
  document.addEventListener('change', function (e) {
    var cb = e.target;
    if (cb.type !== 'checkbox' || !cb.closest('#tab-known')) return;
    var chatId = parseInt(cb.getAttribute('data-chat-id'), 10);
    var kind   = cb.getAttribute('data-kind') || 'private';
    if (isNaN(chatId)) return;
    toggleChatAllowed(cb, chatId, kind, cb.checked);
  });

  function toggleChatAllowed(checkboxEl, chatId, kind, allowed) {
    if (!state.selectedId) return;
    checkboxEl.disabled = true;

    var body = { chat_id: chatId, kind: kind, allowed: allowed };
    P.http.put(
      TG_BASE + '/devices/' + encodeURIComponent(state.selectedId) + '/whitelist',
      body
    ).then(function (res) {
      /* Update local state */
      updateLocalAllowed(chatId, allowed);
      state.version = (res && res.version != null) ? res.version : state.version;
      els.detailVersion.textContent = 'v' + state.version;
      checkboxEl.disabled = false;
      reloadDetailSilent();
    }).catch(function (err) {
      if (err && err.status === 401) return;
      /* Revert the optimistic toggle */
      checkboxEl.checked  = !allowed;
      checkboxEl.disabled = false;
      P.showAlert(els.pageError, 'error',
        'تعذّر تحديث الإذن: ' + ((err && err.message) || 'خطأ غير معروف'));
    });
  }

  function updateLocalAllowed(chatId, allowed) {
    for (var i = 0; i < state.knownChats.length; i++) {
      if (state.knownChats[i].id === chatId) {
        state.knownChats[i].allowed = allowed;
        break;
      }
    }
  }

  /* ── Whitelist tab ─────────────────────────────────────────────── */
  function renderWhitelist() {
    if (!state.whitelist.length) {
      P.tableState(els.wlBody, WL_COLS, 'empty', 'قائمة السماح فارغة.');
      return;
    }

    els.wlBody.innerHTML = state.whitelist.map(function (w) {
      return wlRowHtml(w);
    }).join('');
  }

  function wlRowHtml(w) {
    var allowedBadge = w.allowed
      ? '<span class="badge badge-active">مسموح</span>'
      : '<span class="badge badge-suspended">محظور</span>';
    return (
      '<tr data-chat-id="' + P.escapeHtml(String(w.chat_id)) + '">' +
      '  <td class="cell-ltr">' + P.escapeHtml(String(w.chat_id)) + '</td>' +
      '  <td>' + kindPill(w.kind) + '</td>' +
      '  <td>' + (w.label ? P.escapeHtml(w.label) : '<span class="cell-muted">—</span>') + '</td>' +
      '  <td>' + allowedBadge + '</td>' +
      '  <td class="cell-muted">' + P.formatDateTime(w.updated_at) + '</td>' +
      '  <td><div class="cell-actions">' +
      '    <button type="button" class="btn btn-danger btn-sm"' +
      '            data-act="remove"' +
      '            data-chat-id="' + P.escapeHtml(String(w.chat_id)) + '"' +
      '            title="حذف من قائمة السماح">حذف</button>' +
      '    <span class="save-status"></span>' +
      '  </div></td>' +
      '</tr>'
    );
  }

  function onWlTableClick(e) {
    var btn = e.target.closest('button[data-act]');
    if (!btn || btn.getAttribute('data-act') !== 'remove') return;
    if (!state.selectedId) return;

    var chatId  = btn.getAttribute('data-chat-id');
    var statusEl = btn.closest('td').querySelector('.save-status');

    if (!window.confirm('حذف معرّف المحادثة ' + chatId + ' من قائمة السماح؟ لا يمكن التراجع.')) return;

    setStatus(statusEl, 'busy', 'جارٍ…');
    btn.disabled = true;

    P.http.del(
      TG_BASE + '/devices/' + encodeURIComponent(state.selectedId) +
      '/whitelist/' + encodeURIComponent(chatId)
    ).then(function () {
      setStatus(statusEl, 'ok', 'تم ✓');
      reloadDetailSilent();
    }).catch(function (err) {
      if (err && err.status === 401) return;
      btn.disabled = false;
      setStatus(statusEl, 'err', 'فشل: ' + ((err && err.message) || ''));
    });
  }

  /* ── Bulk add tab ──────────────────────────────────────────────── */
  function onBulkSubmit() {
    if (!state.selectedId) return;
    var text = (els.bulkText.value || '').trim();
    if (!text) {
      setStatus(els.bulkStatus, 'err', 'الحقل فارغ.');
      return;
    }

    els.bulkSubmitBtn.disabled = true;
    setStatus(els.bulkStatus, 'busy', 'جارٍ الإضافة…');
    P.hideAlert(els.pageError);

    P.http.post(
      TG_BASE + '/devices/' + encodeURIComponent(state.selectedId) + '/bulk',
      { text: text }
    ).then(function (res) {
      var added   = (res && res.added   != null) ? res.added   : '?';
      var skipped = (res && res.skipped != null) ? res.skipped : '?';
      setStatus(els.bulkStatus, 'ok', 'أُضيف ' + added + ' · تُجوهل ' + skipped);
      els.bulkText.value = '';
      els.bulkSubmitBtn.disabled = false;
      reloadDetailSilent();
    }).catch(function (err) {
      if (err && err.status === 401) return;
      els.bulkSubmitBtn.disabled = false;
      setStatus(els.bulkStatus, 'err', 'فشل: ' + ((err && err.message) || ''));
    });
  }

  /* ── Silent detail reload (refreshes state without flicker) ────── */
  function reloadDetailSilent() {
    if (!state.selectedId) return;
    P.http.get(TG_BASE + '/devices/' + encodeURIComponent(state.selectedId) + '/chats')
      .then(function (res) {
        state.knownChats = P.asArray(res && res.known,     'known');
        state.whitelist  = P.asArray(res && res.whitelist, 'whitelist');
        state.version    = (res && res.version != null) ? res.version : state.version;
        els.detailVersion.textContent = 'v' + state.version;
        renderKnownChats();
        renderWhitelist();
        /* Also refresh the device card counts */
        loadDevicesCountsOnly();
      })
      .catch(function () { /* non-fatal — UI shows stale data */ });
  }

  /* Refresh device counts without resetting the selected state */
  function loadDevicesCountsOnly() {
    P.http.get(TG_BASE + '/devices')
      .then(function (res) {
        state.devices = P.asArray(res, 'devices');
        renderDevices();
      })
      .catch(function () { /* non-fatal */ });
  }

  /* ── Tab switching ─────────────────────────────────────────────── */
  function onTabClick() {
    var tab = this.getAttribute('data-tab');
    if (!tab) return;

    var allTabs  = document.querySelectorAll('.detail-tab');
    var allPanes = document.querySelectorAll('.tab-pane');

    for (var i = 0; i < allTabs.length; i++) {
      allTabs[i].classList.toggle('active', allTabs[i].getAttribute('data-tab') === tab);
    }
    for (var j = 0; j < allPanes.length; j++) {
      var paneId = 'tab-' + tab;
      allPanes[j].classList.toggle('active', allPanes[j].id === paneId);
    }
  }

  /* ── Shared helpers ────────────────────────────────────────────── */
  function kindPill(kind) {
    var k = kind || 'private';
    var label = { channel: 'قناة', group: 'مجموعة', private: 'خاص', bot: 'بوت' }[k] || P.escapeHtml(k);
    return '<span class="kind-pill kind-' + P.escapeHtml(k) + '">' + label + '</span>';
  }

  function shortId(id) {
    var s = String(id || '');
    return s.length > 20 ? s.slice(0, 10) + '…' + s.slice(-6) : s;
  }

  function num(v) {
    return (v != null) ? String(v) : '0';
  }

  function setStatus(el, kind, msg) {
    if (!el) return;
    el.className = 'save-status' + (kind ? ' ' + kind : '');
    el.textContent = msg || '';
  }
})();
