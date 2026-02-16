import { GitBranch } from 'lucide-react';

export default function GraphCrispTab() {
    return (
        <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            justifyContent: 'center', padding: '60px 20px',
            textAlign: 'center',
        }}>
            <div style={{
                width: 80, height: 80, borderRadius: '50%',
                background: 'rgba(99, 102, 241, 0.1)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                marginBottom: 24,
            }}>
                <GitBranch size={36} color="var(--accent-indigo)" />
            </div>

            <h3 style={{
                fontSize: '1.3rem', fontWeight: 700,
                color: 'var(--text-primary)', marginBottom: 8,
            }}>
                Búsqueda en Grafo
            </h3>

            <p style={{
                fontSize: '0.9rem', color: 'var(--text-secondary)',
                maxWidth: 400, lineHeight: 1.6,
                marginBottom: 24,
            }}>
                La búsqueda por relaciones en Neo4j está en desarrollo.
                Pronto podrás explorar personas, conceptos y sus conexiones
                directamente desde aquí.
            </p>

            <span style={{
                display: 'inline-flex', alignItems: 'center', gap: 8,
                padding: '8px 20px', borderRadius: 20,
                fontSize: '0.8rem', fontWeight: 600,
                background: 'rgba(245, 158, 11, 0.12)',
                color: '#f59e0b',
                border: '1px solid rgba(245, 158, 11, 0.25)',
            }}>
                🚧 Coming Soon
            </span>
        </div>
    );
}
