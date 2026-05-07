# Ticket Promedio Ponderado — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implementar este plan tarea por tarea. Pasos usan checkbox (`- [ ]`) syntax para tracking.

**Goal:** Reemplazar el ticket fijo de $1,500 MXN con un ticket calculado ponderando precios de mercado (investigados con MCP minimax) × frecuencia de servicios detectados en reseñas.

**Arquitectura:** Nuevo módulo `estimate_ticket.py` que recibe los servicios detectados con su frecuencia, usa Claude Code con MCP minimax para investigar precios de mercado, calcula `sum(precio × frecuencia)` y guarda en `_patient_estimates`. Se ejecuta después del scrape como paso fire-and-forget.

**Tech Stack:** Python, Claude Code subprocess, MCP minimax, JSON cache.

---

## Archivos involucrados

- Create: `salesSystem/src/market_suite/scraper/estimate_ticket.py`
- Modify: `salesSystem/src/market_suite/scraper/apify_scraper.py:78-83`
- Modify: `salesSystem/src/market_suite/scraper/apify_scraper.py` (después de `cache.save()`)
- Test: ejecutar scrape manualmente y verificar `_patient_estimates.ticket_promedio_mxn` en debug UI

---

## Tareas

### Task 1: Crear `estimate_ticket.py`

**Files:**
- Create: `salesSystem/src/market_suite/scraper/estimate_ticket.py`

- [ ] **Step 1: Escribir el módulo completo**

```python
"""
Estimate Ticket — Calcula ticket promedio ponderado usando MCP minimax.

Flujo:
1. Recibe servicios detectados con frecuencia (de services_reviews)
2. Arma prompt para Claude con MCP minimax que busque precios de mercado
3. Calcula ticket = sum(precio_i * frecuencia_i)
4. Retorna dict con ticket + breakdown
"""

import subprocess
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_TICKET = 1500


def estimate_ticket(
    services_reviews: list[dict],
    zona: str = "",
    estado: str = "",
    cp: str = "",
    timeout: int = 90,
) -> dict:
    """
    Calcula ticket promedio ponderado.

    Args:
        services_reviews: lista de {nombre_servicio, menciones, frecuencia} de services_reviews
        zona: zona/barrio del negocio
        estado: estado/ciudad
        cp: código postal
        timeout: segundos antes de fallback

    Returns:
        dict con ticket_promedio_mxn, ticket_breakdown, ticket_source, metodo, fuentes_precio
    """
    if not services_reviews:
        logger.info("[estimate_ticket] No services_reviews, usando default $1,500")
        return _default_result("default")

    # Filtrar servicios con frecuencia > 0
    servicios_filtrados = [
        s for s in services_reviews
        if isinstance(s, dict) and s.get("menciones", 0) > 0
    ]
    if not servicios_filtrados:
        return _default_result("default")

    # Construir lista de servicios con frecuencia para el prompt
    servicios_text = "\n".join(
        f"- {s['nombre_servicio']}: {s.get('menciones', 0)} menciones ({s.get('frecuencia_pct', 0):.0%} de reseñas)"
        for s in servicios_filtrados
    )

    zona_full = ", ".join(filter(None, [zona, estado, cp]))

    prompt = f"""Eres un analista de precios de servicios médicos/veterinarios en México.

Tu tarea: usar el MCP de minimax para buscar en la web los precios actuales de estos servicios en la zona de {zona_full or "la zona del negocio"}.

Servicios detectados en reseñas del negocio (con frecuencia):
{servicios_text}

Instrucciones:
1. Usa el MCP de minimax para buscar precios de mercado de CADA UNO de los servicios listados arriba
2. Devuelve SOLO un JSON válido (sin markdown, sin explicaciones)
3. NO inventes precios — si no encuentras un servicio, omítelo
4. Devuelve el JSON con este formato exacto:
{{
  "precios_encontrados": [
    {{"servicio": "nombre exacto del servicio", "precio_min": number, "precio_max": number, "precio_promedio": number, "fuente": "descripcion de donde lo encontraste"}}
  ]
}}

JSON:"""

    try:
        result = subprocess.run(
            ["claude", "--print", "--dangerously-skip-permissions", prompt],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0 or not result.stdout.strip():
            logger.warning(f"[estimate_ticket] Claude exit code {result.returncode}, usando fallback")
            return _default_result("claude_error")

        raw = result.stdout.strip()
        json_start = raw.find("{")
        json_end = raw.rfind("}")
        if json_start == -1 or json_end == -1:
            logger.warning("[estimate_ticket] No JSON encontrado en respuesta de Claude")
            return _default_result("no_json")

        json_str = raw[json_start:json_end + 1]
        data = json.loads(json_str)
        precios = data.get("precios_encontrados", [])

        if not precios:
            logger.info("[estimate_ticket] No precios encontrados, usando fallback")
            return _default_result("no_precios_encontrados")

        # Calcular weighted average
        breakdown = []
        total_weighted = 0.0
        total_freq = 0.0

        for p in precios:
            servicio = p.get("servicio", "").lower()
            precio_promedio = float(p.get("precio_promedio", 0))
            # Buscar frecuencia del servicio en services_reviews
            freq = 0.0
            for s in servicios_filtrados:
                if s["nombre_servicio"].lower() in servicio or servicio in s["nombre_servicio"].lower():
                    freq = float(s.get("frecuencia_pct", 0))
                    break
            if freq > 0 and precio_promedio > 0:
                weighted = precio_promedio * freq
                total_weighted += weighted
                total_freq += freq
                breakdown.append({
                    "servicio": p.get("servicio"),
                    "precio_mercado": precio_promedio,
                    "frecuencia_resenas": round(freq, 4),
                    "fuente": p.get("fuente", ""),
                })

        if total_freq == 0 or total_weighted == 0:
            logger.info("[estimate_ticket] Sin match entre precios y servicios, usando fallback")
            return _default_result("sin_match")

        ticket = round(total_weighted / total_freq)

        return {
            "ticket_promedio_mxn": ticket,
            "ticket_breakdown": breakdown,
            "ticket_source": "weighted_average_minimax",
            "metodo": "weighted_average",
            "fuentes_precio": ["mcp_minimax_web_search", "services_reviews"],
        }

    except subprocess.TimeoutExpired:
        logger.warning("[estimate_ticket] Timeout, usando fallback")
        return _default_result("timeout")
    except Exception as e:
        logger.warning(f"[estimate_ticket] Error: {e}, usando fallback")
        return _default_result("exception")


def _default_result(reason: str) -> dict:
    return {
        "ticket_promedio_mxn": DEFAULT_TICKET,
        "ticket_breakdown": [],
        "ticket_source": f"fallback_{reason}",
        "metodo": "weighted_average",
        "fuentes_precio": [],
    }
```

