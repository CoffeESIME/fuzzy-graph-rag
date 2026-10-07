import type { PathfinderPath } from '../types/pathfinder';

/** Observation only: no thresholds, combined score, ranking or filtering. */
export function overlap(left: Iterable<string>, right: Iterable<string>) {
    const a = new Set(left), b = new Set(right);
    const shared = [...a].filter(x => b.has(x)).sort();
    const onlyLeft = [...a].filter(x => !b.has(x)).sort();
    const onlyRight = [...b].filter(x => !a.has(x)).sort();
    const union = shared.length + onlyLeft.length + onlyRight.length;
    return { jaccard: union ? shared.length / union : null, intersection: shared.length, union, shared, onlyLeft, onlyRight };
}

// Assignments must come from one existing partition; never inferred or computed here.
export interface CommunityAssignments { partition: string; byNode: Record<string, string> }

export function comparePathfinderPaths(paths: PathfinderPath[], communities?: CommunityAssignments) {
    const features = paths.map(path => {
        const endpoints = new Set([path.nodes[0]?.id, path.nodes.at(-1)?.id]);
        const internal = path.nodes.filter(n => !endpoints.has(n.id));
        const concepts = [...new Set(internal.filter(n => n.node_type === 'Concept').map(n => n.id))];
        const assigned = concepts.filter(id => communities?.byNode[id] != null);
        return {
            pathId: path.id, rank: path.rank, mode: path.mode,
            nodeSequence: path.nodes.map(n => n.id),
            relationshipSequence: path.edges.map(e => e.id ?? null),
            internalNodes: internal.map(n => n.id),
            // Pathfinder traverses undirected relationships. Preserve type, ignore ID and stored direction.
            normalizedEdges: path.edges.map(e => JSON.stringify([[e.source, e.target].sort(), e.rel_type])),
            relationshipIds: path.edges.flatMap(e => e.id == null ? [] : [e.id]),
            // Traversed DigitalAssets only; do not interpret provenance.source as an asset ID.
            assets: internal.filter(n => n.node_type === 'DigitalAsset').map(n => n.id),
            communities: assigned.map(id => communities!.byNode[id]),
            communityCoverage: { assigned: assigned.length, total: concepts.length },
            repeatedNodeCount: path.nodes.length - new Set(path.nodes.map(n => n.id)).size,
        };
    });
    const pairs = features.flatMap((a, i) => features.slice(i + 1).map(b => {
        const sameNodeSequence = JSON.stringify(a.nodeSequence) === JSON.stringify(b.nodeSequence);
        const completeIds = ![...a.relationshipSequence, ...b.relationshipSequence].includes(null);
        const sameRelationships = JSON.stringify(a.relationshipSequence) === JSON.stringify(b.relationshipSequence);
        const completeCommunities = communities != null && [a, b].every(f => f.communityCoverage.assigned === f.communityCoverage.total);
        return {
            left: a.pathId, right: b.pathId,
            sameEndpoints: a.nodeSequence[0] === b.nodeSequence[0] && a.nodeSequence.at(-1) === b.nodeSequence.at(-1),
            sameNodeSequence,
            exactRelationshipRoute: completeIds ? sameNodeSequence && sameRelationships : null,
            parallelEdgeVariant: completeIds ? sameNodeSequence && !sameRelationships : null,
            internalNodes: overlap(a.internalNodes, b.internalNodes),
            normalizedEdges: overlap(a.normalizedEdges, b.normalizedEdges),
            relationshipIds: completeIds ? overlap(a.relationshipIds, b.relationshipIds) : null,
            sourceAssets: overlap(a.assets, b.assets),
            communities: completeCommunities ? overlap(a.communities, b.communities) : null,
        };
    }));
    return {
        version: 'pathfinder-overlap-v1',
        communityPartition: communities?.partition ?? null,
        definitions: {
            internalNodes: 'Distinct internal node IDs, excluding endpoint identities even if revisited.',
            normalizedEdges: 'Distinct undirected endpoint pairs plus relationship type; parallel IDs collapse only in this measurement.',
            relationshipIds: 'Distinct relationship IDs; unavailable when any ID is missing.',
            sourceAssets: 'Distinct traversed internal DigitalAsset node IDs. No adjacent assets or inferred provenance; different IDs remain different even with identical content.',
            communities: 'Existing partition on internal Concept nodes; unavailable for incomplete assignments. No community detection is run.',
            emptySets: 'Empty union yields null (no evidence), not perfect agreement. One empty set against a nonempty set yields zero.',
            limitations: 'Set overlaps ignore order, multiplicity, weights and meaning. Inspect sequences and relationship evidence. No near-duplicate threshold or semantic equivalence is asserted.',
        },
        features, pairs,
    };
}
