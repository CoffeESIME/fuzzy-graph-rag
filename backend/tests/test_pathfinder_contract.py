import ast
import importlib.util
import json
from pathlib import Path
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('pathfinder_contract', ROOT/'backend/app/pathfinder_contract.py')
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)


class Node(dict):
    def __init__(self, id, label=None):
        super().__init__(name=label or id)
        self.element_id = id
        self.labels = {'Concept'}


class Edge(dict):
    def __init__(self, id, source, target, weight):
        super().__init__(weight=weight, reasoning='source evidence', source='interactive_latent_explorer')
        self.element_id, self.start_node, self.end_node, self.type = id, source, target, 'EVOKES'


class PathfinderContractTests(unittest.TestCase):
    def setUp(self):
        self.a, self.b, self.c, self.d = [Node(x) for x in 'abcd']
        self.records = [
            {'path_nodes': [self.a,self.b,self.d], 'path_rels': [Edge('ab',self.b,self.a,0.7999),Edge('bd',self.b,self.d,0.7)], 'totalCost':0.5001},
            {'path_nodes': [self.a,self.c,self.d], 'path_rels': [Edge('ac',self.a,self.c,0.6),Edge('cd',self.c,self.d,0.8)], 'totalCost':0.6},
            {'path_nodes': [self.a,self.b,self.d], 'path_rels': [Edge('ab2',self.b,self.a,'0.71'),Edge('bd',self.b,self.d,0.7)], 'totalCost':0.59},
        ]
        self.request = contract.PathfinderRequest(source_element_id='a',target_element_id='d',mode='lateral',threshold=0.82,k_paths=3)

    def test_order_identity_duplicates_and_derived_union(self):
        result = contract.build_pathfinder_response(self.records,self.request)
        self.assertEqual((result.raw_result_count,result.unique_route_count),(3,2))
        self.assertEqual([[n.id for n in p.nodes] for p in result.paths],[['a','b','d'],['a','c','d'],['a','b','d']])
        self.assertEqual([[e.id for e in p.edges] for p in result.paths],[['ab','bd'],['ac','cd'],['ab2','bd']])
        edge = result.paths[0].edges[0]
        self.assertEqual((edge.source,edge.target,edge.traversal_source,edge.traversal_target),('b','a','a','b'))
        self.assertEqual(edge.weight,0.7999)
        self.assertEqual(result.paths[2].edges[0].raw_weight,'0.71')
        self.assertEqual(result.paths[0].metrics.cost,0.5001)
        self.assertEqual(result.paths[0].parameters.lateral_threshold,0.82)
        self.assertEqual(result.paths[2].duplicate_of,result.paths[0].id)
        self.assertEqual({n.id for n in result.nodes},{n.id for p in result.paths for n in p.nodes})
        self.assertEqual({e.id for e in result.edges},{e.id for p in result.paths for e in p.edges})
        self.assertEqual(result.model_dump(),contract.PathfinderResponse.model_validate_json(result.model_dump_json()).model_dump())

    def test_cycles_and_invalid_weights_are_not_silently_dropped(self):
        records=[{'path_nodes':[self.a,self.b,self.a,self.d], 'path_rels':[Edge('1',self.a,self.b,'1.01.0'),Edge('2',self.b,self.a,None),Edge('3',self.a,self.d,0.621)],'totalCost':None}]
        p=contract.build_pathfinder_response(records,self.request).paths[0]
        self.assertEqual([n.id for n in p.nodes],['a','b','a','d'])
        self.assertEqual(p.hop_count,3)
        self.assertEqual(p.metrics.missing_weight_count,2)
        self.assertEqual(p.metrics.min_weight,0.621)
        self.assertEqual(p.edges[0].raw_weight,'1.01.0')
        self.assertIsNone(p.metrics.cost)

    def test_handler_returns_routes_before_union_serialization(self):
        # Execute the actual handler with a read-only driver double, without
        # importing application startup / credentials / other external clients.
        module=ast.parse((ROOT/'backend/app/routers/analysis.py').read_text(encoding='utf-8-sig'))
        handler=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='pathfind')
        handler.decorator_list=[]
        records=self.records
        class Session:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def begin_transaction(self,**kwargs): return self
            def run(self,query,**kwargs): return records
        scope={'PathfinderRequest':contract.PathfinderRequest,'PathfinderResponse':contract.PathfinderResponse,'build_pathfinder_response':contract.build_pathfinder_response,'get_neo4j_driver':lambda:SimpleNamespace(session=Session),'_resolve_minio_url':None,'logger':SimpleNamespace(error=lambda msg:None)}
        exec(compile(ast.Module(body=[handler],type_ignores=[]),'handler','exec'),scope)
        result=scope['pathfind'](self.request)
        self.assertEqual(result.status,'success')
        self.assertEqual(len(result.paths),3)
        self.assertEqual(result.paths[1].rank,2)

    def test_empty_response_and_parameter_snapshot(self):
        req=contract.PathfinderRequest(source_element_id='a',target_element_id='d',mode='topological',topo_threshold=0.695,k_paths=100)
        result=contract.build_pathfinder_response([],req)
        self.assertEqual(result.status,'not_found')
        self.assertEqual(result.parameters.k_paths,10)
        self.assertEqual(result.parameters.requested_k_paths,100)
        self.assertEqual(result.parameters.topological_threshold,0.695)
        self.assertIsNone(result.parameters.lateral_threshold)

if __name__=='__main__': unittest.main()