- [ ] **Step 2: Verificar sintaxis**

Run: `cd /Users/stark/projects/salesSystem && /Users/stark/envs/med/bin/python3 -c "from src.market_suite.scraper.estimate_ticket import estimate_ticket; print('OK')"`
Expected: OK (sin errores de sintaxis)

---

### Task 2: Modificar `apify_scraper.py` — 100 reseñas y llamada a estimate_ticket

**Files:**
- Modify: `salesSystem/src/market_suite/scraper/apify_scraper.py:78-83`

- [ ] **Step 1: Cambiar max_reviews de 50 a 100**

Find this in `scrape_prospect()`:
```python
            result = scrape_google_maps_apify(
                query=query,
                place_url=place_url,
                place_id=place_id,
                max_reviews=50,
                max_images=10,
```

Change to:
```python
            result = scrape_google_maps_apify(
                query=query,
                place_url=place_url,
                place_id=place_id,
                max_reviews=100,
                max_images=10,
```

- [ ] **Step 2: Agregar importación de estimate_ticket**

Find in `apify_scraper.py`:
```python
from .unified_cache import UnifiedCache
```

Add after:
```python
from .estimate_ticket import estimate_ticket
```

- [ ] **Step 3: Agregar llamada a estimate_ticket después de cache.save()**

Find in `scrape_prospect()`, after `cache.save(save_data)` (around line 168):
```python
                cache.save(save_data)
```

