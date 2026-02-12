import re

def normalize_rate(v):
    """
    Convierte el valor a float limpio.
    Valida rango razonable USD/PEN.
    Devuelve None si es inválido.
    """

    if v is None:
        return None

    # Convertir a string
    s = str(v).strip()

    if not s or s.lower() in ("null", "none", "-", "--"):
        return None

    # Quitar todo lo que no sea número, punto o coma
    s = re.sub(r"[^\d.,]", "", s)

    if not s:
        return None

    # Normalizar coma a punto
    s = s.replace(",", ".")

    try:
        fv = float(s)
    except Exception:
        return None

    # Validación rango razonable USD/PEN
    if fv <= 0 or fv < 2.0 or fv > 10.0:
        return None

    return round(fv, 3)
