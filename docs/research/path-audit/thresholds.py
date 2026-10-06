"""Independent alpha-cut checks on a read-only current graph snapshot.
Not an API result: exact edges are retained, simple node paths only, max 8 hops.
"""
import json
import itertools
import networkx as nx
from audit import OUT,write

g=json.loads((OUT/'current-graph.json').read_text(encoding='utf-8'))
inv=json.loads((OUT/'saved-inventory.json').read_text(encoding='utf-8'))
nodes={n['id']:n for n in g['nodes']}
prefixes=['pathfinder_libre_albedr_o_y_responsabilidad_to_laberinto_sin_salida_1774676625062','serendipity_path_1773992550430','pathfinder_ciclos_temporales_y_naturales_to_l_gica_difusa_1772951118546','pathfinder_inmortalidad_to_automatizaci_n_y_control_de_sistemas_1774502971188']
out=[]
for prefix in prefixes:
    entry=next(x for x in inv if x['file'].startswith(prefix))
    for alpha in [0.9,0.8,0.7,0.695,0.65,0.621,0.6,0.4]:
        graph=nx.Graph()
        graph.add_nodes_from(nodes)
        for e in g['edges']:
            w=e['properties'].get('weight',1.0)
            if w is None: w=1.0
            try:
                w=float(w)
            except (TypeError,ValueError):
                # Neo4j toFloat(invalid string) yields null; alpha filter excludes it.
                continue
            if w>=alpha:
                a,b=e['source'],e['target']
                if not graph.has_edge(a,b) or w>graph[a][b]['weight']:
                    graph.add_edge(a,b,weight=w,record=e)
        s,t=entry['source']['id'],entry['target']['id']
        r={'candidate':prefix,'alpha':alpha,'method':'snapshot alpha-cut, undirected shortest simple node paths, <=8 hops; parallel edges represented by strongest qualifying edge','routes':[]}
        try:
            length=nx.shortest_path_length(graph,s,t)
            r['shortest_hops']=length
            if length<=8:
                paths=list(itertools.islice(nx.all_shortest_paths(graph,s,t),101))
                r['number_shortest_node_paths_up_to_101']=len(paths)
                for p in paths[:10]:
                    r['routes'].append({'nodes':[nodes[n] for n in p],'edges':[graph[a][b]['record'] for a,b in zip(p,p[1:])]})
        except nx.NetworkXNoPath:
            r['shortest_hops']=None
        out.append(r)
        print(prefix,alpha,r.get('shortest_hops'),r.get('number_shortest_node_paths_up_to_101',0))
write('snapshot-thresholds.json',out)

# Human-readable inventory: node arrays in Pathfinder are unions, NOT sequences.
lines=['# Inventario de caminos guardados','', 'Los 50 archivos originales se leyeron sin modificarlos. Las rutas Serendipity son secuencias; los nodos y aristas Pathfinder son una unión de rutas. No se interpreta el orden de esa unión como un camino. Los saltos Pathfinder son el máximo declarado, no el total de aristas. `saved-inventory.json` conserva IDs, hashes SHA-256, nodos, pesos, tipos, parámetros, fechas y comprobaciones contra el grafo actual.', '']
for e in inv:
    label=lambda n:n.get('label',n.get('name','?'))
    lines += ['## '+e['file'],'',f"- Extremos: {label(e['source'])} ↔ {label(e['target'])}.",f"- Modo: {e['mode']}; saltos declarados: {e['hops']}; fecha: {e['timestamp']}.",f"- Parámetros conservados: `{json.dumps(e['parameters'],ensure_ascii=False)}`. Puntuación agregada: no conservada.",'- Otros archivos con extremos idénticos: '+(', '.join(e['same_endpoint_files']) or 'ninguno')+'.','- '+('Secuencia: '+' → '.join(label(n) for n in e['nodes']) if e['kind']=='serendipity' else 'Nodos de la unión (no secuencia): '+'; '.join(label(n) for n in e['nodes']))+'.','', '| Origen de arista | Destino de arista | Tipo guardado | Peso guardado | Comprobación actual |','|---|---|---|---|---|']
    lookup={n['id']:label(n) for n in e['nodes']}
    for c in e['current_edge_check']:
        edge=c['saved_edge']
        matches=c['current_matches']
        check=' / '.join(f"{x['type']} ({x['weight']})" for x in matches) or 'Sin coincidencia exacta actual'
        lines.append(f"| {lookup.get(edge['source'],edge['source'])} | {lookup.get(edge['target'],edge['target'])} | {edge.get('rel_type') or 'No guardado'} | {edge.get('weight')} | {check} |")
    lines += ['','Activos: '+ '; '.join(label(n)+' (`'+str(n.get('file_hash'))+'`)' for n in e['nodes'] if n.get('file_hash')),'']
(OUT/'INVENTORY.md').write_text('\n'.join(lines),encoding='utf-8')
