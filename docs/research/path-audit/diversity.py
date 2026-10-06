"""Bounded semantic-review candidates from exact snapshot edges; no graph writes."""
import json
from collections import Counter
import networkx as nx
from audit import OUT,write

data=json.loads((OUT/'current-graph.json').read_text(encoding='utf-8'))
inv=json.loads((OUT/'saved-inventory.json').read_text(encoding='utf-8'))
entry=next(x for x in inv if x['file'].endswith('1774676625062.json'))
s,t=entry['source']['id'],entry['target']['id']
nodes={n['id']:n for n in data['nodes']}
g=nx.Graph()
for e in data['edges']:
    try: w=float(e['properties'].get('weight',1))
    except (ValueError,TypeError): continue
    a,b=e['source'],e['target']
    if not g.has_edge(a,b) or w>g[a][b]['weight']: g.add_edge(a,b,weight=w,record=e)
distance=nx.single_source_shortest_path_length(g,s,cutoff=6)
paths=[]
def walk(path):
    u=path[-1]
    if u==s:
        p=path[::-1]
        edges=[g[a][b]['record'] for a,b in zip(p,p[1:])]
        paths.append({'nodes':[nodes[n] for n in p], 'edges':edges, 'minimum_weight':min(float(e['properties'].get('weight',1)) for e in edges)})
        return
    for v in g[u]:
        if v not in path and len(path)+distance.get(v,999)<=6: walk(path+[v])
walk([t])
write('canonical-six-hop-routes.json',paths)
print('unique simple routes <=6:',len(paths))
for alpha in [0.8,0.7,0.695,0.65,0.621,0.6,0.4]: print(alpha,sum(p['minimum_weight']>=alpha for p in paths))
for p in paths:
    print(p['minimum_weight'],' → '.join(n['name'] or n['filename'] or '/'.join(n['labels']) for n in p['nodes']))
