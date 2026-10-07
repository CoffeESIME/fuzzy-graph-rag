"""Capture actual explanation inputs locally, without sending them to an LLM.

Read-only Neo4j/MinIO/HTTP requests; private captures go in ignored data_dev/.
Run with the backend Poetry environment from the repository root.
"""
import ast
import json
import logging
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'backend'))
import boto3
import requests
from neo4j import GraphDatabase
from pydantic import BaseModel
from config.settings import get_settings

settings = get_settings()
out = ROOT / 'data_dev/path-llm-audit'
out.mkdir(parents=True, exist_ok=True)
endpoint = settings.MINIO_ENDPOINT
if not endpoint.startswith('http'):
    endpoint = ('https://' if settings.MINIO_SECURE else 'http://') + endpoint
client = boto3.client('s3', endpoint_url=endpoint,
                      aws_access_key_id=settings.MINIO_ACCESS_KEY,
                      aws_secret_access_key=settings.MINIO_SECRET_KEY)
sidecars, failures = {}, []

class ReadOnlyStorage:
    def get_object(self, **kwargs):
        try:
            response = client.get_object(**kwargs)
            if kwargs['Key'].endswith('.json'):
                import io
                raw = response['Body'].read()
                sidecars[kwargs['Key']] = json.loads(raw)
                response['Body'] = io.BytesIO(raw)
            return response
        except Exception as exc:
            failures.append({'key': kwargs['Key'], 'error': type(exc).__name__})
            raise

clients = ModuleType('shared.clients')
clients.get_minio_client = lambda: ReadOnlyStorage()
sys.modules['shared.clients'] = clients

captured = []
def intercept_post(url, **kwargs):
    captured.append(dict(url=url, **kwargs))
    return SimpleNamespace(status_code=200, json=lambda: {'choices': [{'message': {'content': 'LOCAL CAPTURE ONLY'}}]})

tree = ast.parse((ROOT/'backend/app/routers/analysis.py').read_text(encoding='utf-8-sig'))
definitions = [n for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef))
               and n.name in ('PathExplanationRequest', 'PathExplanationResponse', 'explain_analytical_path')]
for node in definitions:
    node.decorator_list = []
scope = dict(BaseModel=BaseModel, List=List, Dict=Dict, Any=Any, Optional=Optional,
             json=json, settings=settings, LLM_GATEWAY_URL=settings.LLM_GATEWAY_URL,
             requests=SimpleNamespace(post=intercept_post, exceptions=requests.exceptions),
             logger=logging.getLogger('capture'))
exec(compile(ast.Module(body=definitions, type_ignores=[]), 'explanation-handler', 'exec'), scope)

saved_file = ROOT/'backend/data/saved_paths/pathfinder_libre_albedr_o_y_responsabilidad_to_laberinto_sin_salida_1774676625062.json'
saved = json.loads(saved_file.read_text(encoding='utf-8-sig'))
live = requests.post('http://localhost:8000/analysis/pathfinder', json={
    'source_element_id': saved['source']['id'], 'target_element_id': saved['target']['id'],
    'mode': 'topological', 'k_paths': 3}, timeout=40).json()
cases = {
    'saved_legacy_ui': dict(nodes=saved['nodes'], edges=[{'source': e['source'], 'target': e['target']} for e in saved['edges']]),
    'live_v2': {key: live.get(key, []) for key in ('nodes', 'edges', 'paths')}
}

def leaves(obj, prefix=''):
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield from leaves(value, f'{prefix}.{key}' if prefix else key)
    elif isinstance(obj, str) and obj:
        yield prefix, obj

summary = {}
for name, payload in cases.items():
    sidecars.clear(); failures.clear(); captured.clear()
    req = scope['PathExplanationRequest'](tool_name='pathfinder', **payload)
    response = scope['explain_analytical_path'](req)
    if not captured:
        raise RuntimeError(response.explanation)
    call = captured[0]
    messages = json.loads(call['data']['messages'])
    prompt = messages[-1]['content']
    details = []
    for key, doc in sidecars.items():
        fields = []
        for field, value in leaves(doc):
            if (len(value) > 80 and not any(part in field for part in ['embedding', 'vector', 'base64'])):
                fields.append({'field': field, 'chars': len(value), 'full_value_in_prompt': value in prompt,
                               'first_80_chars_in_prompt': value[:80] in prompt})
        details.append({'key': key, 'top_level_keys': list(doc), 'fields': fields})
    summary[name] = {'node_count': len(payload['nodes']), 'edge_count': len(payload['edges']),
                     'route_count': len(payload.get('paths', [])),
                     'prompt_chars': sum(len(m['content']) for m in messages),
                     'file_contexts': prompt.count("Archivo '"), 'sidecars': details,
                     'storage_failures': list(failures),
                     'edge_reasoning_in_input': sum(bool(e.get('reasoning')) for e in payload['edges'])}
    (out/f'{name}.json').write_text(json.dumps({'input': payload, 'gateway_request': call}, ensure_ascii=False, indent=2), encoding='utf-8')

with GraphDatabase.driver(settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)) as driver:
    with driver.session(default_access_mode='READ') as session:
        summary['node_context_omitted'] = session.run('''MATCH (n) WHERE elementId(n) IN $ids
            RETURN coalesce(n.name, n.filename) AS name, keys(n) AS stored_fields,
                   size(coalesce(n.definition, '')) AS definition_chars,
                   size(coalesce(n.description, '')) AS description_chars''', ids=[n['id'] for n in live.get('nodes', [])]).data()
summary['gateway_models'] = requests.get(settings.LLM_GATEWAY_URL+'/v1/models', timeout=5).json()
(out/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=True, indent=2))
