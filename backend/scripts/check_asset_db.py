import os
import sys
import json
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.json import JSON
from rich.text import Text
from rich import box

# Cargar variables de entorno
load_dotenv()

# Imports de tus clientes (ajusta la ruta según tu estructura)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.clients import get_neo4j_driver, get_weaviate_client
import weaviate.classes.query as wq

console = Console()

def inspect_latest_asset(target_hash=None):
    driver = get_neo4j_driver()
    weaviate = get_weaviate_client()

    try:
        # =====================================================
        # 1. NEO4J: BUSCAR EL NODO (ASSET + INBOX)
        # =====================================================
        console.rule("[bold blue]🔍 INSPECTOR DE GRAFO Y VECTORES")
        
        with driver.session() as session:
            if target_hash:
                query = """
                MATCH (a:DigitalAsset {file_hash: $hash})
                OPTIONAL MATCH (a)-[:HAS_INBOX_ITEM]->(i:InboxItem)
                RETURN a, i
                """
                params = {"hash": target_hash}
                console.print(f"🔎 Buscando Hash específico: [cyan]{target_hash}[/cyan]...")
            else:
                query = """
                MATCH (a:DigitalAsset)
                OPTIONAL MATCH (a)-[:HAS_INBOX_ITEM]->(i:InboxItem)
                RETURN a, i
                ORDER BY a.created_at DESC LIMIT 1
                """
                params = {}
                console.print("🔎 Buscando el [bold]ÚLTIMO ASSET[/bold] ingresado...")

            result = session.run(query, **params).single()

            if not result:
                console.print("[bold red]❌ No se encontró ningún DigitalAsset en Neo4j.[/bold red]")
                return

            asset = result["a"]
            inbox = result["i"]
            
            file_hash = asset["file_hash"]
            filename = asset.get("filename", "N/A")

            # --- TABLA DE NEO4J ---
            neo_table = Table(title="📦 Neo4j: Digital Asset & Inbox", box=box.ROUNDED)
            neo_table.add_column("Property", style="cyan")
            neo_table.add_column("Value", style="white")

            neo_table.add_row("Filename", filename)
            neo_table.add_row("File Hash", file_hash)
            neo_table.add_row("Mime Type", asset.get("mime_type", "N/A"))
            
            if inbox:
                status_color = "green" if inbox["processing_status"] == "REVIEW_REQUIRED" else "yellow"
                neo_table.add_row("Inbox Status", f"[{status_color}]{inbox['processing_status']}[/{status_color}]")
                neo_table.add_row("Inbox ID", inbox["id"])
            else:
                neo_table.add_row("Inbox Item", "[red]MISSING[/red]")

            console.print(neo_table)

            # Mostrar JSON de Sugerencias (Staging) si existe
            if inbox and inbox.get("suggested_entities"):
                try:
                    # Formatear el JSON string para verlo bonito
                    json_str = inbox["suggested_entities"]
                    parsed = json.loads(json_str)
                    console.print(Panel(JSON(json_str), title="🧠 Staged Entities (Inbox)", border_style="blue"))
                except:
                    console.print("[yellow]⚠️ Could not parse suggested_entities JSON[/yellow]")

            # 2. MOSTRAR CONCEPTOS (¡LO QUE FALTABA!)
            if inbox and inbox.get("suggested_concepts"):
                try:
                    json_str = inbox["suggested_concepts"]
                    if len(json_str) > 5:
                        console.print(Panel(JSON(json_str), title="💡 Staged Concepts (Abstract/Fictional)", border_style="magenta"))
                    else:
                        console.print("[dim]   (No concepts detected)[/dim]")
                except:
                    pass
        # =====================================================
        # 2. WEAVIATE: BUSCAR EN TODAS LAS COLECCIONES
        # =====================================================
        console.rule("[bold green]🧬 VECTORES EN WEAVIATE")

        collections_to_check = [
            ("TextSpace", "📄"), 
            ("VisualSpace", "📸"), 
            ("AudioSpace", "🎵"), 
            ("MemorySpace", "🧠")
        ]

        found_any = False

        for col_name, icon in collections_to_check:
            if not weaviate.collections.exists(col_name):
                continue
            
            col = weaviate.collections.get(col_name)
            
            # Buscar por neo4j_hash
            response = col.query.fetch_objects(
                filters=wq.Filter.by_property("neo4j_hash").equal(file_hash),
                include_vector=True, # ¡IMPORTANTE! Traer vectores para verificar
                limit=1
            )

            if response.objects:
                found_any = True
                obj = response.objects[0]
                
                # Panel de éxito
                vec_info = Table(show_header=False, box=None)
                vec_info.add_row("UUID", str(obj.uuid))
                
                # Verificar Vectores
                vectors = obj.vector
                vec_status = []
                if isinstance(vectors, dict):
                    for v_name, v_data in vectors.items():
                        vec_len = len(v_data) if v_data else 0
                        vec_status.append(f"✅ [bold]{v_name}[/bold] ({vec_len} dims)")
                else:
                    # Fallback para colecciones single-vector antiguas
                     vec_status.append("✅ Default Vector")

                vec_info.add_row("Vectors", ", ".join(vec_status))
                
                # Mostrar propiedades clave según colección
                props = obj.properties
                if col_name == "TextSpace":
                    vec_info.add_row("Summary", props.get("ai_summary", "")[:100] + "...")
                    vec_info.add_row("Type", props.get("document_type", "N/A"))
                    vec_info.add_row("Tags", str(props.get("tags", [])))
                elif col_name == "VisualSpace":
                    vec_info.add_row("Mood", props.get("visual_mood", "N/A"))
                    vec_info.add_row("OCR", props.get("ocr_text", "")[:50] + "...")
                elif col_name == "MemorySpace":
                    vec_info.add_row("Sentiment", props.get("sentiment", "N/A"))
                    vec_info.add_row("Connection", props.get("connection_type", "N/A"))

                console.print(Panel(vec_info, title=f"{icon} Encontrado en [bold]{col_name}[/bold]", border_style="green"))
            
        if not found_any:
            console.print(f"[bold red]❌ El hash {file_hash[:8]}... no se encontró en ninguna colección de Weaviate.[/bold red]")
            console.print("   [yellow]Posibles causas:[/yellow]")
            console.print("   1. La tarea Celery falló antes del paso de Weaviate.")
            console.print("   2. El 'generate_uuid5' no coincide.")
            console.print("   3. Docker no está corriendo.")

    except Exception as e:
        console.print_exception()
    finally:
        driver.close()
        weaviate.close()

if __name__ == "__main__":
    # Si pasas un argumento, lo usa como hash. Si no, busca el último.
    target = sys.argv[1] if len(sys.argv) > 1 else None
    inspect_latest_asset(target)