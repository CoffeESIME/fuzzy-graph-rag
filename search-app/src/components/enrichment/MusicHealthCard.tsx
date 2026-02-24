import { useEffect, useState } from 'react';
import { getHealthStats, repairArtists, backfillProjects } from '../../lib/api';
import type { HealthStats } from '../../lib/api';
import { Activity, Wrench, RefreshCcw, Loader2, Music, User, Folder } from 'lucide-react';

export default function MusicHealthCard() {
    const [stats, setStats] = useState<HealthStats | null>(null);
    const [loadingStats, setLoadingStats] = useState(true);
    const [repairingArtists, setRepairingArtists] = useState(false);
    const [backfillingProjects, setBackfillingProjects] = useState(false);
    const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);

    const fetchStats = async () => {
        setLoadingStats(true);
        setMessage(null);
        try {
            const data = await getHealthStats();
            setStats(data);
        } catch (error: any) {
            setMessage({ type: 'error', text: error.message || 'Error fetching stats' });
        } finally {
            setLoadingStats(false);
        }
    };

    useEffect(() => {
        fetchStats();
    }, []);

    const handleRepairArtists = async () => {
        setRepairingArtists(true);
        setMessage(null);
        try {
            const res = await repairArtists();
            setMessage({ type: 'success', text: res.message });
            await fetchStats(); // Refresh stats after repair
        } catch (error: any) {
            setMessage({ type: 'error', text: error.response?.data?.detail || error.message || 'Error repairing artists' });
        } finally {
            setRepairingArtists(false);
        }
    };

    const handleBackfillProjects = async () => {
        setBackfillingProjects(true);
        setMessage(null);
        try {
            const res = await backfillProjects();
            setMessage({ type: 'success', text: res.message });
            await fetchStats(); // Refresh stats after backfill
        } catch (error: any) {
            setMessage({ type: 'error', text: error.response?.data?.detail || error.message || 'Error backfilling projects' });
        } finally {
            setBackfillingProjects(false);
        }
    };

    return (
        <div style={{ padding: '24px', background: 'var(--bg-primary)', minHeight: '100%', borderRadius: '12px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                <h2 style={{ fontSize: '1.5rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-primary)' }}>
                    <Activity size={24} style={{ color: '#ec4899' }} /> Salud de Música y Arte
                </h2>
                <button
                    onClick={fetchStats}
                    disabled={loadingStats}
                    style={{
                        background: 'transparent', border: '1px solid var(--border-subtle)',
                        padding: '6px 12px', borderRadius: '6px', color: 'var(--text-secondary)',
                        display: 'flex', alignItems: 'center', gap: '6px', cursor: 'pointer'
                    }}
                >
                    <RefreshCcw size={14} className={loadingStats ? 'animate-spin' : ''} />
                    Actualizar
                </button>
            </div>

            {message && (
                <div style={{
                    padding: '12px 16px', borderRadius: '8px', marginBottom: '24px',
                    background: message.type === 'success' ? '#22c55e15' : '#ef444415',
                    color: message.type === 'success' ? '#86efac' : '#fca5a5',
                    border: `1px solid ${message.type === 'success' ? '#22c55e30' : '#ef444430'}`
                }}>
                    {message.type === 'success' ? '✅' : '❌'} {message.text}
                </div>
            )}

            {/* Statistics Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '32px' }}>
                <div style={{ background: 'var(--bg-secondary)', padding: '20px', borderRadius: '12px', border: '1px solid var(--border-subtle)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                        <User size={16} /> Total Artistas
                    </div>
                    <div style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                        {loadingStats ? '-' : stats?.total_artists}
                    </div>
                </div>
                <div style={{ background: 'var(--bg-secondary)', padding: '20px', borderRadius: '12px', border: '1px solid var(--border-subtle)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                        <Folder size={16} /> Total Proyectos
                    </div>
                    <div style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                        {loadingStats ? '-' : stats?.total_projects}
                    </div>
                </div>
                <div style={{ background: 'var(--bg-secondary)', padding: '20px', borderRadius: '12px', border: '1px solid #ef444450' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#fca5a5', marginBottom: '8px' }}>
                        <Music size={16} /> Audios Sin Artista
                    </div>
                    <div style={{ fontSize: '2rem', fontWeight: 800, color: '#ef4444' }}>
                        {loadingStats ? '-' : stats?.orphaned_audio_no_artist}
                    </div>
                </div>
                <div style={{ background: 'var(--bg-secondary)', padding: '20px', borderRadius: '12px', border: '1px solid #ef444450' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#fca5a5', marginBottom: '8px' }}>
                        <Music size={16} /> Audios Sin Proyecto
                    </div>
                    <div style={{ fontSize: '2rem', fontWeight: 800, color: '#ef4444' }}>
                        {loadingStats ? '-' : stats?.orphaned_audio_no_project}
                    </div>
                </div>
            </div>

            {/* Action Cards */}
            <h3 style={{ fontSize: '1.2rem', fontWeight: 600, marginBottom: '16px', color: 'var(--text-primary)' }}>Operaciones de Consolidación</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '16px' }}>

                {/* Repair Artists Option */}
                <div style={{
                    background: 'var(--bg-secondary)', borderRadius: '12px', padding: '20px',
                    border: '1px solid var(--border-subtle)', display: 'flex', flexDirection: 'column', gap: '12px'
                }}>
                    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
                        <div>
                            <h4 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '4px' }}>
                                Auto-Vincular Artistas (Filename)
                            </h4>
                            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', maxWidth: '600px', lineHeight: 1.5 }}>
                                Rastrea archivos de audio cuyo nombre siga el patrón <code>"Artista - Cancion"</code> y extrae el artista para crear un nodo <code>Person</code>, vinculándolo automáticamente mediante <code>[:CREATED_BY]</code> con el archivo original.
                            </p>
                        </div>
                        <button
                            onClick={handleRepairArtists}
                            disabled={repairingArtists || loadingStats || stats?.orphaned_audio_no_artist === 0}
                            style={{
                                padding: '8px 16px', borderRadius: '8px', fontSize: '0.9rem', fontWeight: 600,
                                background: 'linear-gradient(135deg, #10b981, #34d399)', color: '#000', border: 'none',
                                cursor: (repairingArtists || stats?.orphaned_audio_no_artist === 0) ? 'not-allowed' : 'pointer',
                                display: 'flex', alignItems: 'center', gap: '8px', opacity: (repairingArtists || stats?.orphaned_audio_no_artist === 0) ? 0.5 : 1
                            }}
                        >
                            {repairingArtists ? <Loader2 size={16} className="animate-spin" /> : <Wrench size={16} />}
                            {repairingArtists ? 'Reparando...' : 'Reparar Artistas'}
                        </button>
                    </div>
                    {stats?.orphaned_audio_no_artist === 0 && (
                        <span style={{ fontSize: '0.8rem', color: '#10b981' }}>✓ No hay audios huérfanos de artista actualmente.</span>
                    )}
                </div>

                {/* Backfill Projects Option */}
                <div style={{
                    background: 'var(--bg-secondary)', borderRadius: '12px', padding: '20px',
                    border: '1px solid var(--border-subtle)', display: 'flex', flexDirection: 'column', gap: '12px'
                }}>
                    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
                        <div>
                            <h4 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '4px' }}>
                                Recuperar Proyectos/Eventos (Sidecars)
                            </h4>
                            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', maxWidth: '600px', lineHeight: 1.5 }}>
                                Escanea el análisis original de la IA guardado en los sidecars de MinIO (<code>data_layers.analysis_json.graph_core.entities.projects/events</code>) y crea las relaciones perdidas hacia <code>Project</code> y <code>Event</code> para archivos aprobados sin estos mappings.
                            </p>
                        </div>
                        <button
                            onClick={handleBackfillProjects}
                            disabled={backfillingProjects || loadingStats || stats?.orphaned_audio_no_project === 0}
                            style={{
                                padding: '8px 16px', borderRadius: '8px', fontSize: '0.9rem', fontWeight: 600,
                                background: 'linear-gradient(135deg, #6366f1, #818cf8)', color: '#fff', border: 'none',
                                cursor: (backfillingProjects || stats?.orphaned_audio_no_project === 0) ? 'not-allowed' : 'pointer',
                                display: 'flex', alignItems: 'center', gap: '8px', opacity: (backfillingProjects || stats?.orphaned_audio_no_project === 0) ? 0.5 : 1
                            }}
                        >
                            {backfillingProjects ? <Loader2 size={16} className="animate-spin" /> : <Folder size={16} />}
                            {backfillingProjects ? 'Recuperando...' : 'Recuperar Elementos'}
                        </button>
                    </div>
                    {stats?.orphaned_audio_no_project === 0 && (
                        <span style={{ fontSize: '0.8rem', color: '#10b981' }}>✓ No hay audios huérfanos de proyecto actualmente.</span>
                    )}
                </div>

            </div>
        </div>
    );
}
