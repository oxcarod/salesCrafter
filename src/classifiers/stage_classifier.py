"""
Stage Classifier — Clasifica prospectos en Stage 0-6 según Expansion Framework de Varkos.

El Stage determina qué servicio proponer (N1/N2/N3) y cómo estructurar la propuesta.

Refs:
- Stage 0: Pre-Revenue — validación de demanda
- Stage 1: Fundaciones — oferta invisible/confusa
- Stage 2: Tráfico — no les encuentran
- Stage 3: Conversión — llegan pero no cierran
- Stage 4: Retención — pacientes no regresan
- Stage 5: Optimización — dueño es el sistema
- Stage 6: Escalabilidad — funciona sin dueño
"""

from typing import Optional


# Nombres legible de cada Stage
STAGE_NAMES = {
    0: "Pre-Revenue",
    1: "Fundaciones",
    2: "Tráfico",
    3: "Conversión",
    4: "Retención",
    5: "Optimización",
    6: "Escalabilidad",
}

# Servicio sugerido por Stage
STAGE_SERVICE = {
    0: "audit_gratis",
    1: "N1",
    2: "N1",
    3: "N2",
    4: "N2",
    5: "N3",
    6: "N3",
}

# Qué decir de equipo según Stage
STAGE_EQUIPO = {
    0: "Cuando confirmen que hay demanda para un servicio, el equipo se justifica con los primeros pacientes.",
    1: "Al publicar fisioterapia, por ejemplo, van a descubrir si hay demanda real. Si la hay, el equipo se paga solo.",
    2: "Ya hay demanda para rehabilitación — ahora la pregunta es si tienen capacidad.",
    3: "El equipo quirúrgico y los testimonios post-operatorios generan confianza antes de que llegue el paciente.",
    4: "Un programa de rehabilitación con equipo especializado es el mejor motivo para regresar a pacientes satisfechos.",
    5: "El Plan de Rehabilitación Integral requiere equipo especializado — eso es lo que propone la expansión.",
    6: "Segunda ubicación o nuevo servicio especializado — el equipo es la infraestructura de esa expansión.",
}


def classify_stage(prospect_data: dict) -> dict:
    """
    Clasifica el Stage de un prospecto según sus datos en UnifiedCache.

    Args:
        prospect_data: dict con campos de UnifiedCache normalizados
            Puede incluir: services, servicios_publicados, review_insights,
            maps_audit, market_audit, geo_audit, numero_reviews, calificacion, etc.

    Returns:
        dict con:
            stage (int 0-6),
            nombre (str): nombre legible del Stage,
            servicio_sugerido (str): N1/N2/N3 o audit_gratis,
            razonamiento (str): por qué se clasificó así,
            evidencia (list[str]): datos que sustentan la decisión
    """
    evidence = []
    score = _score_for_stage(prospect_data, evidence)
    return {
        "stage": score,
        "nombre": STAGE_NAMES[score],
        "servicio_sugerido": STAGE_SERVICE[score],
        "razonamiento": _reasoning(score, evidence),
        "evidencia": evidence,
        "equipo_habla": STAGE_EQUIPO[score],
    }


