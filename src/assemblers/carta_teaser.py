"""
Carta Teaser Assembler — Ensambla la carta teaser con posicionamiento libre de bloques.

Usa dos fuentes de contenido:
1. Bloques generados guardados en blocks/{place_id}/
2. Texto libre del editor (posicionamiento en cursor)

El formato de salida es DOCX → PDF.
"""

from typing import Any
import logging

logger = logging.getLogger(__name__)


class CartaTeaser:
    """
    Ensambla y renderiza una Carta Teaser.

    Uso:
        assembler = CartaTeaser(place_id, prospecto, {"bloque_ids": ["hook_dinero"]})
        html = assembler.render_preview()
    """

    def __init__(self, place_id: str, prospecto: dict, params: dict):
        self.place_id = place_id
        self.prospecto = prospecto
        self.params = params
        self._load_bloques()

    def _load_bloques(self):
        """Carga bloques del prospecto. Si el editor contiene marcadores [bloque:tipo],
        carga TODOS los bloques del prospecto para resolverlos."""
        import re
        from cache_reader import CacheReader
        reader = CacheReader()

        editor_content = self.params.get("contenido_editor", "")

        # Detectar si hay marcadores de bloque en el contenido del editor
        marker_types = set(re.findall(r'\[bloque:(\w+)\]', editor_content))

        if marker_types:
            # Hay marcadores → cargar TODOS los bloques del prospecto
            all_bloques = reader.list_bloques(self.place_id)
            self.bloques = {}
            for bmeta in all_bloques:
                bid = bmeta.get("id")
                if bid:
                    full = reader.get_bloque(self.place_id, bid)
                    if full:
                        self.bloques[bid] = full
        else:
            # Solo cargar los bloques explícitamente seleccionados
            bloque_ids = self.params.get("bloque_ids", [])
            self.bloques = {}
            for bid in bloque_ids:
                bloque = reader.get_bloque(self.place_id, bid)
                if bloque:
                    self.bloques[bid] = bloque

    def render_preview(self) -> str:
        """Renderiza la carta como HTML para preview."""

        nombre_prospecto = self.prospecto.get("name", "[Nombre del Prospecto]")

        # Texto del editor o fallback con bloques
        editor_content = self.params.get("contenido_editor", "")

        if editor_content:
            # El usuario escribió contenido libre — renderizar con bloques sustituidos
            body_html = self._render_editor_content(editor_content)
        else:
            # Template por defecto: hook_dinero + oportunidades
            body_html = self._render_default()

        html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<style>
  body {{ font-family: Georgia, serif; max-width: 700px; margin: 60px auto;
         padding: 40px; background: #fff; color: #16213e; line-height: 1.7; }}
  .headline {{ font-size: 1.4em; font-weight: bold; color: #e94560; margin: 20px 0; }}
  .resumen {{ margin: 15px 0; }}
  .dato {{ margin: 5px 0; font-size: 0.95em; }}
  .cierre {{ margin-top: 30px; border-top: 1px solid #ddd; padding-top: 20px;
             color: #555; font-size: 0.9em; }}
  .varkos {{ color: #16213e; font-weight: bold; }}
  .bloque-field {{ background: #f0f4ff; border-left: 3px solid #e94560;
                  padding: 4px 8px; margin: 3px 0; display: block; }}
  .bloque-insertado {{ background: #eef2ff; border: 1px solid #c7d2fe;
                       padding: 10px; margin: 10px 0; border-radius: 4px; }}
</style>
</head>
<body>
<p>{nombre_prospecto}</p>

{body_html}

<div class="cierre">
  <p>Solo 20 espacios disponibles este mes para un análisis completo sin costo.</p>
  <p>También podemos ayudarles a equipar su clínica con las mejores marcas del mercado y financiamiento accesible.</p>
  <p class="varkos">Varkos — Strategic Advice<br>
  Oscar<br>
  [Teléfono/WhatsApp]</p>
</div>
</body>
</html>"""
        return html

    def _render_editor_content(self, content: str) -> str:
        """
        Renderiza el contenido del editor con bloques sustituidos.
        Soporta dos formatos:
        1. Marcadores nuevos: [bloque:tipo] contenido [/bloque]
        2. Marcadores legacy: {{bloque_id.campo}} (bloque.campo)
        """
        import re

        # ── Marcadores nuevos: [bloque:tipo] ... [/bloque] ──────────────────
        # Reemplaza TODO el bloque con contenido fresco de DB renderizado como HTML
        def replace_new_marker(match):
            bloque_tipo = match.group(1)
            _inline_content = match.group(2)  # contenido "stale" del textarea — se ignora
            # Buscar bloque por tipo en self.bloques
            bloque = None
            for bid, b in self.bloques.items():
                if b.get("tipo") == bloque_tipo:
                    bloque = b
                    break
            if not bloque:
                return f'<em style="color:#999">[bloque:{bloque_tipo} — no encontrado]</em>'
            html = self._render_bloque_html(bloque)
            return html

        # [bloque:tipo]contenido[/bloque] — el contenido puede incluir saltos de línea
        content = re.sub(
            r'\[bloque:(\w+)\](.*?)\[/bloque\]',
            replace_new_marker,
            content,
            flags=re.DOTALL,
        )

        # ── Marcadores legacy: {{bloque_id.campo}} ───────────────────────────
        pattern = re.compile(r'\{\{(\w+)\.([\w_]+)\}\}')

        def replace_legacy(match):
            bloque_id = match.group(1)
            campo = match.group(2)
            bloque = self.bloques.get(bloque_id, {})
            contenido = bloque.get("contenido", {})
            value = contenido
            for key in campo.split("."):
                if isinstance(value, dict):
                    value = value.get(key, f"[{bloque_id}.{campo}]")
                else:
                    value = f"[{bloque_id}.{campo}]"
            return f'<span class="bloque-insertado"><strong>{value}</strong></span>'

        content = pattern.sub(replace_legacy, content)

        # Convertir saltos de línea restantes en párrafos limpios
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        html_parts = []
        for p in paragraphs:
            if p.startswith('<div') or p.startswith('<span') or p.startswith('<em'):
                html_parts.append(p)
            else:
                # Párrafo normal — escapar HTML y convertir saltos de línea
                safe = (p.replace('&', '&amp;')
                          .replace('<', '&lt;')
                          .replace('>', '&gt;')
                          .replace('\n', '<br>'))
                html_parts.append(f'<p>{safe}</p>')

        return '\n'.join(html_parts)

    def _render_bloque_html(self, bloque: dict) -> str:
        """Renderiza un bloque completo como HTML con estilo."""
        from ._bloque_renderer import render_bloque_html
        return render_bloque_html(bloque)

    def _render_default(self) -> str:
        """Renderiza el template por defecto (hook_dinero + oportunidades)."""
        html_parts = []

        hook = self.bloques.get("hook_dinero")
        if hook:
            contenido = hook.get("contenido", {})
            headline = contenido.get("headline", "")
            resumen = contenido.get("resumen", "")
            datos = contenido.get("datos_concretos", [])

            html_parts.append(f'<div class="headline">{headline}</div>')
            if resumen:
                html_parts.append(f'<div class="resumen">{resumen}</div>')
            if datos:
                for d in datos:
                    if isinstance(d, dict):
                        label = d.get("label", "")
                        valor = d.get("valor", "")
                        html_parts.append(f'<div class="dato">• {label}: <strong>{valor}</strong></div>')

        ops = self.bloques.get("oportunidades")
        if ops:
            contenido = ops.get("contenido", {})
            conclusion = contenido.get("conclusion", "")
            if conclusion:
                html_parts.append(f'<p>{conclusion}</p>')

        if not html_parts:
            html_parts.append('<p><em>Selecciona bloques para ver el preview...</em></p>')

        return "\n".join(html_parts)

    def get_texto(self) -> str:
        """Retorna el texto plano de la carta para DOCX."""
        import re
        html = self.render_preview()
        # Strip HTML para texto plano
        text = re.sub(r'<[^>]+>', '', html)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        return text.strip()