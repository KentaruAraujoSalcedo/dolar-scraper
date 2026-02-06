def normalize_rate(v):
    """
    Convierte el valor a float, valida rango razonable para USD/PEN
    y devuelve None si es inválido (0, vacío, fuera de rango).
    """
    try:
        fv = float(str(v).replace(",", ".").strip())
    except Exception:
        return None
    
    # Rango razonable de tipo de cambio USD/PEN
    if fv <= 0 or fv < 2.0 or fv > 10.0:
        return None
    
    return round(fv, 3)
