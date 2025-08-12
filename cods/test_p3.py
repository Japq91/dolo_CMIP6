#!/usr/bin/env python3
# p03_thredds_ncss.py  (actualizado)
import argparse
import os
import re
import shlex
import subprocess
from urllib.parse import urlparse, parse_qs, unquote

"""
ejemplo:
python3 p03_thredds_ncss.py urls_var_period.txt --bbox -83 -30 -58 14
# guardó en ../data/<MODELO>/
"""

def infer_var(dataset_path, forced_var=None):
    if forced_var:
        return forced_var
    parts = dataset_path.split("/")
    if len(parts) >= 2:
        return parts[-2]  # penúltima carpeta suele ser la variable
    base = os.path.basename(dataset_path)
    return (base.split("_", 1)[0]) or "pr"

def infer_year(fname, forced_year=None):
    if forced_year:
        return forced_year
    m = re.search(r"_(\d{4})\.nc$", fname)
    return m.group(1) if m else None

def extract_model_from_catalog_url(catalog_url: str) -> str:
    """
    Esperó: .../GDDP-CMIP6/<MODELO>/<PERIODO>/<MIEMBRO>/<VAR>/catalog.html?... 
    """
    path_parts = urlparse(catalog_url).path.strip("/").split("/")
    # buscar índice del segmento "GDDP-CMIP6"
    try:
        i = path_parts.index("GDDP-CMIP6")
        model = path_parts[i + 1]  # siguiente segmento
        if not model:
            raise ValueError
        return model
    except Exception:
        return "unknown_model"

def build_ncss_url(catalog_url, var=None, bbox=None, stride=1, start=None, end=None, netcdf4=False, add_latlon=True):
    u = urlparse(catalog_url.strip())
    qs = parse_qs(u.query)
    if "dataset" not in qs or not qs["dataset"]:
        raise ValueError("Faltó ?dataset= en la URL de catálogo.")
    dataset_path = unquote(qs["dataset"][0]).lstrip("/")
    fname = os.path.basename(dataset_path) or "out.nc"
    var = infer_var(dataset_path, forced_var=var)
    year = infer_year(fname)
    if (start is None or end is None) and year:
        start = start or f"{year}-01-01T12:00:00Z"
        end   = end   or f"{year}-12-31T12:00:00Z"
    base = f"https://{u.netloc}/thredds/ncss/grid/{dataset_path}"
    q = [f"var={var}"]
    if bbox:
        west, east, south, north = bbox
        q += [f"north={north}", f"west={west}", f"east={east}", f"south={south}", f"horizStride={stride}"]
    if start and end:
        q += [f"time_start={start}", f"time_end={end}"]
    q.append(f"accept={'netcdf4' if netcdf4 else 'netcdf3'}")
    if add_latlon:
        q.append("addLatLon=true")
    return f"{base}?{'&'.join(q)}", fname

def main():
    ap = argparse.ArgumentParser(description="Leer URLs de catálogo THREDDS y descargar vía NCSS.")
    ap.add_argument("txt", help="Archivo .txt con URLs de catálogo (una por línea).")
    ap.add_argument("--bbox", nargs=4, type=float, metavar=("WEST","EAST","SOUTH","NORTH"),
                    help="Caja lon/lat (-180..180). Si no se pasa, no recortó espacialmente.")
    ap.add_argument("--stride", type=int, default=1, help="horizStride (default: 1)")
    ap.add_argument("--var", default=None, help="Variable (opcional; si no, se infirió).")
    ap.add_argument("--start", default=None, help="ISO 8601 (opcional).")
    ap.add_argument("--end",   default=None, help="ISO 8601 (opcional).")
    ap.add_argument("--netcdf4", action="store_true", help="Usó accept=netcdf4.")
    ap.add_argument("--dry-run", action="store_true", help="Solo mostró los comandos.")
    ap.add_argument("--no-add-latlon", action="store_true", help="No incluyó addLatLon=true.")
    ap.add_argument("--tries", type=int, default=5)
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--waitretry", type=int, default=10)
    ap.add_argument("--base-dir", default="../data", help="Directorio base para guardar (default: ../data)")
    args = ap.parse_args()

    if not os.path.isfile(args.txt):
        raise SystemExit(f"No existió {args.txt}")

    with open(args.txt) as f:
        lines = [ln.strip() for ln in f if ln.strip() and not ln.lstrip().startswith("#")]

    if not lines:
        raise SystemExit("No hubo URLs de catálogo en el archivo.")

    for url in lines:
        # 1) construyó URL NCSS y nombre de archivo
        ncss_url, fname = build_ncss_url(
            url, var=args.var, bbox=args.bbox, stride=args.stride,
            start=args.start, end=args.end, netcdf4=args.netcdf4,
            add_latlon=not args.no_add_latlon
        )
        # 2) determinó modelo y carpeta destino
        model = extract_model_from_catalog_url(url)
        out_dir = os.path.join(args.base_dir, model)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, fname)

        cmd = [
            "wget","--continue", f"--tries={args.tries}",
            f"--timeout={args.timeout}", f"--waitretry={args.waitretry}",
            "--retry-connrefused", "-O", out_path, ncss_url
        ]
        print(" ".join(shlex.quote(c) for c in cmd))
        if not args.dry_run:
            subprocess.run(cmd, check=True)

if __name__ == "__main__":
    main()

