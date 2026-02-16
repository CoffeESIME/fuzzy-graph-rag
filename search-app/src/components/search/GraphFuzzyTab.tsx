import { Radar } from 'lucide-react';

export default function GraphFuzzyTab() {
    return (
        <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            justifyContent: 'center', padding: '60px 20px',
            textAlign: 'center',
        }}>
            <div style={{
                width: 80, height: 80, borderRadius: '50%',
                background: 'rgba(139, 92, 246, 0.1)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                marginBottom: 24,
            }}>
                <Radar size={36} color="#8b5cf6" />
            </div>

            <h3 style={{
                fontSize: '1.3rem', fontWeight: 700,
                color: 'var(--text-primary)', marginBottom: 8,
            }}>
                Grafo Difuso
            </h3>

            <p style={{
                fontSize: '0.9rem', color: 'var(--text-secondary)',
                maxWidth: 400, lineHeight: 1.6,
                marginBottom: 24,
            }}>
                La expansión difusa con pesos calibrados sobre el grafo
                de conocimiento está en desarrollo. Permitirá descubrir
                conexiones indirectas y relaciones implícitas.
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
