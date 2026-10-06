"""Read-only corpus audit. Writes evidence here; never changes graph or saved paths.
Run from repository root: python docs/research/path-audit/audit.py
Requires locally installed neo4j and python-dotenv.
"""
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from dotenv import dotenv_values
from neo4j import GraphDatabase, Query

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]

def write(name, obj):
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding='utf-8')

def snapshot():
    cfg = dotenv_values(ROOT / 'backend/.env.development')
    driver = GraphDatabase.driver('bolt://localhost:7687', auth=(cfg['NEO4J_USER'], cfg['NEO4J_PASSWORD']))
    with driver.session(default_access_mode='READ') as session:
        with session.begin_transaction(timeout=40) as tx:
            nodes = tx.run('MATCH (n) RETURN elementId(n) AS id, labels(n) AS labels, n.name AS name, n.filename AS filename, n.file_hash AS file_hash, n.mime_type AS mime_type, n.description AS description').data()
            edges = tx.run('MATCH (a)-[r]->(b) RETURN elementId(r) AS id, elementId(a) AS source, elementId(b) AS target, type(r) AS type, properties(r) AS properties').data()
    driver.close()
    graph = {'captured_at': datetime.now(timezone.utc).isoformat(), 'nodes': nodes, 'edges': edges}
    write('current-graph.json', graph)
    return graph

def inventory(graph):
    entries = []
    live = {(e['source'], e['target'], e['type']): e for e in graph['edges']}
    for f in sorted((ROOT / 'backend/data/saved_paths').glob('*.json')):
        data = json.loads(f.read_text(encoding='utf-8'))
        ser = 'path' in data
        nodes = data.get('path', data.get('nodes', []))
        source = data.get('source', nodes[0] if ser else {})
        target = data.get('target', nodes[-1] if ser else {})
        edges = data.get('edges', [{'source': a['id'], 'target': b['id'], 'weight': b.get('weight'), 'rel_type': None} for a,b in zip(nodes,nodes[1:])])
        checks = []
        for e in edges:
            matches = [x for x in graph['edges'] if {x['source'],x['target']} == {e['source'], e['target']} and (not e.get('rel_type') or x['type']==e['rel_type'])]
            checks.append({'saved_edge': e, 'current_matches': [{'id':x['id'], 'type':x['type'], 'weight':x['properties'].get('weight')} for x in matches]})
        entries.append({'file':f.name, 'sha256':hashlib.sha256(f.read_bytes()).hexdigest(), 'kind':'serendipity' if ser else 'pathfinder', 'source':source, 'target':target, 'nodes':nodes, 'edges':edges, 'hops':len(nodes)-1 if ser else data.get('path_length'), 'mode':data.get('mode','serendipity'), 'parameters':data.get('options',{}), 'timestamp':data.get('generated_at',data.get('exported_at')), 'message':data.get('message'), 'aggregate_score':data.get('score'), 'current_edge_check':checks})
    groups = defaultdict(list)
    for e in entries:
        groups[tuple(sorted([e['source'].get('id',''),e['target'].get('id','')]))].append(e['file'])
    for e in entries:
        e['same_endpoint_files'] = [f for f in groups[tuple(sorted([e['source'].get('id',''),e['target'].get('id','')]))] if f != e['file']]
    write('saved-inventory.json', entries)
    print('Graph',len(graph['nodes']),len(graph['edges']),Counter(e['type'] for e in graph['edges']))
    print('Saved',len(entries),Counter(e['kind'] for e in entries))
    for e in entries:
        name=lambda n:n.get('label',n.get('name','?'))
        print(e['file'], e['mode'],e['hops'], ' | '.join(name(n) for n in e['nodes']), 'weights', [x.get('weight') for x in e['edges']])

if __name__ == '__main__':
    inventory(snapshot())
