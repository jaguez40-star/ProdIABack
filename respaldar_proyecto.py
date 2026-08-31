#!/usr/bin/env python3
"""Empaqueta ProdIA (frontend + backend) en un unico .zip minimo y restaurable.

Uso:
    python respaldar_proyecto.py                 # respaldo estandar
    python respaldar_proyecto.py --con-env       # incluye los .env (CREDENCIALES)
    python respaldar_proyecto.py --con-datos     # incluye las BD SQLite ligeras
    python respaldar_proyecto.py --salida D:\\    # otra carpeta de destino

QUE INCLUYE
    Todo lo que git tiene versionado en los dos repos. Ni un archivo mas.
    Ese es el criterio: si git no lo versiona, o es regenerable o es basura.
    Se anade RESPALDO_MANIFEST.md con el commit de cada repo y como restaurar.

QUE DEJA FUERA, y como se recrea
    venv\\ y .venv\\          ->  install.bat  /  uv sync --python 3.12
    node_modules\\ y dist\\   ->  npm install  /  npm run build
    vector_db\\               ->  python scripts/refresh_vector_db.py
    __pycache__, .pytest_cache, *.pyc
    data/*.db, *.zip, *.xlsm  ->  datos pesados: viajan aparte
    .git\\                    ->  el historial vive en el repositorio remoto
    .env                      ->  solo con --con-env (llevan credenciales)

POR QUE SE DIRIGE POR git ls-files
    Un espejo del arbol (robocopy /MIR, shutil.copytree) arrastra todo lo que
    .gitignore ignora: entornos, temporales, copias " - Copy", bases de datos.
    Fue el mecanismo por el que Azure acumulo ~151 MB de basura desde julio.
    Preguntarle a git es la unica forma de que el respaldo sea exactamente el
    proyecto y nada mas.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

REPOS = ("frontend", "backend")


def _raiz() -> Path:
    """Carpeta que contiene frontend\\ y backend\\.

    El script se versiona dentro de cada repo, pero para funcionar tiene que
    verlos como hermanos. Se busca junto al archivo y un nivel por encima, asi
    sirve tanto en la raiz del espacio de trabajo como dentro de un repo.
    """
    aqui = Path(__file__).resolve().parent
    for cand in (aqui, aqui.parent):
        if all((cand / r).is_dir() for r in REPOS):
            return cand
    return aqui


RAIZ = _raiz()

# Archivos no versionados que si merece la pena llevar, por opcion explicita.
ENV_EXTRA = ["\u002eenv"]
DATOS_EXTRA = ["data/ROBUSTEZ.db", "data/chat_history.db"]


def git(repo: Path, *args: str) -> str:
    """Ejecuta git en un repo y devuelve su salida limpia ('' si falla)."""
    try:
        r = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except FileNotFoundError:
        return ""


def versionados(repo: Path) -> list[str]:
    """Rutas relativas que git tiene en HEAD. Es el contenido del respaldo."""
    salida = git(repo, "ls-files")
    return [l.strip() for l in salida.splitlines() if l.strip()]


def humano(n: int) -> str:
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} TB"


def manifiesto(info: dict, con_env: bool, con_datos: bool) -> str:
    lineas = [
        "# Respaldo de ProdIA",
        "",
        f"**Generado:** {datetime.now():%Y-%m-%d %H:%M}",
        f"**Origen:** `{RAIZ}`",
        "",
        "## Version de cada repo",
        "",
        "| Repo | Rama | Commit | Archivos |",
        "|---|---|---|---|",
    ]
    for nombre, d in info.items():
        lineas.append(
            f"| {nombre} | {d['rama'] or '-'} | `{d['sha'] or '-'}` | {d['n']} |"
        )

    lineas += [
        "",
        f"**`.env` incluidos:** {'SI - CONTIENEN CREDENCIALES' if con_env else 'no'}",
        f"**BD SQLite incluidas:** {'si' if con_datos else 'no'}",
        "",
        "## Como restaurar",
        "",
        "```powershell",
        "# 1. Descomprimir donde vaya a vivir el proyecto",
        "#    Quedan dos carpetas HERMANAS: frontend\\ y backend\\  (no anidadas)",
        "",
        "# 2. Python 3.12 exacto (no 3.13 ni 3.14: onnxruntime no tiene wheels)",
        "uv python install 3.12",
        "uv venv --seed --python 3.12 .\\frontend\\venv",
        "",
        "# 3. Dependencias",
        "cd frontend;         .\\install.bat        # reutiliza el venv ya creado",
        "cd ..\\backend\\backend; uv sync --python 3.12",
        "",
        "# 4. Los .env  (si no venian en el zip, hay que reponerlos a mano)",
        "#    frontend\\.env  y  backend\\.env  -- sin BOM, un solo bloque activo",
        "",
        "# 5. Arrancar y verificar",
        "cd ..\\..;  .\\backend\\iniciar_backend.bat      # INGESTA :5030",
        "           .\\frontend\\iniciar_frontend.bat    # Flask   :5029",
        "cd frontend; .\\verificar_deploy.ps1",
        "```",
        "",
        "## Lo que NO viene, y como se recrea",
        "",
        "| Ausente | Se recrea con |",
        "|---|---|",
        "| `venv\\`, `.venv\\` | `install.bat` / `uv sync --python 3.12` |",
        "| `node_modules\\`, `dist\\` | `npm install` / `npm run build` |",
        "| `vector_db\\` | `python scripts/refresh_vector_db.py` |",
        "| `data/*.db` pesadas | Copia aparte o restauracion desde PostgreSQL |",
        "| `.git\\` | `git clone` del repositorio remoto |",
    ]
    if not con_env:
        lineas.append("| `.env` | Reponer a mano: llevan credenciales |")
    return "\n".join(lineas) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Respaldo minimo de ProdIA en .zip")
    ap.add_argument("--con-env", action="store_true",
                    help="incluye los .env (CREDENCIALES: no circular el zip)")
    ap.add_argument("--con-datos", action="store_true",
                    help="incluye ROBUSTEZ.db y chat_history.db")
    ap.add_argument("--salida", default=str(RAIZ),
                    help="carpeta donde dejar el zip (por defecto, la raiz del repo)")
    args = ap.parse_args()

    faltan = [r for r in REPOS if not (RAIZ / r / ".git").is_dir()]
    if faltan:
        print(f"ERROR: no encuentro repo git en: {', '.join(faltan)}")
        print(f"       Este script debe vivir en la raiz que contiene {' y '.join(REPOS)}.")
        return 1

    destino = Path(args.salida).resolve()
    destino.mkdir(parents=True, exist_ok=True)
    zip_path = destino / f"ProdIA_respaldo_{datetime.now():%Y%m%d_%H%M%S}.zip"

    print(f"Respaldando desde : {RAIZ}")
    print(f"Destino           : {zip_path}\n")

    info: dict[str, dict] = {}
    incluidos = omitidos = 0

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for nombre in REPOS:
            repo = RAIZ / nombre
            rutas = versionados(repo)
            if not rutas:
                print(f"  AVISO: {nombre} no devolvio archivos versionados. Se omite.")
                continue

            sucio = git(repo, "status", "--porcelain")
            if sucio:
                n = len(sucio.splitlines())
                print(f"  AVISO: {nombre} tiene {n} archivo(s) sin commitear.")
                print("         El respaldo lleva el contenido del disco, no el del commit.")

            extras = []
            if args.con_env:
                extras += ENV_EXTRA
            if args.con_datos:
                extras += DATOS_EXTRA

            n_repo = 0
            for rel in rutas + extras:
                origen = repo / rel
                if not origen.is_file():
                    omitidos += 1
                    continue
                z.write(origen, f"{nombre}/{rel}")
                n_repo += 1
                incluidos += 1

            info[nombre] = {
                "rama": git(repo, "rev-parse", "--abbrev-ref", "HEAD"),
                "sha": git(repo, "rev-parse", "--short", "HEAD"),
                "n": n_repo,
            }
            print(f"  {nombre:9} {n_repo:4} archivos  "
                  f"[{info[nombre]['rama']} {info[nombre]['sha']}]")

        z.writestr("RESPALDO_MANIFEST.md",
                   manifiesto(info, args.con_env, args.con_datos))

    tam = zip_path.stat().st_size
    print(f"\n  Total: {incluidos} archivos" +
          (f"  ({omitidos} no encontrados)" if omitidos else ""))
    print(f"  Tamano: {humano(tam)}")
    print(f"\nListo: {zip_path}")
    if args.con_env:
        print("\n  ATENCION: el zip lleva los .env con credenciales.")
        print("            No lo subas a ningun sitio ni lo mandes por correo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
