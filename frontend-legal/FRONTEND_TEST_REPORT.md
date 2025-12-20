# Frontend Test Report

**Date**: 2025-12-13  
**Tester**: Codex  
**Environment**: Windows (PowerShell), Node.js v22.1.0, npm 10.7.0, Django dev server + local Postgres

## Test Results

### Passed Tests
- Page served at `http://localhost:3000` (Next dev/Turbopack running)
- Backend reachable at `http://localhost:8000` (sources endpoint returned 70 records)
- Chat endpoint responde con answer + sources; tarjetas muestran badge y enlace válido
- UI/UX (desktop + 375px): aviso legal visible/dismissible, input + contador, Enviar deshabilitado en vacío/en carga, skeleton visible, markdown render, tarjetas expandibles, botón “Nueva consulta” resetea chat
- Error handling: al abortar el backend se muestra banner rojo + respuesta de error en chat; el banner se puede cerrar
- Multi-turn: 4 turnos seguidos sobre gastos de home studio completan sin bloquear la UI
- Responsive: layout e input operativos a 375px de ancho (headless Chromium)

### Failed Tests
- Sin fallos funcionales en la pasada más reciente; ver issues (warnings/performance)

### Issues Found
- (FIX) Warnings de React por claves duplicadas en tarjetas de fuentes (IDs repetidos); se añadió key compuesta en `LegalChatInterface`
- Latencia alta: chat ~10.0s (primer mensaje) y ~11–13.5s en turnos siguientes; búsqueda ~10.8s (objetivo <5s)
- Calidad LLM no verificada: respuestas siguen genéricas; falta validar con `GEMINI_API_KEY` activo
- Console: pendiente re-run para confirmar que ya no hay warnings de keys duplicadas; `net::ERR_FAILED` esperado al simular error

### Performance
- Chat (UI, `"Puedo deducir gastos de home studio?"`): ~10.0s
- Chat multi-turn (4 mensajes sobre home studio): ~12.7s, ~13.5s, ~11.4s, ~11.4s
- Search POST (`"gastos deducibles"`): ~10.8s
- Page load: 200 OK (manual metric not captured)
- Build size (`.next`): 26.57 MB (dev build artifacts)

### Browser Compatibility
- [x] Chrome (Playwright headless, desktop + 375px)
- [x] Firefox (headless)
- [x] WebKit (headless; tarjetas cargan)
- [ ] Edge
- [ ] Safari

## Additional Checks (2025-12-13)

- Backend pytest: 29 passed, 1 error (missing fixture in `test_rag_engine.py`), 3 warnings (tests returning values).
- 10 artist scenarios (chat API, Gemini 2.5 flash, P1 corpus):
  1) Home studio deducción (IRPF autónomo) → ~9.7s, 5 fuentes  
  2) Retención IRPF actuaciones → ~7.3s, 5 fuentes (sin normativa específica)  
  3) IVA entradas concierto → ~8.5s, 5 fuentes (tipo/cita potencialmente errónea)  
  4) Duración derechos de autor → ~9.2s, 5 fuentes  
  5) Cesión derechos en contrato → ~11.2s, 5 fuentes  
  6) Gastos desplazamiento/dietas gira → ~8.6s, 5 fuentes (pide más info)  
  7) Bolo UE (IVA/inversión sujeto pasivo) → ~7.5s, 5 fuentes (sin normativa específica)  
  8) Merchandising online → ~5.7s, 5 fuentes (sin normativa específica)  
  9) Alta en autónomos esporádico → ~9.4s, 5 fuentes (pide más info)  
  10) IVA servicios culturales a ONG → ~8.2s, 5 fuentes (pide más info)
- Cross-browser smoke (headless): Firefox ok (lat ~9.8s, 5 fuentes); WebKit loaded but returned 0 tarjetas (needs follow-up). Edge/Safari not run.

## Additional Checks (latest run after gating tweaks)
- Health check: 200 OK (`/api/v1/legal-graphrag/health/`).
- Scenario evaluator (`scripts/eval_refinement.py`, local API, post-restart): 10/10 respuestas OK, latencia ~6.3–10s, fuentes 2–5 por consulta; mayoría devuelven “No tengo información…” (contenido de abstención), pero sigue apareciendo un tipo IVA 15% erróneo en conciertos.
- Cross-browser smoke (headless): Chrome/Firefox/WebKit OK (tarjetas cargan); Edge/Safari pendientes.

## LLM Quality / Citations Review (10 escenarios)
- Respuestas siguen genéricas y con citas poco pertinentes o incorrectas:
  - IRPF home studio: cita Art. 98 IRPF (borrador) y artículos de IVA/IS; no aborda deducibilidad real.
  - Retención IRPF actuaciones: sin normativa de retenciones; devuelve IVA/IS/Comercio.
  - IVA entradas concierto: afirma tipo general 15% (incorrecto); cita IS/LSC/PGC sin relación.
  - Cesión de derechos: base genérica, citas contables sin PI.
  - Autónomos esporádico: sin base legal; fuentes Constitución/Comercio irrelevantes.
  - Servicios culturales a ONG: usa Art.160 IVA (recargo equivalencia) y Ley 49/2002 mecenazgo, sin exenciones aplicables.
- Riesgo de alucinación de citas: muchas fuentes no relacionadas con la pregunta; artículos y leyes no aplican al caso.

## Fixes Applied (backend notes from 2025-12-13)
- Source Card Mapping: backend devuelve `id`, `title`, `url`, `source_type`, `relevance_score`, `excerpt` (tarjetas ahora muestran badge/título/enlace)
- Health Endpoint: `/api/v1/legal-graphrag/health/` (200 OK en esta corrida)
- Performance tweaks: reducción de búsquedas híbridas adicionales; optimización del flujo RAG
- Greeting detection: saluda sin consultar buscador cuando el mensaje es solo saludo
- Follow-up support: usa contexto previo para preguntas de seguimiento y evita re-búsquedas

## Historical Performance Summary (backend notes)
| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Chat (legal query) | 13.3s | 6.5s | **51%** |
| Search (hybrid) | 14.4s | 8.3s | **42%** |
| Chat (greeting) | 13.3s | <0.1s | **99%** |
| Chat (follow-up) | 13.3s | ~3s | **77%** |
**Target**: <5s (aún pendiente)

## Recommendations
- Garantizar keys únicas en las tarjetas de fuentes (deduplicar en backend o usar key compuesta en frontend)
- Perf: bajar chat/búsqueda de ~10–13s a <5s (caché de embeddings/búsqueda, reducir contexto, optimizar consultas)
- Validar con `GEMINI_API_KEY` activo para revisar calidad y relevancia de las respuestas
