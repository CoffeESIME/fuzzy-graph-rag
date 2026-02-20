import { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { ResponsiveChord } from '@nivo/chord';
import { RefreshCw, Loader2, Info } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface ChordData {
    keys: string[];
    matrix: number[][];
    method?: string;
}

interface AnalysisResponse {
    tool: string;
    status: string;
    message: string;
    mock_data: ChordData;
}

type ChordMode = 'standard' | 'fuzzy';

const NARRATIVES: Record<ChordMode, { title: string; icon: string; desc: string }> = {
    standard: {
        title: 'Flujo Literal',
        icon: '🔗',
        desc: 'Cuenta el volumen físico de archivos que conectan dos categorías. Ideal para ver la distribución de tu base de datos.',
    },
    fuzzy: {
        title: 'Flujo Semántico',
        icon: '🧠',
        desc: 'Filtra el ruido usando los pesos de la IA. Muestra cintas gruesas solo cuando la IA tiene alta certeza de que dos categorías están profundamente relacionadas en el mismo contexto.',
    },
};

// Fixed vibrant colors per category (order matches backend categories array)
// Person, Organization, Location, Concept, Event, Project
const CATEGORY_COLORS = ['#60a5fa', '#34d399', '#f87171', '#a78bfa', '#fbbf24', '#f472b6'];

const CATEGORY_ICONS: Record<string, string> = {
    Person: '👤',
    Organization: '🏢',
    Location: '📍',
    Concept: '💡',
    Event: '📅',
    Project: '📁',
};

export default function ChordAnalysisCard() {
    const [data, setData] = useState<ChordData | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [message, setMessage] = useState('');
    const [method, setMethod] = useState<ChordMode>('standard');
    const navigate = useNavigate();

    const fetchData = useCallback(async (m: ChordMode) => {
        setLoading(true);
        setError(null);
        try {
            const res = await axios.post<AnalysisResponse>(
                `http://localhost:8000/analysis/chord?method=${m}`
            );
            if (res.data.status === 'error') throw new Error(res.data.message);
            setData(res.data.mock_data);
            setMessage(res.data.message);
        } catch (err: any) {
            console.error(err);
            setError(err.message || 'Error fetching chord data');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { fetchData(method); }, [method, fetchData]);

    const narrative = NARRATIVES[method];

    return (
        <div style={{ padding: 24, paddingBottom: 60, maxWidth: 1200, margin: '0 auto' }}>
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-4">
                    <button onClick={() => navigate('/analysis')} className="btn-secondary">Back</button>
                    <div>
                        <h2 className="text-2xl font-bold flex items-center gap-2 text-slate-100">
                            🍩 Diagrama de Cuerdas
                        </h2>
                        <p className="text-sm text-slate-500">
                            Flujo de información entre categorías del grafo
                        </p>
                    </div>
                </div>
                <button onClick={() => fetchData(method)} className="btn-icon" disabled={loading}>
                    <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
                </button>
            </div>

            {error ? (
                <div className="p-8 text-red-500 border border-red-200 rounded">{error}</div>
            ) : (
                <div style={{ display: 'flex', gap: 20 }}>
                    {/* Chart */}
                    <div
                        className="bg-white dark:bg-slate-950 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800"
                        style={{ flex: 1, height: 620, padding: 16, position: 'relative' }}
                    >
                        {loading ? (
                            <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-400">
                                <Loader2 className="animate-spin mb-4" size={32} />
                                <p>Calculando {method === 'fuzzy' ? 'flujo semántico' : 'flujo literal'}...</p>
                            </div>
                        ) : !data || data.matrix.length === 0 ? (
                            <div className="absolute inset-0 flex items-center justify-center text-slate-400">
                                Sin datos de flujo entre categorías.
                            </div>
                        ) : (
                            <ResponsiveChord
                                data={data.matrix}
                                keys={data.keys}
                                margin={{ top: 60, right: 60, bottom: 60, left: 60 }}
                                padAngle={0.05}
                                innerRadiusRatio={0.96}
                                innerRadiusOffset={0.02}
                                ribbonOpacity={0.5}
                                activeRibbonOpacity={1.0}
                                inactiveRibbonOpacity={0.15}
                                colors={CATEGORY_COLORS}
                                arcBorderWidth={1}
                                arcBorderColor={{ from: 'color', modifiers: [['darker', 0.4]] }}
                                enableLabel={true}
                                label="id"
                                labelOffset={12}
                                labelRotation={-90}
                                labelTextColor="#cbd5e1"
                                arcTooltip={({ arc }) => (
                                    <div
                                        style={{
                                            background: '#0f172a',
                                            color: '#f8fafc',
                                            padding: '8px 14px',
                                            borderRadius: 8,
                                            border: '1px solid #334155',
                                            fontSize: 12,
                                        }}
                                    >
                                        <strong style={{ color: arc.color }}>
                                            {CATEGORY_ICONS[arc.id] || ''} {arc.id}
                                        </strong>
                                        <br />
                                        <span style={{ color: '#94a3b8' }}>
                                            Total {method === 'fuzzy' ? 'peso' : 'flujo'}:{' '}
                                            <strong style={{ color: '#e2e8f0' }}>
                                                {typeof arc.value === 'number' ? arc.value.toFixed(method === 'fuzzy' ? 2 : 0) : arc.value}
                                            </strong>
                                        </span>
                                    </div>
                                )}
                                ribbonTooltip={({ ribbon }) => (
                                    <div
                                        style={{
                                            background: '#0f172a',
                                            color: '#f8fafc',
                                            padding: '10px 14px',
                                            borderRadius: 8,
                                            border: '1px solid #334155',
                                            fontSize: 12,
                                        }}
                                    >
                                        <div style={{ marginBottom: 4 }}>
                                            <span style={{ color: ribbon.source.color }}>
                                                {CATEGORY_ICONS[ribbon.source.id] || ''} {ribbon.source.id}
                                            </span>
                                            {' → '}
                                            <span style={{ color: ribbon.target.color }}>
                                                {CATEGORY_ICONS[ribbon.target.id] || ''} {ribbon.target.id}
                                            </span>
                                        </div>
                                        <span style={{ color: '#94a3b8' }}>
                                            {method === 'fuzzy' ? 'Peso difuso' : 'Archivos compartidos'}:{' '}
                                            <strong style={{ color: '#e2e8f0' }}>
                                                {typeof ribbon.source.value === 'number'
                                                    ? ribbon.source.value.toFixed(method === 'fuzzy' ? 2 : 0)
                                                    : ribbon.source.value}
                                            </strong>
                                        </span>
                                    </div>
                                )}
                                theme={{
                                    labels: { text: { fill: '#cbd5e1', fontSize: 12, fontWeight: 600 } },
                                    tooltip: {
                                        container: {
                                            background: '#0f172a',
                                            color: '#f8fafc',
                                            fontSize: 12,
                                            borderRadius: 8,
                                            border: '1px solid #334155',
                                        },
                                    },
                                }}
                            />
                        )}
                    </div>

                    {/* Explanation Side Panel */}
                    <div
                        className="bg-white dark:bg-slate-950 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800"
                        style={{ width: 260, padding: 20, flexShrink: 0 }}
                    >
                        {/* Mode Toggle */}
                        <div style={{
                            display: 'flex', borderRadius: 8, overflow: 'hidden',
                            border: '1px solid #334155', marginBottom: 16,
                        }}>
                            {(['standard', 'fuzzy'] as ChordMode[]).map(m => (
                                <button
                                    key={m}
                                    onClick={() => setMethod(m)}
                                    style={{
                                        flex: 1, padding: '8px 4px', fontSize: '0.72rem', fontWeight: 600,
                                        border: 'none', cursor: 'pointer',
                                        transition: 'all 0.25s ease',
                                        background: method === m
                                            ? (m === 'fuzzy' ? '#7c3aed' : '#0ea5e9')
                                            : '#0f172a',
                                        color: method === m ? '#ffffff' : '#64748b',
                                    }}
                                >
                                    {m === 'standard' ? '🔗 Standard' : '🧠 Fuzzy'}
                                </button>
                            ))}
                        </div>

                        {/* Dynamic Narrative */}
                        <div style={{
                            background: '#1e293b', borderRadius: 8, padding: 12, marginBottom: 16,
                            border: '1px solid #334155',
                        }}>
                            <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#f8fafc', marginBottom: 6 }}>
                                {narrative.icon} {narrative.title}
                            </div>
                            <p style={{ fontSize: '0.75rem', color: '#94a3b8', lineHeight: 1.6, margin: 0 }}>
                                {narrative.desc}
                            </p>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
                            <Info size={18} className="text-cyan-400" />
                            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#f8fafc', margin: 0 }}>
                                Interconexión de Categorías
                            </h3>
                        </div>

                        <p style={{ fontSize: '0.78rem', color: '#94a3b8', lineHeight: 1.6, marginBottom: 16 }}>
                            Cada <strong style={{ color: '#e2e8f0' }}>arco</strong> representa una categoría.
                            Las <strong style={{ color: '#e2e8f0' }}>cintas</strong> muestran{' '}
                            {method === 'fuzzy'
                                ? 'la fuerza semántica de la conexión entre categorías.'
                                : 'cuántos archivos (DigitalAssets) conectan una categoría con otra.'}
                        </p>

                        <p style={{ fontSize: '0.78rem', color: '#94a3b8', lineHeight: 1.6, marginBottom: 20 }}>
                            {method === 'fuzzy'
                                ? 'Una cinta gruesa = alta certeza de la IA en esa conexión.'
                                : 'Una cinta gruesa = muchos archivos mencionan ambas categorías.'}
                            {' '}La auto-referencia <em>Concept↔Concept</em> se omite para mayor claridad visual.
                        </p>

                        {/* Category Legend */}
                        <div style={{
                            background: '#1e293b', borderRadius: 8, padding: 12,
                            border: '1px solid #334155'
                        }}>
                            <div style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: 600, marginBottom: 10 }}>
                                CATEGORÍAS
                            </div>
                            {data?.keys.map((name, i) => (
                                <div key={name} style={{
                                    display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5,
                                    fontSize: '0.75rem'
                                }}>
                                    <div style={{
                                        width: 10, height: 10, borderRadius: '50%',
                                        background: CATEGORY_COLORS[i] || '#666',
                                        flexShrink: 0
                                    }} />
                                    <span style={{ color: '#94a3b8' }}>
                                        {CATEGORY_ICONS[name] || ''} {name}
                                    </span>
                                </div>
                            ))}
                        </div>

                        {message && (
                            <div style={{
                                marginTop: 16, fontSize: '0.7rem', color: '#4ade80',
                                padding: '8px 12px', background: '#22c55e10', borderRadius: 6,
                                border: '1px solid #22c55e30'
                            }}>
                                ✅ {message}
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
