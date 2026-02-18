import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload, ListChecks, Eye, GitBranch, Search, BrainCircuit } from 'lucide-react';
import TaskControlTab from './TaskControlTab';

const TABS = [
    { id: 'ingest', label: 'Ingesta y Agrupación', icon: Upload },
    { id: 'tasks', label: 'Control de Tareas', icon: ListChecks },
    { id: 'review', label: 'Cola de Revisión', icon: Eye },
    { id: 'graph', label: 'Generador de Nodos', icon: GitBranch },
];

function PlaceholderTab({ title, description }: { title: string; description: string }) {
    return (
        <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            minHeight: 400, gap: 16, color: 'var(--text-secondary, #94a3b8)'
        }}>
            <div style={{
                width: 64, height: 64, borderRadius: 16,
                background: 'linear-gradient(135deg, #6366f120, #a855f720)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 28
            }}>
                🚧
            </div>
            <h3 style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-primary, #f8fafc)' }}>{title}</h3>
            <p style={{ maxWidth: 400, textAlign: 'center', lineHeight: 1.6 }}>{description}</p>
        </div>
    );
}

export default function IngestControlPage() {
    const [activeTab, setActiveTab] = useState('tasks');
    const navigate = useNavigate();

    return (
        <div style={{ minHeight: '100vh', background: 'var(--bg-primary, #0f172a)' }}>
            {/* Header */}
            <div style={{
                padding: '24px 48px', borderBottom: '1px solid var(--border-subtle, #1e293b)',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between'
            }}>
                <div>
                    <h1 style={{
                        fontSize: '1.75rem', fontWeight: 800, marginBottom: 4,
                        background: 'linear-gradient(to right, #6366f1, #a855f7)',
                        WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent'
                    }}>
                        Ingesta y Control de Tareas
                    </h1>
                    <p style={{ color: 'var(--text-secondary, #94a3b8)', fontSize: '0.95rem' }}>
                        Gestión de archivos, procesamiento y calidad de datos.
                    </p>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                    <button onClick={() => navigate('/search')} className="btn-secondary"
                        style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px', borderRadius: 8 }}>
                        <Search size={16} /> Búsqueda
                    </button>
                    <button onClick={() => navigate('/analysis')} className="btn-secondary"
                        style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px', borderRadius: 8 }}>
                        <BrainCircuit size={16} /> Análisis
                    </button>
                </div>
            </div>

            {/* Tab Bar */}
            <div style={{
                display: 'flex', gap: 0, padding: '0 48px',
                borderBottom: '1px solid var(--border-subtle, #1e293b)',
                background: 'var(--bg-secondary, #1e293b20)'
            }}>
                {TABS.map((tab) => {
                    const Icon = tab.icon;
                    const isActive = activeTab === tab.id;
                    return (
                        <button
                            key={tab.id}
                            onClick={() => setActiveTab(tab.id)}
                            style={{
                                display: 'flex', alignItems: 'center', gap: 8,
                                padding: '14px 24px', fontSize: '0.9rem', fontWeight: isActive ? 600 : 400,
                                color: isActive ? '#818cf8' : 'var(--text-secondary, #94a3b8)',
                                background: 'transparent', border: 'none', cursor: 'pointer',
                                borderBottom: isActive ? '2px solid #818cf8' : '2px solid transparent',
                                transition: 'all 0.15s ease'
                            }}
                        >
                            <Icon size={16} />
                            {tab.label}
                        </button>
                    );
                })}
            </div>

            {/* Tab Content */}
            <div style={{ padding: '24px 48px' }}>
                {activeTab === 'ingest' && (
                    <PlaceholderTab
                        title="Ingesta y Agrupación"
                        description="Carga de archivos, agrupación por operación, configuración de vectores y envío al backend. Próximamente."
                    />
                )}
                {activeTab === 'tasks' && <TaskControlTab />}
                {activeTab === 'review' && (
                    <PlaceholderTab
                        title="Cola de Revisión"
                        description="Revisión y aprobación de tareas TEXT_SUMMARY antes de continuar el pipeline. Próximamente."
                    />
                )}
                {activeTab === 'graph' && (
                    <PlaceholderTab
                        title="Generador de Nodos"
                        description="Generación de nodos de grafos (Concept, Person, Organization) a partir de sidecars aprobados. Próximamente."
                    />
                )}
            </div>
        </div>
    );
}
