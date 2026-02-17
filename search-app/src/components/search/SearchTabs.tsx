import * as Tabs from '@radix-ui/react-tabs';
import { Type, Image, Layers, GitBranch, Radar } from 'lucide-react';
import { useSearchStore } from '../../store/searchStore';
import SemanticTextTab from './SemanticTextTab';
import VisualSigLIPTab from './VisualSigLIPTab';
import HybridVisualTab from './HybridVisualTab';
import GraphCrispTab from './GraphCrispTab';
import GraphFuzzyTab from './GraphFuzzyTab';
import type { SearchTab } from '../../types/search';

const TABS: { id: SearchTab; label: string; icon: React.ReactNode; comingSoon?: boolean }[] = [
    { id: 'semantic-text', label: 'Semántica', icon: <Type size={16} /> },
    { id: 'visual-siglip', label: 'Visual', icon: <Image size={16} /> },
    { id: 'hybrid-visual', label: 'Multimodal', icon: <Layers size={16} /> },
    { id: 'graph-crisp', label: 'Grafo', icon: <GitBranch size={16} /> },
    { id: 'graph-fuzzy', label: 'Grafo Difuso', icon: <Radar size={16} /> },
];

export default function SearchTabs() {
    const { activeTab, setActiveTab } = useSearchStore();

    return (
        <Tabs.Root
            value={activeTab}
            onValueChange={(v) => setActiveTab(v as SearchTab)}
        >
            <Tabs.List style={{
                display: 'flex',
                borderBottom: '1px solid var(--border-subtle)',
                overflowX: 'auto',
                marginBottom: 24,
            }}>
                {TABS.map((tab) => (
                    <Tabs.Trigger
                        key={tab.id}
                        value={tab.id}
                        className="search-tab-trigger"
                        style={{ position: 'relative' }}
                    >
                        {tab.icon}
                        {tab.label}
                        {tab.comingSoon && (
                            <span style={{
                                fontSize: '0.55rem', fontWeight: 700,
                                padding: '1px 5px', borderRadius: 6,
                                background: 'rgba(245, 158, 11, 0.15)',
                                color: '#f59e0b',
                                marginLeft: 4,
                                lineHeight: 1.4,
                                whiteSpace: 'nowrap',
                            }}>
                                SOON
                            </span>
                        )}
                    </Tabs.Trigger>
                ))}
            </Tabs.List>

            <Tabs.Content value="semantic-text">
                <SemanticTextTab />
            </Tabs.Content>
            <Tabs.Content value="visual-siglip">
                <VisualSigLIPTab />
            </Tabs.Content>
            <Tabs.Content value="hybrid-visual">
                <HybridVisualTab />
            </Tabs.Content>
            <Tabs.Content value="graph-crisp">
                <GraphCrispTab />
            </Tabs.Content>
            <Tabs.Content value="graph-fuzzy">
                <GraphFuzzyTab />
            </Tabs.Content>
        </Tabs.Root>
    );
}
