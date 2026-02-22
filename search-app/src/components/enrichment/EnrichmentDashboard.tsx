import { useState } from 'react';
import { Sparkles, ArrowLeft, Search, CheckSquare, Square, Check, Eye, X } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { getEnrichmentCandidates, requestEnrichment, getPreviewWeights } from '../../lib/api';
import type { CandidateNode, WeightPreviewResult } from '../../lib/api';

export default function EnrichmentDashboard() {
    const navigate = useNavigate();

    const [nodeType, setNodeType] = useState('Person');
    const [statusFilter, setStatusFilter] = useState('PENDING');
    const [limit, setLimit] = useState(50);
    const [isLoading, setIsLoading] = useState(false);
    const [candidates, setCandidates] = useState<CandidateNode[]>([]);
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [error, setError] = useState<string | null>(null);
    const [successMsg, setSuccessMsg] = useState<string | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);

    // Preview Modal State
    const [previewNode, setPreviewNode] = useState<CandidateNode | null>(null);
    const [previewWeights, setPreviewWeights] = useState<WeightPreviewResult[]>([]);
    const [isPreviewLoading, setIsPreviewLoading] = useState(false);
    const [previewError, setPreviewError] = useState<string | null>(null);

    const allowedTypes = ["Person", "Concept", "Location", "Organization", "Event", "Project", "Device", "Method"];

    const handleSearch = async () => {
        setIsLoading(true);
        setError(null);
        setSuccessMsg(null);
        setCandidates([]);
        setSelectedIds(new Set());

        try {
            const res = await getEnrichmentCandidates(nodeType, limit, statusFilter);
            setCandidates(res.candidates);
        } catch (err: any) {
            console.error(err);
            setError(err.response?.data?.detail || err.message || 'Error fetching candidates');
        } finally {
            setIsLoading(false);
        }
    };

    const toggleSelectAll = () => {
        if (selectedIds.size === candidates.length && candidates.length > 0) {
            setSelectedIds(new Set());
        } else {
            setSelectedIds(new Set(candidates.map(c => c.id)));
        }
    };

    const toggleSelect = (id: string) => {
        const newSet = new Set(selectedIds);
        if (newSet.has(id)) {
            newSet.delete(id);
        } else {
            newSet.add(id);
        }
        setSelectedIds(newSet);
    };

    const handleEnrich = async () => {
        if (selectedIds.size === 0) return;

        setIsSubmitting(true);
        setError(null);
        setSuccessMsg(null);

        try {
            const res = await requestEnrichment(Array.from(selectedIds));
            setSuccessMsg(res.message);
            // Optionally remove selected ones from the UI or refetch
            setCandidates(prev => prev.filter(c => !selectedIds.has(c.id)));
            setSelectedIds(new Set());
        } catch (err: any) {
            console.error(err);
            setError(err.response?.data?.detail || err.message || 'Error requesting enrichment');
        } finally {
            setIsSubmitting(false);
        }
    };

    const handlePreview = async (node: CandidateNode) => {
        setPreviewNode(node);
        setPreviewWeights([]);
        setIsPreviewLoading(true);
        setPreviewError(null);

        try {
            const res = await getPreviewWeights(node.id);
            setPreviewWeights(res.results);
        } catch (err: any) {
            console.error(err);
            setPreviewError(err.response?.data?.detail || err.message || 'Error calculando pesos');
        } finally {
            setIsPreviewLoading(false);
        }
    };

    return (
        <div style={{
            minHeight: '100vh',
            background: 'var(--bg-primary)',
            color: 'var(--text-primary)',
            padding: 24
        }}>
            <div style={{ maxWidth: 1200, margin: '0 auto' }}>
                <header style={{ marginBottom: 32, display: 'flex', alignItems: 'center', gap: 16 }}>
                    <button
                        onClick={() => navigate('/')}
                        style={{
                            background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)',
                            borderRadius: 'var(--radius-md)', padding: 8, cursor: 'pointer',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            color: 'var(--text-secondary)'
                        }}
                    >
                        <ArrowLeft size={20} />
                    </button>
                    <div>
                        <h1 style={{ fontSize: '2rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: 12 }}>
                            <Sparkles size={28} className="text-pink-500" />
                            Enriquecimiento de Grafo
                        </h1>
                        <p style={{ color: 'var(--text-secondary)', marginTop: 4 }}>
                            Centro de control para procesos de descubrimiento y expansión semántica automatizada.
                        </p>
                    </div>
                </header>

                <div style={{ display: 'flex', gap: 24, alignItems: 'flex-start' }}>

                    {/* Control Panel Sidebar */}
                    <div style={{
                        width: 320,
                        background: 'var(--bg-secondary)',
                        border: '1px solid var(--border-subtle)',
                        borderRadius: 16,
                        padding: 24,
                        display: 'flex', flexDirection: 'column', gap: 20
                    }}>
                        <h2 style={{ fontSize: '1.2rem', fontWeight: 600, borderBottom: '1px solid var(--border-subtle)', paddingBottom: 12 }}>
                            Buscar Candidatos
                        </h2>

                        <div>
                            <label style={{ display: 'block', fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: 8 }}>
                                Tipo de Entidad
                            </label>
                            <select
                                className="search-input"
                                value={nodeType}
                                onChange={(e) => setNodeType(e.target.value)}
                                style={{ width: '100%' }}
                            >
                                {allowedTypes.map(t => (
                                    <option key={t} value={t}>{t}</option>
                                ))}
                            </select>
                        </div>

                        <div>
                            <label style={{ display: 'block', fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: 8 }}>
                                Estado
                            </label>
                            <select
                                className="search-input"
                                value={statusFilter}
                                onChange={(e) => setStatusFilter(e.target.value)}
                                style={{ width: '100%' }}
                            >
                                <option value="PENDING">Pendientes</option>
                                <option value="PROCESSING">Procesando</option>
                                <option value="COMPLETED">Completados</option>
                                <option value="FAILED">Fallidos</option>
                                <option value="ALL">Todos</option>
                            </select>
                        </div>

                        <div>
                            <label style={{ display: 'block', fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: 8 }}>
                                Límite de Resultados
                            </label>
                            <input
                                className="search-input"
                                type="number"
                                min={10} max={200}
                                value={limit}
                                onChange={(e) => setLimit(parseInt(e.target.value))}
                                style={{ width: '100%' }}
                            />
                        </div>

                        <button
                            className="btn-primary"
                            style={{ width: '100%', justifyContent: 'center', marginTop: 8 }}
                            onClick={handleSearch}
                            disabled={isLoading}
                        >
                            <Search size={18} />
                            {isLoading ? 'Buscando...' : 'Encontrar Nodos'}
                        </button>
                    </div>

                    {/* Results Panel */}
                    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 16 }}>

                        {error && (
                            <div style={{ padding: 16, background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', borderRadius: 8, border: '1px solid #ef4444' }}>
                                {error}
                            </div>
                        )}

                        {successMsg && (
                            <div style={{ padding: 16, background: 'rgba(16, 185, 129, 0.1)', color: '#10b981', borderRadius: 8, border: '1px solid #10b981', display: 'flex', alignItems: 'center', gap: 8 }}>
                                <Check size={20} />
                                {successMsg}
                            </div>
                        )}

                        <div style={{
                            background: 'var(--bg-secondary)',
                            border: '1px solid var(--border-subtle)',
                            borderRadius: 16,
                            overflow: 'hidden',
                            flex: 1
                        }}>
                            <div style={{
                                padding: '16px 24px',
                                borderBottom: '1px solid var(--border-subtle)',
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center',
                                background: 'rgba(0,0,0,0.2)'
                            }}>
                                <h3 style={{ fontSize: '1.1rem', fontWeight: 600 }}>Candidatos a Enriquecer</h3>
                                <button
                                    className="btn-primary"
                                    onClick={handleEnrich}
                                    disabled={selectedIds.size === 0 || isSubmitting}
                                    style={{ background: selectedIds.size > 0 ? 'var(--accent-primary)' : 'var(--bg-tertiary)', color: selectedIds.size > 0 ? '#fff' : 'var(--text-muted)' }}
                                >
                                    <Sparkles size={16} />
                                    Enriquecer ({selectedIds.size}) Seleccionados
                                </button>
                            </div>

                            {isLoading ? (
                                <div style={{ padding: 60, textAlign: 'center', color: 'var(--text-muted)' }}>
                                    <div className="loading-spinner" style={{ margin: '0 auto 16px' }} />
                                    Buscando en el grafo...
                                </div>
                            ) : candidates.length > 0 ? (
                                <div style={{ overflowX: 'auto' }}>
                                    <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                                        <thead>
                                            <tr style={{ borderBottom: '1px solid var(--border-subtle)', background: 'rgba(255,255,255,0.02)' }}>
                                                <th style={{ padding: '12px 16px', width: 40, textAlign: 'center' }}>
                                                    <div
                                                        onClick={toggleSelectAll}
                                                        style={{ cursor: 'pointer', color: selectedIds.size === candidates.length ? 'var(--accent-primary)' : 'var(--text-muted)' }}
                                                    >
                                                        {selectedIds.size === candidates.length ? <CheckSquare size={18} /> : <Square size={18} />}
                                                    </div>
                                                </th>
                                                <th style={{ padding: '12px 16px', fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: 600 }}>Nombre / Entidad</th>
                                                <th style={{ padding: '12px 16px', fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: 600, width: 120 }}>Tipo</th>
                                                <th style={{ padding: '12px 16px', fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: 600, width: 100, textAlign: 'center' }}>Estado</th>
                                                <th style={{ padding: '12px 16px', fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: 600, width: 100, textAlign: 'center' }}>Refs</th>
                                                <th style={{ padding: '12px 16px', fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: 600, width: 80, textAlign: 'center' }}>Acción</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {candidates.map((cand) => (
                                                <tr
                                                    key={cand.id}
                                                    style={{
                                                        borderBottom: '1px solid var(--border-subtle)',
                                                        background: selectedIds.has(cand.id) ? 'rgba(99, 102, 241, 0.05)' : 'transparent',
                                                        transition: 'background 0.2s'
                                                    }}
                                                    className="hover:bg-indigo-900/10"
                                                >
                                                    <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                                                        <div
                                                            onClick={() => toggleSelect(cand.id)}
                                                            style={{ cursor: 'pointer', color: selectedIds.has(cand.id) ? 'var(--accent-primary)' : 'var(--border-subtle)' }}
                                                        >
                                                            {selectedIds.has(cand.id) ? <CheckSquare size={18} /> : <Square size={18} />}
                                                        </div>
                                                    </td>
                                                    <td style={{ padding: '12px 16px', fontWeight: 500 }}>
                                                        {cand.name}
                                                    </td>
                                                    <td style={{ padding: '12px 16px' }}>
                                                        <span style={{
                                                            fontSize: '0.75rem', padding: '4px 8px', borderRadius: 4,
                                                            background: 'rgba(236, 72, 153, 0.1)', color: '#f472b6', border: '1px solid rgba(236, 72, 153, 0.2)'
                                                        }}>
                                                            {cand.type}
                                                        </span>
                                                    </td>
                                                    <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                                                        <span style={{
                                                            fontSize: '0.75rem', padding: '4px 8px', borderRadius: 4, whiteSpace: 'nowrap',
                                                            background: cand.status === 'COMPLETED' ? 'rgba(16, 185, 129, 0.1)' : cand.status === 'PROCESSING' ? 'rgba(59, 130, 246, 0.1)' : cand.status === 'FAILED' ? 'rgba(239, 68, 68, 0.1)' : 'rgba(255, 255, 255, 0.05)',
                                                            color: cand.status === 'COMPLETED' ? '#10b981' : cand.status === 'PROCESSING' ? '#3b82f6' : cand.status === 'FAILED' ? '#ef4444' : 'var(--text-muted)',
                                                            border: `1px solid ${cand.status === 'COMPLETED' ? 'rgba(16, 185, 129, 0.2)' : cand.status === 'PROCESSING' ? 'rgba(59, 130, 246, 0.2)' : cand.status === 'FAILED' ? 'rgba(239, 68, 68, 0.2)' : 'rgba(255, 255, 255, 0.1)'}`
                                                        }} title={cand.error || ''}>
                                                            {cand.status || 'PENDING'}
                                                        </span>
                                                    </td>
                                                    <td style={{ padding: '12px 16px', textAlign: 'center', color: 'var(--text-secondary)' }}>
                                                        {cand.connections}
                                                    </td>
                                                    <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                                                        {cand.status === 'COMPLETED' && (
                                                            <button
                                                                onClick={(e) => {
                                                                    e.stopPropagation();
                                                                    handlePreview(cand);
                                                                }}
                                                                style={{
                                                                    background: 'transparent',
                                                                    border: 'none',
                                                                    color: 'var(--accent-primary)',
                                                                    cursor: 'pointer',
                                                                    padding: '4px',
                                                                    borderRadius: '4px'
                                                                }}
                                                                title="Previsualizar Pesos Semánticos"
                                                            >
                                                                <Eye size={18} />
                                                            </button>
                                                        )}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            ) : (
                                <div style={{ padding: 60, textAlign: 'center', color: 'var(--text-muted)' }}>
                                    No se encontraron nodos pendientes de enriquecimiento para este tipo.
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>

            {/* Preview Weights Modal */}
            {previewNode && (
                <div style={{
                    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
                    background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)',
                    zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center'
                }}>
                    <div style={{
                        background: 'var(--bg-secondary)', border: '1px solid var(--border-subtle)',
                        borderRadius: 16, width: 1200, maxWidth: '95vw', maxHeight: '90vh',
                        display: 'flex', flexDirection: 'column', overflow: 'hidden', boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.4)'
                    }}>
                        <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <div>
                                <h3 style={{ fontSize: '1.25rem', fontWeight: 600 }}>Simulación de Pesos Difusos</h3>
                                <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginTop: 4 }}>
                                    Entidad: <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{previewNode.name}</span>
                                </p>
                            </div>
                            <button onClick={() => setPreviewNode(null)} style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
                                <X size={24} />
                            </button>
                        </div>

                        <div style={{ padding: 24, overflowY: 'auto', flex: 1 }}>
                            {isPreviewLoading ? (
                                <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>
                                    <div className="loading-spinner" style={{ margin: '0 auto 16px' }} />
                                    Calculando distancias del vector en memoria contra Weaviate...
                                </div>
                            ) : previewError ? (
                                <div style={{ padding: 16, background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', borderRadius: 8, border: '1px solid #ef4444' }}>
                                    {previewError}
                                </div>
                            ) : previewWeights.length === 0 ? (
                                <div style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 20 }}>
                                    No se encontraron conexiones para previsualización.
                                </div>
                            ) : (
                                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                                    <thead>
                                        <tr style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                                            <th style={{ padding: '12px 16px', color: 'var(--text-muted)', fontWeight: 600, fontSize: '0.85rem' }}>Archivo</th>
                                            <th style={{ padding: '12px 16px', color: 'var(--text-muted)', fontWeight: 600, fontSize: '0.85rem' }}>Tipo Relación</th>
                                            <th style={{ padding: '12px 16px', color: 'var(--text-muted)', fontWeight: 600, fontSize: '0.85rem', textAlign: 'center' }}>Espacio Vectorial</th>
                                            <th style={{ padding: '12px 16px', color: 'var(--text-muted)', fontWeight: 600, fontSize: '0.85rem', textAlign: 'right' }}>Peso Actual</th>
                                            <th style={{ padding: '12px 16px', color: 'var(--text-muted)', fontWeight: 600, fontSize: '0.85rem', textAlign: 'right' }}>Sim. Vectorial</th>
                                            <th style={{ padding: '12px 16px', color: 'var(--text-primary)', fontWeight: 600, fontSize: '0.85rem', textAlign: 'right' }}>Peso Fusión (Propuesto)</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {previewWeights.map((w, i) => {
                                            let proposedColor = 'var(--text-muted)';
                                            let proposedBg = 'transparent';
                                            if (w.proposed_weight !== null) {
                                                if (w.proposed_weight > 0.7) {
                                                    proposedColor = '#10b981'; // Green
                                                    proposedBg = 'rgba(16, 185, 129, 0.1)';
                                                } else if (w.proposed_weight >= 0.4) {
                                                    proposedColor = '#f59e0b'; // Amber
                                                    proposedBg = 'rgba(245, 158, 11, 0.1)';
                                                } else {
                                                    proposedColor = '#ef4444'; // Red
                                                    proposedBg = 'rgba(239, 68, 68, 0.1)';
                                                }
                                            }

                                            return (
                                                <tr key={i} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                                                    <td style={{ padding: '12px 16px', fontSize: '0.9rem' }}>{w.filename}</td>
                                                    <td style={{ padding: '12px 16px', fontSize: '0.8rem', color: 'var(--accent-primary)' }}>{w.relation_type || 'N/A'}</td>
                                                    <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                                                        <span style={{ fontSize: '0.75rem', padding: '4px 8px', borderRadius: 4, background: 'var(--bg-tertiary)' }}>
                                                            {w.space}
                                                        </span>
                                                    </td>
                                                    <td style={{ padding: '12px 16px', textAlign: 'right', color: 'var(--text-secondary)' }}>
                                                        {w.current_weight.toFixed(3)}
                                                    </td>
                                                    <td style={{ padding: '12px 16px', textAlign: 'right', color: 'var(--text-secondary)' }}>
                                                        {w.vector_similarity !== null ? w.vector_similarity.toFixed(3) : 'N/A'}
                                                    </td>
                                                    <td style={{ padding: '12px 16px', textAlign: 'right', fontWeight: 600 }}>
                                                        <span style={{ color: proposedColor, background: proposedBg, padding: '4px 8px', borderRadius: '4px' }}>
                                                            {w.proposed_weight !== null ? w.proposed_weight.toFixed(3) : 'N/A'}
                                                        </span>
                                                    </td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                </table>
                            )}
                        </div>
                    </div>
                </div>
            )}

            <style>{`
                .text-pink-500 { color: #ec4899; }
                .search-input {
                    background: var(--bg-tertiary);
                    border: 1px solid var(--border-subtle);
                    color: var(--text-primary);
                    padding: 10px 14px;
                    border-radius: var(--radius-sm);
                    font-size: 0.95rem;
                    outline: none;
                    transition: border-color 0.2s;
                    appearance: none; /* Add this to allow custom styling of the select dropdown arrow if needed, though usually just setting bg is enough */
                }
                .search-input:focus {
                    border-color: var(--accent-primary);
                }
                
                /* Target only select elements with the search-input class */
                select.search-input {
                    background-color: var(--bg-tertiary);
                    color: var(--text-primary);
                }
                
                /* Style the options within the select */
                select.search-input option {
                    background-color: var(--bg-secondary);
                    color: var(--text-primary);
                    padding: 8px;
                }
            `}</style>
        </div>
    );
}
