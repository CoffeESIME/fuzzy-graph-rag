import { useMutation } from '@tanstack/react-query';
import { useSearchStore } from '../store/searchStore';
import {
    searchSemanticText,
    searchVisualSiglip,
    searchHybridVisual,
    searchGraphCrisp,
    searchGraphFuzzy,
} from '../lib/api';
import type {
    SemanticTextRequest,
    VisualSigLIPRequest,
    HybridVisualRequest,
    GraphCrispRequest,
    GraphFuzzyRequest,
    SearchTab,
} from '../types/search';

function useGenericSearch<T>(tab: SearchTab, fn: (data: T) => Promise<any>) {
    const { setResults, setLoading, setError } = useSearchStore();

    return useMutation({
        mutationFn: fn,
        onMutate: () => {
            setLoading(tab, true);
            setError(tab, null);
        },
        onSuccess: (data) => {
            setResults(tab, data);
            setLoading(tab, false);
        },
        onError: (err: Error) => {
            setError(tab, err.message);
            setLoading(tab, false);
        },
    });
}

export function useSemanticTextSearch() {
    return useGenericSearch<SemanticTextRequest>(
        'semantic-text',
        searchSemanticText
    );
}

export function useVisualSigLIPSearch() {
    return useGenericSearch<VisualSigLIPRequest>(
        'visual-siglip',
        searchVisualSiglip
    );
}

export function useHybridVisualSearch() {
    return useGenericSearch<HybridVisualRequest>(
        'hybrid-visual',
        searchHybridVisual
    );
}

export function useGraphCrispSearch() {
    return useGenericSearch<GraphCrispRequest>(
        'graph-crisp',
        searchGraphCrisp
    );
}

export function useGraphFuzzySearch() {
    return useGenericSearch<GraphFuzzyRequest>(
        'graph-fuzzy',
        searchGraphFuzzy
    );
}
