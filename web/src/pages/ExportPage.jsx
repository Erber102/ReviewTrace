import { useEffect, useState } from 'react';
import { api } from '../api';

const KIND_LABELS = {
  papers: { label: 'Papers CSV', desc: 'All papers with screening decisions and duplicate flags' },
  audit: { label: 'Audit JSON', desc: 'Full retrieval provenance in JSON format' },
  'audit-md': { label: 'Audit Markdown', desc: 'Human-readable audit report' },
  graphml: { label: 'Citation Graph', desc: 'GraphML file for Gephi / Cytoscape' },
  'evidence-matrix': { label: 'Evidence Matrix', desc: 'Paper × evidence type count matrix (CSV)' },
  'evidence-items': { label: 'Evidence Items', desc: 'Full extracted evidence grouped by paper (JSON)' },
  taxonomy: { label: 'Taxonomy', desc: 'Thematic clusters with labelled nodes and evidence (Markdown)' },
};

function formatBytes(bytes) {
  if (bytes == null) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function ExportPage() {
  const [exports, setExports] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.exports(), api.stats()])
      .then(([exps, st]) => { setExports(exps); setStats(st); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-8 text-center text-gray-400">Loading…</div>;

  return (
    <div className="space-y-6">
      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            { label: 'Canonical Papers', value: stats.canonical_papers, color: 'text-gray-900' },
            { label: 'Included', value: stats.included, color: 'text-green-600' },
            { label: 'Excluded', value: stats.excluded, color: 'text-red-600' },
            { label: 'Duplicates removed', value: stats.duplicates, color: 'text-gray-400' },
            { label: 'Evidence items', value: stats.total_evidence, color: 'text-gray-900' },
            { label: 'Taxonomy nodes', value: stats.taxonomy_nodes, color: 'text-indigo-600' },
            { label: 'Retrieval runs', value: stats.total_runs, color: 'text-gray-900' },
            { label: 'Unscreened', value: stats.unscreened, color: 'text-yellow-600' },
          ].map(({ label, value, color }) => (
            <div key={label} className="bg-white rounded-xl border border-gray-200 p-4">
              <div className={`text-2xl font-bold ${color}`}>{value}</div>
              <div className="text-sm text-gray-500 mt-0.5">{label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Downloads */}
      <div className="bg-white rounded-xl border border-gray-200 divide-y divide-gray-100">
        <div className="px-6 py-4">
          <h2 className="font-semibold text-gray-800">Download Outputs</h2>
          <p className="text-sm text-gray-400 mt-0.5">Files are generated in the <code className="font-mono text-xs bg-gray-100 px-1 rounded">outputs/</code> directory when you run the pipeline.</p>
        </div>
        {exports.map((exp) => {
          const meta = KIND_LABELS[exp.kind] || { label: exp.kind, desc: '' };
          return (
            <div key={exp.kind} className="flex items-center gap-4 px-6 py-4">
              <div className="flex-1">
                <div className="font-medium text-gray-900 text-sm">{meta.label}</div>
                <div className="text-xs text-gray-400 mt-0.5">{meta.desc}</div>
                <div className="text-xs text-gray-300 font-mono mt-0.5">{exp.filename}</div>
              </div>
              {exp.available ? (
                <div className="flex items-center gap-3">
                  <span className="text-xs text-gray-400">{formatBytes(exp.size_bytes)}</span>
                  <a
                    href={`/api/export/${exp.kind}`}
                    download={exp.filename}
                    className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-lg transition-colors"
                  >
                    Download
                  </a>
                </div>
              ) : (
                <span className="text-xs text-gray-300 bg-gray-50 px-3 py-1.5 rounded-lg">Not generated</span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
