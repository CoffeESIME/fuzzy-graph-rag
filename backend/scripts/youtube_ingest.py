import json
import requests
from urllib.parse import urlparse, parse_qs

# Compatibilidad con youtube-transcript-api v0.6+ (API cambió)
# En v0.6+ se usa instancia: YouTubeTranscriptApi().fetch(video_id)
# En v0.5 se usaba clase: YouTubeTranscriptApi.get_transcript(video_id)
try:
    from youtube_transcript_api import YouTubeTranscriptApi
    _ytt_instance = YouTubeTranscriptApi()
    def get_transcript(video_id, languages=('es', 'en')):
        # v0.6+ retorna una lista de FetchedTranscript iterables
        for lang in languages:
            try:
                fetched = _ytt_instance.fetch(video_id, languages=[lang])
                return [{"text": s.text} for s in fetched]
            except Exception:
                continue
        raise RuntimeError(f"No se encontró transcripción para {video_id} en idiomas {languages}")
except Exception as import_err:
    raise ImportError(f"No se pudo importar youtube_transcript_api: {import_err}")

# ================= CONFIGURACIÓN =================
# Apuntamos a la API de ingestión de texto de GraphRAG
API_URL = 'http://localhost:8000/ingest/text'  
# Lista de videos
YOUTUBE_URLS = [
    "https://www.youtube.com/watch?v=qJZ1Ez28C-A",
    "https://www.youtube.com/watch?v=eLVAMG_3fLg",
    "https://www.youtube.com/watch?v=nmgFG7PUHfo",
    "https://www.youtube.com/watch?v=1sX2oL2N1Iw&list=PL5WVKrojml6mlMA2LNJ6Uh8yk5bTMMMmD&index=31&pp=iAQBsAgC",
    "https://www.youtube.com/watch?v=k1guGqSTYDg&list=PL5WVKrojml6mlMA2LNJ6Uh8yk5bTMMMmD&index=30&pp=iAQBsAgC",
    "https://www.youtube.com/watch?v=kwrDX5qkwvA&list=PL5WVKrojml6mlMA2LNJ6Uh8yk5bTMMMmD&index=13&pp=iAQBsAgC",
    "https://www.youtube.com/watch?v=oFIdIVngeYA&list=PL5WVKrojml6mlMA2LNJ6Uh8yk5bTMMMmD&index=9&pp=iAQBsAgC","https://www.youtube.com/watch?v=Zce-V0YVzeI&list=PL5WVKrojml6mlMA2LNJ6Uh8yk5bTMMMmD&index=4&pp=iAQBsAgC",
    "https://www.youtube.com/watch?v=DPh98ciWClI&list=PL5WVKrojml6mlMA2LNJ6Uh8yk5bTMMMmD&index=2&pp=iAQBsAgC",
    "https://www.youtube.com/watch?v=vpRd52dXHlQ&list=PL5WVKrojml6lJeDJzLHFQ1Tt-wbp-8D0Q&index=34&pp=iAQBsAgC",
    "https://www.youtube.com/watch?v=I_0GBWCKft8&list=PL5WVKrojml6lJeDJzLHFQ1Tt-wbp-8D0Q&index=33&pp=iAQBsAgC",
    "https://www.youtube.com/watch?v=FTWQQukpTn0&list=PL5WVKrojml6lJeDJzLHFQ1Tt-wbp-8D0Q&index=29&pp=iAQB0gcJCaIKAYcqIYzvsAgC",
    "https://www.youtube.com/watch?v=vm8qm5e-mcg&list=PL5WVKrojml6lJeDJzLHFQ1Tt-wbp-8D0Q&index=23&pp=iAQB0gcJCaIKAYcqIYzvsAgC",
    "https://www.youtube.com/watch?v=qmpDK-8ib2Y&list=PL5WVKrojml6lJeDJzLHFQ1Tt-wbp-8D0Q&index=10&pp=iAQBsAgC",
    
]
# =================================================

def extract_video_id(url):
    """Extrae el ID del video de una URL estándar de YouTube."""
    query = urlparse(url)
    if query.hostname == 'youtu.be':
        # Eliminar cualquier query string (?si=...) de las URLs cortas
        return query.path[1:].split('?')[0]
    if query.hostname in ('www.youtube.com', 'youtube.com'):
        if query.path == '/watch':
            return parse_qs(query.query)['v'][0]
    return None

def fetch_and_ingest():
    for url in YOUTUBE_URLS:
        video_id = extract_video_id(url)
        if not video_id:
            print(f"⚠️ URL inválida: {url}")
            continue
            
        print(f"\n🎥 Extrayendo transcripción para: {video_id}")
        
        try:
            # Descargar la transcripción (prioriza español, luego inglés)
            transcript_list = get_transcript(video_id, languages=['es', 'en'])
            
            # Unir todo el texto en un solo bloque legible
            full_text = " ".join([segment['text'] for segment in transcript_list])
            
            # Limpieza básica de saltos de línea extraños
            full_text = full_text.replace('\n', ' ')
            
            print(f"✅ Transcripción obtenida ({len(full_text)} caracteres).")
            print(f"Extracto: {full_text[:150]}...\n")
            
            # Pausa interactiva al estilo de tu script anterior
            choice = input("Acción: [e]nviar a la API | [s]altar | [q]uit : ").strip().lower()
            
            if choice == 'e':
                # Payload compatible con TextIngestRequest
                payload = {
                    "content": full_text,
                    "title": f"Transcripción YouTube: {video_id}",
                    "is_user_memory": False,
                    "vector_types": ["text_chunk"],
                    "privacy_level": "public_cloud",  # Obligamos a procesar en la nube pública
                    "user_notes": f"Fuente original: {url}"
                }
                
                print("➡️  Enviando a GraphRAG...")
                response = requests.post(API_URL, json=payload)
                response.raise_for_status()
                
                res_json = response.json()
                print("🚀 Inyectado con éxito.")
                print(f"   Activos creados: {len(res_json.get('assets_created', []))}")
                
            elif choice == 'q':
                print("Deteniendo script.")
                break
                
        except Exception as e:
            print(f"❌ Error al procesar {video_id}: {e}")

if __name__ == "__main__":
    fetch_and_ingest()
