# PrecioDolarHoy.pe — scrapers y publicación de cotizaciones

Este repositorio extrae cotizaciones de 51 casas de cambio y el histórico mensual de SUNAT. **La extracción de cada casa no se ha modificado** en la mejora de diagnóstico y seguridad del 6 de noviembre de 2026.

## Flujo

1. El Worker externo `scraper-cron-trigger` (Cloudflare) llama a `workflow_dispatch` de `.github/workflows/publish_kv.yml`. **Su programación se configura en Cloudflare**, no aquí.
2. GitHub Actions instala Python y Chromium, y descarga de Cloudflare KV el último `sunat_mensual.json` válido.
3. `run_scrapers.py` consulta las casas y produce los JSON/CSV con sus resultados.
4. `infra/cloudflare_kv.py` verifica que haya suficientes datos válidos y los publica en KV.
5. El Worker externo `dolar-api` y la web consumen las claves existentes. **No se modificaron aquí.**

## ¿Cómo sé qué casa falló?

En GitHub → repositorio **dolar-scraper** → **Actions** → ejecución reciente:

- Abre la pestaña **Summary**: muestra resumen y tabla con las casas que fallaron.
- En **Artifacts**, descarga `diagnostico-scrapers-<run_id>` (retención de siete días); contiene `diagnostico_scrapers.csv` (abrir en Excel), `diagnostico_scrapers.json` (por casa), `meta.json` (agregado) y `sunat_status.json`.
- En **Cloudflare → Workers KV → DOLAR_KV**, busca la clave `diagnostico_scrapers.json` para ver el **último diagnóstico publicado**. Esa clave se sobrescribe en cada publicación válida.
- Si fallan demasiadas casas y se bloquea la publicación, el Artifact de la ejecución fallida **sí se guarda**, pero el diagnóstico de KV **no se reemplaza**. Mira el Artifact nuevo, no solo KV.

### Estados

- `scraper`: extracción correcta, spread dentro del límite competitivo.
- `regular`: válida, spread más amplio; **no significa error del scraper**.
- `missing`: sin compra/venta válida; lee `codigo` y `motivo`.
- `blocked`: fuente con restricción de acceso (403, challenge, CAPTCHA...).
- `outlier`: tasa fuera de los límites; se excluyen sus cifras de `tasas.json` público.

Cada registro incluye `casa`, `estado`, `valida`, `codigo`, `motivo`, `compra`, `venta` y `duracion_ms`. El diagnóstico público **no** contiene trazas, HTML de respuestas ni encabezados de autenticación.

## Protección de publicación

El workflow **no publica ninguna clave nueva** si quedan menos de **30 cotizaciones válidas** (`scraper` + `regular`), o hay incoherencias de conteo o datos sin validar. El umbral está en `MIN_VALID_QUOTES` dentro del workflow y puede ajustarse conscientemente según el comportamiento de varios días. Si bloquea una ejecución, las claves existentes de Cloudflare permanecen intactas durante la fase de validación.

SUNAT no se sobrescribe si la extracción falla: se conserva el último mensual válido, y se registra `sunat_status.json` con `cache_del_dia`, `actualizado`, `conservado_por_error` o `sin_datos_por_error`. **Un histórico viejo sigue siendo viejo**: revisar siempre su mes y fecha. Si se necesita continuidad de varios meses, habrá que implementar almacenamiento histórico separado.

**Importante:** Cloudflare KV no soporta transacciones entre varias claves. Si una escritura falla después de otra exitosa, pueden coexistir versiones de distintas ejecuciones. Para solucionar esto completamente haría falta modificar también `dolar-api` para leer un manifiesto versionado. Esa integración queda fuera de esta actualización; no se afirma atomicidad.

## Comprobaciones locales (sin internet)

Con Python 3.11+ desde la raíz:

```bash
python -m unittest discover -s tests -v
python -m compileall -q run_scrapers.py infra scrapers
```

Para ejecutar los scrapers de verdad, instalar `requirements.txt`, Playwright Chromium y configurar los secretos **solo en el entorno autorizado**. Una ejecución local de `run_scrapers.py` genera archivos dentro de `data/` pero **no publica a Cloudflare** por sí sola. No ejecutar `python -m infra.cloudflare_kv publish` sin revisar los datos.

## Secrets requeridos en GitHub Actions

Solo nombres: `CF_API_TOKEN`, `CF_ACCOUNT_ID`, `CF_KV_NAMESPACE_ID`, `TUCAMBISTA_OCP_KEY` y `CAMBIX_OCP_KEY`. No deben escribirse valores en el repositorio. El Worker `scraper-cron-trigger` mantiene por separado su secreto `GITHUB_TOKEN`.

Usa un token Cloudflare con permisos mínimos para gestionar **únicamente el namespace KV necesario**, cuando los permisos de la cuenta lo permitan. No publiques capturas de los valores de Secrets.

## Límites y cambios pendientes

- No se revisó ni cambió la lógica de los 51 scrapers uno por uno.
- No se implementó scraping de Google Finance ni histórico intradía.
- No se cambió el rango de tasas original (3.00–3.60) ni los límites de spread: requiere una estrategia de validación contrastada antes de alterarlo.
- No hay notificación externa por correo/Telegram ante un fallo; el workflow queda rojo y deja archivos para diagnóstico.
- Este repositorio no incluye el código en producción de `dolar-api` ni del Worker que programa las ejecuciones.
- Ver **`GUIA_CAMBIOS_DIAGNOSTICOS_2026-11-06.md`** para un despliegue seguro y reversión.