Add after (still inside the `if place_id:` block, after `cache.save(save_data)`):
```python
                # ── Calcular ticket promedio ponderado con minimax ──
                services_reviews = save_data.get("services", {}).get("services_reviews", [])
                zona = save_data.get("direccion", "")
                estado = save_data.get("estado", "")
                cp = save_data.get("cp", "")
                try:
                    ticket_result = estimate_ticket(services_reviews, zona, estado, cp)
                    if ticket_result:
                        save_data["_patient_estimates"]["ticket_promedio_mxn"] = ticket_result["ticket_promedio_mxn"]
                        save_data["_patient_estimates"]["ticket_breakdown"] = ticket_result.get("ticket_breakdown", [])
                        save_data["_patient_estimates"]["ticket_source"] = ticket_result.get("ticket_source", "fallback")
                        save_data["_patient_estimates"]["metodo"] = ticket_result.get("metodo", "weighted_average")
                        save_data["_patient_estimates"]["fuentes_precio"] = ticket_result.get("fuentes_precio", [])
                        cache.save(save_data)
                        logger.info(f"[apify_scraper] Ticket actualizado: ${ticket_result['ticket_promedio_mxn']} MXN ({ticket_result.get('ticket_source', '?')})")
                except Exception as e:
                    logger.warning(f"[apify_scraper] Error en estimate_ticket: {e}")
```

Note: Este bloque va después del bloque que calcula `_review_stats` y antes de `return self._normalize_result(result)`.

- [ ] **Step 4: Actualizar el bloque de _review_stats para usar estimate_ticket**

Currently the `_review_stats` block sets `ticket_promedio_mxn: 1500`. Replace the hardcoded value with a call to `estimate_ticket` so that `_patient_estimates` gets the calculated value from the start.

In the `_review_stats` block (around line 152-164 in `apify_scraper.py`), change:
```python
                            "ticket_promedio_mxn": 1500,
                            "est_monthly_revenue_mxn": int(reviews_per_month_avg / (REVIEW_RATE_PCT / 100) * 1500),
```

To:
```python
                            "ticket_promedio_mxn": 1500,  # se actualiza después con estimate_ticket
                            "est_monthly_revenue_mxn": int(reviews_per_month_avg / (REVIEW_RATE_PCT / 100) * 1500),
```

(El ticket real se calcula y actualiza en el bloque fire-and-forget añadido en Step 3.)

- [ ] **Step 5: Reiniciar servidor y probar**

Run: `lsof -ti:8788 | xargs kill -9 2>/dev/null; sleep 1; cd /Users/stark/projects/salesSystem && /Users/stark/envs/med/bin/python3 -m src.market_suite.deliverable_builder.app &`

- [ ] **Step 6: Verificar que estimate_ticket es importable**

Run: `cd /Users/stark/projects/salesSystem && /Users/stark/envs/med/bin/python3 -c "from src.market_suite.scraper.estimate_ticket import estimate_ticket, DEFAULT_TICKET; print('OK - default ticket:', DEFAULT_TICKET)"`
Expected: OK - default ticket: 1500

---

### Task 3: Verificación final

**Files:**
- Verify: `salesSystem/src/market_suite/scraper/estimate_ticket.py` existe y es válido
- Verify: `apify_scraper.py` tiene `max_reviews=100`
- Verify: `apify_scraper.py` tiene import de `estimate_ticket`
- Verify: UI de debug: http://127.0.0.1:8788/debug?place_id=ChIJwyzO_QX_0YURXcI28Js0Dbg muestra sección "Estimación de Clientes"

- [ ] **Step 1: Verificar que el módulo existe**

Run: `ls -la /Users/stark/projects/salesSystem/src/market_suite/scraper/estimate_ticket.py`
Expected: archivo existe

- [ ] **Step 2: Verificar que el servidor corre**

Run: `curl -s "http://127.0.0.1:8788/debug?place_id=ChIJwyzO_QX_0YURXcI28Js0Dbg" | grep -c "Estimación de Clientes" && echo "OK"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add salesSystem/src/market_suite/scraper/estimate_ticket.py salesSystem/src/market_suite/scraper/apify_scraper.py
git commit -m "feat: ticket promedio ponderado con MCP minimax"
```