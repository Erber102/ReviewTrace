import { useEffect, useRef, useState } from 'react';
import { api } from '../api';

const STEP_LABELS = {
  retrieval: 'Retrieval',
  seeds: 'Seeds',
  dedup: 'Dedup',
  expand: 'Expansion',
  screening: 'Screening',
  evidence: 'Evidence',
  taxonomy: 'Taxonomy',
  export: 'Export',
};

function Badge({ type }) {
  const cls = {
    progress: 'bg-blue-100 text-blue-700',
    done: 'bg-green-100 text-green-700',
    error: 'bg-red-100 text-red-700',
  }[type] || 'bg-gray-100 text-gray-600';
  const label = { progress: '…', done: '✓', error: '✗' }[type] || type;
  return <span className={`inline-block px-1.5 py-0.5 rounded text-xs font-mono ${cls}`}>{label}</span>;
}

export default function RunPage() {
  const DEMO_DEFAULTS = { max_results: 10, depth: 0, skip_expand: true, max_queries: 3 };
  const FULL_DEFAULTS = { max_results: 50, depth: 2, skip_expand: false, max_queries: null };

  const [form, setForm] = useState({
    topic: '',
    seeds: '',
    criteria_topic: '',
    inclusion: '',
    exclusion: '',
    max_results: 10,
    depth: 0,
    max_per_hop: 30,
    llm_delay: 0.5,
    skip_expand: true,
    demo: true,
    max_queries: 3,
  });
  const [running, setRunning] = useState(false);
  const [logs, setLogs] = useState([]);
  const [done, setDone] = useState(false);
  const logRef = useRef(null);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logs]);

  function set(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  function toggleDemo(enabled) {
    setForm((f) => ({ ...f, demo: enabled, ...(enabled ? DEMO_DEFAULTS : FULL_DEFAULTS) }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setRunning(true);
    setDone(false);
    setLogs([]);

    const payload = {
      ...form,
      inclusion: form.inclusion.split('\n').map((s) => s.trim()).filter(Boolean),
      exclusion: form.exclusion.split('\n').map((s) => s.trim()).filter(Boolean),
      max_results: Number(form.max_results),
      depth: Number(form.depth),
      max_per_hop: Number(form.max_per_hop),
      llm_delay: Number(form.llm_delay),
      max_queries: form.max_queries != null ? Number(form.max_queries) : null,
    };

    try {
      const { job_id } = await api.startRun(payload);
      api.streamJob(
        job_id,
        (event) => setLogs((prev) => [...prev, event]),
        () => {
          setRunning(false);
          setDone(true);
          window.dispatchEvent(new CustomEvent('stats:refresh'));
        }
      );
    } catch (err) {
      setLogs([{ type: 'error', message: err.message }]);
      setRunning(false);
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Form */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="text-lg font-semibold mb-4">Pipeline Configuration</h2>
        <form onSubmit={handleSubmit} className="space-y-4">

          {/* Demo mode toggle */}
          <div className={`flex items-center justify-between px-3 py-2 rounded-lg border ${form.demo ? 'bg-amber-50 border-amber-300' : 'bg-gray-50 border-gray-200'}`}>
            <div>
              <span className="text-sm font-medium text-gray-700">Demo mode</span>
              <p className="text-xs text-gray-500 mt-0.5">3 queries · max 10 results · no citation expansion</p>
            </div>
            <button
              type="button"
              onClick={() => toggleDemo(!form.demo)}
              className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${form.demo ? 'bg-amber-400' : 'bg-gray-300'}`}
            >
              <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${form.demo ? 'translate-x-4' : 'translate-x-1'}`} />
            </button>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Topic *</label>
            <input
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
              placeholder="e.g. Sparse Autoencoders for Mechanistic Interpretability"
              value={form.topic}
              onChange={(e) => set('topic', e.target.value)}
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Seed Papers</label>
            <textarea
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-indigo-400"
              rows={3}
              placeholder={'arXiv:2309.05144\n10.1234/example.doi'}
              value={form.seeds}
              onChange={(e) => set('seeds', e.target.value)}
              spellCheck={false}
            />
            <p className="text-xs text-gray-400 mt-1">One arXiv ID or DOI per line</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Inclusion Criteria</label>
            <textarea
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
              rows={3}
              placeholder="One criterion per line"
              value={form.inclusion}
              onChange={(e) => set('inclusion', e.target.value)}
              spellCheck={false}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Exclusion Criteria</label>
            <textarea
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
              rows={3}
              placeholder="One criterion per line"
              value={form.exclusion}
              onChange={(e) => set('exclusion', e.target.value)}
              spellCheck={false}
            />
          </div>

          {/* Advanced options */}
          <details className="group">
            <summary className="cursor-pointer text-sm font-medium text-gray-500 hover:text-gray-700">
              Advanced options
            </summary>
            <div className="mt-3 grid grid-cols-2 gap-3">
              {[
                { field: 'max_results', label: 'Max results/query', type: 'number' },
                { field: 'depth', label: 'Expansion depth', type: 'number' },
                { field: 'max_per_hop', label: 'Max papers/hop', type: 'number' },
                { field: 'llm_delay', label: 'LLM delay (s)', type: 'number', step: '0.1' },
              ].map(({ field, label, ...rest }) => (
                <div key={field}>
                  <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
                  <input
                    className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
                    value={form[field]}
                    onChange={(e) => set(field, e.target.value)}
                    {...rest}
                  />
                </div>
              ))}
              <div className="col-span-2 flex items-center gap-2">
                <input
                  type="checkbox"
                  id="skip_expand"
                  checked={form.skip_expand}
                  onChange={(e) => set('skip_expand', e.target.checked)}
                  className="rounded"
                />
                <label htmlFor="skip_expand" className="text-sm text-gray-600">Skip citation expansion</label>
              </div>
            </div>
          </details>

          <button
            type="submit"
            disabled={running || !form.topic.trim()}
            className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-300 text-white font-medium py-2.5 rounded-lg transition-colors text-sm"
          >
            {running ? 'Running…' : 'Run Pipeline'}
          </button>
        </form>
      </div>

      {/* Log */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 flex flex-col">
        <h2 className="text-lg font-semibold mb-4">Progress</h2>
        <div
          ref={logRef}
          className="flex-1 min-h-64 bg-gray-950 rounded-lg p-4 overflow-y-auto font-mono text-xs space-y-1"
        >
          {logs.length === 0 && (
            <p className="text-gray-500">Pipeline output will appear here…</p>
          )}
          {logs.map((event, i) => (
            <div key={i} className="flex gap-2 items-start">
              <Badge type={event.type} />
              {event.step && (
                <span className="text-gray-400 w-20 shrink-0">
                  {STEP_LABELS[event.step] || event.step}
                </span>
              )}
              <span className={event.type === 'error' ? 'text-red-400' : event.type === 'done' ? 'text-green-400' : 'text-gray-200'}>
                {event.message}
              </span>
            </div>
          ))}
        </div>
        {done && (
          <div className="mt-3 text-sm text-green-700 bg-green-50 rounded-lg px-4 py-2">
            Pipeline complete. Go to <a href="/papers" className="underline font-medium">Papers</a> or <a href="/export" className="underline font-medium">Export</a> to see results.
          </div>
        )}
      </div>
    </div>
  );
}
