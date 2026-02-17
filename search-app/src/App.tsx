import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import SearchPage from './components/search/SearchPage';
import HomePage from './components/HomePage';
import AnalysisDashboard from './components/analysis/AnalysisDashboard';
import AnalysisPlaceholder from './components/analysis/AnalysisPlaceholder';
import CommunityAnalysisCard from './components/analysis/CommunityAnalysisCard';
import BridgeAnalysisCard from './components/analysis/BridgeAnalysisCard';
import SerendipityCard from './components/analysis/SerendipityCard';
import FogOfWarCard from './components/analysis/FogOfWarCard';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/analysis" element={<AnalysisDashboard />} />
        <Route path="/analysis/communities" element={<CommunityAnalysisCard />} />
        <Route path="/analysis/bridges" element={<BridgeAnalysisCard />} />
        <Route path="/analysis/serendipity" element={<SerendipityCard />} />
        <Route path="/analysis/fog-of-war" element={<FogOfWarCard />} />
        <Route path="/analysis/:toolId" element={<AnalysisPlaceholder />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
