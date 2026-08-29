"""
Helpers de parseo compartidos — copiados del prototipo ETL (H1: el original NO se toca).
"""
from __future__ import annotations
import re, datetime as dt

# Valores a tratar como nulos en hojas Excel
NOISE = {"", "#REF!", "#DIV/0!", "#N/A", "#VALUE!", "#NAME?", "(en blanco)", "(EN BLANCO)"}

def s(v):
    """Convierte valor a str limpio; devuelve None si es ruido o vacío."""
    if v is None: return None
    t = str(v).strip()
    return None if t in NOISE else t

def num(v):
    """Convierte valor a float; devuelve None si es ruido o no numérico."""
    if v is None: return None
    if isinstance(v, (int, float)): return v
    t = str(v).strip()
    if t in NOISE: return None
    try: return float(t)
    except ValueError: return None

def to_date(v):
    """Convierte int YYYYMMDD, datetime, date o str ISO a date; None si inválido."""
    if v is None or v == "" or v == 0: return None
    if isinstance(v, dt.datetime): return v.date()
    if isinstance(v, dt.date): return v
    t = str(v).strip()
    if t in NOISE: return None
    t = t.split(".")[0]          # "20240930.0" -> "20240930"
    if re.fullmatch(r"\d{8}", t):
        try: return dt.date(int(t[:4]), int(t[4:6]), int(t[6:8]))
        except ValueError: return None
    try: return dt.date.fromisoformat(t[:10])
    except ValueError: return None
