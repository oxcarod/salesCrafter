"""
Bloque Generator — Motor que genera contenido de bloques usando Claude Code.

El flujo:
1. Recibe tipo de bloque + place_id + fuentes seleccionadas
2. Lee datos de UnifiedCache (y/u otros bloques) para cada fuente
3. Construye el prompt con el template del prompt_builder
4. Llama a Claude Code --print
5. Parsea la respuesta → valida JSON
6. Verifica idioma (español mexicano, sin CJK/cirílico/etc.)
7. Retorna el dict del bloque listo para guardar
"""

import json
import logging
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Any

from .prompt_builder import BLOQUE_TEMPLATES, SCHEMAS, get_template, get_schema

logger = logging.getLogger(__name__)

# ─── Verificación de idioma ─────────────────────────────────────────────────

_CJK_PATTERN = re.compile(r'[一-鿿　-〿⺀-⻿㐀-䶿]')
_NON_LATIN_SCRIPT = re.compile(r'[Ѐ-ӿ؀-ۿऀ-ॿ]')
_FOREIGN_PATTERNS = re.compile(
    r'\b(muito|bom dia|obrigado|obrigada|porque nao|qual e|tudo bem|ate mais|'
    r'spasibo|zdravstvuy|horosho|plokho|dostupno|kogda|potomu chto)\b',
    re.IGNORECASE
)


def _has_language_issue(text: str) -> bool:
    """Detecta CJK, cirílico, o palabras en portugués/ruso transliteradas."""
    if not text:
        return False
    if _CJK_PATTERN.search(text):
        return True
    if _NON_LATIN_SCRIPT.search(text):
        return True
    if _FOREIGN_PATTERNS.search(text):
        return True
    return False


def _verify_and_clean(data: dict, max_retries: int = 2) -> dict:
    """
    Verifica que todo el contenido esté en español mexicano.
    Si encuentra CJK u otros problemas, intenta limpiar.
    """
    def _check_dict(d: dict) -> bool:
        for key, val in d.items():
            if isinstance(val, str) and val.strip():
                if _CJK_PATTERN.search(val):
                    return True
                if _NON_LATIN_SCRIPT.search(val):
                    return True
                if _FOREIGN_PATTERNS.search(val):
                    return True
            elif isinstance(val, dict):
                if _check_dict(val):
                    return True
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, dict) and _check_dict(item):
                        return True
                    elif isinstance(item, str) and _has_language_issue(item):
                        return True
        return False

    current = data
    json_str = json.dumps(current, ensure_ascii=False)

    # Strip CJK directly first (same approach as salesSystem)
    had_cjk = bool(_CJK_PATTERN.search(json_str))
    if had_cjk:
        json_str = _CJK_PATTERN.sub('', json_str)
        try:
            current = json.loads(json_str)
            logger.info("[bloque_gen] CJK eliminados directamente")
        except json.JSONDecodeError:
            pass

    # Si aún hay issues, intentar con LLM
    if _check_dict(current):
        cleaned = _retry_clean_with_llm(current, max_retries)
        if cleaned:
            return cleaned

    return current


