"""Exercise the real explanation handler without database, storage or LLM calls."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
import unittest
from pydantic import BaseModel


class ExplanationTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse((Path(__file__).parents[1] / 'app/routers/analysis.py').read_text(encoding='utf-8-sig'))
        definitions = [n for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in ('PathExplanationRequest', 'PathExplanationResponse', 'explain_analytical_path')]
        for n in definitions:
            n.decorator_list = []
        self.calls = []
        def post(url, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(status_code=200, json=lambda: {'choices': [{'message': {'content': 'Interpretation'}}]})
        self.scope = dict(BaseModel=BaseModel, List=List, Dict=Dict, Any=Any, Optional=Optional, json=json, settings=SimpleNamespace(), LLM_GATEWAY_URL='http://test', requests=SimpleNamespace(post=post, exceptions=SimpleNamespace(Timeout=TimeoutError)), logger=SimpleNamespace(info=lambda *a, **kw: None, debug=lambda *a, **kw: None, error=lambda *a, **kw: None))
        exec(compile(ast.Module(body=definitions, type_ignores=[]), 'explanation-handler', 'exec'), self.scope)

    def test_private_timeout_and_explicit_route_boundaries(self):
        for private, seconds in ((True, 900), (False, 60)):
            req = self.scope['PathExplanationRequest'](tool_name='pathfinder', nodes=[{'id': 'a', 'label': 'A'}, {'id': 'b', 'label': 'B'}], edges=[{'source': 'a', 'target': 'b'}], paths=[{'id': 'route-1', 'nodes': ['a', 'b']}, {'id': 'route-2', 'nodes': ['a', 'c', 'b']}], privacy_mode=private)
            response = self.scope['explain_analytical_path'](req)
            self.assertEqual(response.status, 'success')
            call = self.calls[-1]
            self.assertEqual(call['timeout'], (10, seconds))
            self.assertEqual(call['data']['privacy_mode'], 'strict' if private else 'flexible')
            prompt = json.loads(call['data']['messages'])[-1]['content']
            self.assertIn('route-1', prompt)
            self.assertIn('route-2', prompt)
            self.assertIn('No inventes una única cadena combinando rutas', prompt)

    def test_empty_request_never_calls_llm(self):
        req = self.scope['PathExplanationRequest'](tool_name='pathfinder', nodes=[], edges=[])
        self.assertEqual(self.scope['explain_analytical_path'](req).status, 'error')
        self.assertEqual(self.calls, [])


if __name__ == '__main__':
    unittest.main()
