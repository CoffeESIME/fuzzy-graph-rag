/**
 * ScoreNormalizer — Intelligent score visualization for different search strategies.
 *
 * Problem: Cosine similarity returns 0-1 (0.8 = great), but RRF scores are
 * tiny fractions (~0.016) that confuse users when shown as percentages.
 *
 * Solution: Normalize RRF scores relative to the batch maximum so the best
 * result always shows as ~100% relevance.
 */

export type SearchStrategy = 'vector' | 'hybrid' | 'rrf';

export interface NormalizedScore {
    /** Display percentage (0-100) */
    displayPercent: number;
    /** Color class: 'high' | 'medium' | 'low' */
    confidence: 'high' | 'medium' | 'low';
    /** CSS color for the bar */
    barColor: string;
    /** Human-readable label */
    label: string;
    /** Tooltip explanation */
    tooltip: string;
    /** Original raw score */
    rawScore: number;
}

/**
 * Detect which search strategy produced these results.
 */
export function detectStrategy(activeTab: string): SearchStrategy {
    switch (activeTab) {
        case 'semantic-text':
            return 'hybrid';       // Now uses Weaviate hybrid (BM25 + vector)
        case 'visual-siglip':
            return 'vector';       // Pure near_vector (cosine)
        case 'hybrid-visual':
            return 'rrf';          // Reciprocal Rank Fusion
        default:
            return 'vector';
    }
}

/**
 * Normalize a batch of scores according to the search strategy.
 */
export function normalizeScores(
    scores: number[],
    strategy: SearchStrategy
): NormalizedScore[] {
    if (scores.length === 0) return [];

    switch (strategy) {
        case 'vector':
            return scores.map(s => normalizeVector(s));
        case 'hybrid':
            return scores.map(s => normalizeHybrid(s));
        case 'rrf': {
            const maxScore = Math.max(...scores);
            return scores.map(s => normalizeRRF(s, maxScore));
        }
    }
}

/**
 * Cosine / near_vector: score is already 0-1 (1 - distance)
 */
function normalizeVector(score: number): NormalizedScore {
    const pct = Math.min(100, Math.max(0, score * 100));
    return {
        displayPercent: pct,
        confidence: pct >= 75 ? 'high' : pct >= 45 ? 'medium' : 'low',
        barColor: pct >= 75 ? '#10b981' : pct >= 45 ? '#6366f1' : '#6b7280',
        label: `${pct.toFixed(1)}%`,
        tooltip: `Similitud coseno directa: ${score.toFixed(4)} (${pct.toFixed(1)}%)`,
        rawScore: score,
    };
}

/**
 * Weaviate Hybrid: returns a fusion score from BM25+vector.
 * Scores CAN exceed 1.0 depending on the fusion method.
 * We treat the first result's score as reference but still show the relative value.
 */
function normalizeHybrid(score: number): NormalizedScore {
    // Hybrid scores from Weaviate are usually 0-1 when using relative score fusion,
    // but can vary. We clamp to 0-100 for display.
    const pct = Math.min(100, Math.max(0, score * 100));
    return {
        displayPercent: pct,
        confidence: pct >= 70 ? 'high' : pct >= 40 ? 'medium' : 'low',
        barColor: pct >= 70 ? '#10b981' : pct >= 40 ? '#3b82f6' : '#6b7280',
        label: `${pct.toFixed(1)}%`,
        tooltip: `Hybrid BM25 + Vector: score ${score.toFixed(4)} → ${pct.toFixed(1)}%`,
        rawScore: score,
    };
}

/**
 * RRF (Reciprocal Rank Fusion): scores are tiny fractions (~0.016).
 * Normalize relative to the batch maximum so #1 = 100%.
 */
function normalizeRRF(score: number, maxBatchScore: number): NormalizedScore {
    const pct = maxBatchScore > 0
        ? Math.min(100, (score / maxBatchScore) * 100)
        : 0;
    return {
        displayPercent: pct,
        confidence: pct >= 80 ? 'high' : pct >= 50 ? 'medium' : 'low',
        barColor: pct >= 80 ? '#10b981' : pct >= 50 ? '#f59e0b' : '#6b7280',
        label: `${pct.toFixed(0)}%`,
        tooltip: `Ranking combinado (RRF): score raw ${score.toFixed(6)} · Relevancia relativa ${pct.toFixed(1)}%`,
        rawScore: score,
    };
}

/**
 * Get the match type badge info based on the active tab.
 */
export function getMatchTypeBadge(activeTab: string): {
    icon: string;
    label: string;
    color: string;
    bg: string;
} {
    switch (activeTab) {
        case 'semantic-text':
            return { icon: '📝', label: 'Híbrido', color: '#6366f1', bg: 'rgba(99,102,241,0.12)' };
        case 'visual-siglip':
            return { icon: '👁️', label: 'Visual', color: '#8b5cf6', bg: 'rgba(139,92,246,0.12)' };
        case 'hybrid-visual':
            return { icon: '🔀', label: 'Multimodal', color: '#f59e0b', bg: 'rgba(245,158,11,0.12)' };
        default:
            return { icon: '🔍', label: 'Búsqueda', color: '#6b7280', bg: 'rgba(107,114,128,0.12)' };
    }
}

/**
 * Get alpha dominance indicator for multimodal searches.
 */
export function getAlphaDominance(alpha: number | undefined): {
    icon: string;
    label: string;
} | null {
    if (alpha === undefined) return null;
    if (alpha < 0.2) return { icon: '👁️', label: 'Dominancia Visual' };
    if (alpha > 0.8) return { icon: '📝', label: 'Dominancia Textual' };
    return null;
}
