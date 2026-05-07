"""
Bloque Renderer — Renderiza un bloque como HTML con estilo para la carta teaser.
"""

from typing import Any


def render_bloque_html(bloque: dict) -> str:
    """Renderiza el contenido de un bloque como HTML con estilo."""
    contenido = bloque.get("contenido") or {}
    tipo = bloque.get("tipo", "")
    nombre = bloque.get("nombre", tipo)

    tipo_label = TIPO_LABELS.get(tipo, tipo.replace("_", " ").title())

    if tipo == "hook_dinero":
        return _render_hook_dinero(contenido, tipo_label)
    elif tipo in ("oportunidades", "fortalezas", "comparativa_competitiva",
                  "insight_estrategico", "servicios_oportunidad"):
        return _render_conclusion(contenido, tipo, tipo_label)
    elif tipo == "temas_resenas":
        return _render_temas_resenas(contenido, tipo_label)
    elif tipo == "slide_score":
        return _render_slide_score(contenido, tipo_label)
    else:
        return _render_generic(contenido, tipo_label)


TIPO_LABELS = {
    "hook_dinero": "Hook Dinero",
    "oportunidades": "Oportunidades",
    "fortalezas": "Fortalezas",
    "comparativa_competitiva": "Comparativa Competitiva",
    "insight_estrategico": "Insight Estratégico",
    "temas_resenas": "Temas de Reseñas",
    "servicios_oportunidad": "Servicios con Oportunidad",
    "slide_score": "Score",
}


def _tag(tipo: str) -> str:
    """Retorna la etiqueta HTML + color según tipo."""
    colors = {
        "hook_dinero": "#e94560",
        "oportunidades": "#7c3aed",
        "fortalezas": "#059669",
        "comparativa_competitiva": "#0369a1",
        "insight_estrategico": "#d97706",
        "temas_resenas": "#0891b2",
        "servicios_oportunidad": "#be185d",
        "slide_score": "#374151",
    }
    return colors.get(tipo, "#6b7280")


def _render_hook_dinero(contenido: Any, label: str) -> str:
    if isinstance(contenido, str):
        headline = contenido
        resumen = ""
        datos = []
    else:
        headline = contenido.get("headline", "") if isinstance(contenido, dict) else ""
        resumen = contenido.get("resumen", "") if isinstance(contenido, dict) else ""
        datos = contenido.get("datos_concretos", []) if isinstance(contenido, dict) else []

    parts = [f'<div class="bloque-wrapper" style="margin:16px 0;">']

    if headline:
        parts.append(
            f'<div class="bloque-headline" style="'
            f'background:#fff0f2;border-left:4px solid #e94560;'
            f'padding:12px 16px;border-radius:6px;margin-bottom:10px;">'
            f'<div style="font-size:0.72em;font-weight:700;color:#e94560;'
            f'text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px;">{label}</div>'
            f'<div style="font-size:1.1em;font-weight:700;color:#16213e;line-height:1.4;">{headline}</div>'
            f'</div>'
        )

    if resumen:
        parts.append(
            f'<div style="padding:0 4px 8px;font-size:0.95em;color:#374151;line-height:1.6;">{resumen}</div>'
        )

    if datos:
        parts.append('<div style="padding:4px 4px 0;">')
        for d in datos:
            if isinstance(d, dict):
                label_d = d.get("label", "")
                valor_d = d.get("valor", "")
                parts.append(
                    f'<div style="display:flex;gap:8px;padding:4px 0;border-bottom:1px solid #f0f0f0;font-size:0.9em;">'
                    f'<span style="color:#e94560;font-weight:600;flex-shrink:0;">•</span>'
                    f'<span style="color:#374151;"><strong>{label_d}</strong> {valor_d}</span>'
                    f'</div>'
                )
        parts.append('</div>')

    parts.append('</div>')
    return "".join(parts)


def _render_conclusion(contenido: Any, tipo: str, label: str) -> str:
    if isinstance(contenido, str):
        text = contenido
    else:
        text = (
            contenido.get("conclusion")
            or contenido.get("ventaja")
            or contenido.get("oportunidad")
            or ""
        )
    if not text:
        return f'<em style="color:#999">[sin contenido en {tipo}]</em>'

    color = _tag(tipo)
    parts = [
        f'<div class="bloque-wrapper" style="margin:16px 0;">',
        f'<div style="border-left:4px solid {color};padding:10px 14px;'
        f'background:#fafafa;border-radius:0 6px 6px 0;">',
        f'<div style="font-size:0.72em;font-weight:700;color:{color};'
        f'text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px;">{label}</div>',
        f'<div style="font-size:0.95em;color:#16213e;line-height:1.7;">{text}</div>',
        f'</div></div>',
    ]
    return "".join(parts)


