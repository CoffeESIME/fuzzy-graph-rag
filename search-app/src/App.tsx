import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import SearchPage from './components/search/SearchPage';
import HomePage from './components/HomePage';
import AnalysisDashboard from './components/analysis/AnalysisDashboard';
import AnalysisPlaceholder from './components/analysis/AnalysisPlaceholder';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/analysis" element={<AnalysisDashboard />} />
        <Route path="/analysis/:toolId" element={<AnalysisPlaceholder />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
