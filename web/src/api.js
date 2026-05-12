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
  papers: (decision = 'all', includeDuplicates = false) =>
    get(`/api/papers?decision=${decision}&include_duplicates=${includeDuplicates}`),
  paper: (id) => get(`/api/papers/${id}`),
  paperAudit: (id) => get(`/api/papers/${id}/audit`),
  runs: () => get('/api/runs'),
  taxonomy: () => get('/api/taxonomy'),
  evidence: (paperId) =>
    paperId ? get(`/api/evidence?paper_id=${paperId}`) : get('/api/evidence'),
  exports: () => get('/api/export'),
};
