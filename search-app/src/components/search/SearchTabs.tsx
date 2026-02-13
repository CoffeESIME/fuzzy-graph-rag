import * as Tabs from '@radix-ui/react-tabs';
import { Type, Image, Layers, GitBranch, Radar } from 'lucide-react';
import { useSearchStore } from '../../store/searchStore';
import SemanticTextTab from './SemanticTextTab';
import VisualSigLIPTab from './VisualSigLIPTab';
import HybridVisualTab from './HybridVisualTab';
import GraphCrispTab from './GraphCrispTab';
import GraphFuzzyTab from './GraphFuzzyTab';
import type { SearchTab } from '../../types/search';

const TABS: { id: SearchTab; label: string; icon: React.ReactNode }[] = [
    { id: 'semantic-text', label: 'Semántica', icon: <Type size={16} /> },
    { id: 'visual-siglip', label: 'Visual (SigLIP)', icon: <Image size={16} /> },
    { id: 'hybrid-visual', label: 'Híbrida', icon: <Layers size={16} /> },
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
                    >
                        {tab.icon}
                        {tab.label}
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
