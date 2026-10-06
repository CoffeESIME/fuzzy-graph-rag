"""Fetch existing asset previews; no LLM calls, ingestion, or graph writes."""
import json
import requests
from audit import OUT, write

if __name__=='__main__':
    probes=json.loads((OUT/'live-pathfinder-probes.json').read_text(encoding='utf-8'))
    assets={n['id']:n for p in probes for r in p.get('routes',[]) for n in r['nodes'] if 'DigitalAsset' in n['labels']}
    previous=json.loads((OUT/'source-previews.json').read_text(encoding='utf-8')) if (OUT/'source-previews.json').exists() else []
    cached={x['id']:x for x in previous if 'error' not in x}
    out=list(cached.values())
    for id,n in assets.items():
        if id in cached: continue
        try:
            response=requests.get(f'http://localhost:8000/api/explore/asset-preview/{id}',timeout=15)
            response.raise_for_status()
            data=response.json()
            url=data.pop('download_url',None)
            data['file_hash']=n.get('file_hash')
            # Verify original availability without storing expiring signed URLs.
            if url:
                with requests.get(url,timeout=10,stream=True) as original_check:
                    data['original_http_status']=original_check.status_code
                if str(data.get('mime_type','')).startswith('text/'):
                    original=requests.get(url,timeout=10)
                    if original.ok:
                        data['original_text']=original.content.decode('utf-8',errors='replace')
            out.append(data)
            print(n['name'], str(data.get('content',''))[:180].replace('\n',' '),flush=True)
        except Exception as e:
            out.append({'id':id,'name':n['name'],'error':type(e).__name__})
        write('source-previews.json',out)
