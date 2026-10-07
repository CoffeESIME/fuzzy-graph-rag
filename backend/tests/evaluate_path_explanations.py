"""Opt-in real LLM evaluation with synthetic evidence and the actual handler.

python backend/tests/evaluate_path_explanations.py --live [--private]
No graph writes or real corpus content. Outputs are saved for semantic review;
automated assertions check structure only, not the truth of the interpretation.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sys
from unittest.mock import patch

import requests
from test_path_explanations import CASES, fixture_storage, load_handler
from shared.path_explanation import PATH_EXPLANATION_PROMPT_VERSION


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--private', action='store_true')
    parser.add_argument('--case', choices=[c['case_id'] for c in CASES] + ['multiple'])
    args = parser.parse_args()
    if not args.live:
        parser.error('--live is required to call the configured gateway')
    logging.basicConfig(level=logging.INFO)
    groups = [(c['case_id'], [c]) for c in CASES] + [('multiple', CASES[:2])]
    if args.case:
        groups = [group for group in groups if group[0] == args.case]

    def evaluate(group):
        name, cases = group
        calls = []
        def post(url, **kwargs):
            response = requests.post(url, **kwargs)
            if response.status_code == 200:
                raw = response.json()
                calls.append({k: raw.get(k) for k in ('model', 'usage', 'choices')})
            return response
        scope = load_handler(post, logging.getLogger(name))
        from config.settings import get_settings
        scope['LLM_GATEWAY_URL'] = get_settings().LLM_GATEWAY_URL
        routes = [case['route'] for case in cases]
        req = scope['PathExplanationRequest'](tool_name='pathfinder', privacy_mode=args.private,
            paths=routes, nodes=[n for r in routes for n in r['nodes']], edges=[e for r in routes for e in r['edges']])
        response = scope['explain_analytical_path'](req)
        result = {'case': name, 'prompt_version': PATH_EXPLANATION_PROMPT_VERSION,
                  'privacy_mode': 'strict' if args.private else 'flexible',
                  'status': response.status, 'gateway_responses': calls,
                  'explanation': json.loads(response.explanation) if response.status == 'success' else response.explanation}
        print(name, response.status, flush=True)
        return result

    with patch.dict(sys.modules, {'shared.clients': fixture_storage(CASES)}):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(evaluate, groups))
    report = {'generated_at': datetime.now(timezone.utc).isoformat(),
              'notice': 'Synthetic sources, not historical quotations. Semantic conclusions require review.',
              'results': results}
    output = Path(__file__).resolve().parents[2]/'docs/research/path-llm-audit'
    output.mkdir(parents=True, exist_ok=True)
    name = 'v2-controlled-' + ('local' if args.private else 'cloud') + (('-' + args.case) if args.case else '') + '.json'
    (output/name).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(output/name)
    if any(r['status'] != 'success' for r in results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
