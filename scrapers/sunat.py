from playwright.async_api import async_playwright
from datetime import datetime, timezone
import re


def _parse_fecha_from_data_date(data_date: str) -> str | None:
    """
    data-date puede venir como:
    - "2026-02-11T05:00:00.000Z"
    - "2026-02-11"
    Retorna "YYYY-MM-DD"
    """
    if not data_date:
        return None
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", str(data_date).strip())
    return m.group(1) if m else None


def _parse_compra_venta(texto: str):
    """
    Intenta extraer compra/venta desde el texto de la celda.
    Ejemplos comunes:
      "Compra 3.353 Venta 3.362"
      "Compra \"3.353\" Venta \"3.362\""
    Retorna (compra, venta) como floats o (None, None)
    """
    if not texto:
        return None, None

    t = " ".join(str(texto).split())  # compacta espacios

    compra = re.search(r"Compra\s+\"?\s*([\d.]+)", t, re.IGNORECASE)
    venta  = re.search(r"Venta\s+\"?\s*([\d.]+)", t, re.IGNORECASE)

    if compra and venta:
        try:
            return float(compra.group(1)), float(venta.group(1))
        except:
            return None, None

    # fallback: 2 números decimales
    nums = re.findall(r"(\d+\.\d+)", t)
    if len(nums) >= 2:
        try:
            return float(nums[0]), float(nums[1])
        except:
            return None, None

    return None, None


async def scrap_sunat():
    url = "https://www.sunat.gob.pe/cl-at-ittipcam/tcS01Alias"
    base = {"casa": "SUNAT", "url": url}

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )

            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            await page.goto(url, timeout=60000, wait_until="domcontentloaded")
            await page.wait_for_selector("td[data-date]", timeout=60000)

            # Traemos todas las celdas del calendario que tengan data-date
            celdas = page.locator("td[data-date]")
            n = await celdas.count()
            if n == 0:
                await browser.close()
                return {**base, "error": "No se encontraron celdas td[data-date]"}

            dias = []
            for i in range(n):
                celda = celdas.nth(i)

                data_date = await celda.get_attribute("data-date")
                fecha = _parse_fecha_from_data_date(data_date)
                if not fecha:
                    continue

                texto = (await celda.inner_text()).strip()
                compra, venta = _parse_compra_venta(texto)

                # Solo guardamos días que tengan compra y venta
                if isinstance(compra, float) and isinstance(venta, float):
                    dias.append({"fecha": fecha, "compra": compra, "venta": venta})

            # Orden por fecha (string YYYY-MM-DD ordena bien)
            dias.sort(key=lambda x: x["fecha"])

            if not dias:
                await browser.close()
                return {**base, "error": "No se pudo extraer compra/venta de ninguna celda del mes"}

            mes = dias[-1]["fecha"][:7]  # YYYY-MM del último día capturado

            payload = {
                **base,
                "mes": mes,
                "captured_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "dias": dias,
                "total_dias": len(dias),
            }

            await browser.close()
            return payload

    except Exception as e:
        return {**base, "error": str(e)}
