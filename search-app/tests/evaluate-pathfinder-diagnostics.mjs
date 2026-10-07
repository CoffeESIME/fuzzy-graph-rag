// Reproduce observations from the audited corpus; no new search, pruning or writes to source evidence.
// Run: node search-app/tests/evaluate-pathfinder-diagnostics.mjs
import { readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import ts from 'typescript';
const base = new URL('../../docs/research/path-audit/', import.meta.url);
const inputs = {};
async function read(name) {
    const bytes = await readFile(new URL(name, base));
    inputs[name] = createHash('sha256').update(bytes).digest('hex');
    return JSON.parse(bytes);
}
const source = await readFile(new URL('../src/lib/pathfinderDiagnostics.ts', import.meta.url), 'utf8');
const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
const { comparePathfinderPaths: compare } = await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`);
const graph = await read('current-graph.json');
const canonical = await read('canonical-six-hop-routes.json');
const probes = await read('live-pathfinder-probes.json');
function adapt(routes, prefix, mode) {
    return routes.map((p, i) => ({
        id: `${prefix}-${i+1}`, rank: i+1, mode,
        nodes: p.nodes.map(n => ({ ...n, label: n.name || n.filename || n.id, node_type: n.labels.includes('DigitalAsset') ? 'DigitalAsset' : n.labels.includes('Concept') ? 'Concept' : n.labels[0] })),
        edges: p.edges.map(e => ({ ...e, rel_type: e.type })),
    }));
}
const sets = [{ name: 'canonical-six-hop-snapshot', origin: 'Previously enumerated simple snapshot paths, not a native ranking; one edge per node pair was retained by the audit.', paths: adapt(canonical, 'C', 'snapshot') }];
for (const [i, probe] of probes.entries()) {
    const label = n => n.label || n.name || graph.nodes.find(g => g.id === n.id)?.name || n.id;
    sets.push({ name: `${label(probe.source)} ↔ ${label(probe.target)} / ${probe.mode} / ${probe.threshold}`, origin: 'Audited native query records; original order retained.', error: probe.error ?? null, capturedAt: probe.captured_at, paths: adapt(probe.routes ?? [], `Q${i+1}`, probe.mode) });
}
const results = sets.map(({ paths, ...meta }) => ({ ...meta,
    routes: paths.map(p => ({ id: p.id, rank: p.rank, mode: p.mode, labels: p.nodes.map(n => n.label) })),
    diagnostics: compare(paths),
}));
const output = { corpusCapturedAt: graph.captured_at, evidenceSha256: inputs, scope: 'Diagnostics on retained audited candidates only. No live regeneration or community computation; no ranking, filtering or thresholds.', results };
await writeFile(new URL('pathfinder-diagnostics.json', base), JSON.stringify(output, null, 2) + '\n');
for (const r of results) console.log(r.name, r.routes.length, 'routes', r.diagnostics.pairs.length, 'comparisons', r.error ? '(audit timeout/error)' : '');
for (const r of results[0].routes) console.log(r.id, r.labels.join(' → '));
