"""
salesCrafter — Servidor Flask (puerto 8789).

Gestiona bloques de contenido comercial y entregables para Varkos.
Solo lee de UnifiedCache de salesSystem. Nunca escribe en ella.
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Cargar .env
_env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(_env_path)

# Agregar raíz del proyecto al path para que "from src.xxx" funcione
_project_root = str(Path(__file__).resolve().parents[1])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from flask import Flask, jsonify, request, send_file, Response, render_template

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

app = Flask(__name__, template_folder=str(Path(__file__).parent / "templates"))
app.config["TEMPLATES_AUTO_RELOAD"] = True

# ─── Imports lazily ───────────────────────────────────────────────────────────

def _reader():
    from src.cache_reader import CacheReader
    return CacheReader()

def _gen():
    from src.generators.bloque_generator import BloqueGenerator
    return BloqueGenerator()

# ─── Rutas principales ───────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("editor.html")

@app.route("/editor")
def editor():
    return render_template("editor.html")

# ─── API: Prospectos ─────────────────────────────────────────────────────────

@app.route("/api/prospects")
def api_list_prospects():
    """Lista todos los prospectos disponibles en UnifiedCache."""
    reader = _reader()
    prospects = reader.list_prospects()
    return jsonify({"status": "ok", "prospects": prospects})

@app.route("/api/prospect/<place_id>")
def api_prospect(place_id: str):
    """Obtiene datos básicos del prospecto."""
    reader = _reader()
    data = reader.get_prospect(place_id)
    if not data:
        return jsonify({"status": "error", "message": "Prospecto no encontrado"}), 404
    return jsonify({"status": "ok", "prospect": data})

@app.route("/api/prospect/<place_id>/bloques")
def api_list_bloques(place_id: str):
    """Lista todos los bloques guardados del prospecto."""
    reader = _reader()
    bloques = reader.list_bloques(place_id)
    return jsonify({"status": "ok", "bloques": bloques})

@app.route("/api/prospect/<place_id>/bloque/<bloque_id>")
def api_get_bloque(place_id: str, bloque_id: str):
    """Obtiene un bloque específico."""
    reader = _reader()
    bloque = reader.get_bloque(place_id, bloque_id)
    if not bloque:
        return jsonify({"status": "error", "message": "Bloque no encontrado"}), 404
    return jsonify({"status": "ok", "bloque": bloque})

# ─── API: Generar / Guardar Bloques ─────────────────────────────────────────

@app.route("/api/prospect/<place_id>/bloque/generar", methods=["POST"])
def api_generar_bloque(place_id: str):
    """
    Genera un nuevo bloque usando Claude Code.

    Body JSON:
    {
        "tipo": "hook_dinero",
        "fuentes": {"maps_audit": ["Score General"], "review_insights": ["Temas Positivos"]},  (opcional, usa fuentes_default si se omite)
        "nombre": "Hook Dinero — HV Delta",   (opcional)
        "prompt_extra": "texto adicional..."     (opcional — se agrega al prompt base del template)
    }
    """
    body = request.get_json() or {}
    tipo = body.get("tipo")
    fuentes = body.get("fuentes")  # dict {section: [subs]} o None
    nombre = body.get("nombre", "")
    prompt_extra = body.get("prompt_extra", "")

    if not tipo:
        return jsonify({"status": "error", "message": "tipo es requerido"}), 400

    try:
        generator = _gen()
        bloque = generator.generate(
            bloque_type=tipo,
            place_id=place_id,
            fuentes=fuentes,
            prompt_extra=prompt_extra,
            nombre=nombre,
        )
        # Guardar inmediatamente
        reader = _reader()
        reader.save_bloque(place_id, bloque)
        logger.info(f"[api] Bloque generado: {bloque['id']}")
        return jsonify({"status": "ok", "bloque": bloque})
    except Exception as e:
        logger.error(f"[api] Error generando bloque: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/prospect/<place_id>/bloque/guardar", methods=["POST"])
def api_guardar_bloque(place_id: str):
    """
    Guarda o actualiza un bloque (puede venir editado por el usuario).

    Body JSON: el dict completo del bloque
    """
    body = request.get_json() or {}
    if not body.get("id"):
        return jsonify({"status": "error", "message": "id del bloque requerido"}), 400

    # Marcar como editado por usuario
    if "metadata" not in body:
        body["metadata"] = {}
    body["metadata"]["updated_at"] = datetime.now().isoformat()
    body["metadata"]["usuario_edito"] = True

    reader = _reader()
    ok = reader.save_bloque(place_id, body)
    if not ok:
        return jsonify({"status": "error", "message": "Error guardando bloque"}), 500

    return jsonify({"status": "ok", "bloque": body})

@app.route("/api/prospect/<place_id>/bloque/regenerar", methods=["POST"])
def api_regenerar_bloque(place_id: str):
    """
    Regenera un bloque existente con nuevas fuentes.

    Body JSON:
    {
        "bloque_id": "hook_dinero_...",
        "fuentes": ["maps_audit", "services", "review_insights"]  (opcional, usa las actuales)
    }
    """
    body = request.get_json() or {}
    bloque_id = body.get("bloque_id")
    nuevas_fuentes = body.get("fuentes")
    prompt_extra = body.get("prompt_extra", "")

    logger.info(f"[regenerar] bloque_id={bloque_id}, nuevas_fuentes={nuevas_fuentes}, prompt_extra_len={len(prompt_extra)}")

    if not bloque_id:
        return jsonify({"status": "error", "message": "bloque_id requerido"}), 400

    reader = _reader()
    existing = reader.get_bloque(place_id, bloque_id)
    if not existing:
        return jsonify({"status": "error", "message": "Bloque no encontrado"}), 404

    try:
        generator = _gen()
        new_bloque = generator.regenerate(
            existing_bloque=existing,
            place_id=place_id,
            nuevas_fuentes=nuevas_fuentes,
            prompt_extra=prompt_extra,
        )
        reader.save_bloque(place_id, new_bloque)
        logger.info(f"[api] Bloque regenerado: {new_bloque['id']} v{new_bloque['metadata']['version']}")
        return jsonify({"status": "ok", "bloque": new_bloque, "_debug_version": new_bloque['metadata']['version']})
    except Exception as e:
        logger.error(f"[api] Error regenerando bloque: {e}")
        return jsonify({"status": "error", "message": str(e), "trace": str(e)}), 500

@app.route("/api/prospect/<place_id>/bloque/eliminar/<bloque_id>", methods=["DELETE"])
def api_eliminar_bloque(place_id: str, bloque_id: str):
    """Elimina un bloque guardado."""
    reader = _reader()
    ok = reader.delete_bloque(place_id, bloque_id)
    return jsonify({"status": "ok" if ok else "error"})

# ─── API: Tipos de bloque ───────────────────────────────────────────────────

@app.route("/api/bloque/tipos")
def api_tipos_bloque():
    """Lista todos los tipos de bloque disponibles."""
    from generators.prompt_builder import list_tipos, get_schema
    tipos = list_tipos()
    return jsonify({"status": "ok", "tipos": tipos})

@app.route("/api/bloque/tipos/<tipo>/schema")
def api_schema_bloque(tipo: str):
    """Obtiene el schema de salida para un tipo de bloque."""
    from generators.prompt_builder import get_schema
    schema = get_schema(tipo)
    return jsonify({"status": "ok", "schema": schema})

# ─── API: Autogenerar bloques iniciales ─────────────────────────────────────

@app.route("/api/prospect/<place_id>/autogen", methods=["POST"])
def api_autogen_bloques(place_id: str):
    """
    Genera automáticamente los bloques predefinidos para un prospecto.
    Se llama cuando se carga un prospecto nuevo.

    Body JSON (opcional):
    {
        "tipos": ["hook_dinero", "oportunidades", "fortalezas"]  (default: todos con autogenerar=true)
    }
    """
    from generators.prompt_builder import BLOQUE_TEMPLATES

    body = request.get_json() or {}
    tipos_solicitados = body.get("tipos")

    # Tipos con autogenerar por defecto
    default_autogen = ["hook_dinero", "oportunidades", "fortalezas",
                        "comparativa_competitiva", "insight_estrategico", "temas_resenas"]
    tipos_a_generar = tipos_solicitados or default_autogen

    reader = _reader()
    generator = _gen()
    results = []

    for tipo in tipos_a_generar:
        template = BLOQUE_TEMPLATES.get(tipo)
        if not template:
            continue
        fuentes_default = template.get("fuentes_default", {})
        if not fuentes_default:
            continue

        try:
            bloque = generator.generate(
                bloque_type=tipo,
                place_id=place_id,
                fuentes=None,  # usa fuentes_default del template
                prompt_extra="",
                nombre="",
            )
            reader.save_bloque(place_id, bloque)
            results.append({"tipo": tipo, "status": "ok", "id": bloque["id"]})
            logger.info(f"[api_autogen] {tipo} → {bloque['id']}")
        except Exception as e:
            results.append({"tipo": tipo, "status": "error", "message": str(e)})
            logger.warning(f"[api_autogen] Error en {tipo}: {e}")

    return jsonify({"status": "ok", "results": results})

# ─── API: Stage Classifier ────────────────────────────────────────────────────

@app.route("/api/prospect/<place_id>/stage")
def api_stage(place_id: str):
    """Clasifica el Stage del prospecto (0-6) según Expansion Framework."""
    from classifiers.stage_classifier import classify_stage, stage_to_spanish, service_for_stage

    reader = _reader()
    prospect_data = reader.get_prospect(place_id)

    # Enriquecer con secciones completas
    prospect_data["maps_audit"] = reader.get_maps_audit(place_id)
    prospect_data["services"] = reader.get_services(place_id)
    prospect_data["review_insights"] = reader.get_review_insights(place_id)
    prospect_data["competitive_intel"] = reader.get_competitive_intel(place_id)

    stage_result = classify_stage(prospect_data)
    stage_result["nombre_es"] = stage_to_spanish(stage_result["stage"])
    stage_result["servicio"] = service_for_stage(stage_result["stage"])

    return jsonify({"status": "ok", "stage": stage_result})

# ─── API: Entregables ───────────────────────────────────────────────────────

@app.route("/api/prospect/<place_id>/entregable/<tipo>/preview", methods=["POST"])
def api_entregable_preview(place_id: str, tipo: str):
    """
    Genera preview HTML del entregable.

    Body JSON (opcional):
    {
        "bloque_ids": ["hook_dinero", "oportunidades"],
        "contenido_editor": "...",  (texto del editor de posicionamiento libre)
        "stage": 3,
        "servicio_propuesto": "N2",
    }
    """
    body = request.get_json() or {}

    reader = _reader()
    prospecto = reader.get_prospect(place_id)

    try:
        if tipo == "carta_teaser":
            from assemblers.carta_teaser import CartaTeaser
            assembler = CartaTeaser(place_id, prospecto, body)
            html = assembler.render_preview()
            return jsonify({"status": "ok", "html": html, "type": "carta_teaser"})

        elif tipo == "presentacion_intro":
            from assemblers.presentacion_intro import PresentacionIntro
            assembler = PresentacionIntro(place_id, prospecto, body)
            slides = assembler.get_slides()
            return jsonify({"status": "ok", "slides": slides, "type": "presentacion_intro"})

        elif tipo == "presentacion_dirigida":
            from assemblers.presentacion_dirigida import PresentacionDirigida
            assembler = PresentacionDirigida(place_id, prospecto, body)
            slides = assembler.get_slides()
            return jsonify({"status": "ok", "slides": slides, "type": "presentacion_dirigida"})

        else:
            return jsonify({"status": "error", "message": f"Tipo de entregable desconocido: {tipo}"}), 400

    except Exception as e:
        import traceback
        logger.error(f"[api] Error generando preview {tipo}: {e}\n{traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/prospect/<place_id>/exportar/<formato>", methods=["GET", "POST"])
def api_exportar(place_id: str, formato: str):
    """
    Exporta el entregable al formato especificado.

    Formatos: docx, html

    GET: tipo_entregable se pasa como query param
    POST: tipo_entregable viene en el body JSON
    """
    if request.method == "GET":
        body = {"tipo_entregable": request.args.get("tipo_entregable", "carta_teaser")}
    else:
        body = request.get_json() or {"tipo_entregable": "carta_teaser"}

    reader = _reader()
    prospecto = reader.get_prospect(place_id)

    try:
        if formato == "docx":
            from output_exporters.docx_exporter import DocxExporter
            exporter = DocxExporter(place_id, prospecto, body)
            filename, mimetype, data = exporter.export()
            return send_file(
                data,
                mimetype=mimetype,
                as_attachment=True,
                download_name=filename,
            )
        elif formato == "html":
            from output_exporters.html_exporter import HtmlExporter
            exporter = HtmlExporter(place_id, prospecto, body)
            filename, mimetype, data = exporter.export()
            return send_file(
                data,
                mimetype=mimetype,
                as_attachment=True,
                download_name=filename,
            )
        else:
            return jsonify({"status": "error", "message": f"Formato no soportado: {formato}"}), 400
    except Exception as e:
        import traceback
        logger.error(f"[api] Error exportando {formato}: {e}\n{traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ─── API: Secciones de cache (solo lectura) ──────────────────────────────────

@app.route("/api/prospect/<place_id>/cache/<section>")
def api_cache_section(place_id: str, section: str):
    """Obtiene una sección específica de UnifiedCache (solo lectura)."""
    reader = _reader()
    data = reader.get_section(place_id, section)
    return jsonify({"status": "ok", "section": section, "data": data})


@app.route("/api/prospect/<place_id>/sources-tree")
def api_sources_tree(place_id: str):
    """
    Retorna el árbol de subsecciones disponibles para cada sección del prospecto.
    Cada sección tiene un dict de subsecciones { label: text_preview }.
    El text_preview es un resumen corto (primeras 200 chars) del contenido.
    """
    reader = _reader()
    tree = reader.get_subsections(place_id)
    # Aplanar a { section: { subseccion: preview } } para la UI
    preview_tree = {}
    for section, subs in tree.items():
        preview_tree[section] = {
            label: (text[:200] + "..." if len(text) > 200 else text)
            for label, text in subs.items()
        }
    return jsonify({"status": "ok", "tree": preview_tree})


@app.route("/api/prospect/<place_id>/sources-tree/full")
def api_sources_tree_full(place_id: str):
    """
    Retorna el árbol completo de subsecciones con el texto FULL (sin truncar).
    Útil para generar bloques.
    """
    reader = _reader()
    tree = reader.get_subsections(place_id)
    return jsonify({"status": "ok", "tree": tree})

# ─── Error handlers ───────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return jsonify({"status": "error", "message": "Ruta no encontrada"}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"status": "error", "message": "Error interno del servidor"}), 500

# ─── Run ──────────────────────────────────────────────────────────────────────

def run_server(host: str = "127.0.0.1", port: int = 8789, debug: bool = True):
    logger.info(f"Iniciando salesCrafter en http://{host}:{port}/editor")
    app.run(host=host, port=port, debug=debug, use_reloader=False)

if __name__ == "__main__":
    run_server(
        host=os.environ.get("FLASK_HOST", "127.0.0.1"),
        port=int(os.environ.get("FLASK_PORT", 8789)),
        debug=os.environ.get("FLASK_DEBUG", "true").lower() == "true",
    )