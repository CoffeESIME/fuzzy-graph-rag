import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';
import vm from 'node:vm';

const base = resolve(dirname(fileURLToPath(import.meta.url)), '../src/components/graph');
const cache = new Map();
function load(name) {
    if (cache.has(name)) return cache.get(name);
    const module = { exports: {} };
    const source = ts.transpileModule(readFileSync(resolve(base, name + '.ts'), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
    vm.runInNewContext(source, { module, exports: module.exports, require: id => load(id.replace('./', '')) });
    cache.set(name, module.exports); return module.exports;
}
const { graphSvg } = load('figureExport');
const { edgeVisual, visualNode } = load('visualSystem');
const nodes = [{ id: '4:uuid:1', position: { x: -90, y: -20 }, data: { label: '<script>& "Corpus"', nodeType: 'Concept' } }, { id:'4:uuid:2',position:{x:250,y:0},data:{raw:{name:'Documento',type:'Asset'}}}];
const edges = [{id:'e',source:nodes[0].id,target:nodes[1].id,markerEnd:'arrow',data:{relation:'FUZZY',weight:0}}];
const options = {title:'Figura <&>',labels:true,weights:true,background:'#fff',surface:'#fff',text:'#111',line:'#555'};
test('SVG preserves topology, zero weights, semantic type and escaped corpus text', () => {
    const before = JSON.stringify({nodes,edges}); const svg = graphSvg(nodes,edges,options);
    assert.ok(svg.includes('DigitalAsset')); assert.ok(svg.includes('FUZZY · 0'));
    assert.ok(svg.includes('&lt;script&gt;&amp;')); assert.ok(!svg.includes('<script>'));
    assert.ok(svg.includes('marker-end="url(#arrow)"')); assert.ok(svg.includes('stroke-dasharray="7 4"'));
    assert.equal(JSON.stringify({nodes,edges}),before);
});
test('labels and weights can be independently excluded; transparency omits only the canvas background', () => {
    const svg=graphSvg(nodes,edges,{...options,labels:false,weights:false,transparent:true});
    assert.ok(!svg.includes('FUZZY · 0')); assert.ok(!svg.includes('<rect width="100%"'));
    assert.ok(svg.includes('DigitalAsset')); assert.ok(svg.includes('<title>&lt;script&gt;'));
});
test('unknown types and missing weights are not fabricated', () => {
    assert.equal(visualNode({id:'x',data:{nodeType:'CustomEntity',label:'X'}}).type,'CustomEntity');
    assert.equal(edgeVisual({data:{relation:'RELATED'}}).weight,undefined);
    assert.equal(edgeVisual({data:{weight:0}}).weight,0);
});