def _retry_clean_with_llm(data: dict, max_retries: int) -> dict:
    """Reintenta limpieza de idioma con Claude Code."""
    json_str = json.dumps(data, ensure_ascii=False)

    clean_prompt = (
        "El siguiente JSON fue generado por un LLM. Contiene errores de idioma.\n"
        "Tu tarea: limpiar TODO el contenido para que esté en español mexicano.\n\n"
        "REGLAS:\n"
        "1. Elimina TODOS los caracteres chinos/japoneses/coreanos (CJK).\n"
        "2. Traduce cualquier texto en otros idiomas al español mexicano.\n"
        "3. Excepciones que NO deben traducirse: SEO, ROI, CRM, Google, Facebook, "
        "Instagram, TikTok, WhatsApp, SMS, email, URL, GPS, KPIs.\n"
        "4. NO modifiques la estructura ni las keys del JSON.\n"
        "5. NO cambies números, fechas ni identificadores.\n"
        "6. Responde SOLO con el JSON corregido, sin comentarios ni markdown.\n\n"
        "JSON a limpiar:\n" + json_str
    )

    for _ in range(max_retries):
        try:
            result = subprocess.run(
                ["claude", "--print", "--dangerously-skip-permissions", clean_prompt],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=120,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode != 0 or not result.stdout.strip():
                break
            raw = result.stdout.strip()
            json_start = raw.find("{")
            json_end = raw.rfind("}")
            if json_start != -1 and json_end != -1:
                clean = raw[json_start:json_end + 1]
                try:
                    candidate = json.loads(clean)
                    # Verify no issues
                    json_check = json.dumps(candidate, ensure_ascii=False)
                    if not _CJK_PATTERN.search(json_check) and not _FOREIGN_PATTERNS.search(json_check):
                        return candidate
                except json.JSONDecodeError:
                    pass
        except Exception:
            break

    return data


# ─── Bloque Generator ──────────────────────────────────────────────────────

class BloqueGenerator:
    """
    Genera bloques de contenido usando Claude Code.

    Uso:
        gen = BloqueGenerator()
        bloque = gen.generate(
            bloque_type="hook_dinero",
            place_id="ChIJxxxx",
            fuentes=["maps_audit", "services", "review_insights"],
            prompt_extra=""
        )
    """

    def __init__(self):
        self.cache_reader = self._import_cache_reader()

    def _import_cache_reader(self):
        """Lazy import para evitar circular dependency."""
        try:
            from ..cache_reader import CacheReader
            return CacheReader()
        except ImportError:
            # fallback: usar path absoluto
            import sys
            sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
            from cache_reader import CacheReader
            return CacheReader()

    def generate(
        self,
        bloque_type: str,
        place_id: str,
        fuentes: Optional[list[str]] = None,
        prompt_extra: str = "",
        nombre: str = "",
    ) -> dict:
        """
        Genera un bloque de contenido.

        Args:
            bloque_type: tipo de bloque (hook_dinero, oportunidades, etc.)
            place_id: Google Maps place ID
            fuentes: fuentes a usar. Si None, usa fuentes_default del template.
                     Puede ser:
                     - lista de secciones (backward compat): ["maps_audit", "review_insights"]
                     - dict de fuentes: {"maps_audit": ["Score General"], "review_insights": []}
            prompt_extra: texto libre del usuario (para bloques personalizados o para
                         enriquecer el prompt base del template)
            nombre: nombre personalizado para el bloque
        """
        template = get_template(bloque_type)
        if not template:
            raise ValueError(f"Tipo de bloque desconocido: {bloque_type}")

        # Normalizar fuentes
        if fuentes is None:
            fuentes = list(template.get("fuentes_default", {}).keys())
            # Construir dict desde fuentes_default
            fuentes_dict_input = {
                sec: list(subs) for sec, subs in template.get("fuentes_default", {}).items()
            }
        elif isinstance(fuentes, list):
            # Legacy: lista de secciones — usar fuentes_default para subs
            fuentes_dict_input = self._normalize_fuentes(fuentes, template.get("fuentes_default", {}))
        elif isinstance(fuentes, dict):
            # Dict explícito {section: [subs]} — solo las seleccionadas, sin defaults
            fuentes_dict_input = fuentes

        # 1. Cargar datos de cada fuente
        source_data = self._load_sources(place_id, fuentes_dict_input)

        # 2. Construir el prompt
        prompt = self._build_prompt_with_data(template, place_id, fuentes_dict_input, source_data, prompt_extra)

        # 3. Llamar a Claude Code
        logger.info(f"[bloque_gen] Generando {bloque_type} para {place_id} con fuentes {fuentes}")
        raw_response = self._call_claude(prompt)

        if not raw_response:
            raise RuntimeError("Claude Code no devolvió respuesta")

        # 4. Parsear JSON — con retry si falla
        contenido = self._parse_with_retry(raw_response, bloque_type, source_data, prompt)
        if not contenido:
            raise RuntimeError("No se pudo parsear la respuesta de Claude como JSON")

        # 5. Verificar idioma
        contenido = _verify_and_clean(contenido)

        # 6. Armar el bloque completo
        now = datetime.now().isoformat()
        bloque_id = self._make_bloque_id(bloque_type, place_id)

        bloque = {
            "id": bloque_id,
            "tipo": bloque_type,
            "nombre": nombre or f"{template['nombre']} — {self._get_prospect_name(place_id)}",
            "autogenerar": True,
            "fuentes": fuentes,
            "prompt_usado": prompt,   # prompt completo con DATOS (para enviar a Claude en regenerate)
            "prompt_custom": self._build_prompt_for_edit(template, prompt_extra),  # prompt sin DATOS (para UI/editar)
            "contenido": contenido,
            "metadata": {
                "created_at": now,
                "updated_at": now,
                "version": 1,
                "generado_por": "claude-code",
                "modelo_ia": "sonnet-4",
                "usuario_edito": False,
                "nota_editor": "",
            }
        }

        return bloque

    def regenerate(
        self,
        existing_bloque: dict,
        place_id: str,
        nuevas_fuentes: Optional[dict[str, list[str]]] = None,
        prompt_extra: str = "",
    ) -> dict:
        """
        Regenera un bloque existente con nuevas fuentes o prompt.
        Incrementa la versión y marca como re-generado.

        Si prompt_extra viene vacío del frontend → usa SIEMPRE el template actual,
        no el prompt_custom guardado (que puede ser de un template anterior).
        """
        bloque_type = existing_bloque.get("tipo", "bloque_personalizado")
        nombre = existing_bloque.get("nombre", "")

        # Si nuevas_fuentes está vacío o no se pasó, usar las fuentes del bloque existente
        if not nuevas_fuentes:
            nuevas_fuentes = existing_bloque.get("fuentes", {})

        # Si el usuario NO envió prompt_extra (regenerar desde sidebar sin abrir editor),
        # usar SIEMPRE el template actual para asegurar que usa prompts mejorados.
        # Esto evita que regenerar con prompts viejos muestre contenido con schemas viejo.
        if not prompt_extra:
            prompt_extra = ""  # generate() usará el template actual
        else:
            # Limpiar cualquier --- DATOS --- que haya quedado en el textarea
            prompt_extra = prompt_extra.split("--- DATOS ---")[0].strip()

        new_bloque = self.generate(
            bloque_type=bloque_type,
            place_id=place_id,
            fuentes=nuevas_fuentes,
            prompt_extra=prompt_extra,
            nombre=nombre,
        )

        # Preservar metadata original + marcar como regenerado
        old_meta = existing_bloque.get("metadata", {})
        new_bloque["id"] = existing_bloque.get("id", new_bloque["id"])
        new_bloque["autogenerar"] = existing_bloque.get("autogenerar", True)
        new_bloque["metadata"]["version"] = (old_meta.get("version", 0) or 0) + 1
        new_bloque["metadata"]["usuario_edito"] = False
        new_bloque["metadata"]["nota_editor"] = ""

        return new_bloque

    # ─── Internos ─────────────────────────────────────────────────────────

    def _normalize_fuentes(
        self,
        fuentes: list,
        fuentes_default: dict,
    ) -> dict[str, list[str]]:
        """
        Convierte fuentes al formato {section: [subsections]}.
        Si una sección viene explícitamente en fuentes (como dict), se usa tal cual.
        Las secciones en fuentes_default que NO vienen en fuentes se agregan automáticamente.
        """
        result: dict[str, list[str]] = {}

        for f in fuentes:
            if isinstance(f, dict):
                # Dict explícito {section: [subs]} — usar tal cual (vacío = vacío)
                for sec, subs in f.items():
                    result[sec] = subs if isinstance(subs, list) else []
            elif isinstance(f, str):
                # String: usar subs del fuentes_default
                if f not in result:
                    result[f] = list(fuentes_default.get(f) or [])

        # Agregar fuentes_default solo para secciones que NO vengan en result
        for sec, subs in fuentes_default.items():
            if sec not in result:
                result[sec] = list(subs)

        return result

    def _load_sources(self, place_id: str, fuentes: dict[str, list[str]]) -> dict[str, Any]:
        """
        Carga datos de las fuentes especificadas con selección de subsecciones.
        `fuentes` es un dict {section_key: [sub_labels]}.
        """
        from ..cache_reader import CacheReader

        reader = CacheReader()
        data = {}
        prospect_data = reader.get_prospect(place_id)
        data["_prospecto"] = prospect_data

        cache_sections = {
            "maps_audit": reader.get_maps_audit,
            "market_audit": reader.get_market_audit,
            "geo_audit": reader.get_geo_audit,
            "competitive_intel": reader.get_competitive_intel,
            "review_insights": reader.get_review_insights,
            "prospect_analysis": reader.get_prospect_analysis,
            "services": reader.get_services,
            "competitors": reader.get_competitors,
            "social_audit": lambda pid: reader.get_section(pid, "social_audit"),
            "photos": lambda pid: reader.get_section(pid, "photos"),
            "_patient_estimates": lambda pid: reader.get_section(pid, "_patient_estimates"),
        }

        for sec_key, subs_selected in fuentes.items():
            if sec_key in cache_sections:
                if subs_selected:
                    tree = reader.get_subsections(place_id)
                    section_tree = tree.get(sec_key, {})
                    for sub_label in subs_selected:
                        if sub_label in section_tree:
                            if sec_key not in data:
                                data[sec_key] = {}
                            data[sec_key][sub_label] = section_tree[sub_label]
                else:
                    data[sec_key] = cache_sections[sec_key](place_id)
            elif sec_key == "servicios_publicados":
                data["servicios_publicados"] = prospect_data.get("servicios_publicados") or []

        bloque_sources = [
            "hook_dinero", "oportunidades", "fortalezas",
            "comparativa_competitiva", "insight_estrategico",
            "slide_score", "temas_resenas", "servicios_oportunidad",
        ]
        for sec_key in fuentes:
            if sec_key in bloque_sources:
                bloque = reader.get_bloque(place_id, sec_key)
                if bloque:
                    data[sec_key] = bloque.get("contenido", {})

        return data

    def _build_prompt_for_edit(
        self,
        template: dict,
        prompt_extra: str,
    ) -> str:
        """
        Retorna el prompt_custom tal cual, sin los DATOS.
        Si viene vacío (bloque nuevo), usa el placeholder del template.
        """
        if "--- DATOS ---" in prompt_extra:
            return prompt_extra.split("--- DATOS ---")[0].strip()
        if prompt_extra.strip():
            return prompt_extra
        return template.get("prompt_custom_default", "")

    def _build_prompt_with_data(
        self,
        template: dict,
        place_id: str,
        fuentes: dict[str, list[str]],
        source_data: dict[str, Any],
        prompt_extra: str,
    ) -> str:
        """
        Construye el prompt completo con DATOS adjuntos al final.
        Este es el prompt que se envía a Claude Code.
        """
        prompt_base = self._build_prompt_for_edit(template, prompt_extra)
        datos_parts = self._build_datos_section(source_data, fuentes)
        if datos_parts:
            return prompt_base + "\n\n--- DATOS ---\n" + datos_parts
        return prompt_base

    def _build_datos_section(
        self,
        source_data: dict[str, Any],
        fuentes: list[str],
    ) -> str:
        """
        Construye el texto de DATOS adjuntando cada fuente seleccionada.
        Formato:
        sección: Subsección
        ---
        contenido
        """
        parts = []
        for sec_key, data in source_data.items():
            if sec_key.startswith("_") or not data:
                continue

            if isinstance(data, dict):
                # Es un dict de subsecciones (clave = label)
                sub_parts = []
                for sub_label, sub_text in data.items():
                    if sub_text and isinstance(sub_text, str):
                        sub_parts.append(f"{sec_key}: {sub_label}\n---\n{sub_text.strip()}")
                if sub_parts:
                    parts.append("\n\n".join(sub_parts))
            else:
                # Es una sección completa (backward compat) — convertir a texto
                text = self._section_to_text(sec_key, data)
                if text:
                    parts.append(f"{sec_key}\n---\n{text}")

        return "\n\n".join(parts)

    def _call_claude(self, prompt: str, timeout: int = 180) -> str:
        """Llama a Claude Code --print y retorna la respuesta."""
        instruction = (
            "Responde con SOLO un objeto JSON válido, sin markdown, sin explicaciones."
        )
        full_input = f"{instruction}\n\n{prompt}"

        try:
            result = subprocess.run(
                ["claude", "--print", "--dangerously-skip-permissions", full_input],
                input=full_input,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode != 0:
                logger.warning(f"[bloque_gen] Claude exit code {result.returncode}: {result.stderr[:200]}")
                return ""
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            logger.error("[bloque_gen] Timeout en llamada a Claude")
            return ""
        except Exception as e:
            logger.error(f"[bloque_gen] Error llamando a Claude: {e}")
            return ""

    def _parse_json_response(self, raw: str) -> Optional[dict]:
        """Extrae y parsea el JSON de la respuesta de Claude."""
        if not raw:
            return None

        json_start = raw.find("{")
        if json_start == -1:
            logger.warning("[bloque_gen] No se encontró JSON en la respuesta")
            return None

        json_str = raw[json_start:]
        json_end = json_str.rfind("}")
        if json_end != -1:
            json_str = json_str[:json_end + 1]

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"[bloque_gen] JSON decode error: {e}")
            return None

    def _parse_with_retry(
        self,
        raw: str,
        bloque_type: str,
        source_data: dict,
        original_prompt: str = "",
    ) -> Optional[dict]:
        """
        Intenta parsear JSON de la respuesta de Claude. Si falla, reintenta
        con un prompt de reparación que pide JSON limpio, hasta 2 veces.
        """
        max_retries = 2
        current_raw = raw

        for attempt in range(max_retries + 1):
            result = self._parse_json_response(current_raw)
            if result:
                return result

            if attempt < max_retries:
                logger.warning(f"[bloque_gen] Intento {attempt+1} falló, pedindo reparación JSON...")
                current_raw = self._request_json_repair(current_raw, bloque_type)
                if not current_raw:
                    break

        # Último intento: reconstruir desde el contenido más probable
        return self._parse_json_response(raw)

    def _request_json_repair(self, broken_raw: str, bloque_type: str) -> str:
        """Pide a Claude que arregle el JSON roto."""
        # Tomar solo los primeros 500 chars del raw para no enviar todo
        snippet = broken_raw[:800]

        repair_prompt = (
            f"Esta respuesta tiene un error de JSON. Corrígelo y responde SOLO con el JSON válido corregido.\n\n"
            f"Fragmento проблема:\n{snippet}\n\n"
            f"Responde SOLO con el JSON corregido, sin explicaciones ni markdown."
        )

        try:
            result = subprocess.run(
                ["claude", "--print", "--dangerously-skip-permissions", repair_prompt],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=60,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception as e:
            logger.warning(f"[bloque_gen] Repair attempt failed: {e}")
        return ""

    def _make_bloque_id(self, bloque_type: str, place_id: str) -> str:
        """Genera un ID único para el bloque."""
        safe_place = place_id.replace(":", "_").replace("/", "_")
        return f"{bloque_type}_{safe_place}"

    def _get_prospect_name(self, place_id: str) -> str:
        """Obtiene el nombre del prospecto para el nombre del bloque."""
        from ..cache_reader import CacheReader
        reader = CacheReader()
        data = reader.get_prospect(place_id)
        return data.get("name", "Prospecto")