# Plan — salesCrafter

## Contexto

salesCrafter es el hermano de salesSystem. Lee de la misma UnifiedCache
(`data/prospectos/reports/runs/{place_id}/{place_id}.json`) y genera los entregables
comerciales editables para el flujo de ventas de Varkos.

- **salesSystem** = investigar y auditar (puerto 8788)
- **salesCrafter** = sintetizar investigación en contenido comercial editable (puerto 8789)

---

## Concepto Central: Bloque de Contenido

Un **bloque** es una unidad de contenido comercial generada con Claude Code.

```json
{
  "id": "hook_dinero_hvdelta",
  "tipo": "hook_dinero",
  "nombre": "Hook Dinero — HV Delta",
  "autogenerar": true,
  "fuentes": {"maps_audit": ["Score General", "Resumen Ejecutivo"], "review_insights": ["Temas Positivos"]},
  "prompt_custom": "Eres un experto en análisis financiero...\n(texto BASE sin DATOS — editable por usuario)",
  "prompt_usado": "Eres un experto en análisis financiero...\n\n--- DATOS ---\nmaps_audit: Score General\n---\n{\"score\": 72.55...}\n...(todo el contenido de las fuentes)",
  "contenido": {
    "headline": "~$12,000 MXN/mes sin capturar",
    "resumen": "Tienen 8 servicios que ofrece el hospital pero solo 3 publicados...",
    "datos_concretos": [...]
  },
  "metadata": {
    "created_at": "2026-05-02T...",
    "updated_at": "2026-05-02T...",
    "version": 1,
    "generado_por": "claude-code",
    "modelo_ia": "sonnet-4",
    "usuario_edito": false,
    "nota_editor": ""
  }
}
```

**Prompts separados:**
- `prompt_custom` = texto BASE que ve y edita el usuario en la UI (sin DATOS)
- `prompt_usado` = prompt BASE + `--- DATOS ---\n<contenido de fuentes>` que se envía a Claude

**Ciclo de vida:**
```
Crear → Generar con IA (fuentes_default del template)
  ↓
Editar a mano
  ↓
Regenerar (mismas fuentes o diferentes)
  ↓
Ensamblar en entregable
```

---

## Arquitectura

```
salesCrafter/
├── src/
│   ├── app.py                      ← Flask 8789, todas las rutas API
│   ├── cache_reader.py            ← lector de UnifiedCache (solo lectura)
│   ├── blocks/                     ← bloques guardados por prospecto
│   │   └── {place_id}/
│   │       └── {bloque_id}.json
│   ├── generators/
│   │   ├── bloque_generator.py    ← motor: Claude Code → bloque JSON
│   │   └── prompt_builder.py      ← templates de prompts por tipo
│   ├── classifiers/
│   │   └── stage_classifier.py    ← Stage 0-6 del Expansion Framework
│   ├── assemblers/                ← lógica de cada entregable
│   │   ├── carta_teaser.py
│   │   ├── presentacion_intro.py
│   │   └── presentacion_dirigida.py
│   └── output_exporters/           ← exportación a múltiples formatos
│       ├── docx_exporter.py
│       └── html_exporter.py
├── docs/
│   └── PLAN.md                    ← este archivo
└── templates/
    └── editor.html                ← interfaz web de edición
```

**Regla:** salesCrafter solo LEE de UnifiedCache. Nunca escribe en ella.

---

## Estado Actual

### Completado ✅

#### 1. Cache Reader + Subsections Tree
- `CacheReader.get_subsections(place_id)` retorna `{ section: { sub_label: text } }`
- Secciones con `secciones` jerárquicos (geo_audit, market_audit, competitive_intel,
  prospect_analysis) → usan títulos principales como subsecciones
- Subsecciones anidadas se adjuntan dentro de cada sección
- Secciones planas (maps_audit, review_insights, services, social_audit, photos)
  → parsing específico por tipo

**Subsecciones disponibles por sección:**

