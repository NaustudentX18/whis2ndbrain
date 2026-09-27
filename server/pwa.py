"""PWA shell, service worker, and mobile-first responsive review UI."""

from __future__ import annotations


def get_manifest_json() -> bytes:
    return b"""{
  "name": "Whis2ndBrain",
  "short_name": "Whis2ndBrain",
  "start_url": "/pwa",
  "display": "standalone",
  "background_color": "#0d1117",
  "theme_color": "#161b22",
  "description": "Privacy-first wearable voice second brain",
  "icons": [
    {
      "src": "/brand/mark.svg",
      "sizes": "any",
      "type": "image/svg+xml"
    }
  ]
}"""


def get_service_worker_js() -> bytes:
    return b"""// Whis2ndBrain App Shell Service Worker
const CACHE_NAME = 'whis2ndbrain-v1';
const SHELL_ASSETS = ['/pwa', '/manifest.json', '/brand/mark.svg'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(SHELL_ASSETS)));
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(clients.claim());
});

self.addEventListener('fetch', (e) => {
  // Only cache GET navigation/shell requests, never API or audio mutations
  if (e.request.method === 'GET' && e.request.url.includes('/pwa')) {
    e.respondWith(
      fetch(e.request).catch(() => caches.match('/pwa'))
    );
  }
});
"""


def get_pwa_html() -> bytes:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="#161b22">
  <link rel="manifest" href="/manifest.json">
  <link rel="icon" href="/brand/mark.svg" type="image/svg+xml">
  <title>Whis2ndBrain Review</title>
  <style>
    :root {
      --bg: #0d1117;
      --surface: #161b22;
      --border: #30363d;
      --text: #c9d1d9;
      --text-bright: #f0f6fc;
      --accent: #58a6ff;
      --success: #238636;
      --warning: #d29922;
      --danger: #f85149;
      --badge-bg: #21262d;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      font-size: 16px;
      line-height: 1.5;
      padding-bottom: 5rem;
    }
    header {
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 0.8rem 1rem;
      position: sticky;
      top: 0;
      z-index: 100;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 0.6rem;
      font-weight: 700;
      color: var(--text-bright);
      text-decoration: none;
    }
    .brand img { width: 28px; height: 28px; }
    .status-dot {
      width: 8px; height: 8px; border-radius: 50%; background: #8b949e;
    }
    .container {
      max-width: 48rem;
      margin: 0 auto;
      padding: 1rem;
    }
    .controls {
      display: flex;
      flex-direction: column;
      gap: 0.8rem;
      margin-bottom: 1.2rem;
    }
    .search-input {
      width: 100%;
      background: var(--surface);
      border: 1px solid var(--border);
      color: var(--text-bright);
      padding: 0.6rem 0.8rem;
      border-radius: 6px;
      font-size: 1rem;
    }
    .search-input:focus {
      outline: none;
      border-color: var(--accent);
    }
    .filters {
      display: flex;
      gap: 0.4rem;
      overflow-x: auto;
      padding-bottom: 0.2rem;
    }
    .filter-btn {
      background: var(--badge-bg);
      border: 1px solid var(--border);
      color: var(--text);
      padding: 0.35rem 0.75rem;
      border-radius: 20px;
      font-size: 0.85rem;
      cursor: pointer;
      white-space: nowrap;
    }
    .filter-btn.active {
      background: var(--accent);
      color: #000;
      font-weight: 600;
      border-color: var(--accent);
    }
    .notes-list {
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }
    .note-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1rem;
      display: flex;
      flex-direction: column;
      gap: 0.7rem;
    }
    .card-meta {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 0.85rem;
      color: #8b949e;
    }
    .badge {
      display: inline-block;
      padding: 0.15rem 0.5rem;
      border-radius: 12px;
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
    }
    .badge-transcribing { background: rgba(210, 153, 34, 0.2); color: var(--warning); }
    .badge-reviewed { background: rgba(35, 134, 54, 0.2); color: #3fb950; }
    .badge-transcribed { background: rgba(88, 166, 255, 0.2); color: var(--accent); }
    .badge-purged { background: rgba(248, 81, 73, 0.2); color: var(--danger); }
    .transcript-text {
      color: var(--text-bright);
      font-size: 1.05rem;
      line-height: 1.4;
      white-space: pre-wrap;
    }
    .empty-state {
      text-align: center;
      padding: 3rem 1rem;
      color: #8b949e;
    }
    audio { width: 100%; height: 36px; border-radius: 4px; }
    .card-actions {
      display: flex;
      gap: 0.5rem;
      margin-top: 0.3rem;
    }
    .btn {
      background: var(--badge-bg);
      border: 1px solid var(--border);
      color: var(--text-bright);
      padding: 0.4rem 0.8rem;
      border-radius: 6px;
      font-size: 0.85rem;
      cursor: pointer;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 0.3rem;
    }
    .btn:hover { border-color: var(--text); }
    :is(.btn, .filter-btn, .search-input, textarea):focus-visible {
      outline: 2px solid var(--accent);
      outline-offset: 2px;
    }
    .btn-primary { background: var(--accent); color: #000; font-weight: 600; }
    .visually-hidden {
      position: absolute; width: 1px; height: 1px; padding: 0;
      margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0);
      white-space: nowrap; border: 0;
    }
    .modal {
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.7);
      align-items: center;
      justify-content: center;
      padding: 1rem;
      z-index: 200;
    }
    .modal.open { display: flex; }
    .modal-box {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      max-width: 36rem;
      width: 100%;
      padding: 1.2rem;
      display: flex;
      flex-direction: column;
      gap: 0.8rem;
    }
    textarea {
      width: 100%;
      min-height: 8rem;
      background: var(--bg);
      border: 1px solid var(--border);
      color: var(--text-bright);
      padding: 0.6rem;
      border-radius: 6px;
      font: inherit;
    }
  </style>
