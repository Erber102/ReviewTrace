import { useEffect, useState } from 'react';
import { api } from '../api';

const CURRENT_RUN_KEY = 'reviewtrace.currentRun';

const SOURCE_COLORS = {
  openalex: 'bg-blue-100 text-blue-700',
  semantic_scholar: 'bg-purple-100 text-purple-700',
  arxiv: 'bg-orange-100 text-orange-700',
};

const STATUS_COLORS = {
  done: 'bg-green-100 text-green-700',
  zero_results: 'bg-gray-100 text-gray-500',
  rate_limited: 'bg-orange-100 text-orange-700',
  skipped: 'bg-gray-100 text-gray-400',
  error: 'bg-red-100 text-red-700',
  pending: 'bg-yellow-100 text-yellow-700',
};

const STATUS_LABELS = {
  done: 'done',
  zero_results: 'zero results',
  rate_limited: 'rate limited',
  skipped: 'skipped',
  error: 'error',
  pending: 'pending',
};

function RunRow({ run }) {
  return (
    <div className="flex items-center gap-4 py-3 border-b border-gray-100 last:border-0">
      <div className="w-2 h-2 rounded-full bg-gray-300 shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`px-2 py-0.5 rounded text-xs font-medium ${SOURCE_COLORS[run.source] || 'bg-gray-100 text-gray-600'}`}>
            {run.source || 'unknown'}
          </span>
          <span className={`px-2 py-0.5 rounded text-xs ${STATUS_COLORS[run.status] || 'bg-gray-100 text-gray-500'}`}>
            {STATUS_LABELS[run.status] || run.status}
          </span>
          <span className="text-xs bg-gray-50 text-gray-500 px-2 py-0.5 rounded">
            {run.expansion_type}
          </span>
          {run.result_count != null && (
            <span className="text-xs text-gray-400">{run.result_count} results</span>
          )}
        </div>
        <div className="text-sm text-gray-700 mt-1 truncate">{run.query || '(no query)'}</div>
      </div>
      <div className="text-xs text-gray-400 whitespace-nowrap">
        {run.timestamp ? new Date(run.timestamp).toLocaleString() : ''}
      </div>
    </div>
  );
}

export default function AuditPage() {
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');

  const [currentRun, setCurrentRun] = useState(() => {
    try {
      const stored = localStorage.getItem(CURRENT_RUN_KEY);
      return stored ? JSON.parse(stored) : null;
    } catch { return null; }
  });

  const dbPath = currentRun?.db_path ?? null;

  function clearRun() {
    localStorage.removeItem(CURRENT_RUN_KEY);
    setCurrentRun(null);
  }

  useEffect(() => {
    setLoading(true);
    api.runs(dbPath)
      .then(setRuns)
      .catch(() => setRuns([]))
      .finally(() => setLoading(false));
  }, [dbPath]);

  const sources = ['all', ...new Set(runs.map((r) => r.source).filter(Boolean))];
  const visible = filter === 'all' ? runs : runs.filter((r) => r.source === filter);

  const stats = {
    total: runs.length,
    done: runs.filter((r) => r.status === 'done' || r.status === 'zero_results').length,
    total_results: runs.reduce((s, r) => s + (r.result_count || 0), 0),
  };

  return (
    <div className="space-y-4">
      {/* Selected run banner */}
      {currentRun && (
        <div className="flex flex-col gap-1.5 px-4 py-3 bg-indigo-50 border border-indigo-200 rounded-xl text-sm">
          <div className="flex items-center gap-3">
            <span className="text-indigo-700 font-medium shrink-0">Viewing run:</span>
            <span className="text-indigo-800 font-medium truncate flex-1" title={currentRun.topic}>
              {currentRun.topic || dbPath}
            </span>
            <button
              type="button"
              onClick={clearRun}
              className="shrink-0 text-xs text-indigo-500 hover:text-indigo-700 border border-indigo-200 hover:border-indigo-400 rounded px-2 py-0.5 transition-colors"
            >
              Clear
            </button>
          </div>
          <code className="text-indigo-400 font-mono text-xs truncate" title={dbPath}>{dbPath}</code>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Total Runs', value: stats.total },
          { label: 'Successful', value: stats.done },
          { label: 'Total Results', value: stats.total_results },
        ].map(({ label, value }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="text-2xl font-bold text-gray-900">{value}</div>
            <div className="text-sm text-gray-500">{label}</div>
          </div>
        ))}
      </div>

      {/* Runs list */}
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="flex items-center gap-3 p-4 border-b border-gray-100">
          <h2 className="font-semibold text-gray-800">Retrieval Runs</h2>
          <div className="flex gap-1 ml-auto">
            {sources.map((s) => (
              <button
                key={s}
                onClick={() => setFilter(s)}
                className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                  filter === s ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
        <div className="px-4">
          {loading ? (
            <div className="py-8 text-center text-gray-400">Loading…</div>
          ) : visible.length === 0 ? (
            <div className="py-8 text-center text-gray-400">No retrieval runs yet</div>
          ) : (
            visible.map((run) => <RunRow key={run.id} run={run} />)
          )}
        </div>
      </div>
    </div>
  );
}
