# Guía de publicación — Diagnóstico y seguridad del repositorio `dolar-scraper`

Fecha: 6 de noviembre de 2026. Esta actualización **no modifica las 51 fuentes individuales** ni `scrapers/sunat.py`, el Worker de Cloudflare, la API `dolar-api` ni el frontend.

## Cambios de código

- `run_scrapers.py`: JSON/CSV por casa; datos de errores resumidos para no divulgar stacktraces; se impide reemplazar SUNAT por `dias: []`; conserva el mensual válido y genera `sunat_status.json`.
- `infra/health.py`: normalización de estados, exportación CSV, metadatos seguros y protección de publicación.
- `infra/sunat_guard.py`: validación del histórico, fechas, duplicados y tasas; escritura atómica local.
- `infra/cloudflare_kv.py`: descarga de SUNAT validada, control de errores HTTP, reintentos limitados y publicación protegida.
- `.github/workflows/publish_kv.yml`: pruebas automáticas, artefacto de diagnóstico de 7 días, reporte Summary, 30 cotizaciones válidas como mínimo y no cancelar una ejecución en curso.
- `tests/`: pruebas sin conexiones externas.

## Publicación recomendada (sin reemplazar `.git`)

1. Descarga y descomprime el ZIP en una carpeta separada.
2. Clona o abre el repositorio `dolar-scraper` (no `dolar-web`). Verifica que estás en la rama correcta y que no haya cambios locales sin guardar: `git status`.
3. Trabaja con una rama nueva basada en `main`: `git switch main`, `git pull --ff-only origin main`, `git switch -c diagnosticos-scrapers-2026-11-06`. **No ejecutes switch/pull si hay cambios sin guardar.**
4. Copia los cambios desde el ZIP sobre esa rama, sin reemplazar `.git`.
5. Ejecuta `python -m unittest discover -s tests -v` y `git diff --check`.
6. Comprueba con `git status --short` que solo se modifican los archivos indicados. No uses `git add .` si hay archivos ajenos.
7. Haz commit, push y Pull Request. Espera las validaciones.
8. **Antes de fusionar**, confirma que `MIN_VALID_QUOTES: '30'` es apropiado: tus últimos datos mostraban aproximadamente 40 válidas de 51. Si la disponibilidad disminuye de forma legítima, habrá que analizar el umbral.
9. Una vez fusionado, en GitHub → Actions verifica la primera ejecución completa, su Summary, Artifact y la clave `diagnostico_scrapers.json` en `DOLAR_KV`.
10. Comprueba que la web sigue mostrando cotizaciones y SUNAT con fecha coherente.

## ¿Qué pasa si hay problemas?

- **Falla la validación del lote**: el workflow queda rojo; no actualiza KV. La web continúa utilizando los datos anteriores. Revisa el Artifact de la corrida fallida y el Summary.
- **SUNAT falla**: el workflow puede continuar con las cotizaciones comerciales; no actualiza `sunat_mensual.json` y guarda el estado de SUNAT en el diagnóstico.
- **La autenticación de Cloudflare falla**: el workflow se detiene con el estado HTTP; no se imprimen los valores de los secretos. Revisar permisos, caducidad del token y namespace.
- **Una escritura individual a KV falla a mitad del proceso**: puede quedar inconsistencia temporal entre `tasas.json`, `meta.json` y `diagnostico_scrapers.json`. No existe transacción multi-clave. Si ocurre, evita reintentos manuales repetidos sin revisar la causa. Una corrida completa posterior recupera la consistencia.
- **No hay diagnóstico nuevo en KV**: la publicación pudo bloquearse. Siempre mira GitHub Actions/Artifacts.

### Revertir

GitHub → Pull Request fusionado → `Revert` (o una nueva rama que revierta ese commit), luego comprobar una ejecución. El rollback del **código** no revierte automáticamente los valores de KV. Guarda una copia de los JSON previos si necesitas restaurarlos.

## Cómo encontrar una casa defectuosa

- **Actions → ejecución → Summary**: tabla de problemas sin abrir logs.
- **Actions → ejecución → Artifacts**: archivo `diagnostico_scrapers.csv`, ordenado con las casas problemáticas arriba, para abrir en Excel.
- **Cloudflare → Workers KV → DOLAR_KV → `diagnostico_scrapers.json`**: último resultado publicado para las 51 casas, también ordenado por prioridad.

El campo `codigo` agrupa causas (`http_404`, `blocked_403`, `dns_error`, `parse_error`, `timeout`, `outlier_spread_high`...). Estos códigos son diagnósticos, no reparaciones automáticas.

## Lo que **no** se ha verificado

No se han ejecutado los scrapers contra los sitios reales ni se ha desplegado a tu Cloudflare. Las pruebas son unitarias/simuladas y la publicación debe hacerse mediante una rama y PR. Las reglas del Worker `dolar-api` pueden requerir ajustes para ofrecer el JSON públicamente; desde el panel KV sí puedes consultarlo sin cambiar esa API.
