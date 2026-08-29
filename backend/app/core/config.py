"""Configuración central (pydantic-settings), lee el .env de la raíz del repo."""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"  # backend/app/core -> raíz

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ROOT_ENV, extra="ignore")
    database_url: str
    # BD operacional ROBUSTEZ (schema ops) — fuente del EBITDA Inspector (solo lectura). Vacío si no
    # se configura (la ruta /ebitda degrada con error claro en vez de tumbar el arranque).
    ops_database_url: str = ""
    data_dir: str = str(Path(__file__).resolve().parents[3] / "data")
    app_name: str = "Robustez Ingesta API"
    # Consulta (slot-filling): LLM de extracción. Dev = qwen2.5:3b local; prod/139 = gemma4:latest,
    # que puede correr en otra máquina → apuntar la URL a esa IP (ej. http://10.100.26.139:11434/...).
    consulta_ollama_url: str = "http://localhost:11434/api/generate"
    consulta_llm_model: str = "qwen2.5:3b"
    # Consulta · Narración (Fase 3.1): en dev off (qwen es extractor, redacta pobre → se sirve la
    # plantilla determinista); en prod (gemma4:latest) poner CONSULTA_NARRA_LLM=true en el .env.
    consulta_narra_llm: bool = False
    # Motor Q v2 · respuesta al grupo OUT (desconocido): el chat responde UN texto redactado por el
    # LLM (recalca que la pregunta está fuera de contexto + ofrece los 3 temas). Default true (basta
    # un redirect simple, qwen lo hace bien); poner CONSULTA_OUT_LLM=false para servir el texto
    # estático sin llamar al LLM. Si el LLM falla/está frío, SIEMPRE cae al estático (fallback D4).
    consulta_out_llm: bool = True
    # Motor Q v2 · grupo Jerarquizar: el LLM ENVUELVE los hechos (saludo cordial dinámico + pregunta
    # de cierre); los hechos del árbol van VERBATIM (Python) → el LLM no toca el catálogo. Default
    # true; false = versión determinista (hechos + cierre fijo). Si el LLM falla/está frío → fallback
    # determinista (nunca se rompe, mismo patrón que OUT).
    consulta_jerarq_llm: bool = True
    # Motor Q v2 · grupo Cuantificar: el LLM ENVUELVE la cifra (saludo cordial dinámico); la cifra va
    # VERBATIM (Python) → el LLM no toca el número (regla madre + validador). Default true; false =
    # solo cuerpo + cierre. Si el LLM falla/está frío → fallback determinista (nunca se rompe).
    consulta_cuant_llm: bool = True
    # Motor Q v2 · grupo Analizar: el LLM ENVUELVE el análisis (saludo cordial dinámico); los HECHOS/
    # CAUSAS/números van VERBATIM (Python) → el LLM no toca el análisis (regla madre + red anti-dígitos).
    # Default true; false = solo cuerpo + cierre. Si el LLM falla/está frío → fallback determinista.
    consulta_analiza_llm: bool = True
    # Warm-up del LLM de Consulta al arrancar el backend: un ping de carga (keep_alive=-1) en 2º plano
    # para que gemma@139 quede caliente ANTES de la 1ª petición real (frío ~342s > timeout → fallback
    # sin cordialidad). Default true. ⚠️ En dev con RAM ajustada (qwen residente ~2.2GB) poner
    # CONSULTA_WARMUP=false; en 139 dejarlo true.
    consulta_warmup: bool = True
    # keep_alive de CADA petición REAL a Ollama (analisis.ejecutivo, clasificador, respuesta_*): cuánto
    # queda residente el modelo tras esa llamada. "-1" = indefinido (139). 🔑 El warm-up deja el modelo
    # residente con keep_alive=-1, PERO una petición real SIN keep_alive resetea el keep-alive de Ollama
    # al default de 5 min → el modelo se descarga en el primer hueco de inactividad y la siguiente
    # petición vuelve a pagar el frío ~342s (síntoma: "el análisis principal demora una eternidad").
    # Con "-1" cada inferencia REAFIRMA la residencia indefinida. En dev con RAM ajustada poner
    # CONSULTA_KEEP_ALIVE="5m" (o "0") para que qwen no quede residente para siempre.
    consulta_keep_alive: str = "-1"
    # Análisis Ejecutivo: en dev sirve el composer determinista (superior al qwen local);
    # en prod (gemma4:latest) poner EJECUTIVO_USAR_LLM=true en el .env para el pulido de prosa.
    ejecutivo_usar_llm: bool = False
    # En pruebas: EJECUTIVO_FALLBACK=false → si Gemma falla NO se muestra el texto base, sino el
    # error + la respuesta cruda de Gemma (para validar el comportamiento del LLM). Default true (prod).
    ejecutivo_fallback: bool = True
    # Tarjetas KPI de cierre (Nivel 1, plan_tarjetas_kpi_cierre_2026-07-21): eje de estado PROPIO
    # (alineado/ajustado/actuar), independiente de _estado() (L596 de analisis/api.py, que sirve
    # los chips/tabs existentes con otros umbrales — 90/75). Ámbar desde meta*0.93; rojo (actuar)
    # por debajo; verde (alineado) en o sobre la meta. Calibrado a ojo con mayo-2026 (Rubiales
    # 95.6% -> ajustado, APIAY 50.7% -> actuar); recalibrar aquí si hace falta, nunca en el código.
    kpi_cierre_ambar_pct: float = 0.93

    @property
    def keep_alive_ollama(self):
        """Valor de keep_alive para el body de Ollama: int si es numérico ("-1"/"0"/"600" segundos),
        si no la string de duración tal cual ("5m", "10m"). Ollama exige el ENTERO -1 como número JSON
        (la string "-1" la interpretaría como duración Go inválida y fallaría); "5m" sí va como string."""
        v = self.consulta_keep_alive.strip()
        try:
            return int(v)
        except ValueError:
            return v

def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
