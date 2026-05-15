import { useEffect, useState } from 'react';
import { api } from '../api';

const CURRENT_RUN_KEY = 'reviewtrace.currentRun';

const DECISION_COLORS = {
  include: 'bg-green-100 text-green-700',
  exclude: 'bg-red-100 text-red-700',
  uncertain: 'bg-yellow-100 text-yellow-700',
};

function DecisionBadge({ decision }) {
  if (!decision) return <span className="text-gray-400 text-xs">—</span>;
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${DECISION_COLORS[decision] || 'bg-gray-100 text-gray-600'}`}>
      {decision}
    </span>
  );
}

function SourceBadge({ sourceType }) {
  if (!sourceType) return null;
  const colors = {
    peer_reviewed: 'bg-blue-50 text-blue-700',
    preprint: 'bg-purple-50 text-purple-700',
    workshop: 'bg-orange-50 text-orange-700',
    blog: 'bg-gray-50 text-gray-600',
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs ${colors[sourceType] || 'bg-gray-50 text-gray-500'}`}>
      {sourceType}
    </span>
  );
}

function PaperRow({ paper, dbPath }) {
  const [expanded, setExpanded] = useState(false);
  const [audit, setAudit] = useState(null);

  async function toggleExpand() {
    if (!expanded && !audit) {
      const entries = await api.paperAudit(paper.id, dbPath).catch(() => []);
      setAudit(entries);
    }
    setExpanded((v) => !v);
  }

  const authors = (() => {
    try {
      const arr = JSON.parse(paper.authors || '[]');
      return Array.isArray(arr) ? arr.slice(0, 3).join(', ') + (arr.length > 3 ? ' et al.' : '') : paper.authors;
    } catch { return paper.authors || ''; }
  })();

  return (
    <>
      <tr
        className={`border-b border-gray-100 hover:bg-gray-50 cursor-pointer ${paper.is_duplicate ? 'opacity-40' : ''}`}
        onClick={toggleExpand}
      >
        <td className="py-3 px-4 text-sm font-medium text-gray-900 max-w-xs">
          <div className="line-clamp-2">{paper.title || '(no title)'}</div>
          <div className="text-xs text-gray-400 mt-0.5">{authors}</div>
        </td>
        <td className="py-3 px-4 text-sm text-gray-500 whitespace-nowrap">{paper.year || '—'}</td>
        <td className="py-3 px-4 text-sm text-gray-500 max-w-[160px] truncate">{paper.venue || '—'}</td>
        <td className="py-3 px-4"><DecisionBadge decision={paper.decision} /></td>
        <td className="py-3 px-4"><SourceBadge sourceType={paper.source_type} /></td>
        <td className="py-3 px-4 text-xs text-gray-400">{paper.is_duplicate ? 'dup' : ''}</td>
      </tr>
      {expanded && (
        <tr className="bg-gray-50 border-b border-gray-200">
          <td colSpan={6} className="px-6 pb-4 pt-2">
            {paper.abstract && (
              <div className="mb-3">
                <div className="text-xs font-semibold text-gray-500 mb-1 uppercase tracking-wide">Abstract</div>
                <p className="text-sm text-gray-700 leading-relaxed">{paper.abstract}</p>
              </div>
            )}
            {paper.reason && (
              <div className="mb-3">
                <div className="text-xs font-semibold text-gray-500 mb-1 uppercase tracking-wide">Screening Reason</div>
                <p className="text-sm text-gray-700">{paper.reason}</p>
                {paper.confidence != null && (
                  <span className="text-xs text-gray-400">confidence: {(paper.confidence * 100).toFixed(0)}%</span>
                )}
              </div>
            )}
            {audit && audit.length > 0 && (
              <div>
                <div className="text-xs font-semibold text-gray-500 mb-1 uppercase tracking-wide">Retrieval Provenance</div>
                <div className="space-y-1">
                  {audit.map((e, i) => (
                    <div key={i} className="text-xs text-gray-600 font-mono bg-white rounded px-2 py-1 border border-gray-200">
                      [{e.source}] {e.query} {e.citation_path ? `— ${e.citation_path}` : ''}
                    </div>
                  ))}
                </div>
              </div>
            )}
            {paper.doi && (
              <a
                href={`https://doi.org/${paper.doi}`}
                target="_blank"
                rel="noreferrer"
                className="inline-block mt-2 text-xs text-indigo-600 hover:underline"
                onClick={(e) => e.stopPropagation()}
              >
                doi:{paper.doi}
              </a>
            )}
            {paper.arxiv_id && (
              <a
                href={`https://arxiv.org/abs/${paper.arxiv_id}`}
                target="_blank"
                rel="noreferrer"
                className="inline-block mt-2 ml-3 text-xs text-indigo-600 hover:underline"
                onClick={(e) => e.stopPropagation()}
              >
                arXiv:{paper.arxiv_id}
              </a>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

export default function PapersPage() {
  const [papers, setPapers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [showDuplicates, setShowDuplicates] = useState(false);

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
    api.papers(filter, showDuplicates, dbPath)
      .then(setPapers)
      .catch(() => setPapers([]))
      .finally(() => setLoading(false));
  }, [filter, showDuplicates, dbPath]);

  const visible = papers.filter((p) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (p.title || '').toLowerCase().includes(q) || (p.venue || '').toLowerCase().includes(q);
  });

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

    <div className="bg-white rounded-xl border border-gray-200">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3 p-4 border-b border-gray-100">
        <input
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm w-56 focus:outline-none focus:ring-2 focus:ring-indigo-400"
          placeholder="Search title or venue…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <div className="flex gap-1">
          {['all', 'include', 'exclude', 'uncertain', 'unscreened'].map((d) => (
            <button
              key={d}
              onClick={() => setFilter(d)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                filter === d ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {d}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-1.5 text-xs text-gray-600 ml-auto">
          <input type="checkbox" checked={showDuplicates} onChange={(e) => setShowDuplicates(e.target.checked)} />
          Show duplicates
        </label>
        <span className="text-xs text-gray-400">{visible.length} papers</span>
      </div>

      {/* Table */}
      {loading ? (
        <div className="p-8 text-center text-gray-400">Loading…</div>
      ) : visible.length === 0 ? (
        <div className="p-8 text-center text-gray-400">No papers found</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-xs font-medium text-gray-500 uppercase tracking-wide border-b border-gray-100">
                <th className="text-left py-2 px-4">Title / Authors</th>
                <th className="text-left py-2 px-4">Year</th>
                <th className="text-left py-2 px-4">Venue</th>
                <th className="text-left py-2 px-4">Decision</th>
                <th className="text-left py-2 px-4">Source Type</th>
                <th className="py-2 px-4"></th>
              </tr>
            </thead>
            <tbody>
              {visible.map((p) => <PaperRow key={p.id} paper={p} dbPath={dbPath} />)}
            </tbody>
          </table>
        </div>
      )}
    </div>
    </div>
  );
}
