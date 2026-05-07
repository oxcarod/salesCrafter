"""
Cache Reader — Lee datos de la UnifiedCache de salesSystem (solo lectura).

El path de la cache se configura via UNIFIED_CACHE_ROOT en .env
o apunta por defecto a la carpeta compartida con salesSystem.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Any

logger = logging.getLogger(__name__)

# Path a la carpeta compartida de UnifiedCache (salesSystem)
# Se puedeoverride con la variable de entorno UNIFIED_CACHE_ROOT
_DEFAULT_CACHE_ROOT = Path(__file__).resolve().parents[1] / ".." / "salesSystem" / "data" / "prospectos" / "reports" / "runs"


def _get_cache_root() -> Path:
    """Retorna el path raíz de la UnifiedCache."""
    import os
    root = os.environ.get("UNIFIED_CACHE_ROOT", "")
    if root:
        return Path(root)
    return _DEFAULT_CACHE_ROOT.resolve()


class CacheReader:
    """
    Lee datos de UnifiedCache. Solo lectura.

    Uso:
        reader = CacheReader()
        prospect = reader.get_prospect("ChIJxxxx")
        maps_audit = reader.get_section("ChIJxxxx", "maps_audit")
    """

    def __init__(self):
        self.cache_root = _get_cache_root()

    # ─── Rutas ───────────────────────────────────────────────────────────────

    def _prospect_folder(self, place_id: str) -> Optional[Path]:
        """Retorna la carpeta del prospecto si existe."""
        safe = place_id.replace(":", "_").replace("/", "_").replace("\\", "_")
        # Buscar en subcarpetas directas
        if self.cache_root.exists():
            for sub in self.cache_root.iterdir():
                if sub.is_dir() and sub.name == safe:
                    cache_file = sub / f"{safe}.json"
                    if cache_file.exists():
                        return sub
        return None

    def _cache_file(self, place_id: str) -> Optional[Path]:
        """Retorna el archivo JSON del prospecto."""
        folder = self._prospect_folder(place_id)
        if not folder:
            return None
        safe = place_id.replace(":", "_").replace("/", "_").replace("\\", "_")
        f = folder / f"{safe}.json"
        return f if f.exists() else None

    def _load_json(self, place_id: str) -> dict:
        """Carga el JSON completo del prospecto."""
        cf = self._cache_file(place_id)
        if not cf:
            return {}
        try:
            with open(cf, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Error loading cache for {place_id}: {e}")
            return {}

    # ─── Acceso público ───────────────────────────────────────────────────────

    def get_prospect(self, place_id: str) -> dict:
        """
        Carga el prospecto completo y retorna datos normalizados.
        Solo retorna los campos relevantes para salesCrafter.
        """
        data = self._load_json(place_id)
        if not data:
            return {}

        # Normalizar: puede venir con diferentes schemas (flat, apify, etc.)
        return {
            "place_id": data.get("place_id") or place_id,
            "name": data.get("name") or data.get("titulo") or data.get("nombre") or "Desconocido",
            "calificacion": data.get("calificacion") or data.get("rating") or data.get("score") or 0,
            "numero_reviews": data.get("numero_reviews") or data.get("review_count")
                              or data.get("num_resenas") or 0,
            "categoria": data.get("categoria") or data.get("category") or "",
            "direccion": data.get("direccion") or data.get("address") or "",
            "telefono": data.get("telefono") or data.get("phone") or "",
            "horarios": data.get("horarios") or data.get("hours") or "",
            "sitio_web": data.get("sitio_web") or data.get("website") or "",
            "maps_url": data.get("maps_url") or "",
            "coordenadas": data.get("coordenadas") or data.get("coordinates") or "",
            "servicios_publicados": data.get("servicios_publicados") or data.get("published_services") or [],
            "score_gral": self._get_score(data),
            "cached_sections": self._get_cached_sections(data),
            "cached_at": data.get("cached_at") or "",
        }

    def _get_score(self, data: dict) -> Optional[float]:
        """Extrae score general de cualquier sección disponible."""
        for section_key in ["maps_audit", "market_audit", "geo_audit", "prospect_analysis"]:
            section = data.get(section_key, {})
            if isinstance(section, dict):
                score = section.get("score_gral")
                if score is not None:
                    return float(score)
        return None

    def _get_cached_sections(self, data: dict) -> list[str]:
        """Lista las secciones disponibles en cache."""
        reserved = {
            "place_id", "name", "titulo", "nombre", "calificacion", "rating", "score",
            "numero_reviews", "review_count", "num_resenas", "categoria", "category",
            "direccion", "address", "telefono", "phone", "horarios", "hours",
            "sitio_web", "website", "maps_url", "coordenadas", "coordinates",
            "servicios_publicados", "published_services", "cached_at", "_raw_apify",
            "apify_data", "result",
        }
        return [k for k in data if k not in reserved and isinstance(data[k], dict)]

    def get_section(self, place_id: str, section: str) -> dict:
        """Obtiene una sección específica del cache."""
        data = self._load_json(place_id)
        section_data = data.get(section, {})
        if isinstance(section_data, dict):
            return section_data
        return {}

    def get_all_audits(self, place_id: str) -> dict:
        """Obtiene todas las secciones de auditoría disponibles."""
        data = self._load_json(place_id)
        audit_sections = {
            "maps_audit", "market_audit", "geo_audit", "prospect_analysis",
            "competitive_intel", "review_insights", "social_audit",
        }
        return {k: v for k, v in data.items()
                 if k in audit_sections and isinstance(v, dict)}

    # ─── Subsections tree ─────────────────────────────────────────────────────

    def get_subsections(self, place_id: str) -> dict[str, dict]:
        """
        Retorna un árbol de subsecciones disponibles para cada sección del prospecto.
        Cada subsección tiene: { label, value }
        value = texto plano listo para interpolar en un prompt.
        """
        data = self._load_json(place_id)
        tree = {}
        for section_key in data:
            if isinstance(data[section_key], dict):
                parsed = _parse_section_subsections(section_key, data[section_key])
                if parsed:
                    tree[section_key] = parsed
            elif section_key == "servicios_publicados" and isinstance(data[section_key], list):
                # Servicios publicados como sección virtual
                items = data[section_key]
                if items:
                    tree[section_key] = {
                        "Servicios Publicados": "\n".join([f"  • {s}" for s in items])
                    }
            elif section_key == "owner_response_metrics" and isinstance(data[section_key], dict):
                m = data[section_key]
                parts = []
                if m.get("reply_rate_percent") is not None:
                    parts.append(f"Tasa de respuesta: {m['reply_rate_percent']}%")
                if m.get("owner_replies_count") is not None:
                    parts.append(f"Respuestas del dueño: {m['owner_replies_count']}")
                if m.get("total_reviews_considered") is not None:
                    parts.append(f"Reseñas consideradas: {m['total_reviews_considered']}")
                if parts:
                    tree[section_key] = {"Métricas de Respuesta": " | ".join(parts)}

            elif section_key == "_patient_estimates" and isinstance(data[section_key], dict):
                rs = data[section_key]
                parts = []
                if rs.get("total_reviews_google"):
                    parts.append(f"Total reseñas Google: {rs['total_reviews_google']}")
                if rs.get("sample_size"):
                    parts.append(f"Muestra analizada: {rs['sample_size']} reseñas")
                if rs.get("sample_date_from") and rs.get("sample_date_to"):
                    parts.append(f"Periodo muestra: {rs['sample_date_from']} a {rs['sample_date_to']}")
                if rs.get("reviews_per_month_avg"):
                    parts.append(f"Reseñas/mes (muestra): {rs['reviews_per_month_avg']}")
                if rs.get("est_total_patients"):
                    parts.append(f"Pacientes estimados totales: {rs['est_total_patients']:,}")
                if rs.get("est_patients_per_month"):
                    parts.append(f"Pacientes/mes estimados: {rs['est_patients_per_month']:,}")
                if rs.get("est_monthly_revenue_mxn"):
                    parts.append(f"Ingresos mensuales est. (ticket $1,500): ${rs['est_monthly_revenue_mxn']:,} MXN")
                if parts:
                    tree[section_key] = {"Estimación de Pacientes": " | ".join(parts)}

            # Calcular _patient_estimates al vuelo si no existe en cache (prospectos cacheados antes del feature)
            elif section_key == "reviews" and isinstance(data[section_key], list) and data[section_key]:
                computed = _compute_patient_estimates(data)
                if computed:
                    tree["_patient_estimates"] = {"Estimación de Pacientes": _format_patient_estimates(computed)}

        # maps_audit: enriquecer con datos de otras secciones del prospecto
        if "maps_audit" in tree and tree["maps_audit"]:
            _enrich_maps_audit(place_id, tree["maps_audit"], data)

        return tree

    def get_services(self, place_id: str) -> dict:
        """Obtiene la sección de servicios."""
        data = self._load_json(place_id)
        services = data.get("services", {})
        if isinstance(services, dict):
            return services
        # Legacy: puede venir como array
        if isinstance(services, list):
            return {"real": services, "services_reviews": []}
        return {"real": [], "services_reviews": []}

    def get_review_insights(self, place_id: str) -> dict:
        """Obtiene insights de reseñas."""
        return self.get_section(place_id, "review_insights")

    def get_competitors(self, place_id: str) -> list:
        """Obtiene lista de competidores."""
        data = self._load_json(place_id)
        comp = data.get("competitors", [])
        if isinstance(comp, list):
            return comp
        return []

    def get_maps_audit(self, place_id: str) -> dict:
        """Shortcut para maps_audit."""
        return self.get_section(place_id, "maps_audit")

    def get_market_audit(self, place_id: str) -> dict:
        """Shortcut para market_audit."""
        return self.get_section(place_id, "market_audit")

    def get_geo_audit(self, place_id: str) -> dict:
        """Shortcut para geo_audit."""
        return self.get_section(place_id, "geo_audit")

    def get_competitive_intel(self, place_id: str) -> dict:
        """Shortcut para competitive_intel."""
        return self.get_section(place_id, "competitive_intel")

    def get_prospect_analysis(self, place_id: str) -> dict:
        """Shortcut para prospect_analysis."""
        return self.get_section(place_id, "prospect_analysis")

    def list_prospects(self) -> list[dict]:
        """
        Lista todos los prospectos disponibles en cache.

        Returns:
            Lista de dicts con {place_id, name, score, cached_sections}
        """
        results = []
        if not self.cache_root.exists():
            return results

        for sub in self.cache_root.iterdir():
            if not sub.is_dir():
                continue
            cache_file = sub / f"{sub.name}.json"
            if not cache_file.exists():
                continue
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Intentar obtener el Apify ID real (puede estar en _raw_apify)
                apify_id = None
                for src in [data, data.get("apify_data", {}), data.get("result", {})]:
                    if isinstance(src, dict):
                        raw = src.get("_raw_apify", {})
                        if isinstance(raw, dict) and raw.get("placeId"):
                            apify_id = raw["placeId"]
                            break
                        if src.get("place_id") and src.get("place_id") != sub.name:
                            apify_id = src["place_id"]
                            break

                # Obtener score
                score = None
                for section_key in ["maps_audit", "market_audit", "geo_audit"]:
                    section = data.get(section_key, {})
                    if isinstance(section, dict) and section.get("score_gral") is not None:
                        score = section["score_gral"]
                        break

                results.append({
                    "place_id": apify_id or sub.name,
                    "folder_name": sub.name,
                    "name": data.get("name") or data.get("titulo") or data.get("nombre") or sub.name,
                    "calificacion": data.get("calificacion") or data.get("rating") or 0,
                    "score_gral": score,
                    "cached_sections": list(self._get_cached_sections(data)),
                    "cached_at": data.get("cached_at") or "",
                })
            except Exception as e:
                logger.warning(f"Error reading {sub.name}: {e}")
                continue

        return sorted(results, key=lambda x: x.get("name", ""))

    def get_bloque(self, place_id: str, bloque_id: str) -> Optional[dict]:
        """Lee un bloque guardado desde blocks/{place_id}/{bloque_id}.json."""
        blocks_dir = self._blocks_dir(place_id)
        if not blocks_dir:
            return None
        f = blocks_dir / f"{bloque_id}.json"
        if not f.exists():
            return None
        try:
            with open(f, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def list_bloques(self, place_id: str) -> list[dict]:
        """Lista todos los bloques guardados de un prospecto."""
        blocks_dir = self._blocks_dir(place_id)
        if not blocks_dir or not blocks_dir.exists():
            return []
        results = []
        for f in sorted(blocks_dir.glob("*.json")):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                results.append({
                    "id": data.get("id") or f.stem,
                    "nombre": data.get("nombre", f.stem),
                    "tipo": data.get("tipo", "desconocido"),
                    "autogenerar": data.get("autogenerar", False),
                    "updated_at": data.get("metadata", {}).get("updated_at", ""),
                    "version": data.get("metadata", {}).get("version", 1),
                    "usuario_edito": data.get("metadata", {}).get("usuario_edito", False),
                })
            except Exception:
                continue
        return results

    def save_bloque(self, place_id: str, bloque: dict) -> bool:
        """Guarda un bloque en blocks/{place_id}/{bloque_id}.json. Crea la carpeta si no existe."""
        blocks_dir = self._blocks_dir(place_id, create=True)
        if not blocks_dir:
            return False
        bloque_id = bloque.get("id", "bloque")
        safe_name = bloque_id.replace(":", "_").replace("/", "_").replace("\\", "_")
        f = blocks_dir / f"{safe_name}.json"
        try:
            with open(f, "w", encoding="utf-8") as fh:
                json.dump(bloque, fh, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving bloque {bloque_id}: {e}")
            return False

    def delete_bloque(self, place_id: str, bloque_id: str) -> bool:
        """Elimina un bloque guardado."""
        blocks_dir = self._blocks_dir(place_id)
        if not blocks_dir:
            return False
        safe_name = bloque_id.replace(":", "_").replace("/", "_").replace("\\", "_")
        f = blocks_dir / f"{safe_name}.json"
        if f.exists():
            f.unlink()
            return True
        return False

    def _blocks_dir(self, place_id: str, create: bool = False) -> Optional[Path]:
        """Retorna la carpeta de bloques para un prospecto."""
        base = Path(__file__).resolve().parents[1] / "blocks"
        safe = place_id.replace(":", "_").replace("/", "_").replace("\\", "_")
        folder = base / safe
        if create:
            folder.mkdir(parents=True, exist_ok=True)
        return folder


# ─── Helpers para subsections ─────────────────────────────────────────────────

def _dict_to_subsections(data: dict, max_len: int = 4000) -> dict:
    """Convierte un dict a subsecciones planas con label=key, value=json.dumps."""
    result = {}
    for key, val in data.items():
        if val is None or val == "":
            continue
        if isinstance(val, (str, int, float, bool)):
            text = str(val)
        elif isinstance(val, list):
            if not val:
                continue
            # Si es lista de dicts simples, formatear como lista legible
            if all(isinstance(x, dict) for x in val[:5]):
                lines = []
                for item in val[:20]:
                    parts = [f"{k}: {v}" for k, v in item.items() if v]
                    if parts:
                        lines.append("  • " + " | ".join(parts))
                text = "\n".join(lines) if lines else ""
            else:
                text = json.dumps(val, ensure_ascii=False)[:max_len]
        elif isinstance(val, dict):
            # Recursivo: aplanar sub-keys
            sub = _dict_to_subsections(val, max_len)
            for sub_key, sub_val in sub.items():
                result[f"{key}.{sub_key}"] = sub_val
            continue
        else:
            text = str(val)

        if text.strip():
            result[key] = text.strip()[:max_len]
    return result


def _enrich_maps_audit(place_id: str, maps_subs: dict, data: dict) -> None:
    """
    Enrich maps_audit con subsecciones derivadas de otras secciones del prospecto.
    Mutates maps_subs in place.
    """
    # ── Análisis de Fotos (desde photos.checklist) ──
    photos = data.get("photos", {})
    checklist = photos.get("checklist", {}).get("checklist", {})
    if checklist:
        total = sum(v.get("score", 0) for v in checklist.values())
        mx = sum(v.get("max", 10) for v in checklist.values())
        pct = round(total / mx * 100) if mx else 0
        lines = [f"Puntaje total: {total}/{mx} ({pct}%)"]
        for k, v in sorted(checklist.items(), key=lambda x: x[1].get("score", 0)):
            s = v.get("score", 0)
            m = v.get("max", 10)
            lines.append(f"  [{s}/{m}] {v.get('pregunta', k)}")
        maps_subs["Análisis de Fotos"] = "\n".join(lines)

    # ── Servicios Reales vs Publicados (gap de servicios) ──
    services = data.get("services", {})
    real = services.get("real", [])
    published = data.get("servicios_publicados", [])
    if real or published:
        gap = [s for s in real if s not in published]
        gap = [s for s in gap if any(p.lower() in s.lower() or s.lower() in p.lower()
                                     for p in published) is False]
        # Servicios que NO están publicados
        lines = [f"Servicios reales ({len(real)}): {', '.join(sorted(real[:20]))}"]
        if published:
            lines.append(f"Servicios publicados ({len(published)}): {', '.join(sorted(published))}")
        if gap:
            lines.append(f"Gap — no publicados ({len(gap)}): {', '.join(sorted(gap[:15]))}")
        maps_subs["Gap de Servicios"] = "\n".join(lines)

    # ── Análisis de Reseñas (desde review_insights) ──
    ri = data.get("review_insights", {})
    if ri.get("insight"):
        # Insight general
        maps_subs["Análisis de Reseñas"] = ri["insight"]
    elif ri.get("resumen"):
        maps_subs["Análisis de Reseñas"] = ri["resumen"]

    # ── Presencia Online resumida (datos del listing + social) ──
    partes = []
    if data.get("sitio_web"):
        partes.append(f"Sitio web: {data['sitio_web']}")
    else:
        partes.append("Sitio web: NO")
    if data.get("telefono"):
        partes.append(f"Teléfono: {data['telefono']}")
    if data.get("horarios"):
        partes.append(f"Horarios: {data['horarios']}")
    if data.get("calificacion"):
        partes.append(f"Rating: {data['calificacion']}/5 ({data.get('numero_reviews',0)} reseñas)")
    if data.get("abierto_24_horas"):
        partes.append("Horario: 24 hrs")
    if data.get("descripcion"):
        partes.append(f"Descripción GBP: {data['descripcion'][:200]}")
    if partes:
        maps_subs["Presencia Online"] = " | ".join(partes)

    # ── Resumen del Perfil ──
    perfil_parts = []
    ma = data.get("maps_audit", {})
    if ma.get("profile_completeness") is not None:
        pct = ma["profile_completeness"]
        perfil_parts.append(f"Completitud del perfil: {pct:.0f}%")
    if ma.get("map_visibility_risk") is not None:
        risk = ma["map_visibility_risk"]
        label = "Alto" if risk > 0.5 else "Medio" if risk > 0.2 else "Bajo"
        perfil_parts.append(f"Riesgo de visibilidad: {label} ({risk:.0%})")
    if ma.get("has_24h") is not None and ma["has_24h"]:
        perfil_parts.append("Abierto 24h: Sí")
    if ma.get("has_photos") is not None and ma["has_photos"]:
        perfil_parts.append("Fotos en listing: Sí")
    else:
        perfil_parts.append("Fotos en listing: No")
    if ma.get("responds_to_reviews") is not None:
        perfil_parts.append(f"Responde reseñas: {'Sí' if ma['responds_to_reviews'] else 'No'}")
    if data.get("owner_response_metrics"):
        m = data["owner_response_metrics"]
        pct = m.get("reply_rate_percent")
        if pct is not None:
            perfil_parts.append(f"Tasa respuesta dueño: {pct:.0f}%")
    if perfil_parts:
        maps_subs["Resumen del Perfil"] = "\n".join(perfil_parts)

    # ── Oportunidades de Negocio (de review_insights + competitive_intel) ──
    opp_lines = []
    ri = data.get("review_insights", {})
    if ri.get("oportunidades"):
        opp = ri["oportunidades"]
        if isinstance(opp, list):
            opp_lines += [f"  • {o}" for o in opp[:5] if o]
        else:
            opp_lines.append(f"  • {opp}")
    if ri.get("prioridad_accion"):
        opp_lines.append(f"\nPrioridad de acción: {ri['prioridad_accion']}")
    if opp_lines:
        maps_subs["Oportunidades de Negocio"] = "\n".join(opp_lines)

    # ── Acciones (de market_audit quick wins + geo_audit acciones) ──
    action_lines = []
    if ma.get("quick_wins"):
        for q in ma.get("quick_wins", [])[:5]:
            if isinstance(q, dict):
                action_lines.append(f"  • {q.get('accion', q.get('descripcion', str(q)))}")
            elif isinstance(q, str):
                action_lines.append(f"  • {q}")
    # Acciones de geo_audit
    geo = data.get("geo_audit", {})
    for sec in geo.get("secciones", []):
        titulo = sec.get("titulo", "")
        if "Acciones" in titulo or "Rápidas" in titulo:
            for sub in sec.get("subsecciones", []):
                content = sub.get("contenido") or sub.get("items")
                if isinstance(content, list):
                    for item in content[:5]:
                        action_lines.append(f"  • {item}")
    # Acciones de market_audit
    ma_audit = data.get("market_audit", {})
    for sec in ma_audit.get("secciones", []):
        titulo = sec.get("titulo", "")
        if "GANANCIAS" in titulo:
            content = sec.get("contenido") or []
            if isinstance(content, str):
                action_lines.append(f"  {content[:200]}")
            elif sec.get("subsecciones"):
                for sub in sec["subsecciones"]:
                    content = sub.get("contenido") or sub.get("items") or []
                    if isinstance(content, list):
                        for item in content[:3]:
                            action_lines.append(f"  • {item}")
    if action_lines:
        maps_subs["Acciones"] = "\n".join(action_lines[:15])

    # ── Análisis Competitivo (resumen de competitive_intel) ──
    ci = data.get("competitive_intel", {})
    if ci.get("score_gral") is not None or ci.get("secciones"):
        comp_parts = []
        if ci.get("score_gral") is not None:
            comp_parts.append(f"Score competitivo: {ci['score_gral']}/100")
        if ci.get("grado"):
            comp_parts.append(f"Grado: {ci['grado']}")
        # Top amenazas
        for sec in ci.get("secciones", []):
            titulo = sec.get("titulo", "")
            if "Brechas" in titulo or "Panorama" in titulo:
                content = sec.get("contenido")
                if isinstance(content, str) and content.strip():
                    comp_parts.append(f"\n{titulo}\n{content[:300]}")
                break
        if comp_parts:
            maps_subs["Análisis Competitivo"] = "\n".join(comp_parts)


def _section_to_text(section: str, data: dict) -> str:
    """Convierte una sección a texto plano para usar como fuente."""
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        # Si tiene secciones jerárquicas, usar las secciones principales
        if "secciones" in data and isinstance(data["secciones"], list):
            lines = []
            for sec in data["secciones"][:10]:
                titulo = sec.get("titulo", "")
                contenido = sec.get("contenido")
                if contenido is None:
                    lines.append(titulo)
                elif isinstance(contenido, str):
                    lines.append(f"{titulo}\n{contenido}")
                else:
                    lines.append(titulo)
            return "\n".join(lines)
        # Si tiene contenido clave, usar ese
        if data.get("summary"):
            return data["summary"]
        if data.get("insight"):
            return data["insight"]
        if data.get("resumen"):
            return data["resumen"]
        if data.get("contenido"):
            return data["contenido"]
    return ""


def _format_subseccion(sub: dict) -> str:
    """Formatea el contenido de una subsección de las auditorías a texto."""
    if sub.get("tipo") == "tabla" and sub.get("contenido"):
        lines = []
        cols = sub.get("columnas", [])
        if cols:
            lines.append(" | ".join(cols))
            lines.append("-" * 40)
        for row in sub.get("contenido", [])[:15]:
            if isinstance(row, dict):
                parts = [str(row.get(c, "")) for c in cols]
                lines.append(" | ".join(parts))
        return "\n".join(lines)
    elif sub.get("tipo") == "tabla" and sub.get("items"):
        # Items en lugar de contenido directo (algunos audits)
        cols = sub.get("columnas", []) or (list(sub["items"][0].keys()) if sub["items"] else [])
        lines = []
        if cols:
            lines.append(" | ".join(cols))
            lines.append("-" * 40)
        for row in sub.get("items", [])[:15]:
            if isinstance(row, dict):
                parts = [str(row.get(c, "")) for c in cols]
                lines.append(" | ".join(parts))
        return "\n".join(lines)
    elif sub.get("tipo") == "lista" and sub.get("contenido"):
        return "\n".join([f"  • {c}" for c in sub.get("contenido", [])])
    elif sub.get("tipo") == "item" and sub.get("contenido"):
        if isinstance(sub["contenido"], list):
            return "\n".join([f"  • {c}" for c in sub["contenido"]])
        return str(sub["contenido"])
    elif sub.get("contenido") is not None:
        if isinstance(sub["contenido"], str):
            return sub["contenido"]
        return json.dumps(sub["contenido"], ensure_ascii=False, indent=2)[:3000]
    elif sub.get("items") and isinstance(sub["items"], list):
        # Sin contenido pero con items
        if not sub["items"]:
            return ""
        if isinstance(sub["items"][0], dict):
            cols = sub.get("columnas", []) or list(sub["items"][0].keys())
            lines = []
            if cols:
                lines.append(" | ".join(cols))
                lines.append("-" * 40)
            for row in sub["items"][:15]:
                parts = [str(row.get(c, "")) for c in cols]
                lines.append(" | ".join(parts))
            return "\n".join(lines)
        else:
            return "\n".join([f"  • {i}" for i in sub["items"]])
    return ""


def _parse_section_subsections(section: str, data: dict) -> dict:
    """
    Dado el dict de una sección, extrae subsecciones relevantes.
    Retorna { subseccion_label: text } para cada subsección.
    """
    if not isinstance(data, dict):
        return {}

    result = {}

    # ── competitive_intel / geo_audit / market_audit / prospect_analysis
    #    → usar las secciones principales (top-level) como subsecciones.
    #    Cada seccion tiene: titulo + contenido + subsecciones.
    #    Se extrae el contenido de nivel 1 directamente; sub-subsecciones
    #    se muestran como items dentro de cada sección.
    if section in ("competitive_intel", "geo_audit", "market_audit", "prospect_analysis"):
        ci = data
        # Resumen general al inicio
        score = ci.get("score_gral") or ci.get("score")
        grado = ci.get("grado") or ""
        if score is not None:
            result["Resumen"] = f"Score: {score} | Grado: {grado}"
        # Secciones principales
        for sec in ci.get("secciones", []):
            titulo = sec.get("titulo", "").strip()
            if not titulo:
                continue

            parts = []
            # Contenido directo de la sección
            contenido = sec.get("contenido")
            if contenido is not None:
                if isinstance(contenido, str) and contenido.strip():
                    parts.append(contenido.strip())
                elif isinstance(contenido, list) and contenido:
                    # Lista de items
                    for item in contenido[:10]:
                        if isinstance(item, dict):
                            line = " | ".join(f"{k}: {v}" for k, v in item.items() if v)
                            if line:
                                parts.append(f"  • {line}")
                        elif isinstance(item, str):
                            parts.append(f"  • {item}")

            # Subsecciones dentro de esta sección
            for sub in sec.get("subsecciones", []):
                sub_titulo = sub.get("titulo", "").strip()
                if not sub_titulo:
                    continue
                sub_content = _format_subseccion(sub)
                if sub_content.strip():
                    parts.append(f"[{sub_titulo}]\n{sub_content.strip()}")
                elif sub.get("contenido") is None:
                    # Subsección sin contenido (marker o título)
                    parts.append(f"[{sub_titulo}]")

            if parts:
                text = "\n".join(parts).strip()
                if text:
                    result[titulo] = text
        return result

    # ── review_insights ──────────────────────────────────────────────────────
    if section == "review_insights":
        ri = data
        if ri.get("temas") and isinstance(ri["temas"], list):
            pos = [t for t in ri["temas"] if isinstance(t, dict) and t.get("categoria") == "positivo"]
            neg = [t for t in ri["temas"] if isinstance(t, dict) and t.get("categoria") == "negativo"]
            pos_lines = [f"  • {t.get('nombre','?')} ({t.get('resenas_count',0)} menciones, {float(t.get('porcentaje') or 0):.0f}%)" for t in pos[:10]]
            neg_lines = [f"  • {t.get('nombre','?')} ({t.get('resenas_count',0)} menciones, {float(t.get('porcentaje') or 0):.0f}%)" for t in neg[:10]]
            if pos_lines:
                result["Temas Positivos"] = "\n".join(pos_lines)
            if neg_lines:
                result["Temas Negativos"] = "\n".join(neg_lines)
        # Top-5 separados (más recientes)
        if ri.get("temas_positivos_top5"):
            lines = [f"  • {t.get('nombre','?')} ({t.get('resenas_count',0)})" for t in ri["temas_positivos_top5"][:5] if isinstance(t, dict)]
            if lines:
                result["Top 5 Positivos"] = "\n".join(lines)
        if ri.get("temas_negativos_top5"):
            lines = [f"  • {t.get('nombre','?')} ({t.get('resenas_count',0)})" for t in ri["temas_negativos_top5"][:5] if isinstance(t, dict)]
            if lines:
                result["Top 5 Negativos"] = "\n".join(lines)
        if ri.get("insight"):
            result["Insight"] = ri["insight"]
        if ri.get("fortalezas"):
            flines = ri["fortalezas"] if isinstance(ri["fortalezas"], list) else [ri["fortalezas"]]
            result["Fortalezas del Negocio"] = "\n".join(f"  • {f}" for f in flines if f)
        if ri.get("debilidades"):
            dlines = ri["debilidades"] if isinstance(ri["debilidades"], list) else [ri["debilidades"]]
            result["Debilidades"] = "\n".join(f"  • {d}" for d in dlines if d)
        if ri.get("oportunidades"):
            olines = ri["oportunidades"] if isinstance(ri["oportunidades"], list) else [ri["oportunidades"]]
            result["Oportunidades"] = "\n".join(f"  • {o}" for o in olines if o)
        if ri.get("prioridad_accion"):
            result["Prioridad de Acción"] = ri["prioridad_accion"]
        if ri.get("resumen"):
            result["Resumen"] = ri["resumen"]
        total = ri.get("total_resenas_analizadas")
        con_texto = ri.get("total_resenas_con_texto")
        if total:
            result["Métricas"] = f"Analizadas: {total} | Con texto: {con_texto or 0}"
        return result

    # ── maps_audit ────────────────────────────────────────────────────────────
    if section == "maps_audit":
        ma = data
        if ma.get("summary"):
            result["Resumen Ejecutivo"] = ma["summary"]
        if ma.get("score") is not None:
            result["Score General"] = json.dumps({
                "score": ma.get("score"),
                "rating": ma.get("rating"),
                "reviews": ma.get("reviews"),
                "competitor_pressure": ma.get("competitor_pressure"),
                "map_visibility_risk": ma.get("map_visibility_risk"),
                "profile_completeness": ma.get("profile_completeness"),
            }, ensure_ascii=False)
        if ma.get("subscores"):
            result["Subscores"] = json.dumps(ma["subscores"], ensure_ascii=False)
        if ma.get("findings"):
            lines = [f"[{f.get('severity','?')}] {f.get('finding','')}" for f in ma.get("findings", []) if f.get("finding")]
            result["Findings"] = "\n".join(lines)
        if ma.get("quick_wins"):
            result["Quick Wins"] = json.dumps(ma.get("quick_wins", []), ensure_ascii=False)
        if ma.get("competitor_pressure"):
            result["Presión Competitiva"] = f"{ma.get('competitor_pressure')} — {ma.get('competitors_better','?')} competidores con mejor rating."
        if ma.get("competitive_table"):
            result["Tabla Competitiva"] = json.dumps(ma.get("competitive_table", [])[:10], ensure_ascii=False, indent=2)
        return result

    # ── services ────────────────────────────────────────────────────────────
    if section == "services":
        real = data.get("real", [])
        reviews = data.get("services_reviews", [])
        if real:
            result["Servicios Reales"] = ", ".join(real) if isinstance(real, list) else str(real)
        if reviews:
            lines = [f"  • {r.get('nombre','?')} ({r.get('menciones',0)} menciones)" for r in reviews[:15] if isinstance(r, dict)]
            result["Servicios por Reviews"] = "\n".join(lines)
        return result

    # ── social_audit ─────────────────────────────────────────────────────────
    if section == "social_audit":
        for platform in ["facebook", "instagram", "tiktok"]:
            pdata = data.get(platform, {})
            if not pdata:
                continue
            parts = [f"Existe: {pdata.get('exists', False)}"]
            if pdata.get("followers"):
                parts.append(f"Seguidores: {pdata.get('followers')}")
            if pdata.get("score"):
                parts.append(f"Score: {pdata.get('score')}/100")
            if pdata.get("posts_count"):
                parts.append(f"Posts: {pdata.get('posts_count')}")
            if pdata.get("days_since_last_post"):
                parts.append(f"Días sin publicar: {pdata.get('days_since_last_post')}")
            if pdata.get("url"):
                parts.append(f"URL: {pdata.get('url')}")
            result[platform.capitalize()] = " | ".join(parts)
        return result

    # ── photos ──────────────────────────────────────────────────────────────
    if section == "photos":
        checklist = data.get("checklist", {}).get("checklist", {})
        if checklist:
            total = sum(v.get("score", 0) for v in checklist.values())
            mx = sum(v.get("max", 10) for v in checklist.values())
            pct = round(total / mx * 100) if mx else 0
            lines = [f"Puntaje total: {total}/{mx} ({pct}%)"]
            for k, v in sorted(checklist.items(), key=lambda x: x[1].get("score", 0)):
                s = v.get("score", 0)
                m = v.get("max", 10)
                pre = v.get("pregunta", k)
                lines.append(f"  [{s}/{m}] {pre}")
            result["Análisis de Fotos"] = "\n".join(lines)
        return result

    # ── Para secciones desconocidas: aplanar dict ──────────────────────────
    return _dict_to_subsections(data)


def _compute_patient_estimates(data: dict) -> dict:
    """Calcula estadísticas de pacientes a partir de las reseñas muestreadas."""
    reviews = data.get("reviews") or []
    total_reviews = data.get("numero_reviews") or len(reviews)
    if not reviews:
        return {}
    try:
        from datetime import datetime
        dates = []
        for r in (reviews or []):
            d = r.get("fecha", "")
            if d:
                try:
                    dates.append(datetime.fromisoformat(d.replace("Z", "")))
                except Exception:
                    pass
        if not dates:
            return {}
        dates.sort()
        sample = len(dates)
        months_span = max(1, (dates[-1] - dates[0]).days / 30)
        reviews_per_month_avg = round(sample / months_span, 1)
        REVIEW_RATE_PCT = 7
        return {
            "sample_size": sample,
            "sample_date_from": dates[0].strftime("%Y-%m-%d"),
            "sample_date_to": dates[-1].strftime("%Y-%m-%d"),
            "sample_months_span": round(months_span, 1),
            "reviews_per_month_avg": reviews_per_month_avg,
            "review_rate_pct": REVIEW_RATE_PCT,
            "total_reviews_google": total_reviews,
            "est_total_patients": int(total_reviews / (REVIEW_RATE_PCT / 100)),
            "est_patients_per_month": int(reviews_per_month_avg / (REVIEW_RATE_PCT / 100)),
            "ticket_promedio_mxn": 1500,
            "est_monthly_revenue_mxn": int(reviews_per_month_avg / (REVIEW_RATE_PCT / 100) * 1500),
        }
    except Exception:
        return {}


def _format_patient_estimates(stats: dict) -> str:
    """Formatea las estadísticas como texto legible para el prompt."""
    parts = []
    if stats.get("total_reviews_google"):
        parts.append(f"Total reseñas Google: {stats['total_reviews_google']}")
    if stats.get("sample_size"):
        parts.append(f"Muestra analizada: {stats['sample_size']} reseñas")
    if stats.get("sample_date_from") and stats.get("sample_date_to"):
        parts.append(f"Periodo muestra: {stats['sample_date_from']} a {stats['sample_date_to']}")
    if stats.get("reviews_per_month_avg"):
        parts.append(f"Reseñas/mes (muestra): {stats['reviews_per_month_avg']}")
    if stats.get("est_total_patients"):
        parts.append(f"Pacientes estimados totales: {stats['est_total_patients']:,}")
    if stats.get("est_patients_per_month"):
        parts.append(f"Pacientes/mes estimados: {stats['est_patients_per_month']:,}")
    if stats.get("est_monthly_revenue_mxn"):
        parts.append(f"Ingresos mensuales est. (ticket $1,500 MXN): ${stats['est_monthly_revenue_mxn']:,} MXN")
    return " | ".join(parts)