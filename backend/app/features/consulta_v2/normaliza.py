# FORK de consulta/normaliza.py @ 2026-07-30 — razón: aislamiento v2 (edificio separado;
# v1 congelada, cero imports cruzados).
import unicodedata


def norm(s: str) -> str:
    """UPPER + trim + colapsar espacios + plegar acentos/ñ (NFKD sin combining)."""
    s = unicodedata.normalize("NFKD", (s or "").strip().upper())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(s.split())
