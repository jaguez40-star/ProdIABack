"""Uso: PYTHONPATH=. uv run python app/features/consulta/golden/run_golden.py"""
import yaml, pathlib
from app.features.consulta.extraccion import extraer

def main():
    p = pathlib.Path(__file__).with_name("extraccion_golden.yaml")
    casos = yaml.safe_load(p.read_text(encoding="utf-8"))
    ok = 0
    for c in casos:
        got = extraer(c["pregunta"])
        exp = c["esperado"]
        match = all(str(got.get(k)).upper() == str(exp.get(k)).upper() if k == "entidad"
                    else got.get(k) == exp.get(k) for k in exp)
        ok += bool(match)
        print(("OK " if match else "XX ") + c["pregunta"] + (" -> " + str(got) if not match else ""))
    print(f"\nEXACTITUD: {ok}/{len(casos)} = {100*ok//len(casos)}%   (umbral D7: >=90%)")

if __name__ == "__main__":
    main()
