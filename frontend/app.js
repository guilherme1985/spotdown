const form          = document.getElementById('form');
const urlInput      = document.getElementById('url-input');
const submitBtn     = document.getElementById('submit-btn');
const limitHint     = document.getElementById('limit-hint');
const jobsEl        = document.getElementById('jobs');
const jobsToolbar   = document.getElementById('jobs-toolbar');
const connectSection = document.getElementById('connect-section');
const formSection   = document.getElementById('form-section');
const authIndicator = document.getElementById('auth-indicator');

const activeSSE = {};

// ── Init ─────────────────────────────────────────────────────────────────────
(async () => {
    const { authenticated } = await fetch('/api/auth/status').then(r => r.json());
    setAuthState(authenticated);

    if (authenticated) {
        try {
            const jobs = await fetch('/api/jobs').then(r => r.json());
            for (const job of [...jobs].reverse()) {
                jobsEl.appendChild(buildCard(job));
                if (!['completed', 'error', 'cancelled'].includes(job.status)) {
                    startSSE(job.id);
                }
            }
            if (jobs.length > 0 && jobs[0].max_tracks) {
                limitHint.textContent = `Limite: primeiras ${jobs[0].max_tracks} faixas por playlist`;
            }
            updateToolbar();
        } catch { /* server not ready yet */ }
    }
})();

function setAuthState(authenticated) {
    if (authenticated) {
        connectSection.classList.add('hidden');
        formSection.classList.remove('hidden');
        authIndicator.textContent = '● Conectado';
        authIndicator.classList.remove('hidden');
    } else {
        connectSection.classList.remove('hidden');
        formSection.classList.add('hidden');
        authIndicator.classList.add('hidden');
    }
}

function updateToolbar() {
    const hasJobs = jobsEl.children.length > 0;
    jobsToolbar.classList.toggle('hidden', !hasJobs);
}

// ── Form ─────────────────────────────────────────────────────────────────────
form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const url = urlInput.value.trim();
    if (!url) return;
    urlInput.value = '';
    await createJobFromUrl(url);
});

async function createJobFromUrl(url) {
    submitBtn.disabled = true;
    submitBtn.textContent = 'Aguarde...';
    try {
        const res = await fetch('/api/jobs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url }),
        });
        if (res.status === 401) {
            setAuthState(false);
            throw new Error('Sessão expirada. Reconecte sua conta Spotify.');
        }
        if (!res.ok) throw new Error((await res.json()).detail || `Erro ${res.status}`);

        const job = await res.json();
        if (job.max_tracks) limitHint.textContent = `Limite: primeiras ${job.max_tracks} faixas por playlist`;
        const card = buildCard(job);
        jobsEl.prepend(card);
        card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        startSSE(job.id);
        updateToolbar();
    } catch (err) {
        alert(`Erro: ${err.message}`);
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Baixar';
    }
}

// ── SSE ──────────────────────────────────────────────────────────────────────
function startSSE(jobId) {
    if (activeSSE[jobId]) return;
    const es = new EventSource(`/api/jobs/${jobId}/events`);
    activeSSE[jobId] = es;
    es.onmessage = (e) => {
        const job = JSON.parse(e.data);
        refreshCard(job);
        if (['completed', 'error', 'cancelled'].includes(job.status)) {
            es.close();
            delete activeSSE[jobId];
        }
    };
    es.onerror = () => { es.close(); delete activeSSE[jobId]; };
}

// ── Card rendering ───────────────────────────────────────────────────────────
function buildCard(job) {
    const card = document.createElement('div');
    card.className = 'job-card';
    card.id = `job-${job.id}`;
    card.dataset.url = job.url;
    card.innerHTML = cardHTML(job);
    return card;
}

function refreshCard(job) {
    const card = document.getElementById(`job-${job.id}`);
    if (!card) return;
    card.dataset.url = job.url;
    const listEl  = card.querySelector('.tracks-list');
    const wasOpen = listEl && !listEl.classList.contains('hidden');
    card.innerHTML = cardHTML(job);
    const newList = card.querySelector('.tracks-list');
    if (newList && !wasOpen) newList.classList.add('hidden');
    if (job.status === 'downloading') {
        card.querySelector('.track-item.is-downloading')?.scrollIntoView({ block: 'nearest' });
    }
}

function cardHTML(job) {
    const labels = {
        pending: 'Aguardando', fetching: 'Buscando...', downloading: 'Baixando',
        completed: 'Concluído', error: 'Erro', cancelled: 'Cancelado',
    };
    const title = job.playlist_name || (job.url.length > 65 ? job.url.slice(0, 62) + '…' : job.url);
    const pct   = job.total > 0 ? Math.round((job.done / job.total) * 100) : 0;
    return `
        <div class="job-header">
            <span class="job-url">${esc(title)}</span>
            <span class="status-badge badge-${job.status}">${labels[job.status] || job.status}</span>
        </div>
        <div class="job-body">${bodyHTML(job, pct)}</div>
    `;
}

