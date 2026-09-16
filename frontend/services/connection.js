/* Talking to the server: connect, disconnect, pull, push.
   Moved verbatim from Bhumijo_Proposal_Tracker_22Jul2026.html — 10 function(s), not rewritten.
   Loaded in a fixed order by index.html, sharing one scope, exactly as before. */

function normalizeServerBase(raw) {
  raw = (raw || '').trim();
  // The page was served BY the server, so the address is already known.
  // Asking for it was left over from when this file was opened from disk.
  if (!raw) return defaultServerBase();
  if (!/^https?:\/\//i.test(raw)) raw = 'http://' + raw;
  return raw.replace(/\/+$/, '');
}

function defaultServerBase() {
  // file:// has no origin worth using; anything else served us this page.
  if (window.location.protocol === 'http:' || window.location.protocol === 'https:') {
    return window.location.origin;
  }
  return '';
}

function setServerUI(state, message) {
  const dot = document.getElementById('server-dot');
  const btn = document.getElementById('server-connect-btn');
  const status = document.getElementById('server-status-text');
  const ipInput = document.getElementById('server-ip-input');
  const tokenInput = document.getElementById('server-token-input');
  if (!dot || !btn || !status) return;
  dot.className = 'server-dot ' + (state === 'on' ? 'on' : state === 'error' ? 'error' : 'off');
  status.className = 'server-status ' + (state === 'on' ? 'on' : state === 'error' ? 'error' : '');
  status.textContent = message || (state === 'on' ? 'Connected' : 'Not connected');
  if (state === 'on') {
    btn.textContent = 'Disconnect';
    btn.className = 'server-btn disconnect';
    if (ipInput) ipInput.disabled = true;
    if (tokenInput) tokenInput.disabled = true;
  } else {
    btn.textContent = 'Connect';
    btn.className = 'server-btn connect';
    if (ipInput) ipInput.disabled = false;
    if (tokenInput) tokenInput.disabled = false;
  }
}

function toggleServerConnection() {
  if (serverConnected) {
    disconnectServer();
  } else {
    connectServer();
  }
}

function connectServer() {
  const ipInput = document.getElementById('server-ip-input');
  const tokenInput = document.getElementById('server-token-input');
  // The address is only needed when this page was NOT served by the server
  // (opened from disk). Otherwise it is simply where the page came from.
  const ip = (ipInput ? ipInput.value.trim() : '') || defaultServerBase();
  const token = tokenInput ? tokenInput.value.trim() : '';
  if (!ip) {
    toast('Enter the server address first', 'error');
    return;
  }
  if (!token) {
    toast('Enter the access token first', 'error');
    return;
  }
  const base = normalizeServerBase(ip);
  setServerUI('off', 'Connecting…');

  // Ask the server to remember this browser, so the token is typed once and
  // never again. Same-origin only — a page opened from disk falls back to
  // the old verify-and-store-locally path.
  const sameOrigin = base === defaultServerBase() && !!defaultServerBase();
  const check = sameOrigin
    ? fetch(base + '/api/v1/auth/connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ token: token })
      }).then(r => r.json().then(d => ({ ok: r.ok && d && d.ok, remembered: true })))
    : fetch(base + '/verify?token=' + encodeURIComponent(token))
        .then(r => r.json())
        .then(d => ({ ok: !!(d && d.ok), remembered: false }));

  check
    .then(data => {
      if (data && data.ok) {
        serverBaseUrl = base;
        serverToken = token;
        serverConnected = true;
        try {
          localStorage.setItem(SERVER_IP_KEY, ip);
          localStorage.setItem(SERVER_TOKEN_KEY, token);
        } catch (e) {}
        setServerUI('on', 'Connected');
        toast(data.remembered
          ? 'Connected — this device is remembered, no need to enter it again'
          : 'Connected to server', 'success');
        pullFromServer();
      } else {
        setServerUI('error', 'Bad token');
        toast('Connection failed: bad access token', 'error');
      }
    })
    .catch(() => {
      setServerUI('error', 'Could not reach server');
      toast('Could not reach server — check the IP and that it\'s on the same network', 'error');
    });
}

function disconnectServer() {
  // Also tell the server to stop remembering this browser, otherwise
  // "Disconnect" would appear to do nothing and it would reconnect on reload.
  const base = serverBaseUrl || defaultServerBase();
  if (base && base === defaultServerBase()) {
    fetch(base + '/api/v1/auth/forget', { method: 'POST', credentials: 'same-origin' })
      .catch(() => {});
  }
  serverConnected = false;
  serverBaseUrl = '';
  serverToken = '';
  try {
    localStorage.removeItem(SERVER_IP_KEY);
    localStorage.removeItem(SERVER_TOKEN_KEY);
  } catch (e) {}
  setServerUI('off', 'Not connected');
  toast('Disconnected from server', 'success');
}

