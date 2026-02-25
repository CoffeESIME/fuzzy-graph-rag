import { useState } from 'react';
import { Search, Network, Check, X, Layers, RefreshCw, Eye, FileText } from 'lucide-react';
import {
    getExplorableSeeds,
    getLatentConnections,
    approveLatentConnection,
    getAssetPreview,
} from '../../lib/api';
import type { SeedNode, LatentConnectionSuggestion, AssetPreviewResponse } from '../../lib/api';
import MediaPreview from '../search/MediaPreview';

export default function LatentExplorer() {
    const allowedTypes = ["DigitalAsset"];

    // Search State
    const [nodeType, setNodeType] = useState('DigitalAsset');
    const [limit, setLimit] = useState(20);
    const [seeds, setSeeds] = useState<SeedNode[]>([]);
    const [isLoadingSeeds, setIsLoadingSeeds] = useState(false);

    // Selection State
    const [selectedSeed, setSelectedSeed] = useState<SeedNode | null>(null);
    const [suggestions, setSuggestions] = useState<LatentConnectionSuggestion[]>([]);
    const [isLoadingLatent, setIsLoadingLatent] = useState(false);
    const [alpha, setAlpha] = useState(0.3); // Default weight for vector similarity

    // UI states
    const [error, setError] = useState<string | null>(null);
    const [toast, setToast] = useState<{ message: string, type: 'success' | 'error' } | null>(null);
    const [approvingIds, setApprovingIds] = useState<Set<string>>(new Set());

    const showToast = (message: string, type: 'success' | 'error') => {
        setToast({ message, type });
        setTimeout(() => setToast(null), 3000);
    };

    // Asset Preview State
    const [previewAsset, setPreviewAsset] = useState<AssetPreviewResponse | null>(null);
    const [isLoadingPreview, setIsLoadingPreview] = useState(false);

    // Weights local edits
    const [editedWeights, setEditedWeights] = useState<Record<string, number>>({});

    const fetchSeeds = async () => {
        setIsLoadingSeeds(true);
        setSelectedSeed(null);
        setSuggestions([]);
        try {
            const res = await getExplorableSeeds(nodeType, limit);
            setSeeds(res.seeds);
        } catch (err: any) {
            console.error('Failed to fetch seeds:', err);
        } finally {
            setIsLoadingSeeds(false);
        }
    };

    const handleExplore = async () => {
        if (!selectedSeed) return;

        setIsLoadingLatent(true);
        setError(null);
        setSuggestions([]);
        setEditedWeights({});

        try {
            const res = await getLatentConnections(selectedSeed.id, 5, alpha);
            setSuggestions(res.suggestions);
            if (res.suggestions.length === 0) {
                setError('No se encontraron conexiones latentes nuevas para este nodo.');
            }
        } catch (err: any) {
            console.error(err);
            setError(err.response?.data?.detail || err.message || 'Error al explorar conexiones latentes');
        } finally {
            setIsLoadingLatent(false);
        }
    };

    const handleApprove = async (suggestion: LatentConnectionSuggestion, uniqueKey: string) => {
        setApprovingIds(prev => new Set(prev).add(uniqueKey));

        const finalWeight = editedWeights[uniqueKey] !== undefined ? editedWeights[uniqueKey] : suggestion.proposed_weight;

        try {
            await approveLatentConnection({
                asset_id: suggestion.asset_id,
                target_concept_id: suggestion.target_concept_id,
                relation_type: suggestion.relation_type,
                proposed_weight: Math.min(Math.max(finalWeight, 0), 1),
                reasoning: suggestion.reasoning
            });

            // Remove from list on success
            setSuggestions(prev => prev.filter(s => `${s.asset_id}-${s.target_concept_id}-${s.relation_type}-${s.direction}` !== uniqueKey));
            showToast('¡Conexión aprobada e inyectada en el Grafo!', 'success');

        } catch (err: any) {
            console.error(err);
            showToast(err.response?.data?.detail || 'Error al aprobar la conexión', 'error');
        } finally {
            setApprovingIds(prev => {
                const next = new Set(prev);
                next.delete(uniqueKey);
                return next;
            });
        }
    };

    const handleDiscard = (uniqueKey: string) => {
        setSuggestions(prev => prev.filter(s => `${s.asset_id}-${s.target_concept_id}-${s.relation_type}-${s.direction}` !== uniqueKey));
    };

    const handleWeightChange = (uniqueKey: string, val: string) => {
        const num = parseFloat(val);
        setEditedWeights(prev => ({
            ...prev,
            [uniqueKey]: isNaN(num) ? 0 : num
        }));
    };

    const handlePreviewAsset = async (assetId: string) => {
        setIsLoadingPreview(true);
        try {
            const data = await getAssetPreview(assetId);

            // Auto-fetch raw text content if it's missing (No textual content available) but we have the download URL for a text file
            if (data.download_url && data.content === 'No textual content available' &&
                (data.mime_type === 'text/plain' || data.mime_type === 'text/markdown' || data.name.endsWith('.txt') || data.name.endsWith('.md'))) {
                try {
                    const res = await fetch(data.download_url);
                    if (res.ok) {
                        const rawText = await res.text();
                        data.content = rawText.slice(0, 1500) + (rawText.length > 1500 ? '\n\n... (Contenido truncado para la vista previa)' : '');
                    }
                } catch (e) {
                    console.error("Failed to fetch text directly from MinIO", e);
                }
            }

            setPreviewAsset(data);
        } catch (err: any) {
            console.error("Failed to load asset preview", err);
            setError(err.response?.data?.detail || err.message || 'Error al cargar previsualización del activo');
        } finally {
            setIsLoadingPreview(false);
        }
    };

    return (
        <div className="flex flex-col gap-6" style={{ background: 'var(--bg-primary)', color: 'var(--text-primary)' }}>
            <div className="flex gap-6 items-start">

                {/* Lateral Control Panel */}
                <div style={{ width: 320, background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 16, padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}>
                    <h2 style={{ fontSize: '1.2rem', fontWeight: 600, borderBottom: '1px solid var(--border-subtle)', paddingBottom: 12 }}>
                        Configuración de Exploración
                    </h2>

                    <div>
                        <label style={{ display: 'block', fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: 8 }}>
                            Tipo de Entidad Semilla
                        </label>
                        <select
                            className="search-input"
                            value={nodeType}
                            onChange={(e) => setNodeType(e.target.value)}
                            style={{ width: '100%', marginBottom: 12 }}
                        >
                            {allowedTypes.map(t => (
                                <option key={t} value={t}>{t}</option>
                            ))}
                        </select>

                        <div className="flex justify-between items-center mb-4">
                            <label style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Límite</label>
                            <input
                                type="number"
                                className="search-input w-20 py-1 text-center"
                                value={limit}
                                onChange={e => setLimit(parseInt(e.target.value))}
                                min={5} max={100}
                            />
                        </div>

                        <button
                            className="btn-primary w-full justify-center mb-4"
                            onClick={fetchSeeds}
                            disabled={isLoadingSeeds}
                            style={{ background: 'var(--accent-primary)', color: 'white', border: 'none', padding: '10px', borderRadius: '8px', cursor: isLoadingSeeds ? 'not-allowed' : 'pointer', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '8px' }}
                        >
                            <Search size={16} />
                            {isLoadingSeeds ? 'Cargando...' : 'Buscar Semillas'}
                        </button>

                        <div style={{ marginTop: 8, maxHeight: 240, overflowY: 'auto', background: 'var(--bg-tertiary)', borderRadius: 8, border: '1px solid var(--border-subtle)' }}>
                            {seeds.length === 0 && !isLoadingSeeds ? (
                                <div className="p-4 text-center text-sm text-gray-500">Haz clic en Buscar</div>
                            ) : isLoadingSeeds ? (
                                <div className="p-4 text-center text-sm text-gray-500">Cargando...</div>
                            ) : (
                                <div className="flex flex-col">
                                    {seeds.map(seed => (
                                        <button
                                            key={seed.id}
                                            onClick={() => setSelectedSeed(seed)}
                                            style={{
                                                padding: '8px 12px', textAlign: 'left', borderBottom: '1px solid var(--border-subtle)',
                                                background: selectedSeed?.id === seed.id ? 'rgba(236, 72, 153, 0.1)' : 'transparent',
                                                borderLeft: selectedSeed?.id === seed.id ? '2px solid #ec4899' : '2px solid transparent'
                                            }}
                                            className="hover:bg-gray-800/50 transition-colors"
                                        >
                                            <div className="font-medium text-sm truncate" title={seed.name}>{seed.name}</div>
                                            <div className="text-xs text-pink-500 flex justify-between mt-1">
                                                <span>{seed.type}</span>
                                                <span className="text-gray-400">{seed.connections} refs</span>
                                            </div>
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>

                    <div>
                        <div className="flex justify-between items-center mb-2">
                            <label style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Fusión de Vectores (Alpha)</label>
                            <span className="text-sm font-bold text-pink-500">{Math.round(alpha * 100)}%</span>
                        </div>
                        <input
                            type="range"
                            min="0"
                            max="1"
                            step="0.05"
                            value={alpha}
                            onChange={(e) => setAlpha(parseFloat(e.target.value))}
                            style={{ width: '100%', accentColor: '#ec4899' }}
                        />
                        <p className="text-xs text-gray-500 mt-2 leading-relaxed">
                            Controla cuánto peso se le da a la similitud vectorial ({Math.round(alpha * 100)}%) frente al peso estructural existente del grafo ({Math.round((1 - alpha) * 100)}%).
                        </p>
                    </div>

                    <button
                        onClick={handleExplore}
                        disabled={!selectedSeed || isLoadingLatent}
                        style={{
                            width: '100%', background: selectedSeed ? 'var(--accent-primary)' : 'var(--bg-tertiary)',
                            color: selectedSeed ? '#fff' : 'var(--text-muted)', padding: '10px 14px', borderRadius: 8,
                            border: 'none', cursor: selectedSeed && !isLoadingLatent ? 'pointer' : 'not-allowed',
                            display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 8, fontWeight: 600,
                            marginTop: 10
                        }}
                        className="transition-colors"
                    >
                        {isLoadingLatent ? <RefreshCw size={18} className="animate-spin" /> : <Network size={18} />}
                        Explorar Latencias
                    </button>
                </div>

                {/* Main View Panel */}
                <div className="flex-1 flex flex-col gap-4">
                    {error && (
                        <div style={{ padding: 16, background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', borderRadius: 8, border: '1px solid #ef4444' }}>
                            {error}
                        </div>
                    )}

                    {!selectedSeed && !isLoadingLatent && suggestions.length === 0 && (
                        <div style={{ padding: 60, textAlign: 'center', color: 'var(--text-muted)', background: 'var(--bg-secondary)', border: '1px dashed var(--border-subtle)', borderRadius: 16 }}>
                            <Layers size={48} className="mx-auto mb-4 opacity-50" />
                            <h3 className="text-lg font-medium mb-2">Buscador Latente</h3>
                            <p>Selecciona un nodo semilla a la izquierda y presiona explorar para descubrir conexiones ocultas generadas mediante topología vectorial.</p>
                        </div>
                    )}

                    {isLoadingLatent && (
                        <div style={{ padding: 60, textAlign: 'center', color: 'var(--text-muted)', background: 'var(--bg-secondary)', borderRadius: 16, border: '1px solid var(--border-subtle)' }}>
                            <div className="loading-spinner mb-4 mx-auto" />
                            <p>Mapeando espacios vectoriales y contrastando grafo estructural...</p>
                        </div>
                    )}

                    {!isLoadingLatent && suggestions.length > 0 && (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {suggestions.map(s => {
                                const uniqueKey = `${s.asset_id}-${s.target_concept_id}-${s.relation_type}-${s.direction}`;
                                const isApproving = approvingIds.has(uniqueKey);
                                const currentEditedWeight = editedWeights[uniqueKey] !== undefined ? editedWeights[uniqueKey] : s.proposed_weight;

                                return (
                                    <div key={uniqueKey} style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)', borderRadius: 12, padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }} className="shadow-lg">

                                        <div className="flex justify-between items-start gap-4">
                                            <div className="flex-1 min-w-0">
                                                <div className="text-xs text-gray-500 mb-1">
                                                    Transferencia Ontológica: {s.direction === 'seed_to_neighbor' ? 'Semilla ➔ Vecino' : 'Vecino ➔ Semilla'}
                                                </div>
                                                <div className="font-medium text-gray-300 text-sm mb-1">
                                                    Agregar concepto a <span className="text-white font-bold">{s.asset_name}</span>
                                                </div>
                                                <div className="font-semibold text-pink-400 break-all text-lg">
                                                    {s.target_concept_name}
                                                </div>
                                            </div>
                                            <div className="flex flex-col items-end gap-2 flex-shrink-0">
                                                <div className="bg-gray-800 text-xs px-2 py-1 rounded text-gray-400 border border-gray-700 whitespace-nowrap">
                                                    {s.relation_type}
                                                </div>
                                                <button
                                                    onClick={() => handlePreviewAsset(s.asset_id)}
                                                    className="text-indigo-400 hover:text-indigo-300 transition-colors flex items-center gap-1 bg-indigo-500/10 hover:bg-indigo-500/20 px-2 py-1 rounded text-xs border border-indigo-500/20 whitespace-nowrap"
                                                    title="Previsualizar metadatos del archivo"
                                                >
                                                    <Eye size={12} /> Detalles
                                                </button>
                                            </div>
                                        </div>

                                        <div className="flex items-center gap-2">
                                            <div className="bg-gray-800/50 flex-1 p-2 rounded border border-gray-700/50 text-center">
                                                <div className="text-[0.65rem] text-gray-500 uppercase tracking-wider">Grafo Origen</div>
                                                <div className="text-sm font-medium">{s.current_weight.toFixed(2)}</div>
                                            </div>
                                            <div className="text-gray-600">+</div>
                                            <div className="bg-indigo-900/20 flex-1 p-2 rounded border border-indigo-900/40 text-center">
                                                <div className="text-[0.65rem] text-indigo-400 uppercase tracking-wider">Similitud Vectorial</div>
                                                <div className="text-sm font-medium text-indigo-300">{s.cosine_similarity.toFixed(2)}</div>
                                            </div>
                                            <div className="text-gray-600">=</div>
                                            <div className="bg-pink-900/20 flex-1 p-2 rounded border border-pink-900/40 text-center">
                                                <div className="text-[0.65rem] text-pink-400 uppercase tracking-wider">Peso Final</div>
                                                <div className="text-sm font-bold text-pink-400">{s.proposed_weight.toFixed(2)}</div>
                                            </div>
                                        </div>

                                        <div className="text-xs text-gray-400 bg-black/20 p-3 rounded-lg border border-gray-800">
                                            <strong className="text-gray-300 block mb-1">Motivación:</strong>
                                            {s.reasoning}
                                        </div>

                                        <div className="flex items-center gap-4 mt-auto pt-4 border-t border-gray-800">
                                            <div className="flex items-center gap-2">
                                                <label className="text-xs text-gray-500">Ajuste Manual:</label>
                                                <input
                                                    type="number"
                                                    step="0.05" min="0" max="1"
                                                    value={currentEditedWeight}
                                                    onChange={e => handleWeightChange(uniqueKey, e.target.value)}
                                                    className="w-20 bg-gray-900 border border-gray-700 rounded px-2 py-1 text-sm text-center"
                                                />
                                            </div>

                                            <div className="flex gap-2 ml-auto">
                                                <button
                                                    onClick={() => handleDiscard(uniqueKey)}
                                                    className="p-2 rounded hover:bg-red-900/20 text-gray-500 hover:text-red-400 transition-colors"
                                                    title="Descartar"
                                                >
                                                    <X size={18} />
                                                </button>
                                                <button
                                                    onClick={() => handleApprove(s, uniqueKey)}
                                                    disabled={isApproving}
                                                    className="flex items-center gap-2 px-3 py-1.5 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-sm transition-colors shadow-lg shadow-emerald-900/20"
                                                >
                                                    {isApproving ? <RefreshCw size={16} className="animate-spin" /> : <Check size={16} />}
                                                    Aprobar
                                                </button>
                                            </div>
                                        </div>

                                    </div>
                                );
                            })}
                        </div>
                    )}

                </div>
            </div>

            {/* Preview Modals */}
            {isLoadingPreview && (
                <div style={{ position: 'fixed', inset: 0, zIndex: 50, background: 'rgba(0,0,0,0.5)', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                    <div className="bg-gray-900 p-6 rounded-xl border border-gray-700 flex items-center gap-4 text-white">
                        <RefreshCw size={20} className="animate-spin text-pink-500" /> Cargando vista previa...
                    </div>
                </div>
            )}

            {previewAsset && (
                <div style={{ position: 'fixed', inset: 0, zIndex: 100, background: 'rgba(0,0,0,0.75)', display: 'flex', justifyContent: 'center', alignItems: 'center', backdropFilter: 'blur(4px)' }}>
                    <div className="bg-gray-900 border border-gray-700 rounded-xl shadow-2xl w-11/12 max-w-2xl max-h-[85vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-200">
                        <div className="flex justify-between items-center p-4 border-b border-gray-800 bg-gray-900/50">
                            <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-lg bg-indigo-500/10 flex items-center justify-center border border-indigo-500/20 text-indigo-400">
                                    <FileText size={20} />
                                </div>
                                <h3 className="font-semibold text-lg text-white truncate max-w-sm" title={previewAsset.name}>{previewAsset.name}</h3>
                            </div>
                            <button onClick={() => setPreviewAsset(null)} className="p-2 rounded-lg hover:bg-gray-800 text-gray-400 hover:text-white transition-colors">
                                <X size={20} />
                            </button>
                        </div>
                        <div className="p-6 overflow-y-auto custom-scrollbar flex-1 text-sm text-gray-300">
                            <div className="mb-4 flex flex-wrap items-center gap-2">
                                <span className="bg-gray-800 border border-gray-700 text-gray-300 px-2 py-1 rounded text-xs">Tipo: {previewAsset.type}</span>
                                {previewAsset.tags.map((tag, idx) => (
                                    <span key={idx} className="bg-indigo-900/30 text-indigo-300 border border-indigo-500/30 px-2 py-1 rounded-full text-xs">#{tag}</span>
                                ))}
                            </div>

                            {(previewAsset.minio_path || previewAsset.download_url) && (
                                <div className="mb-4">
                                    <MediaPreview
                                        path={previewAsset.minio_path}
                                        url={previewAsset.download_url}
                                    />
                                </div>
                            )}

                            <div className="bg-black/40 border border-gray-800 rounded-lg p-4 font-mono text-xs whitespace-pre-wrap leading-relaxed text-gray-400 select-text">
                                {previewAsset.content}
                            </div>
                        </div>
                        <div className="p-4 border-t border-gray-800 bg-gray-900/50 text-right">
                            <button onClick={() => setPreviewAsset(null)} className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-white rounded-lg transition-colors font-medium text-sm border border-gray-700">
                                Cerrar Vista Previa
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Toast Notification */}
            {toast && (
                <div style={{
                    position: 'fixed', bottom: 24, right: 24, zIndex: 9999,
                    background: toast.type === 'success' ? 'rgba(16, 185, 129, 0.95)' : 'rgba(239, 68, 68, 0.95)',
                    color: 'white', padding: '14px 24px', borderRadius: '12px',
                    boxShadow: '0 10px 25px rgba(0,0,0,0.5)', fontWeight: 500,
                    display: 'flex', alignItems: 'center', gap: 10,
                    backdropFilter: 'blur(8px)', border: '1px solid rgba(255,255,255,0.1)',
                    animation: 'fadeInUp 0.3s ease-out'
                }}>
                    {toast.type === 'success' ? <Check size={20} className="text-emerald-200" /> : <X size={20} className="text-red-200" />}
                    {toast.message}
                </div>
            )}
        </div>
    );
}

