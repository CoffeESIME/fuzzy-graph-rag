import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import ts from 'typescript';

// Pure domain module: use the existing TypeScript compiler, no extra runtime.
const source = await readFile(new URL('../src/lib/pathfinderRoutes.ts', import.meta.url), 'utf8');
const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
const { routeGroups, routeView, combinedGraph, exportPathfinder, readSavedPathfinder, explanationInput, explanationFor, readPathfinderExplanations } = await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`);
const fixture = JSON.parse(await readFile(new URL('./fixtures/canonical-pathfinder-v2.json', import.meta.url), 'utf8'));

test('audited fixture has three distinct ordered routes, not three interpretations invented by UI', () => {
    assert.equal(routeGroups(fixture.paths).length, 3);
    assert.deepEqual(fixture.paths.map(p => p.hop_count), [4, 6, 6]);
    assert.deepEqual(fixture.paths.map(p => p.metrics.min_weight), [.7, .695, .621]);
    for (const p of fixture.paths) assert.equal(p.edges.length, p.nodes.length - 1);
});

test('selecting a route isolates exactly its ordered occurrences and relationships', () => {
    for (const path of fixture.paths) {
        const view = routeView(fixture, path.id);
        assert.deepEqual(view.nodes.map(n => n.data.raw.id), path.nodes.map(n => n.id));
        assert.deepEqual(view.edges.map(e => e.data.raw.id), path.edges.map(e => e.id));
        view.edges.forEach((e, i) => { assert.equal(e.source, view.nodes[i].id); assert.equal(e.target, view.nodes[i + 1].id); });
    }
    const all = routeView(fixture, null);
    assert.equal(all.nodes.length, new Set(fixture.paths.flatMap(p => p.nodes.map(n => n.id))).size);
    assert.ok(all.edges.some(e => e.data.routeLabel.includes('R2 · R3')));
});

test('same node sequence groups parallel-edge variants without losing export data', () => {
    const duplicate = structuredClone(fixture.paths[0]); duplicate.id = 'parallel-variant'; duplicate.edges[0].id = 'different-edge';
    const result = { ...fixture, paths: [...fixture.paths, duplicate] };
    assert.equal(routeGroups(result.paths).length, 3);
    assert.equal(routeGroups(result.paths)[0].variants.length, 2);
    assert.equal(exportPathfinder(result).paths.length, 4);
    assert.equal(routeView(result, duplicate.id).edges[0].data.raw.id, 'different-edge');
});

test('v2 JSON round-trip preserves all ordered paths, metrics, parameters, provenance and endpoints', () => {
    const exported = exportPathfinder(fixture);
    const restored = readSavedPathfinder(JSON.parse(JSON.stringify(exported)));
    assert.ok(restored);
    assert.deepEqual(restored.paths, exported.paths);
    assert.deepEqual(restored.source, exported.source);
    assert.deepEqual(restored.target, exported.target);
    const union = combinedGraph(restored.paths);
    assert.deepEqual(new Set(union.nodes.map(n => n.id)), new Set(fixture.nodes.map(n => n.id)));
    assert.deepEqual(new Set(union.edges.map(e => e.id)), new Set(fixture.edges.map(e => e.id)));
});

test('export removes expiring asset URLs but retains hashes and permanent metadata', () => {
    const result = structuredClone(fixture);
    result.paths[0].nodes[1].download_url = 'https://temporary.invalid/signed';
    const out = exportPathfinder(result);
    assert.equal(out.paths[0].nodes[1].download_url, undefined);
    assert.equal(out.paths[0].nodes[1].file_hash, result.paths[0].nodes[1].file_hash);
});

test('all existing Pathfinder saved unions remain readable without inferred routes', async () => {
    const directory = new URL('../../backend/data/saved_paths/', import.meta.url);
    const files = (await readdir(directory)).filter(f => f.startsWith('pathfinder_') && f.endsWith('.json'));
    assert.ok(files.length >= 1);
    for (const file of files) {
        const old = JSON.parse(await readFile(new URL(file, directory), 'utf8'));
        const read = readSavedPathfinder(old);
        assert.ok(read, file);
        assert.equal(read.paths.length, 0);
        assert.deepEqual(read.nodes, old.nodes);
        assert.deepEqual(read.edges, old.edges);
        assert.equal(routeView(read, null).nodes.length, old.nodes.length);
    }
});

test('malformed v2 route ordering fails closed, not as an inferred legacy path', () => {
    const wrong = structuredClone(fixture);
    [wrong.paths[0].nodes[1], wrong.paths[0].nodes[2]] = [wrong.paths[0].nodes[2], wrong.paths[0].nodes[1]];
    assert.equal(readSavedPathfinder(wrong), null);
    assert.equal(readSavedPathfinder({ ...fixture, schema_version: 99 }), null);
});

test('cycles retain separate canvas occurrences', () => {
    const p = structuredClone(fixture.paths[0]);
    p.nodes[2] = p.nodes[0];
    const view = routeView({ ...fixture, paths: [p] }, p.id);
    assert.equal(view.nodes.length, p.nodes.length);
    assert.equal(new Set(view.nodes.map(n => n.id)).size, p.nodes.length);
    assert.equal(view.nodes[0].data.raw.id, view.nodes[2].data.raw.id);
});


test('explanations for separate routes and all routes survive export independently', () => {
    const entries = fixture.paths.slice(0, 2).map((p, i) => ({ path_id: p.id, path_ids: [p.id], explanation: `Explanation ${i}`, generated_at: '2026-10-06T12:00:00Z', privacy_mode: true }));
    entries.push({ path_id: null, path_ids: fixture.paths.map(p => p.id), explanation: 'Comparison', generated_at: '2026-10-06T12:01:00Z', privacy_mode: true });
    entries.push({ ...entries[0], explanation: 'Second interpretation' });
    const restored = readPathfinderExplanations(JSON.parse(JSON.stringify(exportPathfinder(fixture, 'Comparison', null, entries))));
    assert.deepEqual(restored, entries);
    assert.equal(explanationFor(restored, fixture.paths[0].id), 'Second interpretation');
    assert.equal(explanationFor(restored, fixture.paths[1].id), 'Explanation 1');
    assert.equal(explanationFor(restored, fixture.paths[2].id), null);
    assert.equal(explanationFor(restored, null), 'Comparison');
});

test('LLM request preserves selected route scope and all-route boundaries', () => {
    const one = explanationInput(fixture, fixture.paths[1]);
    assert.deepEqual(one.paths, [fixture.paths[1]]);
    assert.deepEqual(one.nodes, fixture.paths[1].nodes);
    const all = explanationInput(fixture, null);
    assert.deepEqual(all.paths, fixture.paths);
    assert.deepEqual(all.edges, fixture.edges);
});

test('legacy explanation retains its original scope without invented metadata', () => {
    const legacy = readPathfinderExplanations({ llm_explanation: 'Old narrative', explanation_path_id: 'old-route' });
    assert.equal(explanationFor(legacy, 'old-route'), 'Old narrative');
    assert.equal(explanationFor(legacy, null), null);
    assert.equal(legacy[0].privacy_mode, null);
    assert.equal(legacy[0].generated_at, null);
});
