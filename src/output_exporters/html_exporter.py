"""
HTML Exporter — Exporta entregables como HTML autónomo.

Genera un archivo HTML completo con CSS inline, listo para imprimir o compartir.
"""

import io
from typing import Any
import logging
import re

logger = logging.getLogger(__name__)


class HtmlExporter:
    """
    Exporta entregables como HTML.
    """

    def __init__(self, place_id: str, prospecto: dict, params: dict):
        self.place_id = place_id
        self.prospecto = prospecto
        self.params = params

    def export(self) -> tuple[str, str, io.BytesIO]:
        """Retorna (filename, mimetype, data_bytes)."""
        tipo = self.params.get("tipo_entregable", "carta_teaser")

        if tipo == "carta_teaser":
            html = self._render_carta_teaser()
        else:
            html = self._render_fallback()

        buf = io.BytesIO(html.encode("utf-8"))
        nombre = self.prospecto.get("name", "Prospecto").replace(" ", "_")
        filename = f"Entregable_{tipo}_{nombre}.html"
        return filename, "text/html; charset=utf-8", buf

    def _render_carta_teaser(self) -> str:
        """Renderiza la carta teaser como HTML completo."""
        from cache_reader import CacheReader
        from assemblers._bloque_renderer import render_bloque_html
        import re

        reader = CacheReader()
        nombre = self.prospecto.get("name", "[Nombre del Prospecto]")
        editor_content = self.params.get("contenido_editor", "")

        # Cargar bloques: si hay marcadores en el editor, cargar todos
        bloque_ids = self.params.get("bloque_ids", [])
        editor_has_markers = bool(re.findall(r'\[bloque:\w+\]', editor_content))

        if editor_has_markers:
            all_bloques_meta = reader.list_bloques(self.place_id)
            bloques = {}
            for bmeta in all_bloques_meta:
                bid = bmeta.get("id")
                if bid:
                    full = reader.get_bloque(self.place_id, bid)
                    if full:
                        bloques[bid] = full
        else:
            bloques = {}
            for bid in bloque_ids:
                b = reader.get_bloque(self.place_id, bid)
                if b:
                    bloques[bid] = b

        def replace_bloque_marker(match):
            bloque_tipo = match.group(1)
            for bid, b in bloques.items():
                if b.get("tipo") == bloque_tipo:
                    return render_bloque_html(b)
            return f'<em style="color:#999">[bloque:{bloque_tipo} — no encontrado]</em>'

        # Reemplazar marcadores en el contenido del editor
        if editor_content:
            body_html = re.sub(
                r'\[bloque:(\w+)\](.*?)\[/bloque\]',
                replace_bloque_marker,
                editor_content,
                flags=re.DOTALL,
            )
            # Convertir párrafos restantes a HTML
            body_parts = []
            for para in body_html.split('\n\n'):
                p = para.strip()
                if not p:
                    continue
                if p.startswith('<div') or p.startswith('<span') or p.startswith('<em'):
                    body_parts.append(p)
                else:
                    safe = (p.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                              .replace('\n', '<br>'))
                    body_parts.append(f'<p>{safe}</p>')
            body_html = '\n'.join(body_parts)
        else:
            body_html = '<p><em>Selecciona bloques para ver el contenido...</em></p>'

        return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Carta Teaser — {nombre}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: Georgia, 'Times New Roman', serif;
    max-width: 700px;
    margin: 60px auto;
    padding: 50px 60px;
    background: #ffffff;
    color: #16213e;
    line-height: 1.75;
    box-shadow: 0 2px 20px rgba(0,0,0,0.08);
  }}
  .headline {{
    font-size: 1.5em;
    font-weight: bold;
    color: #e94560;
    margin: 24px 0 12px;
    line-height: 1.3;
  }}
  .resumen {{
    margin-bottom: 16px;
    color: #16213e;
  }}
  .dato {{
    font-size: 0.95em;
    margin: 4px 0;
    color: #444;
  }}
  .oportunidad {{
    background: #f8f9ff;
    border-left: 3px solid #e94560;
    padding: 10px 16px;
    margin: 10px 0;
    border-radius: 0 4px 4px 0;
  }}
  .bloque-wrapper {{
    margin: 16px 0;
  }}
  .cierre {{
    margin-top: 40px;
    padding-top: 24px;
    border-top: 1px solid #e0e0e0;
    color: #555;
    font-size: 0.92em;
    line-height: 1.7;
  }}
  .varkos {{
    margin-top: 16px;
    color: #16213e;
    font-weight: bold;
    font-size: 1em;
  }}
  @media print {{
    body {{ box-shadow: none; margin: 0; padding: 40px; }}
  }}
</style>
</head>
<body>

<p><strong>{nombre}</strong></p>

{body_html}

<div class="cierre">
  <p>Solo 20 espacios disponibles este mes para un análisis completo sin costo.</p>
  <p>También podemos ayudarles a equipar su clínica con las mejores marcas del mercado y financiamiento accesible.</p>
  <p class="varkos">Varkos — Strategic Advice<br>Oscar<br>[Teléfono/WhatsApp]</p>
</div>

</body>
</html>"""

    def _render_fallback(self) -> str:
        nombre = self.prospecto.get("name", "Prospecto")
        return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8">
<title>{nombre}</title>
<style>
  body {{ font-family: Georgia, serif; max-width: 700px; margin: 60px auto;
         padding: 40px; color: #16213e; }}
</style>
</head>
<body>
<p><strong>{nombre}</strong></p>
<p><em>Selecciona bloques para generar contenido...</em></p>
</body></html>"""