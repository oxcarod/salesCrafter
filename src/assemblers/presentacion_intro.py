"""
Presentacion Intro Assembler — Genera slides de la Presentación Introductoria.

Las slides se renderizan como JSON con contenido estructurado.
El exportador HTML las muestra como presentación interactiva con Reveal.js.
"""

from typing import Any
import logging

logger = logging.getLogger(__name__)


# Definición de las 9 slides con sus fuentes de bloques
SLIDE_DEFINITIONS = [
    {
        "num": 1,
        "titulo": "Portada",
        "tipo": "estatico",
        "contenido": "prospecto_name",
    },
    {
        "num": 2,
        "titulo": "Tu Score",
        "tipo": "bloque",
        "bloque_tipo": "hook_dinero",
        "campos": ["headline", "resumen"],
    },
    {
        "num": 3,
        "titulo": "Top 3 Fortalezas",
        "tipo": "bloque",
        "bloque_tipo": "fortalezas",
        "campos": ["fortalezas"],
    },
    {
        "num": 4,
        "titulo": "Áreas de Oportunidad",
        "tipo": "bloque",
        "bloque_tipo": "oportunidades",
        "campos": ["oportunidades"],
    },
    {
        "num": 5,
        "titulo": "Niveles de Servicio",
        "tipo": "estatico",
        "template": "niveles",
    },
    {
        "num": 6,
        "titulo": "Equipos + Financiamiento",
        "tipo": "estatico",
        "template": "equipos",
    },
    {
        "num": 7,
        "titulo": "Beneficios de Expandir",
        "tipo": "estatico",
        "template": "beneficios",
    },
    {
        "num": 8,
        "titulo": "Proyección de Crecimiento",
        "tipo": "bloque",
        "bloque_tipo": "hook_dinero",
        "campos": ["datos_concretos"],
    },
    {
        "num": 9,
        "titulo": "Próximos Pasos",
        "tipo": "estatico",
        "template": "cta",
    },
]


