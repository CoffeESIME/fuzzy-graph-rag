// Development-only entry. No production code imports this fixture.
import { useState } from 'react';
import { createRoot } from 'react-dom/client';
import PathfinderRoutes from '../src/components/analysis/PathfinderRoutes';
import { exportPathfinder, readSavedPathfinder } from '../src/lib/pathfinderRoutes';
import fixture from './fixtures/canonical-pathfinder-v2.json';
import '../src/index.css';

function Harness() {
    const [result, setResult] = useState(readSavedPathfinder(fixture)!);
    const [light, setLight] = useState(true);
    return <main data-theme={light ? 'light' : 'dark'} style={{ padding: 20, background: 'var(--background)', color: 'var(--text-primary)' }}><h1>Fixture: tres rutas auditadas</h1><p>Dos consultas originales; no es un resultado mixto de una sola petición.</p>
        <button onClick={() => setLight(!light)}>Cambiar tema</button>
        <button onClick={() => setResult(readSavedPathfinder(JSON.parse(JSON.stringify(exportPathfinder(result))))!)}>Verificar round-trip v2</button>
        <PathfinderRoutes key={JSON.stringify(result)} result={result} />
    </main>;
}
createRoot(document.getElementById('root')!).render(<Harness />);
