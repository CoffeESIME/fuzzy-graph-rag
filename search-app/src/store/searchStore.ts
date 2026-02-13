import { create } from 'zustand';
import type { SearchTab, SearchResponse } from '../types/search';

interface SearchState {
    // Active tab
    activeTab: SearchTab;
    setActiveTab: (tab: SearchTab) => void;

    // Results per tab
    results: Partial<Record<SearchTab, SearchResponse | null>>;
    setResults: (tab: SearchTab, data: SearchResponse | null) => void;

    // Loading per tab
    loading: Partial<Record<SearchTab, boolean>>;
    setLoading: (tab: SearchTab, val: boolean) => void;

    // Error per tab
    error: Partial<Record<SearchTab, string | null>>;
    setError: (tab: SearchTab, err: string | null) => void;

    // Clear a tab's results
    clearTab: (tab: SearchTab) => void;
}

export const useSearchStore = create<SearchState>((set) => ({
    activeTab: 'semantic-text',
    setActiveTab: (tab) => set({ activeTab: tab }),

    results: {},
    setResults: (tab, data) =>
        set((s) => ({ results: { ...s.results, [tab]: data } })),

    loading: {},
    setLoading: (tab, val) =>
        set((s) => ({ loading: { ...s.loading, [tab]: val } })),

    error: {},
    setError: (tab, err) =>
        set((s) => ({ error: { ...s.error, [tab]: err } })),

    clearTab: (tab) =>
        set((s) => ({
            results: { ...s.results, [tab]: null },
            error: { ...s.error, [tab]: null },
        })),
}));
