import { useEffect, useState } from 'react';
import { api } from '../api';

const CURRENT_RUN_KEY = 'reviewtrace.currentRun';
const LEGACY_OUTPUT_DIR_KEY = 'reviewtrace.currentOutputDir';

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

function downloadUrl(kind, outputDir) {
  if (outputDir) return `/api/export/${kind}?output_dir=${encodeURIComponent(outputDir)}`;
  return `/api/export/${kind}`;
}

export default function ExportPage() {
  const [exports, setExports] = useState([]);
  const [dbStats, setDbStats] = useState(null);
  const [manifestStats, setManifestStats] = useState(null);
  const [loading, setLoading] = useState(true);

  // Read current run from localStorage. Fall back to legacy output_dir key if present.
  const [currentRun, setCurrentRun] = useState(() => {
    try {
      const stored = localStorage.getItem(CURRENT_RUN_KEY);
      if (stored) return JSON.parse(stored);
    } catch {}
    const legacyDir = localStorage.getItem(LEGACY_OUTPUT_DIR_KEY);
    return legacyDir ? { output_dir: legacyDir } : null;
  });

  const outputDir = currentRun?.output_dir ?? null;

  function clearRun() {
    localStorage.removeItem(CURRENT_RUN_KEY);
    localStorage.removeItem(LEGACY_OUTPUT_DIR_KEY);
    setCurrentRun(null);
  }

  useEffect(() => {
    setLoading(true);
    setManifestStats(null);
    const fetches = [api.exports(outputDir), api.stats()];
    if (outputDir) fetches.push(api.exportManifest(outputDir).catch(() => null));
    Promise.all(fetches)
      .then(([exps, st, manifest]) => {
        setExports(exps);
        setDbStats(st);
        setManifestStats(manifest?.stats ?? null);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [outputDir]);

  // Use manifest stats when viewing a historical run and they're available; fall back to DB.
  const stats = (outputDir && manifestStats) ? manifestStats : dbStats;
  const statsSource = (outputDir && manifestStats) ? 'manifest' : 'db';

  if (loading) return <div className="p-8 text-center text-gray-400">Loading…</div>;

  return (
    <div className="space-y-6">

      {/* Active run banner */}
      {currentRun && (
        <div className="flex flex-col gap-1.5 px-4 py-3 bg-indigo-50 border border-indigo-200 rounded-xl text-sm">
          <div className="flex items-center gap-3">
            <span className="text-indigo-700 font-medium shrink-0">Viewing run:</span>
            <span className="text-indigo-800 font-medium truncate flex-1" title={currentRun.topic}>
              {currentRun.topic || outputDir}
            </span>
            <button
              type="button"
              onClick={clearRun}
              className="shrink-0 text-xs text-indigo-500 hover:text-indigo-700 border border-indigo-200 hover:border-indigo-400 rounded px-2 py-0.5 transition-colors"
            >
              Clear
            </button>
          </div>
          <code className="text-indigo-400 font-mono text-xs truncate" title={outputDir}>{outputDir}</code>
        </div>
      )}

      {/* Stats */}
      {stats && (
        <div className="space-y-2">
          <p className="text-xs text-gray-400 px-0.5">
            {statsSource === 'manifest'
              ? 'Stats from selected run manifest'
              : 'Stats from active database'}
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {(statsSource === 'manifest' ? [
              { label: 'Canonical Papers', value: stats.canonical_papers, color: 'text-gray-900' },
              { label: 'Included', value: stats.included, color: 'text-green-600' },
              { label: 'Excluded', value: stats.excluded, color: 'text-red-600' },
              { label: 'Duplicates removed', value: stats.duplicates, color: 'text-gray-400' },
              { label: 'Evidence items', value: stats.evidence_items, color: 'text-gray-900' },
              { label: 'Taxonomy nodes', value: stats.taxonomy_nodes, color: 'text-indigo-600' },
              { label: 'Retrieval runs', value: stats.retrieval_runs, color: 'text-gray-900' },
              { label: 'Unscreened', value: stats.unscreened, color: 'text-yellow-600' },
            ] : [
              { label: 'Canonical Papers', value: stats.canonical_papers, color: 'text-gray-900' },
              { label: 'Included', value: stats.included, color: 'text-green-600' },
              { label: 'Excluded', value: stats.excluded, color: 'text-red-600' },
              { label: 'Duplicates removed', value: stats.duplicates, color: 'text-gray-400' },
              { label: 'Evidence items', value: stats.total_evidence, color: 'text-gray-900' },
              { label: 'Taxonomy nodes', value: stats.taxonomy_nodes, color: 'text-indigo-600' },
              { label: 'Retrieval runs', value: stats.total_runs, color: 'text-gray-900' },
              { label: 'Unscreened', value: stats.unscreened, color: 'text-yellow-600' },
            ]).map(({ label, value, color }) => (
              <div key={label} className="bg-white rounded-xl border border-gray-200 p-4">
                <div className={`text-2xl font-bold ${color}`}>{value}</div>
                <div className="text-sm text-gray-500 mt-0.5">{label}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Downloads */}
      <div className="bg-white rounded-xl border border-gray-200 divide-y divide-gray-100">
        <div className="px-6 py-4">
          <h2 className="font-semibold text-gray-800">Download Outputs</h2>
          <p className="text-sm text-gray-400 mt-0.5">
            Files are generated in the{' '}
            <code className="font-mono text-xs bg-gray-100 px-1 rounded">{outputDir || 'outputs/'}</code>{' '}
            directory when you run the pipeline.
          </p>
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
                    href={downloadUrl(exp.kind, outputDir)}
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
