import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import SearchPage from './components/search/SearchPage';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/search" element={<SearchPage />} />
        <Route path="*" element={<Navigate to="/search" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