def _score_for_stage(data: dict, evidence: list) -> int:
    """Calcula el Stage basándose en los datos disponibles."""

    # ── Stage 0: Pre-Revenue ──────────────────────────────────────────────
    # No hay reviews, no hay website, acaba de abrir
    num_reviews = data.get("numero_reviews") or data.get("num_resenas") or 0
    website = data.get("sitio_web") or data.get("website") or ""
    if num_reviews < 3 and not website:
        evidence.append(f"Sin reseñas ({num_reviews}) y sin sitio web → probable negocio nuevo")
        return 0

    # ── Stage 1: Fundaciones (oferta invisible/confusa) ───────────────────
    services_real = []
    if isinstance(data.get("services"), dict):
        services_real = data["services"].get("real", [])
    elif isinstance(data.get("services"), list):
        services_real = data["services"]

    servicios_publicados = data.get("servicios_publicados") or []
    if len(services_real) > 0 and len(servicios_publicados) == 0:
        evidence.append(
            f"{len(services_real)} servicios detectados en web, 0 publicados en Google"
        )
        return 1
    if 0 < len(servicios_publicados) <= 3 and len(services_real) > len(servicios_publicados) * 2:
        evidence.append(
            f"Solo {len(servicios_publicados)} servicios publicados pero {len(services_real)} detectados"
        )
        return 1

    # ── Stage 2: Tráfico (no les encuentran) ──────────────────────────────
    rating = float(data.get("calificacion") or 0)
    if num_reviews > 10 and rating >= 4.0:
        # Buena reputación pero no aparecen para lo que buscan
        services_count = len(services_real) or len(servicios_publicados) or 0
        if services_count <= 5:
            evidence.append(
                f"{num_reviews} reseñas, {rating}★, pero solo {services_count} servicios publicados"
            )
            return 2

    # ── Stage 3: Conversión (llegan pero no cierran) ─────────────────────
    review_insights = data.get("review_insights") or {}
    if isinstance(review_insights, dict):
        fortalezas = review_insights.get("fortalezas") or []
        debilidades = review_insights.get("debilidades") or []
        # Si hay quejas de atención/trato/confianza (conversión)
        conversion_issues = [
            d for d in debilidades
            if any(k in d.lower() for k in [
                "trato", "atención", "confianza", "no regresó",
                "no volvieron", "cara", "caro", "tiempo de espera"
            ])
        ]
        if len(conversion_issues) >= 2:
            evidence.append(
                f"Problemas de conversión detectados: {len(conversion_issues)} temas relacionados"
            )
            return 3

        # Muchas reseñas sin respuesta → desconfianza
        temas = review_insights.get("temas") or []
        unanswered_temas = [t for t in temas if isinstance(t, dict)
                           and t.get("categoria") == "negativo"
                           and t.get("ejemplo_resena")]
        if len(unanswered_temas) >= 3:
            evidence.append(f"{len(unanswered_temas)} temas negativos en reseñas (confianza)")
            return 3

    # ── Stage 4: Retención (pacientes no regresan) ───────────────────────
    if isinstance(review_insights, dict):
        temas = review_insights.get("temas") or []
        retencion_issues = [
            t for t in temas
            if isinstance(t, dict)
            and any(k in t.get("nombre", "").lower() for k in [
                "regreso", "retorno", "repit", "seguimiento", "no volvió"
            ])
        ]
        if retencion_issues:
            evidence.append(f"Temas de retención detectados en reseñas")
            return 4

    # ── Stage 5: Optimización (dueño = sistema) ───────────────────────────
    if num_reviews > 50 and rating >= 4.0:
        # Ya tienen flujo pero dependen del dueño
        maps_audit = data.get("maps_audit") or {}
        oportunidades = maps_audit.get("oportunidades_negocio") or []
        if isinstance(oportunidades, list) and len(oportunidades) > 3:
            evidence.append(
                f"Alto volumen ({num_reviews} reseñas, {rating}★) con múltiples oportunidades pendientes"
            )
            return 5

    # ── Stage 6: Escalabilidad (funciona sin dueño, límite externo) ──────
    if num_reviews > 100 and rating >= 4.5:
        geo_audit = data.get("geo_audit") or {}
        secciones = geo_audit.get("secciones") or []
        if len(secciones) >= 5:
            evidence.append(
                f"Negocio consolidado ({num_reviews} reseñas, {rating}★), múltiples auditorías completas"
            )
            return 6

    # ── Default: Stage 2 (tráfico) si tiene reseñas pero no Stage claro ──
    if num_reviews >= 5:
        evidence.append(
            f"No se detectaron flags claros — clasificado por volumen: "
            f"{num_reviews} reseñas, {rating}★"
        )
        return 2

    evidence.append("Datos insuficientes — clasificación por defecto Stage 1")
    return 1


def _reasoning(stage: int, evidence: list) -> str:
    """Genera texto de razonamiento para presentar al cliente."""
    templates = {
        0: "El negocio parece estar iniciando. Lo primero es validar que hay demanda en la zona.",
        1: "Tienen más servicios de los que Google conoce. El primer paso es publicar lo que ya ofrecen.",
        2: "Tienen buena reputación pero no aparecen para lo que son especialistas. Hay que trabajar visibilidad.",
        3: "Ya les llegan pacientes pero no se traducen en citas. Hay que trabajar confianza y conversión.",
        4: "Los pacientes no regresan. Hay que implementar un sistema de seguimiento y relación.",
        5: "Ya generan bien pero el dueño está atrapado en el día a día. Hay que externalizar operaciones.",
        6: "El negocio funciona sin el dueño. El siguiente paso es identificar nuevas fuentes de ingreso.",
    }
    base = templates.get(stage, "")
    return base


def stage_to_spanish(stage: int) -> str:
    """Retorna el nombre del Stage en español."""
    names_es = {
        0: "Pre-Revenue",
        1: "Fundaciones",
        2: "Tráfico",
        3: "Conversión",
        4: "Retención",
        5: "Optimización",
        6: "Escalabilidad",
    }
    return names_es.get(stage, f"Stage {stage}")


def service_for_stage(stage: int) -> dict:
    """Retorna metadata del servicio sugerido para un Stage."""
    services = {
        0: {"nombre": "Audit de Mercado (gratis)", "precio": "Gratis", "tiempo": "N/A"},
        1: {"nombre": "N1 — Monitoreo", "precio": "$499/mes", "tiempo": "1-2 años"},
        2: {"nombre": "N1 — Monitoreo", "precio": "$499/mes", "tiempo": "1-2 años"},
        3: {"nombre": "N2 — Ejecución", "precio": "$3,500/mes", "tiempo": "~1 año"},
        4: {"nombre": "N2 — Ejecución", "precio": "$3,500/mes", "tiempo": "~1 año"},
        5: {"nombre": "N3 — Gestión Completa", "precio": "$10,000/mes", "tiempo": "4-6 meses"},
        6: {"nombre": "N3 + Equipo", "precio": "$10,000/mes +", "tiempo": "4-6 meses"},
    }
    return services.get(stage, services[1])