"""
Prompt Builder — Define tipos de bloque, schemas de salida y fuentes por defecto.

El usuario escribe su propio prompt en la UI.
El sistema adjunta "--- DATOS ---\n<contenido de las fuentes>" al prompt del usuario.
"""

# ─── Schemas de salida por tipo ─────────────────────────────────────────────────

SCHEMAS = {
    "hook_dinero": {
        "headline": "string — frase de impacto de 1 línea (ej: '~$12,000 MXN/mes sin capturar')",
        "resumen": "string — explicación de 2-3 oraciones del problema/oportunidad",
        "datos_concretos": [
            {"label": "string", "valor": "string"}
        ]
    },
    "oportunidades": {
        "conclusion": "string — conclusión directa de 2-4 oraciones en español mexicano"
    },
    "fortalezas": {
        "conclusion": "string — conclusión directa de 2-4 oraciones sobre lo que mejor hace el negocio"
    },
    "comparativa_competitiva": {
        "conclusion": "string — conclusión directa de 2-4 oraciones: en qué gana vs. la competencia"
    },
    "insight_estrategico": {
        "conclusion": "string — conclusión estratégica de 2-4 oraciones que el dueño debe recordar"
    },
    "slide_score": {
        "score": "number — score de 0-100",
        "interpretacion": "string — palabra corta: Crítico, Deficiente, Promedio, Bueno, Excelente",
        "contexto": "string — 1-2 oraciones",
        "hook": "string — frase de impacto del score",
    },
    "temas_resenas": {
        "resumen": "string — párrafo de 2-3 oraciones del sentir general",
        "temas_positivos": ["string — tema positivo"],
        "temas_negativos": ["string — tema negativo"],
        "oportunidad_principal": "string — la mayor oportunidad",
    },
    "servicios_oportunidad": {
        "conclusion": "string — conclusión directa de 2-4 oraciones sobre qué servicios publicar"
    },
    "bloque_personalizado": {
        "contenido": "string — texto libre",
    },
}


# ─── Templates por tipo ───────────────────────────────────────────────────────
# `fuentes_default` define las subsecciones seleccionadas al autogenerar.

BLOQUE_TEMPLATES = {

    "hook_dinero": {
        "nombre": "Hook Dinero",
        "descripcion": "Cuantifica en dinero el costo de no optimizar su presencia digital",
        "prompt_custom_default": "Analiza los datos y calcula cuanto dinero esta dejando ir el negocio cada mes por no tener su presencia digital optimizada. Responde con JSON: {headline, resumen, datos_concretos}",
        "fuentes_default": {
            "maps_audit": ["Resumen Ejecutivo", "Score General", "Presión Competitiva", "Gap de Servicios"],
            "review_insights": ["Resumen", "Insight"],
            "services": ["Servicios Reales", "Servicios por Reviews"],
            "_patient_estimates": ["Estimación de Pacientes"],
        },
    },

    "oportunidades": {
        "nombre": "Oportunidades",
        "descripcion": "La oportunidad digital más urgente con impacto directo en ingresos",
        "prompt_custom_default": "Identifica la oportunidad digital con mayor impacto en ingresos y explicala en 2-4 oraciones impactantes. Responde con JSON: {conclusion}",
        "fuentes_default": {
            "maps_audit": ["Resumen Ejecutivo", "Presión Competitiva", "Gap de Servicios"],
            "review_insights": ["Oportunidades", "Debilidades", "Insight"],
            "services": ["Servicios Reales", "Servicios por Reviews"],
        },
    },

    "fortalezas": {
        "nombre": "Fortalezas",
        "descripcion": "La ventaja secreta que convierte prospecto en cliente de Varkos",
        "prompt_custom_default": "Encuentra la fortaleza que mas impresione al dueno y que haga que quiera escuchar la propuesta de Varkos. Responde con JSON: {conclusion}",
        "fuentes_default": {
            "review_insights": ["Fortalezas del Negocio", "Temas Positivos", "Insight"],
            "maps_audit": ["Resumen del Perfil", "Findings", "Análisis de Reseñas"],
            "competitive_intel": ["Resumen"],
        },
    },

    "comparativa_competitiva": {
        "nombre": "Comparativa Competitiva",
        "descripcion": "Quién es, quién viene, y cómo ganar",
        "prompt_custom_default": "Presenta al dueno el panorama competitivo: quien le esta robando pacientes y como recuperarlos. Responde con JSON: {conclusion}",
        "fuentes_default": {
            "maps_audit": ["Resumen Ejecutivo", "Tabla Competitiva", "Presión Competitiva", "Score General"],
            "review_insights": ["Resumen", "Insight"],
            "competitive_intel": ["Resumen"],
        },
    },

    "insight_estrategico": {
        "nombre": "Insight Estratégico",
        "descripcion": "La única verdad que el dueño debe recordar sobre su clínica",
        "prompt_custom_default": "Di al dueno LA UNICA COSA que cambiara su negocio si la hace manana. Responde con JSON: {conclusion}",
        "fuentes_default": {
            "maps_audit": ["Resumen Ejecutivo", "Findings", "Presencia Online"],
            "review_insights": ["Insight", "Oportunidades", "Debilidades"],
            "competitive_intel": ["Resumen", "Análisis Competitivo"],
        },
    },

    "slide_score": {
        "nombre": "Slide de Score",
        "descripcion": "Score con interpretación y frase de impacto",
        "prompt_custom_default": "Genera el contenido de la slide de score: score 0-100, interpretacion, contexto, hook. Responde con JSON: {score, interpretacion, contexto, hook}",
        "fuentes_default": {
            "maps_audit": ["Score General", "Subscores"],
        },
    },

    "temas_resenas": {
        "nombre": "Temas de Reseñas",
        "descripcion": "Lo que los pacientes revelan que nadie les dice",
        "prompt_custom_default": "Analiza las reseñas. Identifica temas positivos y negativos, y di la oportunidad principal. Responde con JSON: {resumen, temas_positivos: [string], temas_negativos: [string], oportunidad_principal}",
        "fuentes_default": {
            "review_insights": ["Temas Positivos", "Temas Negativos", "Métricas", "Insight"],
            "maps_audit": ["Análisis de Reseñas"],
        },
    },

    "servicios_oportunidad": {
        "nombre": "Servicios con Oportunidad",
        "descripcion": "Qué servicios ofrecer pero no promocionan — y cuánto valen",
        "prompt_custom_default": "Identifica servicios que la clinica tiene pero no promociona y traducelos en dinero perdido. Responde con JSON: {conclusion}",
        "fuentes_default": {},
    },
}


def get_template(bloque_type: str) -> dict:
    """Retorna el template para un tipo de bloque, o None si no existe."""
    return BLOQUE_TEMPLATES.get(bloque_type)


def list_tipos() -> list[dict]:
    """Lista todos los tipos de bloque disponibles."""
    return [
        {
            "tipo": tipo,
            "nombre": tpl["nombre"],
            "descripcion": tpl["descripcion"],
            "fuentes_default": tpl.get("fuentes_default", {}),
        }
        for tipo, tpl in BLOQUE_TEMPLATES.items()
    ]


def get_schema(bloque_type: str) -> dict:
    """Retorna el schema de salida esperado para un tipo de bloque."""
    return SCHEMAS.get(bloque_type, {"contenido": "string — contenido libre del bloque"})