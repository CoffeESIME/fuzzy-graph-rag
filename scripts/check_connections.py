import sys
import os
import socket
from urllib.parse import urlparse

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from config.settings import get_settings
except ImportError:
    print("❌ Error de Importación: No se encuentra 'config.settings'.")
    print("Asegúrate de ejecutar este script desde la raíz del proyecto así:")
    print("poetry run python scripts/check_connections.py")
    sys.exit(1)

settings = get_settings()

def check_socket(host: str, port: int, service_name: str):
    """Intenta conectar a un socket TCP puro."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((host, int(port)))
        sock.close()
        
        if result == 0:
            print(f"✅ {service_name:<15} -> ONLINE ({host}:{port})")
            return True
        else:
            print(f"❌ {service_name:<15} -> CERRADO/TIMEOUT ({host}:{port})")
            return False
    except Exception as e:
        print(f"❌ {service_name:<15} -> ERROR: {e}")
        return False

def parse_and_check():
    print(f"\n--- 🔍 DIAGNÓSTICO DE RED (Environment: {settings.ENV_STATE}) ---")
    print(f"Host Configurado: {settings.API_HOST}")
    print("-" * 60)

    check_socket(settings.POSTGRES_SERVER, settings.POSTGRES_PORT, "Postgres")
    check_socket(settings.REDIS_HOST, settings.REDIS_PORT, "Redis")
    check_socket(settings.WEAVIATE_URL, settings.WEAVIATE_PORT, "Weaviate HTTP")
    check_socket(settings.WEAVIATE_URL, settings.WEAVIATE_GRPC_PORT, "Weaviate gRPC")
    try:
        if "://" in settings.NEO4J_URI:
            parsed = urlparse(settings.NEO4J_URI)
            neo_host = parsed.hostname
            neo_port = parsed.port or 7687
        else:
            neo_host = settings.NEO4J_URI
            neo_port = 7687 
        check_socket(neo_host, neo_port, "Neo4j Bolt")
    except Exception as e:
        print(f"⚠️ Error parseando URI de Neo4j: {e}")
    try:
        if ":" in settings.MINIO_ENDPOINT:
            m_host, m_port = settings.MINIO_ENDPOINT.split(":")
        else:
            m_host = settings.MINIO_ENDPOINT
            m_port = 9000
        check_socket(m_host, int(m_port), "MinIO API")
    except Exception as e:
        print(f"⚠️ Error parseando Endpoint de MinIO: {e}")

    print("-" * 60)

if __name__ == "__main__":
    parse_and_check()