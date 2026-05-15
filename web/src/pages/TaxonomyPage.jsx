import { useEffect, useState } from 'react';
import { api } from '../api';

const CURRENT_RUN_KEY = 'reviewtrace.currentRun';

const EVIDENCE_TYPE_COLORS = {
  method_proposal: 'bg-blue-50 text-blue-700',
  empirical_finding: 'bg-green-50 text-green-700',
  theoretical_claim: 'bg-purple-50 text-purple-700',
  limitation: 'bg-red-50 text-red-700',
  comparison: 'bg-orange-50 text-orange-700',
  dataset_contribution: 'bg-yellow-50 text-yellow-700',
};

function EvidenceChip({ type }) {
  return (
    <span className={`px-2 py-0.5 rounded text-xs ${EVIDENCE_TYPE_COLORS[type] || 'bg-gray-100 text-gray-600'}`}>
      {type?.replace(/_/g, ' ')}
    </span>
  );
}

function NodeCard({ node }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      <div
        className="p-5 cursor-pointer hover:bg-gray-50 transition-colors"
        onClick={() => setExpanded((v) => !v)}
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="font-semibold text-gray-900">{node.label || 'Unnamed node'}</h3>
            <p className="text-sm text-gray-500 mt-1 leading-relaxed">{node.description}</p>
          </div>
          <div className="flex gap-2 shrink-0">
            <span className="text-xs bg-indigo-50 text-indigo-700 px-2 py-1 rounded-full font-medium">
              {node.paper_ids.length} papers
            </span>
            <span className="text-xs bg-gray-50 text-gray-600 px-2 py-1 rounded-full">
              {node.evidence_links.length} evidence
            </span>
          </div>
        </div>
      </div>

      {expanded && (
        <div className="border-t border-gray-100 px-5 pb-5 pt-3 space-y-3">
          {node.evidence_links.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">Evidence</div>
              <div className="space-y-2">
                {node.evidence_links.slice(0, 10).map((e, i) => (
                  <div key={i} className="flex gap-2 items-start text-sm">
                    <EvidenceChip type={e.evidence_type} />
                    <span className="text-gray-700 leading-snug">{e.content}</span>
                    {e.relevance_score != null && (
                      <span className="text-xs text-gray-400 whitespace-nowrap ml-auto">
                        {(e.relevance_score * 100).toFixed(0)}%
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function TaxonomyPage() {
  const [nodes, setNodes] = useState([]);
  const [loading, setLoading] = useState(true);

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
    api.taxonomy(dbPath)
      .then(setNodes)
      .catch(() => setNodes([]))
      .finally(() => setLoading(false));
  }, [dbPath]);

  if (loading) return <div className="p-8 text-center text-gray-400">Loading taxonomy…</div>;

  return (
    <div className="space-y-4">
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

      {nodes.length === 0 ? (
        <div className="p-8 text-center text-gray-400">
          No taxonomy nodes yet — run the pipeline first.
        </div>
      ) : (
        <div>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-800">{nodes.length} Taxonomy Nodes</h2>
            <span className="text-sm text-gray-400">Click a node to expand evidence</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {nodes.map((node) => <NodeCard key={node.id} node={node} />)}
          </div>
        </div>
      )}
    </div>
  );
}