def _render_temas_resenas(contenido: Any, label: str) -> str:
    if isinstance(contenido, str):
        resumen = contenido
        positivos, negativos, oportunidad = [], [], ""
    else:
        resumen = contenido.get("resumen", "") if isinstance(contenido, dict) else ""
        positivos = contenido.get("temas_positivos", []) if isinstance(contenido, dict) else []
        negativos = contenido.get("temas_negativos", []) if isinstance(contenido, dict) else []
        oportunidad = contenido.get("oportunidad_principal", "") if isinstance(contenido, dict) else ""

    parts = [
        f'<div class="bloque-wrapper" style="margin:16px 0;">',
        f'<div style="border-left:4px solid #0891b2;padding:10px 14px;'
        f'background:#fafafa;border-radius:0 6px 6px 0;">',
        f'<div style="font-size:0.72em;font-weight:700;color:#0891b2;'
        f'text-transform:uppercase;letter-spacing:0.06em;margin-bottom:8px;">{label}</div>',
    ]

    if resumen:
        parts.append(
            f'<div style="font-size:0.92em;color:#374151;line-height:1.6;'
            f'margin-bottom:10px;font-style:italic;">{resumen}</div>'
        )

    if positivos:
        parts.append('<div style="margin-bottom:8px;">')
        parts.append('<div style="font-size:0.75em;font-weight:700;color:#059669;margin-bottom:4px;">✓ LO QUE VALORAN</div>')
        for t in positivos:
            parts.append(f'<div style="font-size:0.88em;color:#374151;padding:2px 0;">• {t}</div>')
        parts.append('</div>')

    if negativos:
        parts.append('<div style="margin-bottom:8px;">')
        parts.append('<div style="font-size:0.75em;font-weight:700;color:#dc2626;margin-bottom:4px;">✗ LO QUEJAS</div>')
        for t in negativos:
            parts.append(f'<div style="font-size:0.88em;color:#374151;padding:2px 0;">• {t}</div>')
        parts.append('</div>')

    if oportunidad:
        parts.append(
            f'<div style="margin-top:8px;padding:8px 10px;background:#fff7ed;'
            f'border-radius:4px;font-size:0.88em;color:#92400e;">'
            f'<strong>OPORTUNIDAD:</strong> {oportunidad}</div>'
        )

    parts.append('</div></div>')
    return "".join(parts)


def _render_slide_score(contenido: dict, label: str) -> str:
    score = contenido.get("score", "")
    interp = contenido.get("interpretacion", "")
    hook = contenido.get("hook", "")
    ctx = contenido.get("contexto", "")

    parts = [
        f'<div class="bloque-wrapper" style="margin:16px 0;">',
        f'<div style="background:#16213e;color:white;padding:14px 18px;border-radius:8px;">',
        f'<div style="font-size:0.72em;font-weight:700;color:rgba(255,255,255,0.6);'
        f'text-transform:uppercase;letter-spacing:0.06em;margin-bottom:8px;">{label}</div>',
    ]
    if hook:
        parts.append(f'<div style="font-size:1.1em;font-weight:700;margin-bottom:6px;">{hook}</div>')
    if score or interp:
        parts.append(f'<div style="font-size:0.95em;opacity:0.8;">Score: {score} — {interp}</div>')
    if ctx:
        parts.append(f'<div style="font-size:0.88em;opacity:0.7;margin-top:4px;">{ctx}</div>')
    parts.append('</div></div>')
    return "".join(parts)


def _render_generic(contenido: Any, label: str) -> str:
    if isinstance(contenido, str):
        text = contenido
    elif isinstance(contenido, dict):
        entries = [(k, v) for k, v in contenido.items() if v]
        text = "\n".join(f"**{k}**: {v}" for k, v in entries)
    else:
        text = str(contenido)
    safe = (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace("\n", "<br>"))
    return (
        f'<div class="bloque-wrapper" style="margin:16px 0;">'
        f'<div style="border-left:4px solid #6b7280;padding:10px 14px;background:#fafafa;border-radius:0 6px 6px 0;">'
        f'<div style="font-size:0.72em;font-weight:700;color:#6b7280;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px;">{label}</div>'
        f'<div style="font-size:0.95em;color:#16213e;line-height:1.7;">{safe}</div>'
        f'</div></div>'
    )
