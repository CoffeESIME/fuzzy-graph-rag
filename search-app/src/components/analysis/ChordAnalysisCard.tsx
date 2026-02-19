import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { ResponsiveChord } from '@nivo/chord';
import { RefreshCw, Component, Loader2, Info } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface AnalysisResponse {
    tool: string;
    status: string;
    message: string;
    mock_data: {
        matrix: number[][];
        keys: string[];
    };
}

// Fixed colors per category for visual consistency
const CATEGORY_COLORS: Record<string, string> = {
    Concept: '#a78bfa', // Violet
    Person: '#60a5fa', // Blue
    Location: '#f87171', // Red
    Event: '#fbbf24', // Amber
    Organization: '#34d399', // Emerald
};

const CATEGORY_ICONS: Record<string, string> = {
    Concept: '💡',
    Person: '👤',
    Location: '📍',
    Event: '📅',
    Organization: '🏢',
};

export default function ChordAnalysisCard() {
    const [matrix, setMatrix] = useState<number[][]>([]);
    const [keys, setKeys] = useState<string[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [message, setMessage] = useState('');
    const navigate = useNavigate();

    const fetchData = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await axios.post<AnalysisResponse>('http://localhost:8000/analysis/chord');
            if (res.data.status === 'error') throw new Error(res.data.message);
            setMatrix(res.data.mock_data.matrix);
            setKeys(res.data.mock_data.keys);
            setMessage(res.data.message);
        } catch (err: any) {
            console.error(err);
            setError(err.message || 'Error fetching chord data');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, []);

    // Map keys to fixed colors in order
    const colors = keys.map(k => CATEGORY_COLORS[k] || '#64748b');

    const theme = {
        background: 'transparent',
        textColor: '#e2e8f0',
        fontSize: 12,
        tooltip: {
            container: {
                background: '#0f172a',
                color: '#f8fafc',
                fontSize: 12,
                borderRadius: 8,
                boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
                padding: '10px 14px',
                border: '1px solid #334155'
            }
        }
    };

    if (loading) return (
        <div className="flex flex-col items-center justify-center p-12 text-gray-500 min-h-[400px]">
            <Loader2 className="animate-spin mb-4" size={32} />
            <p>Calculando flujos entre categorías...</p>
        </div>
    );

    return (
        <div style={{ padding: 24, paddingBottom: 60, maxWidth: 1200, margin: '0 auto' }}>
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-4">
                    <button onClick={() => navigate('/analysis')} className="btn-secondary">Back</button>
                    <div>
                        <h2 className="text-2xl font-bold flex items-center gap-2">
                            <Component className="text-teal-500" />
                            Interconexión de Categorías
                        </h2>
                        <p className="text-gray-500">Flujo de información entre tipos de entidades del grafo.</p>
                    </div>
                </div>
                <button onClick={fetchData} className="btn-icon">
                    <RefreshCw size={18} />
                </button>
            </div>

            {error ? (
                <div className="p-8 text-red-500 border border-red-200 rounded">{error}</div>
            ) : (
                <div style={{ display: 'flex', gap: 20 }}>
                    {/* Main Chord */}
                    <div
                        className="bg-white dark:bg-slate-950 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800"
                        style={{ flex: '1 1 0', height: 700, padding: 16, position: 'relative', minWidth: 0 }}
                    >
                        {matrix.length === 0 ? (
                            <div className="absolute inset-0 flex items-center justify-center text-slate-400">
                                No hay datos disponibles
                            </div>
                        ) : (
                            <ResponsiveChord
                                data={matrix}
                                keys={keys}
                                margin={{ top: 60, right: 60, bottom: 90, left: 60 }}
                                valueFormat=".0f"
                                padAngle={0.02}
                                innerRadiusRatio={0.96}
                                innerRadiusOffset={0.02}
                                inactiveArcOpacity={0.25}
                                arcOpacity={1}
                                activeArcOpacity={1}
                                inactiveRibbonOpacity={0.15}
                                ribbonOpacity={0.5}
                                activeRibbonOpacity={0.9}
                                labelRotation={-90}
                                labelOffset={12}
                                labelTextColor="#e2e8f0"
                                colors={colors}
                                motionConfig="stiff"
                                theme={theme}
                                arcTooltip={({ arc }) => (
                                    <div style={{
                                        background: '#0f172a', border: '1px solid #334155',
                                        borderRadius: 8, padding: '10px 14px', color: '#f8fafc',
                                        fontSize: 12, boxShadow: '0 8px 24px rgba(0,0,0,0.4)'
                                    }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                            <span>{CATEGORY_ICONS[arc.label] || '🔷'}</span>
                                            <strong>{arc.label}</strong>
                                        </div>
                                        <div style={{ color: '#94a3b8', marginTop: 2 }}>
                                            {arc.value} conexiones vía archivos
                                        </div>
                                    </div>
                                )}
                                ribbonTooltip={({ ribbon }) => (
                                    <div style={{
                                        background: '#0f172a', border: '1px solid #334155',
                                        borderRadius: 8, padding: '10px 14px', color: '#f8fafc',
                                        fontSize: 12, boxShadow: '0 8px 24px rgba(0,0,0,0.4)'
                                    }}>
                                        <div style={{ fontWeight: 700, marginBottom: 4 }}>
                                            {CATEGORY_ICONS[ribbon.source.label] || ''} {ribbon.source.label} ↔ {CATEGORY_ICONS[ribbon.target.label] || ''} {ribbon.target.label}
                                        </div>
                                        <div style={{ color: '#94a3b8' }}>
                                            <strong style={{ color: '#f8fafc' }}>{ribbon.source.value}</strong> archivos compartidos
                                        </div>
                                    </div>
                                )}
                            />
                        )}
                    </div>

                    {/* Explanation Side Panel */}
                    <div
                        className="bg-white dark:bg-slate-950 rounded-2xl shadow-sm border border-slate-200 dark:border-slate-800"
                        style={{ width: 280, padding: 20, flexShrink: 0 }}
                    >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
                            <Info size={18} className="text-teal-400" />
                            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#f8fafc', margin: 0 }}>
                                ¿Qué veo aquí?
                            </h3>
                        </div>

                        <p style={{ fontSize: '0.78rem', color: '#94a3b8', lineHeight: 1.6, marginBottom: 16 }}>
                            Este diagrama muestra cómo fluye la información entre
                            <strong style={{ color: '#e2e8f0' }}> tipos de entidades</strong>.
                            Si la cinta entre <strong style={{ color: '#60a5fa' }}>Persona</strong> y
                            <strong style={{ color: '#fbbf24' }}> Evento</strong> es gruesa,
                            significa que tienes muchas fotos o textos sobre gente participando en eventos.
                        </p>

                        <p style={{ fontSize: '0.78rem', color: '#94a3b8', lineHeight: 1.6, marginBottom: 20 }}>
                            A diferencia de una conexión directa, esto cuenta cuántos
                            <strong style={{ color: '#e2e8f0' }}> archivos (DigitalAssets)</strong> conectan
                            un tipo de entidad con otro.
                        </p>

                        {/* Category Legend */}
                        <div style={{
                            background: '#1e293b', borderRadius: 8, padding: 12, marginBottom: 16,
                            border: '1px solid #334155'
                        }}>
                            <div style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: 600, marginBottom: 10 }}>
                                CATEGORÍAS
                            </div>
                            {Object.entries(CATEGORY_COLORS).map(([name, color]) => (
                                <div key={name} style={{
                                    display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6,
                                    fontSize: '0.75rem'
                                }}>
                                    <div style={{
                                        width: 12, height: 12, borderRadius: 3,
                                        background: color, flexShrink: 0
                                    }} />
                                    <span style={{ color: '#94a3b8' }}>
                                        {CATEGORY_ICONS[name]} {name}
                                    </span>
                                </div>
                            ))}
                        </div>

                        <div style={{
                            background: '#1e293b', borderRadius: 8, padding: 12,
                            border: '1px solid #334155'
                        }}>
                            <div style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: 600, marginBottom: 6 }}>
                                LECTURA
                            </div>
                            <p style={{ fontSize: '0.72rem', color: '#94a3b8', lineHeight: 1.5, margin: 0 }}>
                                <strong style={{ color: '#e2e8f0' }}>Arco fino</strong> = proporción del total.
                                <br />
                                <strong style={{ color: '#e2e8f0' }}>Cinta gruesa</strong> = muchos archivos comparten ambas categorías.
                            </p>
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