| Sección | Subsecciones |
|--------|-------------|
| `maps_audit` | Resumen Ejecutivo, Score General, Subscores, Findings, Quick Wins, Presión Competitiva, Tabla Competitiva, **Análisis de Fotos**, **Gap de Servicios**, **Análisis de Reseñas**, **Presencia Online**, **Resumen del Perfil**, **Oportunidades de Negocio**, **Acciones**, **Análisis Competitivo** |
| `geo_audit` | 1. Resumen Ejecutivo, 2. Problemas Críticos, 3. Prioridad Media, 4. Baja Prioridad, 5. Análisis por Categoría, 6. Acciones Rápidas, 7. Plan de 30 Días, 8. Oportunidades SEO GEO, Resumen |
| `market_audit` | RESUMEN EJECUTIVO, PUNTAJES POR CATEGORÍA, GANANCIAS RÁPIDAS, RECOMENDACIONES ESTRATÉGICAS, INICIATIVAS DE LARGO PLAZO, ANÁLISIS POR CATEGORÍA, RESUMEN DE IMPACTO EN INGRESOS, PRÓXIMOS PASOS, NOTAS METODOLÓGICAS, Resumen |
| `competitive_intel` | 1. Resumen Ejecutivo, 2. Stack Tecnológico, 3. Puntuación Competitiva, 4. Panorama Competitivo, 5. Análisis de Brechas, 6. Posicionamiento para la Venta, 7. Objeciones Previsibles, 8. Recomendaciones de Acción, Indicadores de Seguimiento, Nota Metodológica, Resumen |
| `prospect_analysis` | Resumen Ejecutivo, 1. Perfil de la Empresa, 2. Mapa de Tomadores de Decisión, 3. Evaluación de Oportunidad, 4. Panorama Competitivo, 5. Estrategia de Aproximación, 6. Plan de Acción, 7. Borrador de Email, Notas de Seguimiento, Resumen del Prospecto, Resumen |
| `review_insights` | Temas Positivos, Temas Negativos, Top 5 Positivos, Top 5 Negativos, Fortalezas del Negocio, Debilidades, Oportunidades, Prioridad de Acción, Insight, Métricas |
| `services` | Servicios Reales, Servicios por Reviews |
| `social_audit` | Facebook, Instagram, Tiktok |
| `photos` | Análisis de Fotos |
| `servicios_publicados` | Servicios Publicados |
| `owner_response_metrics` | owner_replies_count, reply_rate_percent, total_reviews_considered |

#### 2. Motor de Generación de Bloques ✅
- `BloqueGenerator.generate()` — usa `fuentes_default` del template si `fuentes=null`
- `BloqueGenerator.regenerate()` — usa `prompt_custom` como base
- Separación `prompt_custom` (UI) vs `prompt_usado` (Claude con DATOS)
- Verificación de idioma (CJK, cirílico, portugués/ruso transliterado)
- Retry con reintento automático si el JSON falla

#### 3. Editor Web (editor.html) ✅
- Selección de prospecto con autocomplete
- Lista de bloques con indicador autogenerado/editado
- Panel de edición con contenido formateado
- **Árbol de subsecciones expandible** — llamado `/sources-tree/full`,
  secciones colapsables con checkboxes por subsección
- `getSelectedFuentes()` retorna `{ section: [subs] }` para el nuevo sistema
- `applyBloqueFuentes()` pre-selecciona fuentes al abrir bloque existente

#### 4. Tipos de Bloque (prompt_builder.py) ✅
8 tipos definidos con `prompt_template` + `fuentes_default`:

| Tipo | Descripción | Fuentes default |
|------|-------------|-----------------|
| `hook_dinero` | Cuantifica en dinero la oportunidad | maps_audit + review_insights + services |
| `oportunidades` | Mayor oportunidad detectada | maps_audit + review_insights |
| `fortalezas` | Lo mejor del negocio | review_insights + maps_audit |
| `comparativa_competitiva` | Cómo gana vs. competencia | maps_audit + competitive_intel |
| `insight_estrategico` | Conclusión estratégica clave | maps_audit + review_insights + competitive_intel |
| `slide_score` | Score con interpretación | maps_audit |
| `temas_resenas` | Temas positivos/negativos | review_insights |
| `servicios_oportunidad` | Qué servicios publicar | services + maps_audit + competitive_intel |

---

## Pendiente

### 2.1 Editor de subsecciones en UI ⚠️
- El modal de nuevo bloque (`crearBloque`) no muestra el árbol de subsecciones,
  solo pasa `fuentes: null` al backend. Debería permitir seleccionar fuentes
  antes de generar.
