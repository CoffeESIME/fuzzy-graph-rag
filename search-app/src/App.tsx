import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import SearchPage from './components/search/SearchPage';
import HomePage from './components/HomePage';
import AnalysisDashboard from './components/analysis/AnalysisDashboard';
import AnalysisPlaceholder from './components/analysis/AnalysisPlaceholder';
import CommunityAnalysisCard from './components/analysis/CommunityAnalysisCard';
import BridgeAnalysisCard from './components/analysis/BridgeAnalysisCard';
import SerendipityCard from './components/analysis/SerendipityCard';
import FogOfWarCard from './components/analysis/FogOfWarCard';
import HeatmapAnalysisCard from './components/analysis/HeatmapAnalysisCard';
import ChordAnalysisCard from './components/analysis/ChordAnalysisCard';
import PageRankCard from './components/analysis/PageRankCard';
import RadialTreeCard from './components/analysis/RadialTreeCard';
import AbstractConceptsCard from './components/analysis/AbstractConceptsCard';
import OrphansCard from './components/analysis/OrphansCard';
import WeightDistributionCard from './components/analysis/WeightDistributionCard';

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
        <Route path="/analysis/heatmap" element={<HeatmapAnalysisCard />} />
        <Route path="/analysis/chord" element={<ChordAnalysisCard />} />
        <Route path="/analysis/pagerank" element={<PageRankCard />} />
        <Route path="/analysis/radial-tree" element={<RadialTreeCard />} />
        <Route path="/analysis/abstract-concepts" element={<AbstractConceptsCard />} />
        <Route path="/analysis/orphans" element={<OrphansCard />} />
        <Route path="/analysis/weight-distribution" element={<WeightDistributionCard />} />
        <Route path="/analysis/:toolId" element={<AnalysisPlaceholder />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
