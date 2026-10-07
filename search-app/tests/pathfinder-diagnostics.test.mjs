import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import ts from 'typescript';

const source = await readFile(new URL('../src/lib/pathfinderDiagnostics.ts', import.meta.url), 'utf8');
const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
const { comparePathfinderPaths: compare, overlap } = await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`);
const fixture = JSON.parse(await readFile(new URL('./fixtures/canonical-pathfinder-v2.json', import.meta.url), 'utf8'));

test('canonical routes retain shared bridges without collapsing distinct sequences', () => {
    const before = JSON.stringify(fixture.paths);
    const result = compare(fixture.paths);
    assert.equal(JSON.stringify(fixture.paths), before);
    assert.equal(result.pairs.length, 3);
    assert.deepEqual(result.pairs.map(p => p.internalNodes.jaccard), [1/7, 1/7, 2/8]);
    assert.deepEqual(result.pairs.map(p => p.sourceAssets.jaccard), [1/4, 1/4, 1/5]);
    assert.deepEqual(result.pairs.map(p => p.normalizedEdges.jaccard), [1/9, 1/9, 2/10]);
    assert.ok(result.pairs.every(p => !p.sameNodeSequence && p.communities === null));
});

test('exact copies and parallel variants remain separate observations', () => {
    const a = fixture.paths[0], b = structuredClone(a), c = structuredClone(a);
    b.id = 'copy'; c.id = 'parallel'; c.edges[0].id = 'different';
    const { pairs, features } = compare([a, b, c]);
    assert.equal(features.length, 3);
    assert.equal(pairs[0].exactRelationshipRoute, true);
    assert.equal(pairs[1].parallelEdgeVariant, true);
    assert.equal(pairs[1].normalizedEdges.jaccard, 1);
    assert.equal(pairs[1].relationshipIds.jaccard, 3/5);
    delete c.edges[0].id;
    assert.equal(compare([a, c]).pairs[0].exactRelationshipRoute, null);
});

test('normalization ignores stored direction but preserves relationship type', () => {
    const a = fixture.paths[0], b = structuredClone(a);
    [b.edges[0].source, b.edges[0].target] = [b.edges[0].target, b.edges[0].source];
    assert.equal(compare([a, b]).pairs[0].normalizedEdges.jaccard, 1);
    b.edges[0].rel_type = 'OTHER';
    assert.equal(compare([a, b]).pairs[0].normalizedEdges.jaccard, 3/5);
});

test('empty data is not perfect agreement, overlap is symmetric and differences inspectable', () => {
    assert.equal(overlap([], []).jaccard, null);
    assert.equal(overlap([], ['x']).jaccard, 0);
    assert.deepEqual(overlap(['b', 'a', 'a'], ['b', 'c']), { jaccard: 1/3, intersection: 1, union: 3, shared: ['b'], onlyLeft: ['a'], onlyRight: ['c'] });
    assert.equal(overlap(['a','b'], ['b']).jaccard, overlap(['b'], ['a','b']).jaccard);
    assert.equal(compare([]).pairs.length, 0);
    assert.equal(compare([fixture.paths[0]]).pairs.length, 0);
});

test('community coverage must be complete; a single broad region can hide distinct paths', () => {
    const assignments = { partition: 'test-only', byNode: {} };
    for (const p of fixture.paths) for (const n of p.nodes) if (n.node_type === 'Concept') assignments.byNode[n.id] = '0';
    const result = compare(fixture.paths, assignments);
    assert.ok(result.pairs.every(p => p.communities.jaccard === 1 && !p.sameNodeSequence));
    delete assignments.byNode[fixture.paths[0].nodes[2].id];
    assert.equal(compare(fixture.paths, assignments).pairs[0].communities, null);
});

test('cycles and order differences cannot be inferred from set equality', () => {
    const a = fixture.paths[0], b = structuredClone(a);
    b.nodes.splice(2, 0, a.nodes[0]);
    const { pairs, features } = compare([a, b]);
    assert.equal(pairs[0].internalNodes.jaccard, 1);
    assert.equal(pairs[0].sameNodeSequence, false);
    assert.equal(features[1].repeatedNodeCount, 1);
    assert.ok(!features[1].internalNodes.includes(a.nodes[0].id));
});