function restoreServerConnection() {
  const base0 = defaultServerBase();

  // First: has this browser already been remembered? If so there is nothing
  // to type and nothing to restore from storage.
  if (base0) {
    fetch(base0 + '/api/v1/auth/session', { credentials: 'same-origin' })
      .then(r => r.json())
      .then(data => {
        if (data && data.connected) {
          serverBaseUrl = base0;
          serverToken = '';   // trusted network, or a remembered device
          serverConnected = true;
          setServerUI('on', data.reason === 'trusted network'
            ? 'Connected (office network)'
            : 'Connected');
          pullFromServer();
        } else {
          restoreServerConnectionFromStorage();
        }
      })
      .catch(function () {
        // The server may still be starting when the page loads. Give it one
        // more go before falling back to asking the user for the token.
        setTimeout(function () {
          fetch(base0 + '/api/v1/auth/session', { credentials: 'same-origin' })
            .then(r => r.json())
            .then(function (data) {
              if (data && data.connected) {
                serverBaseUrl = base0;
                serverToken = '';
                serverConnected = true;
                setServerUI('on', data.reason === 'trusted network'
                  ? 'Connected (office network)' : 'Connected');
                pullFromServer();
              } else {
                restoreServerConnectionFromStorage();
              }
            })
            .catch(() => restoreServerConnectionFromStorage());
        }, 1500);
      });
    return;
  }
  restoreServerConnectionFromStorage();
}

function restoreServerConnectionFromStorage() {
  let ip = '', token = '';
  try {
    ip = localStorage.getItem(SERVER_IP_KEY) || '';
    token = localStorage.getItem(SERVER_TOKEN_KEY) || '';
  } catch (e) {}
  const ipInput = document.getElementById('server-ip-input');
  const tokenInput = document.getElementById('server-token-input');
  if (ip && ipInput) ipInput.value = ip;
  if (token && tokenInput) tokenInput.value = token;
  if (!ip || !token) return;
  const base = normalizeServerBase(ip);
  fetch(base + '/verify?token=' + encodeURIComponent(token))
    .then(r => r.json())
    .then(data => {
      if (data && data.ok) {
        serverBaseUrl = base;
        serverToken = token;
        serverConnected = true;
        setServerUI('on', 'Connected');
        pullFromServer();
      } else {
        setServerUI('error', 'Saved token no longer valid');
      }
    })
    .catch(() => {
      setServerUI('error', 'Server unreachable');
    });
}

function pullFromServer() {
  if (!serverConnected) return;
  fetch(serverBaseUrl + '/proposals/load?token=' + encodeURIComponent(serverToken))
    .then(r => r.json())
    .then(data => {
      if (data && data.ok && Array.isArray(data.proposals) && data.proposals.length) {
        proposals = data.proposals;
        try { localStorage.setItem(STORAGE_KEY, JSON.stringify(proposals)); } catch (e) {}
        renderDashboard();
        filterTable();
      }
    })
    .catch(() => {});
  fetch(serverBaseUrl + '/api/clients', { headers: { 'X-Auth-Token': serverToken } })
    .then(r => r.json())
    .then(data => {
      if (data && data.ok && Array.isArray(data.clients) && data.clients.length) {
        clients = data.clients;
        try { localStorage.setItem(CLIENTS_KEY, JSON.stringify(clients)); } catch (e) {}
        if (typeof renderClients === 'function') renderClients();
      }
    })
    .catch(() => {});
}

function pushProposalsToServer() {
  if (!serverConnected || serverSyncing) return;
  serverSyncing = true;
  fetch(serverBaseUrl + '/proposals/save?token=' + encodeURIComponent(serverToken), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ proposals: proposals })
  })
    .catch(() => { setServerUI('error', 'Sync failed — check connection'); })
    .finally(() => { serverSyncing = false; });
}

function pushClientsToServer() {
  if (!serverConnected) return;
  fetch(serverBaseUrl + '/api/clients', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Auth-Token': serverToken },
    body: JSON.stringify({ clients: clients })
  }).catch(() => {});
}

function deleteProposalOnServer(id) {
  return fetch(serverBaseUrl + '/proposals/delete?token=' + encodeURIComponent(serverToken), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id: id })
  }).then(r => r.json());
}
