import { useState } from 'react';
import { Sparkles, ArrowLeft, Search, CheckSquare, Square, Check } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { getEnrichmentCandidates, requestEnrichment } from '../../lib/api';
import type { CandidateNode } from '../../lib/api';

export default function EnrichmentDashboard() {
    const navigate = useNavigate();

    const [nodeType, setNodeType] = useState('Person');
    const [limit, setLimit] = useState(50);
    const [isLoading, setIsLoading] = useState(false);
    const [candidates, setCandidates] = useState<CandidateNode[]>([]);
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [error, setError] = useState<string | null>(null);
    const [successMsg, setSuccessMsg] = useState<string | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);

    const allowedTypes = ["Person", "Concept", "Location", "Organization", "Event", "Project", "Device", "Method"];

    const handleSearch = async () => {
        setIsLoading(true);
        setError(null);
        setSuccessMsg(null);
        setCandidates([]);
        setSelectedIds(new Set());

        try {
            const res = await getEnrichmentCandidates(nodeType, limit);
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
                                                <th style={{ padding: '12px 16px', fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: 600, width: 150, textAlign: 'center' }}>Referencias (Assets)</th>
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
                                                    <td style={{ padding: '12px 16px', textAlign: 'center', color: 'var(--text-secondary)' }}>
                                                        {cand.connections}
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
