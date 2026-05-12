import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import Navbar from './components/Navbar';
import AuditPage from './pages/AuditPage';
import ExportPage from './pages/ExportPage';
import PapersPage from './pages/PapersPage';
import RunPage from './pages/RunPage';
import TaxonomyPage from './pages/TaxonomyPage';

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50">
        <Navbar />
        <main className="max-w-7xl mx-auto px-4 py-6">
          <Routes>
            <Route path="/" element={<Navigate to="/run" replace />} />
            <Route path="/run" element={<RunPage />} />
            <Route path="/papers" element={<PapersPage />} />
            <Route path="/taxonomy" element={<TaxonomyPage />} />
            <Route path="/audit" element={<AuditPage />} />
            <Route path="/export" element={<ExportPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