class PresentacionIntro:
    """
    Ensambla la presentación introductoria con slides estructuradas.

    Uso:
        assembler = PresentacionIntro(place_id, prospecto, params)
        slides = assembler.get_slides()
        # → [{num, titulo, html, tipo, es_static}]
    """

    STATIC_CONTENT = {
        "niveles": {
            "titulo": "Niveles de Servicio",
            "niveles": [
                {"nombre": "N1 — Monitoreo Mensual", "precio": "$499/mes", "tiempo": "1-2 años", "incluye": [
                    "Monitoreo mensual de presencia digital",
                    "Análisis de métricas y recomendaciones",
                    "Asesoría mensual",
                ]},
                {"nombre": "N2 — Ejecución Activa", "precio": "$3,500/mes", "tiempo": "~1 año", "incluye": [
                    "Todo lo de N1, más:",
                    "Ejecución de acciones del mes",
                    "Gestión de redes sociales",
                    "Reporte quincenal",
                ]},
                {"nombre": "N3 — Gestión Completa", "precio": "$10,000/mes", "tiempo": "4-6 meses", "incluye": [
                    "Todo lo de N2, más:",
                    "Gestión completa de presencia digital",
                    "Contenido profesional",
                    "Reporte semanal",
                    "Secret Shopper (cliente misterioso)",
                ]},
            ],
        },
        "equipos": {
            "titulo": "Equipos + Financiamiento",
            "intro": "Podemos ayudarles a equipar su clínica con las mejores marcas del mercado y financiamiento accesible.",
            "ejemplo": {
                "equipo": "Equipo de fisioterapia/rehabilitación",
                "mensualidad": "~$3,500/mes a 24 meses",
                "punto_equilibrio": "~2 pacientes/mes con el equipo",
                "ganancia_estimada": "$8,000+ MXN/mes después del punto de equilibrio",
            },
        },
        "beneficios": {
            "titulo": "Beneficios de Expandir Servicios",
            "beneficios": [
                "Fuente de ingresos adicional recurrente",
                "Mayor retención de pacientes (vuelven para tratamientos)",
                "Diferenciación vs. la competencia",
                "Mayor valor percibido de la clínica",
                "Equipo que se paga solo",
            ],
        },
        "cta": {
            "titulo": "Próximos Pasos",
            "pasos": [
                "Aceptar el diagnóstico y seleccionar nivel de servicio",
                "Agendar fecha de inicio",
                "Primeros resultados visibles en 30-60 días",
            ],
            "cierre": "¿Cuándo quieren empezar — mañana o la siguiente semana?",
        },
    }

    def __init__(self, place_id: str, prospecto: dict, params: dict):
        self.place_id = place_id
        self.prospecto = prospecto
        self.params = params
        self._load_bloques()

    def _load_bloques(self):
        from cache_reader import CacheReader
        reader = CacheReader()
        bloque_ids = self.params.get("bloque_ids", [
            "hook_dinero", "oportunidades", "fortalezas",
            "comparativa_competitiva", "insight_estrategico",
        ])
        self.bloques = {}
        for bid in bloque_ids:
            b = reader.get_bloque(self.place_id, bid)
            if b:
                self.bloques[bid] = b

    def get_slides(self) -> list[dict]:
        """Retorna lista de slides con contenido HTML."""
        slides = []
        for defn in SLIDE_DEFINITIONS:
            slide = self._build_slide(defn)
            slides.append(slide)
        return slides

    def _build_slide(self, defn: dict) -> dict:
        num = defn["num"]
        titulo = defn.get("titulo", f"Slide {num}")
        tipo = defn.get("tipo", "estatico")

        if tipo == "estatico":
            template = defn.get("template", "")
            html = self._render_static(template, titulo, num)
        else:
            bloque_tipo = defn.get("bloque_tipo", "")
            campos = defn.get("campos", [])
            html = self._render_bloque_slide(bloque_tipo, campos, titulo, num)

        return {
            "num": num,
            "titulo": titulo,
            "html": html,
            "tipo": tipo,
            "es_static": tipo == "estatico",
        }

    def _render_static(self, template: str, titulo: str, num: int) -> str:
        if template == "niveles":
            return self._render_slide_niveles(titulo)
        elif template == "equipos":
            return self._render_slide_equipos(titulo)
        elif template == "beneficios":
            return self._render_slide_beneficios(titulo)
        elif template == "cta":
            return self._render_slide_cta(titulo)
        else:
            return f'<div class="slide-content"><h2>{titulo}</h2><p>Contenido pendiente...</p></div>'

    def _render_bloque_slide(self, bloque_tipo: str, campos: list, titulo: str, num: int) -> str:
        bloque = self.bloques.get(bloque_tipo)
        if not bloque:
            return f'<div class="slide-content"><h2>{titulo}</h2><p class="empty">Bloque no disponible. Selecciona este bloque en el editor.</p></div>'

        contenido = bloque.get("contenido", {})

        if bloque_tipo == "hook_dinero":
            headline = contenido.get("headline", "")
            resumen = contenido.get("resumen", "")
            datos = contenido.get("datos_concretos", [])

            datos_html = ""
            for d in datos:
                if isinstance(d, dict):
                    datos_html += f'<div class="dato-item"><span class="dato-label">{d.get("label","")}</span><span class="dato-val">{d.get("valor","")}</span></div>'

            return f"""
<div class="slide-content slide-score">
  <div class="score-number" style="font-size:4em; font-weight:bold; color:#e94560; text-align:center; margin:20px 0;">{headline}</div>
  <div class="score-resumen" style="font-size:1.1em; text-align:center; margin:10px 0 30px;">{resumen}</div>
  <div class="score-datos">{datos_html}</div>
</div>"""

        elif bloque_tipo == "fortalezas":
            conclusion = contenido.get("conclusion", "(sin conclusión)")
            return f'<div class="slide-content"><h2>{titulo}</h2><div class="conclusion-text" style="font-size:1.2em; line-height:1.6;">{conclusion}</div></div>'

        elif bloque_tipo == "oportunidades":
            conclusion = contenido.get("conclusion", "(sin conclusión)")
            return f'<div class="slide-content"><h2>{titulo}</h2><div class="conclusion-text" style="font-size:1.2em; line-height:1.6;">{conclusion}</div></div>'

        elif bloque_tipo == "comparativa_competitiva":
            conclusion = contenido.get("conclusion", "(sin conclusión)")
            return f'<div class="slide-content"><h2>{titulo}</h2><div class="conclusion-text" style="font-size:1.2em; line-height:1.6;">{conclusion}</div></div>'

        elif bloque_tipo == "insight_estrategico":
            conclusion = contenido.get("conclusion", "(sin conclusión)")
            return f'<div class="slide-content slide-insight"><h2>{titulo}</h2><div class="conclusion-text" style="font-size:1.3em; font-weight:bold; line-height:1.6;">{conclusion}</div></div>'

        else:
            return f'<div class="slide-content"><h2>{titulo}</h2><pre style="font-size:0.7em; overflow:auto; max-height:400px;">{str(contenido)[:500]}</pre></div>'

    def _render_slide_niveles(self, titulo: str) -> str:
        data = self.STATIC_CONTENT["niveles"]
        niveles_html = ""
        for n in data["niveles"]:
            inc_html = "".join(f"<li>{i}</li>" for i in n["incluye"])
            niveles_html += f"""
<div class="nivel-card">
  <h3>{n['nombre']}</h3>
  <div class="nivel-precio">{n['precio']}</div>
  <div class="nivel-tiempo">Resultados en {n['tiempo']}</div>
  <ul>{inc_html}</ul>
</div>"""
        return f'<div class="slide-content slide-niveles"><h2>{titulo}</h2><div class="niveles-grid">{niveles_html}</div></div>'

    def _render_slide_equipos(self, titulo: str) -> str:
        data = self.STATIC_CONTENT["equipos"]
        ex = data["ejemplo"]
        return f"""
<div class="slide-content slide-equipos">
  <h2>{titulo}</h2>
  <p class="intro">{data['intro']}</p>
  <div class="ejemplo-equipo">
    <h3>Ejemplo:</h3>
    <p><strong>Equipo:</strong> {ex['equipo']}</p>
    <p><strong>Mensualidad:</strong> {ex['mensualidad']}</p>
    <p><strong>Punto de equilibrio:</strong> {ex['punto_equilibrio']}</p>
    <p><strong>Ganancia estimada:</strong> {ex['ganancia_estimada']}</p>
  </div>
</div>"""

    def _render_slide_beneficios(self, titulo: str) -> str:
        data = self.STATIC_CONTENT["beneficios"]
        items = "".join(f"<li>{b}</li>" for b in data["beneficios"])
        return f'<div class="slide-content slide-beneficios"><h2>{titulo}</h2><ul class="beneficios-list">{items}</ul></div>'

    def _render_slide_cta(self, titulo: str) -> str:
        data = self.STATIC_CONTENT["cta"]
        pasos = "".join(f"<li>{p}</li>" for p in data["pasos"])
        return f"""
<div class="slide-content slide-cta">
  <h2>{titulo}</h2>
  <ol class="pasos-list">{pasos}</ol>
  <div class="cierre-cta">{data['cierre']}</div>
  <div class="contacto">Varkos — Strategic Advice<br>Oscar<br>[Teléfono/WhatsApp]</div>
</div>"""