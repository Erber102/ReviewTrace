import { NavLink, useLocation } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { api } from '../api';

const CURRENT_RUN_KEY = 'reviewtrace.currentRun';

const links = [
  { to: '/run', label: 'Run' },
  { to: '/papers', label: 'Papers' },
  { to: '/taxonomy', label: 'Taxonomy' },
  { to: '/audit', label: 'Audit' },
  { to: '/export', label: 'Export' },
];

function readCurrentRun() {
  try {
    const stored = localStorage.getItem(CURRENT_RUN_KEY);
    return stored ? JSON.parse(stored) : null;
  } catch { return null; }
}

export default function Navbar() {
  const [activeStats, setActiveStats] = useState(null);
  const [currentRun, setCurrentRun] = useState(readCurrentRun);
  const location = useLocation();

  function refresh() {
    setCurrentRun(readCurrentRun());
    api.stats().then(setActiveStats).catch(() => {});
  }

  // Re-sync on every navigation (picks up Clear actions from any page)
  useEffect(() => {
    refresh();
  }, [location.pathname]);

  // Re-sync when the pipeline signals completion
  useEffect(() => {
    window.addEventListener('stats:refresh', refresh);
    return () => window.removeEventListener('stats:refresh', refresh);
  }, []);

  // Prefer run-manifest stats when a run is selected
  const runStats = currentRun?.stats ?? null;
  const displayStats = runStats ?? activeStats;

  return (
    <nav className="bg-white border-b border-gray-200 sticky top-0 z-10">
      <div className="max-w-7xl mx-auto px-4 flex items-center h-14 gap-6">
        <span className="font-bold text-indigo-700 text-lg tracking-tight">ReviewTrace</span>

        <div className="flex gap-1">
          {links.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-indigo-50 text-indigo-700'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                }`
              }
            >
              {label}
            </NavLink>
          ))}
        </div>

        {displayStats && (
          <div className="ml-auto flex gap-4 text-xs text-gray-500">
            <span><span className="font-semibold text-gray-700">{displayStats.canonical_papers}</span> papers</span>
            <span><span className="font-semibold text-green-600">{displayStats.included}</span> included</span>
            <span><span className="font-semibold text-gray-700">{displayStats.taxonomy_nodes}</span> nodes</span>
          </div>
        )}
      </div>
    </nav>
  );
}
