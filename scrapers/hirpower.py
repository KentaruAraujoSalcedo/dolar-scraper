from playwright.async_api import async_playwright
import re

async def scrap_hirpower():
    url = "https://hirpower.com/"
    casa = "HirPower"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(url, timeout=60000)

            # Esperar que al menos 2 tasas reales (> 0.000) aparezcan
            await page.wait_for_function(
                """() => {
                    const spans = Array.from(document.querySelectorAll("span.precioActivo"));
                    return spans.filter(s => parseFloat(s.textContent.replace(/[^\\d.]/g, '')) > 0).length >= 2;
                }""",
                timeout=20000
            )

            # Obtener todo el texto
            spans = await page.locator("span.precioActivo").all_text_contents()

            # Filtrar los que tienen valores reales
            tasas_validas = [s for s in spans if re.search(r"3\.\d{3}", s)]
            if len(tasas_validas) < 2:
                raise Exception("No se encontraron suficientes tasas válidas")

            # Extraer los valores numéricos
            compra = float(re.search(r"3\.\d{3}", tasas_validas[0]).group())
            venta = float(re.search(r"3\.\d{3}", tasas_validas[1]).group())

            await browser.close()

            return {
                "casa": casa,
                "url": url,
                "compra": compra,
                "venta": venta
            }

    except Exception as e:
        return {
            "casa": casa,
            "url": url,
            "error": f"No se pudo scrapear: {e}"
        }

# Test manual
if __name__ == "__main__":
    import asyncio
    resultado = asyncio.run(scrap_hirpower())
    print(resultado)
