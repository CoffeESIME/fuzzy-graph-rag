import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';
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
    GraphCrispRequest,
    GraphFuzzyRequest,
    SearchTab,
    MultimodalFusionResponse,
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

/**
 * Custom hook for hybrid visual search — returns MultimodalFusionResponse
 * with separate text/visual/fused result lists (not the generic SearchResponse).
 */
export function useHybridVisualSearch() {
    const [fusionData, setFusionData] = useState<MultimodalFusionResponse | null>(null);
    const [fusionLoading, setFusionLoading] = useState(false);
    const [fusionError, setFusionError] = useState<string | null>(null);

    const mutation = useMutation({
        mutationFn: searchHybridVisual,
        onMutate: () => {
            setFusionLoading(true);
            setFusionError(null);
        },
        onSuccess: (data) => {
            setFusionData(data);
            setFusionLoading(false);
        },
        onError: (err: Error) => {
            setFusionError(err.message);
            setFusionLoading(false);
        },
    });

    return { mutation, fusionData, fusionLoading, fusionError };
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
