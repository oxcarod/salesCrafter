# Ticket Promedio Ponderado — Diseño

**Fecha:** 2026-05-07
**Proyecto:** salesSystem + salesCrafter

## Problema

El ticket promedio de `_patient_estimates` está hardcodeado en $1,500 MXN, lo cual no refleja la realidad del negocio. El modelo debería calcular un ticket basado en datos reales del mercado.

## Solución

Un nuevo paso en el pipeline de scrape de Apify que:

1. Detecta servicios desde las reseñas (con frecuencia) — ya existe en `services.services_reviews`
2. Usa Claude Code con MCP de minimax para investigar precios de mercado por zona/sector
3. Calcula ticket ponderado: `sum(precio_i × frecuencia_i)` para todos los servicios detectados
4. Guarda el resultado en `_patient_estimates.ticket_promedio_mxn`

## Cambios

### 1. `apify_scraper.py` — Más reseñas
```python
max_reviews=100,  # antes 50
```

### 2. Nuevo módulo `estimate_ticket.py`
En `salesSystem/src/market_suite/scraper/estimate_ticket.py`:

- Función `estimate_ticket(services_reviews, zona, estado, cp)` → dict con ticket + breakdown
- Usa `claude --print` con prompt que invoca MCP minimax
- Prompt: *"Usa el MCP de minimax para buscar en la web precios de estos servicios médicos/veterinarios en [zona]. No inventes información. Devuelve JSON."*
- Fallback: `$1,500` si falla o no hay servicios

### 3. `apify_scraper.py` — Integración
Después de `cache.save()` en `scrape_prospect()`, llamar a `estimate_ticket()` y guardar resultado en `_patient_estimates`.

### 4. `_patient_estimates` actualizado
```json
{
  "ticket_promedio_mxn": 780,
  "ticket_breakdown": [
    {"servicio": "consulta general", "precio_mercado": 450, "frecuencia_resenas": 0.35},
    {"servicio": "vacunas", "precio_mercado": 280, "frecuencia_resenas": 0.25}
  ],
  "ticket_source": "weighted_average_minimax",
  "metodo": "weighted_average",
  "fuentes_precio": ["mcp_minimax_web_search", "services_reviews"]
}
```

## Manejo de errores

| Caso | Comportamiento |
|------|---------------|
| MCP minimax falla | Fallback `$1,500`, `ticket_source: "fallback"` |
| No hay servicios detectados | Fallback `$1,500`, `ticket_source: "default"` |
| Prompt timeout (>60s) | Fallback `$1,500`, `ticket_source: "timeout"` |
| Modelo inventa precios | Prompt explicitly says "no inventes", fallback si respuesta vacía |

## Orden de ejecución

1. `scrape_google_maps_apify()` → obtiene reseñas + servicios
2. `cache.save(save_data)` → guarda datos crudos
3. `estimate_ticket()` → calcula ticket ponderado con minimax
4. `cache.update_section("_patient_estimates", result)` → guarda resultado final

Pasos 3-4 son fire-and-forget, no bloquean el scrape.