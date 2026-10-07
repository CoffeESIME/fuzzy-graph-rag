"""Run unchanged Pathfinder Cypher read-only and preserve individual routes.
Unlike the API's union response, this retains each record's totalCost and order.
"""
import ast
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from dotenv import dotenv_values
from neo4j import GraphDatabase
from audit import OUT, ROOT, write

def queries():
    tree = ast.parse((ROOT/'backend/app/routers/analysis.py').read_text(encoding='utf-8-sig'))
    fn = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='pathfind')
    strings = []
    for n in ast.walk(fn):
        if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='cypher' for t in n.targets):
            strings.append(eval(compile(ast.Expression(n.value), '<repository query>', 'eval'), {'k':3}))
    return {'lateral':next(s for s in strings if 'hubCost' in s), 'direct':next(s for s in strings if 'REDUCE' in s and 'hubCost' not in s), 'filtered':next(s for s in strings if 'WHERE ALL' in s), 'topological':next(s for s in strings if 'allShortestPaths' in s)}

if __name__=='__main__':
    inventory=json.loads((OUT/'saved-inventory.json').read_text(encoding='utf-8'))
    # Exact endpoint IDs from saved evidence, not guessed labels.
    prefixes=['pathfinder_libre_albedr_o_y_responsabilidad_to_laberinto_sin_salida_1774676625062','serendipity_path_1773992550430','pathfinder_ciclos_temporales_y_naturales_to_l_gica_difusa_1772951118546','pathfinder_inmortalidad_to_automatizaci_n_y_control_de_sistemas_1774502971188']
    cfg=dotenv_values(ROOT/'backend/.env.development')
    driver=GraphDatabase.driver('bolt://localhost:7687',auth=(cfg['NEO4J_USER'],cfg['NEO4J_PASSWORD']))
    results=[]
    for prefix in prefixes:
        entry=next(x for x in inventory if x['file'].startswith(prefix))
        for mode,alpha in [('topological',0),('direct',0),('lateral',0.85),('filtered',0.8),('filtered',0.6),('filtered',0.4)]:
            result={'candidate':prefix,'source':entry['source'],'target':entry['target'],'mode':mode,'threshold':alpha,'k':3,'captured_at':datetime.now(timezone.utc).isoformat(),'query':queries()[mode]}
            start=time.monotonic()
            try:
                with driver.session(default_access_mode='READ') as s:
                    with s.begin_transaction(timeout=20) as tx:
                        records=list(tx.run(queries()[mode],source=entry['source']['id'],target=entry['target']['id'],threshold=alpha,topo_threshold=alpha))
                        result['routes']=[{'nodes':[{'id':n.element_id,'name':n.get('name') or n.get('filename') or n.get('title'),'labels':list(n.labels),'file_hash':n.get('file_hash')} for n in r['path_nodes']], 'edges':[{'id':e.element_id,'source':e.start_node.element_id,'target':e.end_node.element_id,'type':e.type,'properties':dict(e)} for e in r['path_rels']], 'cost':r['totalCost']} for r in records]
            except Exception as e:
                result['error']=type(e).__name__ + ': '+str(e)[:500]
            result['seconds']=round(time.monotonic()-start,2)
            results.append(result)
            write('live-pathfinder-probes.json',results)
            print(prefix,mode,alpha,'routes',len(result.get('routes',[])),result.get('error',''),result['seconds'],flush=True)
    driver.close()
