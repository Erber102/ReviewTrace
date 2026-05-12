import { NavLink, useLocation } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { api } from '../api';

const links = [
  { to: '/run', label: 'Run' },
  { to: '/papers', label: 'Papers' },
  { to: '/taxonomy', label: 'Taxonomy' },
  { to: '/audit', label: 'Audit' },
  { to: '/export', label: 'Export' },
];

export default function Navbar() {
  const [stats, setStats] = useState(null);
  const location = useLocation();

  function fetchStats() {
    api.stats().then(setStats).catch(() => {});
  }

  // Refetch on every navigation
  useEffect(() => {
    fetchStats();
  }, [location.pathname]);

  // Refetch when pipeline signals completion
  useEffect(() => {
    window.addEventListener('stats:refresh', fetchStats);
    return () => window.removeEventListener('stats:refresh', fetchStats);
  }, []);

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

        {stats && (
          <div className="ml-auto flex gap-4 text-xs text-gray-500">
            <span><span className="font-semibold text-gray-700">{stats.canonical_papers}</span> papers</span>
            <span><span className="font-semibold text-green-600">{stats.included}</span> included</span>
            <span><span className="font-semibold text-gray-700">{stats.taxonomy_nodes}</span> nodes</span>
          </div>
        )}
      </div>
    </nav>
  );
}