function bodyHTML(job, pct) {
    if (job.status === 'error') {
        return `<div class="error-msg">${esc(job.error || 'Erro desconhecido')}</div>${actionsHTML(job)}`;
    }
    if (['pending', 'fetching'].includes(job.status)) {
        return `<div class="fetching-row"><div class="spinner"></div> Buscando faixas na API do Spotify…</div>${actionsHTML(job)}`;
    }
    if (job.total === 0) return '';

    let html = '';

    if (job.truncated) {
        html += `<div class="truncation-notice">⚠ Playlist tem ${job.original_total} faixas — baixando apenas as primeiras ${job.max_tracks}.</div>`;
    }

    html += `
        <div class="progress-row">
            <div class="progress-track"><div class="progress-fill" style="width:${pct}%"></div></div>
            <span class="progress-label">${job.done} / ${job.total}</span>
        </div>
    `;

    const downloading = job.tracks.filter(t => t.status === 'downloading');
    if (downloading.length > 0) {
        const names = downloading.map(t => `${esc(t.artist)} — ${esc(t.title)}`).join('<br>');
        html += `<div class="current-tracks"><span class="pulse">♪</span><div>${names}</div></div>`;
    }

    if (job.tracks.length > 0) html += trackListHTML(job.id, job.tracks);

    if (job.status === 'completed') {
        const downloaded = job.done - job.skipped - job.failed_count;
        let items = `<div class="summary-item"><div class="dot dot-green"></div> ${downloaded} baixada${downloaded !== 1 ? 's' : ''}</div>`;
        if (job.skipped > 0)      items += `<div class="summary-item"><div class="dot dot-yellow"></div> ${job.skipped} já existia${job.skipped !== 1 ? 'm' : ''}</div>`;
        if (job.failed_count > 0) items += `<div class="summary-item"><div class="dot dot-red"></div> ${job.failed_count} com erro</div>`;
        html += `<div class="summary">${items}</div>`;
    }

    html += actionsHTML(job);
    return html;
}

function actionsHTML(job) {
    const btns = [];

    if (['downloading', 'fetching'].includes(job.status)) {
        btns.push(`<button class="btn-danger" onclick="cancelJob('${job.id}', this)">Cancelar</button>`);
    }

    const retryable = job.tracks.filter(t => ['failed', 'cancelled'].includes(t.status)).length;
    if (['completed', 'cancelled'].includes(job.status) && retryable > 0) {
        btns.push(`<button class="btn-accent" onclick="retryJob('${job.id}', this)">Tentar novamente (${retryable})</button>`);
    }

    if (['completed', 'cancelled', 'error'].includes(job.status)) {
        btns.push(`<button class="btn-secondary" onclick="downloadAgain('${job.id}')">Baixar novamente</button>`);
    }

    return btns.length > 0 ? `<div class="card-actions">${btns.join('')}</div>` : '';
}

function trackListHTML(jobId, tracks) {
    const icons = {
        pending:     `<span style="color:var(--text-dim)">○</span>`,
        downloading: `<div class="spinner"></div>`,
        done:        `<span style="color:var(--accent)">✓</span>`,
        skipped:     `<span style="color:var(--warning)">–</span>`,
        failed:      `<span style="color:var(--error)">✗</span>`,
        cancelled:   `<span style="color:var(--text-dim)">⊘</span>`,
    };
    const items = tracks.map(t => `
        <div class="track-item is-${t.status}">
            <div class="track-icon">${icons[t.status] || '○'}</div>
            <div class="track-name">${esc(t.artist)} — ${esc(t.title)}</div>
        </div>
    `).join('');
    return `
        <button class="tracks-toggle" onclick="toggleList('tracks-${jobId}', this)">▾ Faixas (${tracks.length})</button>
        <div class="tracks-list" id="tracks-${jobId}">${items}</div>
    `;
}

// ── Actions ───────────────────────────────────────────────────────────────────
window.toggleList = function (listId, btn) {
    const el = document.getElementById(listId);
    if (!el) return;
    const hidden = el.classList.toggle('hidden');
    btn.textContent = (hidden ? '▸' : '▾') + btn.textContent.slice(1);
};

window.cancelJob = async function (jobId, btn) {
    btn.disabled = true;
    btn.textContent = 'Cancelando…';
    try { await fetch(`/api/jobs/${jobId}`, { method: 'DELETE' }); }
    catch { btn.disabled = false; btn.textContent = 'Cancelar'; }
};

window.retryJob = async function (jobId, btn) {
    btn.disabled = true;
    btn.textContent = 'Iniciando…';
    try {
        const res = await fetch(`/api/jobs/${jobId}/retry`, { method: 'POST' });
        if (!res.ok) throw new Error((await res.json()).detail);
        refreshCard(await res.json());
        startSSE(jobId);
    } catch (err) {
        alert(`Erro: ${err.message}`);
        btn.disabled = false;
        btn.textContent = 'Tentar novamente';
    }
};

window.downloadAgain = function (jobId) {
    const card = document.getElementById(`job-${jobId}`);
    if (card) createJobFromUrl(card.dataset.url);
};

window.clearHistory = async function () {
    const res = await fetch('/api/jobs', { method: 'DELETE' });
    const { removed } = await res.json();
    if (removed === 0) return;

    // Remove cards dos jobs finalizados do DOM
    document.querySelectorAll('.job-card').forEach(card => {
        const jobId = card.id.replace('job-', '');
        if (!activeSSE[jobId]) card.remove();
    });
    updateToolbar();
};

// ── Utils ─────────────────────────────────────────────────────────────────────
function esc(str) {
    return (str ?? '')
        .replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
