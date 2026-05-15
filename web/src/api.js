const BASE = '';

async function get(path) {
  const r = await fetch(`${BASE}${path}`);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

async function post(path, body) {
  const r = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const text = await r.text();
    throw new Error(text || `${r.status} ${r.statusText}`);
  }
  return r.json();
}

export const api = {
  stats: () => get('/api/stats'),
  startRun: (params) => post('/api/run', params),
  getJob: (jobId) => get(`/api/jobs/${jobId}`),
  streamJob: (jobId, onEvent, onClose) => {
    const es = new EventSource(`/api/jobs/${jobId}/stream`);
    es.onmessage = (e) => {
      const event = JSON.parse(e.data);
      onEvent(event);
      if (event.type === 'done' || event.type === 'error') {
        es.close();
        onClose?.(event);
      }
    };
    es.onerror = () => {
      es.close();
      onClose?.({ type: 'error', message: 'Connection lost' });
    };
    return es;
  },
  papers: (decision = 'all', includeDuplicates = false, dbPath = null) => {
    let url = `/api/papers?decision=${decision}&include_duplicates=${includeDuplicates}`;
    if (dbPath) url += `&db_path=${encodeURIComponent(dbPath)}`;
    return get(url);
  },
  paper: (id, dbPath = null) => {
    const q = dbPath ? `?db_path=${encodeURIComponent(dbPath)}` : '';
    return get(`/api/papers/${id}${q}`);
  },
  paperAudit: (id, dbPath = null) => {
    const q = dbPath ? `?db_path=${encodeURIComponent(dbPath)}` : '';
    return get(`/api/papers/${id}/audit${q}`);
  },
  runs: (dbPath = null) => {
    const q = dbPath ? `?db_path=${encodeURIComponent(dbPath)}` : '';
    return get(`/api/runs${q}`);
  },
  reviewRuns: () => get('/api/review-runs'),
  taxonomy: (dbPath = null) => {
    const q = dbPath ? `?db_path=${encodeURIComponent(dbPath)}` : '';
    return get(`/api/taxonomy${q}`);
  },
  evidence: (paperId, dbPath = null) => {
    let url = paperId ? `/api/evidence?paper_id=${paperId}` : '/api/evidence';
    if (dbPath) url += `${paperId ? '&' : '?'}db_path=${encodeURIComponent(dbPath)}`;
    return get(url);
  },
  exports: (outputDir) => get(outputDir ? `/api/export?output_dir=${encodeURIComponent(outputDir)}` : '/api/export'),
  exportManifest: (outputDir) => get(outputDir ? `/api/export/manifest?output_dir=${encodeURIComponent(outputDir)}` : '/api/export/manifest'),
};