</head>
<body>
  <header>
    <a href="/pwa" class="brand">
      <img src="/brand/mark.svg" alt="logo" onerror="this.style.display='none'">
      <span>Whis2ndBrain</span>
    </a>
    <div style="display:flex; align-items:center; gap:0.5rem;">
      <span class="status-dot" title="Review page loaded; device connection not checked"></span>
      <a href="/" class="btn" style="padding:0.25rem 0.6rem; font-size:0.75rem;">Classic</a>
    </div>
  </header>

  <main class="container">
    <div class="controls">
      <label for="searchInput" class="visually-hidden">Search transcripts</label>
      <input type="search" id="searchInput" class="search-input" placeholder="Search transcripts...">
      <div class="filters">
        <button class="filter-btn active" data-status="">All</button>
        <button class="filter-btn" data-status="transcribing">Transcribing</button>
        <button class="filter-btn" data-status="transcribed">Transcribed</button>
        <button class="filter-btn" data-status="reviewed">Reviewed</button>
      </div>
    </div>

    <div id="notesContainer" class="notes-list" aria-live="polite">
      <div class="empty-state">Loading notes...</div>
    </div>
  </main>

  <div id="editModal" class="modal" role="dialog" aria-modal="true" aria-labelledby="editModalTitle">
    <div class="modal-box">
      <h3 id="editModalTitle">Edit Note Correction</h3>
      <label for="editTranscriptInput" class="visually-hidden">Corrected transcript</label>
      <textarea id="editTranscriptInput"></textarea>
      <div style="display:flex; justify-content:flex-end; gap:0.5rem;">
        <button id="cancelModalBtn" type="button" class="btn">Cancel</button>
        <button id="saveModalBtn" type="button" class="btn btn-primary">Save Correction</button>
      </div>
    </div>
  </div>

  <script>
    let activeFilter = '';
    let currentEditId = null;
    let lastEditButton = null;

    async function fetchNotes() {
      const search = document.getElementById('searchInput').value.trim();
      let url = `/api/v1/notes?limit=50`;
      if (activeFilter) url += `&status=${encodeURIComponent(activeFilter)}`;
      if (search) url += `&search=${encodeURIComponent(search)}`;

      try {
        const res = await fetch(url);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        renderNotes(data.items);
      } catch (err) {
        document.getElementById('notesContainer').innerHTML = `
          <div class="empty-state" style="color:var(--danger)">Failed to load notes: ${err.message}</div>
        `;
      }
    }

    function renderNotes(items) {
      const container = document.getElementById('notesContainer');
      if (!items || items.length === 0) {
        container.innerHTML = '<div class="empty-state">No notes match this filter.</div>';
        return;
      }
      container.innerHTML = items.map(n => {
        const id = String(n.capture_id || '');
        const encodedId = encodeURIComponent(id);
        const badgeClass = `badge-${String(n.status || '').replace('_', '-')}`;
        const sourceBadge = n.transcript_source === 'owner' ? ' • Owner Edit' : (n.transcript_source === 'model' ? ' • Machine' : '');
        const player = n.audio_purged_at ? '<div style="font-size:0.85rem; color:#8b949e">Audio hold ended. Note kept.</div>' :
          `<audio controls preload="none" src="/n/${encodedId}/audio"></audio>`;
        const transcript = n.transcript || (n.status === 'transcribing' ? 'Transcribing audio...' : 'No transcript available.');

        return `
          <div class="note-card" data-id="${escapeHtml(id)}">
            <div class="card-meta">
              <span>${escapeHtml(id.substring(0, 12))}...</span>
              <div>
                <span class="badge ${escapeHtml(badgeClass)}">${escapeHtml(n.status)}</span>
                <span style="font-size:0.75rem">${escapeHtml(sourceBadge)}</span>
              </div>
            </div>
            <div class="transcript-text">${escapeHtml(transcript)}</div>
            ${player}
            <div class="card-actions">
              <button class="btn edit-btn" type="button">Edit</button>
              <a href="/api/v1/notes/${encodedId}/markdown" class="btn" download="${escapeHtml(id)}.md">Markdown</a>
            </div>
          </div>
        `;
      }).join('');
      container.querySelectorAll('.edit-btn').forEach(button => {
        button.addEventListener('click', () => openEdit(button.closest('.note-card'), button));
      });
    }

    function escapeHtml(str) {
      return (str || '').replace(/[&<>"']/g, m => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
      })[m]);
    }

    function openEdit(card, button) {
      currentEditId = card.dataset.id;
      lastEditButton = button;
      document.getElementById('editTranscriptInput').value = card.querySelector('.transcript-text').innerText;
      document.getElementById('editModal').classList.add('open');
      document.getElementById('editTranscriptInput').focus();
    }

    function closeEdit() {
      document.getElementById('editModal').classList.remove('open');
      currentEditId = null;
      if (lastEditButton?.isConnected) lastEditButton.focus();
    }

    document.getElementById('cancelModalBtn').addEventListener('click', closeEdit);
    document.getElementById('editModal').addEventListener('keydown', e => {
      if (e.key === 'Escape') closeEdit();
    });

    document.getElementById('saveModalBtn').addEventListener('click', async () => {
      if (!currentEditId) return;
      const text = document.getElementById('editTranscriptInput').value;
      try {
        const res = await fetch(`/api/v1/notes/${encodeURIComponent(currentEditId)}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ transcript: text })
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        closeEdit();
        fetchNotes();
      } catch (err) {
        alert('Save failed: ' + err.message);
      }
    });

    document.querySelectorAll('.filter-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        activeFilter = btn.dataset.status;
        fetchNotes();
      });
    });

    let searchTimer = null;
    document.getElementById('searchInput').addEventListener('input', () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(fetchNotes, 300);
    });

    // Initial load
    fetchNotes();

    // Auto-refresh every 5s if in-flight transcribing notes exist
    setInterval(fetchNotes, 5000);

    // Register Service Worker
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js').catch(console.error);
    }
  </script>
</body>
</html>
""".encode()