- El `renderFuentesTree()` ya está implementado pero solo se usa al abrir un bloque
  existente — falta integrarlo en el flujo de creación.
- `applyBloqueFuentes()` maneja arrays legacy pero el formato actual de `fuentes`
  en bloques guardados probablemente es un array, no un dict. Necesita verificarse.

### 2.2 Verificación de idioma en frontend
- Si `_verify_and_clean` falla en backend, el bloque puede tener contenido mixto.
- Opciones: hacer check visual en editor (resaltar texto no español) o dejar solo
  en backend.

### 2.3 Pruebas E2E del flujo completo
- Crear prospecto nuevo → autogenerar → abrir bloque → editar fuentes → regenerar
- Verificar que `prompt_usado` en el bloque regenerado tenga DATOS correctos
- Verificar que el entregable (carta teaser) renderice los bloques correctamente

### 2.4 Entregables
- `carta_teaser` → ensamblador funciona, preview funciona
- `presentacion_intro` → ensamblador + slides
- `presentacion_dirigida` → con stage y notas de reunión
- DocxExporter, HtmlExporter → funcionan

### 2.5 Stage Classifier
- `classify_stage()` conecta con los datos del prospecto
- Devuelve `stage`, `nombre_es`, `servicio`

### 2.6 Exportación mejorada
- PPTX animado (python-pptx con animaciones programables)
- HTML5 interactivo (Reveal.js o similar)
- Canva MCP como alternativa futura

---

## Flujo Completo

```
1. Usuario abre salesCrafter /editor
   → carga tipos de bloque desde /api/bloque/tipos
   → carga árbol de subsecciones desde /api/prospect/{id}/sources-tree/full

2. Usuario selecciona prospecto
   → loadBloques() + loadFuentesTree()
   → Si no hay bloques: autogen con fuentes_default del template

3. Usuario abre un bloque existente
   → openBloque(id) → GET /api/prospect/{id}/bloque/{id}
   → applyBloqueFuentes() → renderFuentesTree() (con checkboxes correctos)

4. Usuario modifica fuentes → Regenerar
   → POST /api/prospect/{id}/bloque/regenerar
   → Backend: usa prompt_custom + nuevas fuentes → Claude Code → JSON
   → Nuevo bloque con version+1

5. Usuario edita contenido a mano → Guardar
   → POST /api/prospect/{id}/bloque/guardar
   → metadata.usuario_edito = true

6. Usuario arma entregable (Carta Teaser)
   → Selecciona bloques del panel izquierdo
   → Inserta en canvas como [bloque_id]
   → Genera preview / Exporta DOCX
```

---

## API Endpoints

```
GET  /api/prospects                                   → lista prospectos
GET  /api/prospect/{place_id}                          → datos del prospecto
GET  /api/prospect/{place_id}/bloques                 → lista bloques
GET  /api/prospect/{place_id}/bloque/{id}             → un bloque
GET  /api/prospect/{place_id}/sources-tree            → árbol con previews (200 chars)
GET  /api/prospect/{place_id}/sources-tree/full       → árbol completo

POST /api/prospect/{place_id}/bloque/generar           → generar nuevo bloque
POST /api/prospect/{place_id}/bloque/guardar            → guardar/editado
POST /api/prospect/{place_id}/bloque/regenerar         → regenerar con nuevas fuentes
DELETE /api/prospect/{place_id}/bloque/eliminar/{id}   → eliminar bloque

POST /api/prospect/{place_id}/autogen                  → autogenerar bloques iniciales

GET  /api/bloque/tipos                                 → lista tipos con fuentes_default
GET  /api/bloque/tipos/{tipo}/schema                  → schema de salida

POST /api/prospect/{place_id}/stage                   → classify stage
POST /api/prospect/{place_id}/entregable/{tipo}/preview → preview HTML
POST /api/prospect/{place_id}/exportar/{formato}       → exportar DOCX/HTML
```

---

## Notas Técnicas

- Venv compartida: `/Users/stark/envs/med` con salesSystem
- `.env` configura `UNIFIED_CACHE_ROOT` para apuntar a salesSystem
- Claude Code: `claude --print --dangerously-skip-permissions` en subprocess
- El servidor detecta cambios de código automáticamente (debug=True)
- Puerto: 8789 /editor
