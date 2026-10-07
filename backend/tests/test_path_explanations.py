"""Explanation pipeline tests. Generation/storage are controlled, not semantic evals."""
import ast
import copy
import io
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from typing import Any, Dict, List, Optional
import unittest
from unittest.mock import Mock, patch
from pydantic import BaseModel

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from shared.path_explanation import LEGACY_ROUTE_ID, PATH_EXPLANATION_PROMPT_VERSION, ROUTE_TEMPLATE, SYSTEM_PROMPT, validate_explanation
CASES = json.loads((BACKEND/'tests/fixtures/path_explanation_cases.json').read_text(encoding='utf-8'))['cases']


def fixture_storage(cases):
    sidecars = {key: value for case in cases for key, value in case['sidecars'].items()}
    def get_object(**kwargs):
        key = kwargs['Key'].split('/')[-1].removesuffix('.json')
        if key not in sidecars:
            raise FileNotFoundError(key)
        return {'Body': io.BytesIO(json.dumps(sidecars[key]).encode('utf-8'))}
    module = ModuleType('shared.clients')
    module.get_minio_client = lambda: SimpleNamespace(get_object=get_object)
    return module


def load_handler(post, logger=None):
    tree = ast.parse((BACKEND/'app/routers/analysis.py').read_text(encoding='utf-8-sig'))
    definitions = [n for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in ('PathExplanationRequest', 'PathExplanationResponse', 'explain_analytical_path')]
    for node in definitions:
        node.decorator_list = []
    scope = dict(BaseModel=BaseModel, List=List, Dict=Dict, Any=Any, Optional=Optional,
                 json=json, settings=SimpleNamespace(), LLM_GATEWAY_URL='http://localhost:8765',
                 requests=SimpleNamespace(post=post, exceptions=SimpleNamespace(Timeout=TimeoutError)), logger=logger or Mock())
    exec(compile(ast.Module(body=definitions, type_ignores=[]), 'explanation-handler', 'exec'), scope)
    return scope


def valid_analysis(route):
    """Structural double; it does not demonstrate model quality."""
    analysis = copy.deepcopy(ROUTE_TEMPLATE)
    analysis['ruta_id'] = route['id']
    analysis['evaluacion_general']['calidad'] = 'insuficiente'
    analysis['pasos'] = []
    for edge in route['edges']:
        step = copy.deepcopy(ROUTE_TEMPLATE['pasos'][0])
        step.update(desde=edge.get('traversal_source') or edge['source'], hacia=edge.get('traversal_target') or edge['target'],
                    relacion_grafo=edge.get('rel_type'), peso=edge.get('weight'), reasoning_registrado=edge.get('reasoning'),
                    evidencia_fuentes=[], grado_soporte='insuficiente')
        analysis['pasos'].append(step)
    return analysis


class ExplanationTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.route = CASES[0]['route']
        self.answer = json.dumps({'analisis_serendipia': valid_analysis(self.route)})
        self.finish_reason = 'stop'
        def post(url, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(status_code=200, json=lambda: {'model': 'test-model', 'usage': {'prompt_tokens': 123},
                'choices': [{'finish_reason': self.finish_reason, 'message': {'content': self.answer}}]})
        self.logger = Mock()
        self.scope = load_handler(post, self.logger)
        storage = patch.dict(sys.modules, {'shared.clients': fixture_storage(CASES)})
        storage.start()
        self.addCleanup(storage.stop)

    def request(self, routes=None, **kwargs):
        routes = routes or [self.route]
        return self.scope['PathExplanationRequest'](tool_name='pathfinder', nodes=[n for r in routes for n in r['nodes']],
            edges=[e for r in routes for e in r['edges']], paths=routes, **kwargs)

    def run_handler(self, req=None):
        return self.scope['explain_analytical_path'](req or self.request())

    def test_string_json_contract_privacy_temperature_and_logging(self):
        for private, seconds in ((True, 900), (False, 60)):
            response = self.run_handler(self.request(privacy_mode=private))
            self.assertEqual(response.status, 'success')
            self.assertIsInstance(response.explanation, str)
            self.assertEqual(json.loads(response.explanation)['analisis_serendipia']['ruta_id'], self.route['id'])
            call = self.calls[-1]
            self.assertEqual(call['timeout'], (10, seconds))
            self.assertEqual(call['data']['privacy_mode'], 'strict' if private else 'flexible')
            self.assertEqual(call['data']['temperature'], 0.35)
        self.assertTrue(any(PATH_EXPLANATION_PROMPT_VERSION in c.args for c in self.logger.info.call_args_list))
        self.assertTrue(any('test-model' in c.args and 'stop' in c.args for c in self.logger.info.call_args_list))
        self.logger.debug.assert_called_with('Path explanation usage=%s', {'prompt_tokens': 123})

    def test_four_controlled_inputs_preserve_evidence_and_separate_routes(self):
        routes = [case['route'] for case in CASES]
        self.answer = json.dumps({'analisis_serendipia': [valid_analysis(r) for r in routes]})
        response = self.run_handler(self.request(routes))
        self.assertEqual(response.status, 'success')
        self.assertEqual(len(json.loads(response.explanation)['analisis_serendipia']), 4)
        system, user = json.loads(self.calls[-1]['data']['messages'])
        self.assertEqual(system['content'], SYSTEM_PROMPT)
        for route in routes:
            self.assertIn(route['id'], user['content'])
            for edge in route['edges']:
                if edge['reasoning']:
                    self.assertIn(edge['reasoning'], user['content'])
        self.assertIn('Archivo source_id=analogia-1', user['content'])
        self.assertIn('La voz de Khayyam cuestiona', user['content'])
        expected = user['content'].split('Extremos EXACTOS de los pasos, en orden, que debes conservar en el JSON de salida:\n')[1].split('\n', 1)[0]
        self.assertEqual(json.loads(expected)[0]['pasos'][0], {'desde': 'analogia-0', 'hacia': 'analogia-1'})
        schema = user['content'].split('opciones, elige una; repite pasos para cubrir todos los saltos de cada ruta):\n')[1].split('\n', 1)[0]
        self.assertEqual([r['ruta_id'] for r in json.loads(schema)['analisis_serendipia']], [r['id'] for r in routes])
        route = CASES[-1]['route']
        self.answer = json.dumps({'analisis_serendipia': valid_analysis(route)})
        self.run_handler(self.request([route]))
        self.assertIn('No se recuperó contenido', json.loads(self.calls[-1]['data']['messages'])[-1]['content'])

    def test_rejects_prose_fences_empty_truncated_and_incomplete_json(self):
        for content in ('Interpretation', '```json\n{}\n```', '', None, '{', '{}', '{"analisis_serendipia": []}'):
            with self.subTest(content=content):
                self.answer = content
                self.assertEqual(self.run_handler().status, 'error')
        self.answer = json.dumps({'analisis_serendipia': valid_analysis(self.route)})
        self.finish_reason = 'length'
        self.assertEqual(self.run_handler().status, 'error')

    def test_rejects_missing_routes_mixed_steps_and_unknown_sources(self):
        routes = [case['route'] for case in CASES[:2]]
        analyses = [valid_analysis(r) for r in routes]
        invalid = [analyses[:1]]
        changed = copy.deepcopy(analyses); changed[0]['ruta_id'] = 'invented'; invalid.append(changed)
        changed = copy.deepcopy(analyses); changed[0]['pasos'].reverse(); invalid.append(changed)
        changed = copy.deepcopy(analyses); changed[0]['pasos'].pop(); invalid.append(changed)
        changed = copy.deepcopy(analyses); changed[0]['pasos'][0] = changed[1]['pasos'][0]; invalid.append(changed)
        for field, value in [('peso', 0.99), ('relacion_grafo', 'CAUSES'), ('reasoning_registrado', 'Invented evidence')]:
            changed = copy.deepcopy(analyses); changed[0]['pasos'][0][field] = value; invalid.append(changed)
        changed = copy.deepcopy(analyses)
        changed[0]['pasos'][0]['evidencia_fuentes'] = [{'source_id': 'invented', 'fragmento_o_descripcion': 'x', 'tipo_evidencia': 'texto'}]
        invalid.append(changed)
        for response in invalid:
            with self.subTest(response=response), self.assertRaises(ValueError):
                validate_explanation(json.dumps({'analisis_serendipia': response}), [r['id'] for r in routes], routes)

    def test_legacy_and_serendipity_without_inferred_routes(self):
        for tool in ('serendipity', 'saved_path'):
            route = dict(self.route, id=LEGACY_ROUTE_ID)
            self.answer = json.dumps({'analisis_serendipia': valid_analysis(route)})
            req = self.scope['PathExplanationRequest'](tool_name=tool, nodes=route['nodes'], edges=route['edges'])
            self.assertEqual(self.run_handler(req).status, 'success')
            prompt = json.loads(self.calls[-1]['data']['messages'])[-1]['content']
            self.assertIn('no una nueva ruta inferida', prompt)
            self.assertIn(route['edges'][0]['reasoning'], prompt)

    def test_context_labels_distinguish_summaries_from_literal_content(self):
        cases = copy.deepcopy(CASES[:1])
        sidecar = next(iter(cases[0]['sidecars'].values()))
        sidecar['data_layers'] = {'analysis_json': {'graph_core': {'summary': 'RESUMEN CONTROLADO'},
                                                  'audio_specifics': {'lyrics_summary': 'RESUMEN DE LETRA'}}}
        with patch.dict(sys.modules, {'shared.clients': fixture_storage(cases)}):
            self.run_handler()
        prompt = json.loads(self.calls[-1]['data']['messages'])[-1]['content']
        self.assertIn('Resumen previo (no cita literal): RESUMEN CONTROLADO', prompt)
        self.assertIn('Resumen previo de letra (no letra literal): RESUMEN DE LETRA', prompt)

    def test_empty_request_never_calls_llm(self):
        req = self.scope['PathExplanationRequest'](tool_name='pathfinder', nodes=[], edges=[])
        self.assertEqual(self.run_handler(req).status, 'error')
        self.assertEqual(self.calls, [])


if __name__ == '__main__':
    unittest.main()
