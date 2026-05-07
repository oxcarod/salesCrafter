"""
Presentacion Dirigida Assembler — Genera slides de la Presentación Dirigida.

A diferencia de la Introductoria, esta incluye datos de la reunión
(stage confirmado, feedback del cliente, servicio propuesto).
"""

from typing import Any
import logging

from .presentacion_intro import PresentacionIntro

logger = logging.getLogger(__name__)


class PresentacionDirigida(PresentacionIntro):
    """
    Ensambla la presentación dirigida post-reunión.

    Hereda de PresentacionIntro — solo cambia el contenido de algunas slides
    basándose en los datos de la reunión.

    Uso:
        assembler = PresentacionDirigida(place_id, prospecto, {
            "stage": 3,
            "servicio_propuesto": "N2",
            "notas_reunion": "...",
            "bloque_ids_usar": ["hook_dinero", "oportunidades", "insight_dirigido"]
        })
        slides = assembler.get_slides()
    """

    def __init__(self, place_id: str, prospecto: dict, params: dict):
        self.params = params
        self.place_id = place_id
        self.prospecto = prospecto
        self.stage = params.get("stage")
        self.servicio = params.get("servicio_propuesto", "")
        self.notas = params.get("notas_reunion", "")
        self._load_bloques()

    def get_slides(self) -> list[dict]:
        slides = []

        # Slide 1: Portada personalizada
        slides.append(self._build_slide({
            "num": 1, "titulo": "Portada", "tipo": "estatico", "template": "portada_dirigida"
        }))

        # Slides 2-4: basadas en bloques con contenido de reunión
        for defn in [
            {"num": 2, "titulo": "Tu Score + Oportunidad", "tipo": "bloque",
             "bloque_tipo": "hook_dinero", "campos": ["headline", "resumen", "datos_concretos"]},
            {"num": 3, "titulo": "Tus Fortalezas (confirmadas)", "tipo": "bloque",
             "bloque_tipo": "fortalezas", "campos": ["fortalezas"]},
            {"num": 4, "titulo": "Oportunidades Prioritarias", "tipo": "bloque",
             "bloque_tipo": "oportunidades", "campos": ["oportunidades"]},
        ]:
            slides.append(self._build_slide(defn))

        # Slide 5: Propuesta personalizada según Stage
        slides.append(self._build_slide({
            "num": 5, "titulo": "Propuesta para Ti", "tipo": "estatico", "template": "propuesta_personalizada"
        }))

        # Slides 6-9: estáticas
        for defn in [
            {"num": 6, "titulo": "Equipos + Financiamiento", "tipo": "estatico", "template": "equipos"},
            {"num": 7, "titulo": "Proyección de Crecimiento", "tipo": "estatico", "template": "beneficios"},
            {"num": 8, "titulo": "Plan de 30 Días", "tipo": "estatico", "template": "plan_30_dias"},
            {"num": 9, "titulo": "Cierre", "tipo": "estatico", "template": "cierre_dirigido"},
        ]:
            slides.append(self._build_slide(defn))

        return slides

    def _render_static(self, template: str, titulo: str, num: int) -> str:
        if template == "portada_dirigida":
            nombre = self.prospecto.get("name", "Prospecto")
            stage_nombre = self._stage_nombre()
            servicio = self.servicio or "Por definir"
            from datetime import datetime
            fecha = datetime.now().strftime("%d de %B de %Y")
            return f"""
<div class="slide-content slide-portada">
  <h1 style="font-size:2.5em; color:#16213e;">{nombre}</h1>
  <p style="font-size:1.2em; color:#e94560; margin-top:10px;">Stage {self.stage or '?'}: {stage_nombre}</p>
  <p style="margin-top:20px;">Propuesta: <strong>{servicio}</strong></p>
  <p style="margin-top:30px; color:#888;">{fecha}</p>
  <p style="margin-top:20px; font-size:0.9em;">Varkos — Strategic Advice</p>
</div>"""

        elif template == "propuesta_personalizada":
            return self._render_slide_propuesta()

        elif template == "plan_30_dias":
            return self._render_slide_plan_30_dias()

        elif template == "cierre_dirigido":
            stage_nombre = self._stage_nombre()
            return f"""
<div class="slide-content slide-cierre">
  <h2>Próximos Pasos</h2>
  <p style="font-size:1.1em; margin-bottom:20px;">
    Clasificamos su negocio como <strong>Stage {self.stage or '?'}: {stage_nombre}</strong>.
  </p>
  <p style="font-size:1em; margin-bottom:20px;">{self.notas or 'A definir según la conversación...'}</p>
  <h3>¿Cuándo quieren empezar — mañana o la siguiente semana?</h3>
  <div class="contacto" style="margin-top:40px;">
    <strong>Varkos — Strategic Advice</strong><br>
    Oscar — [Teléfono/WhatsApp]
  </div>
</div>"""

        else:
            return super()._render_static(template, titulo, num)

    def _render_slide_propuesta(self) -> str:
        stage = self.stage
        if stage is None:
            stage = 1

        propuestas = {
            0: ("Audit de Mercado (gratis)", "Gratis", "Validar demanda en la zona antes de abrir"),
            1: ("N1 — Monitoreo", "$499/mes", "Publicar lo que ya ofrecen y construir presencia digital"),
            2: ("N1 + GBP", "$499/mes +", "Ser encontrados para lo que ya son especialistas"),
            3: ("N2 — Ejecución", "$3,500/mes", "Generar confianza suficiente para agendar"),
            4: ("N2 → N3", "$3,500 → $10,000/mes", "Sistema de retención y crecimiento sostenido"),
            5: ("N3 — Gestión Completa", "$10,000/mes", "Liberar al dueño del día a día"),
            6: ("N3 + Equipo", "$10,000/mes +", "Expandir fuentes de ingreso y estructura"),
        }

        nombre, precio, objetivo = propuestas.get(stage, propuestas[1])
        tiempos = {
            0: "N/A", 1: "1-2 años", 2: "1-2 años",
            3: "~1 año", 4: "~1 año", 5: "4-6 meses", 6: "4-6 meses"
        }

        return f"""
<div class="slide-content slide-propuesta">
  <h2>Propuesta para {self.prospecto.get('name', 'su negocio')}</h2>
  <div class="propuesta-servicio">
    <div class="propuesta-nombre">{nombre}</div>
    <div class="propuesta-precio">{precio}</div>
    <div class="propuesta-tiempo">Resultados en {tiempos.get(stage, '~1 año')}</div>
  </div>
  <div class="propuesta-objetivo">
    <strong>Objetivo:</strong> {objetivo}
  </div>
  <div class="propuesta-equipo">
    <strong>Equipo:</strong> {self._stage_equipo()}
  </div>
</div>"""

    def _render_slide_plan_30_dias(self) -> str:
        stage = self.stage or 1
        planes = {
            0: ["Confirmar demanda en la zona", "Configurar Google Business Profile"],
            1: ["Publicar servicios en Google", "Responder reseñas pendientes", "Configurar GBP completo"],
            2: ["Optimizar descripción de GBP", "Publicar servicios faltantes", "Revisar palabras clave"],
            3: ["Activar gestión de redes", "Implementar protocolo de respuesta", "Contenido de confianza"],
            4: ["Sistema de seguimiento post-consulta", "Programa de retención", "Generar referidos"],
            5: ["Externalizar gestión digital", "Documentar procesos", "Monitoreo semanal"],
            6: ["Identificar nueva fuente de ingreso", "Evaluar expansión de equipo", "Plan de crecimiento"],
        }
        items = planes.get(stage, planes[1])
        items_html = "".join(f"<li>{item}</li>" for item in items)
        return f"""
<div class="slide-content slide-plan">
  <h2>Plan de 30 Días</h2>
  <ol class="plan-list">{items_html}</ol>
</div>"""

    def _stage_nombre(self) -> str:
        names = {
            0: "Pre-Revenue", 1: "Fundaciones", 2: "Tráfico",
            3: "Conversión", 4: "Retención", 5: "Optimización", 6: "Escalabilidad"
        }
        return names.get(self.stage, "Por definir")

    def _stage_equipo(self) -> str:
        equipo_textos = {
            0: "Cuando confirmen demanda, el equipo se justifica con los primeros pacientes.",
            1: "Al publicar nuevos servicios, si hay demanda real, el equipo se paga solo.",
            2: "Si hay demanda para rehabilitación, el equipo permite atender más sin más doctores.",
            3: "El equipo quirúrgico genera confianza antes de que llegue el paciente.",
            4: "Un programa de rehabilitación con equipo es el mejor motivo para regresar.",
            5: "El Plan de Rehabilitación Integral requiere equipo especializado.",
            6: "Segunda ubicación o nuevo servicio especializado — el equipo es infraestructura.",
        }
        return equipo_textos.get(self.stage, "")