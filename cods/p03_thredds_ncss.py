#!/usr/bin/env python3
# p03_thredds_ncss.py  (mensual + calendario + reintento 400)
import argparse, os, re, shlex, subprocess, calendar as calmod
from urllib.parse import urlparse, parse_qs, unquote

def infer_var(dataset_path, forced_var=None):
    if forced_var: return forced_var
    parts = dataset_path.split("/")
    if len(parts) >= 2: return parts[-2]
    base = os.path.basename(dataset_path)
    return (base.split("_", 1)[0]) or "var"

def extract_model_from_catalog_url(catalog_url: str) -> str:
    parts = urlparse(catalog_url).path.strip("/").split("/")
    try:
        i = parts.index("GDDP-CMIP6")
        model = parts[i + 1]
        return model or "unknown_model"
    except Exception:
        return "unknown_model"

def parse_fname_year_version(fname: str):
    m = re.search(r'_(\d{4})(?:(_v\d+(?:\.\d+)?))?\.nc$', fname)
    if not m: return None, ''
    return int(m.group(1)), (m.group(2) or '')

def make_monthly_fname(fname: str, year: int, month: int):
    m = re.search(r'(?P<base>.*_)(?P<year>\d{4})(?P<ver>(_v\d+(?:\.\d+)?)?)\.nc$', fname)
    if not m:
        base, ext = os.path.splitext(fname)
        return f"{base}_{year:04d}{month:02d}{ext}"
    base = m.group('base'); ver = m.group('ver') or ''
    return f"{base}{year:04d}{month:02d}{ver}.nc"

def build_ncss_base_and_fname(catalog_url, var=None):
    u = urlparse(catalog_url.strip())
    qs = parse_qs(u.query)
    if "dataset" not in qs or not qs["dataset"]:
        raise ValueError("Faltó ?dataset= en la URL de catálogo.")
    dataset_path = unquote(qs["dataset"][0]).lstrip("/")
    fname = os.path.basename(dataset_path) or "out.nc"
    var = infer_var(dataset_path, forced_var=var)
    base = f"https://{u.netloc}/thredds/ncss/grid/{dataset_path}"
    return base, var, fname

def month_last_day(year: int, month: int, cal: str) -> int:
    cal = cal.lower()
    if cal == "360_day":
        return 30
    if cal == "noleap":
        return 28 if month == 2 else calmod.monthrange(year, month)[1]
    if cal == "auto":
        # auto: trató febrero como noleap (seguro para CMIP/NEX); resto gregoriano
        return 28 if month == 2 else calmod.monthrange(year, month)[1]
    # gregoriano
    return calmod.monthrange(year, month)[1]

def monthly_bounds(year: int, month: int, hour: int, calname: str):
    last = month_last_day(year, month, calname)
    start = f"{year:04d}-{month:02d}-01T{hour:02d}:00:00Z"
    end   = f"{year:04d}-{month:02d}-{last:02d}T{hour:02d}:00:00Z"
    return start, end, last

def run_wget(out_path: str, url: str, tries=5, timeout=60, waitretry=10):
    cmd = [
        "wget","--continue", f"--tries={tries}",
        f"--timeout={timeout}", f"--waitretry={waitretry}",
        "--retry-connrefused", "-O", out_path, url
    ]
    print(" ".join(shlex.quote(c) for c in cmd), flush=True)
    subprocess.run(cmd, check=True)

def main():
    ap = argparse.ArgumentParser(description="Descarga mensual vía NCSS; respeta calendario; guarda en ../data/<MODELO>/")
    ap.add_argument("txt", help="Archivo .txt con URLs de catálogo (una por línea).")
    ap.add_argument("--bbox", nargs=4, type=float, metavar=("WEST","EAST","SOUTH","NORTH"),
                    help="Caja lon/lat (-180..180). Si se omite, sin recorte.")
    ap.add_argument("--stride", type=int, default=1, help="horizStride (default: 1)")
    ap.add_argument("--var", default=None, help="Variable (si no, se infiere).")
    ap.add_argument("--hour", type=int, default=12, help="Hora UTC para time_start/time_end (default: 12)")
    ap.add_argument("--calendar", choices=["auto","noleap","gregorian","360_day"], default="auto",
                    help="Calendario temporal (default: auto=noleap en feb).")
    ap.add_argument("--netcdf4", action="store_true", help="accept=netcdf4 (si no, netcdf3)")
    ap.add_argument("--dry-run", action="store_true", help="Solo imprime comandos.")
    ap.add_argument("--no-add-latlon", action="store_true", help="No incluye addLatLon=true.")
    ap.add_argument("--tries", type=int, default=5)
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--waitretry", type=int, default=10)
    ap.add_argument("--base-dir", default="../data", help="Directorio base (default: ../data)")
    args = ap.parse_args()

    if not os.path.isfile(args.txt):
        raise SystemExit(f"No existió {args.txt}")

    with open(args.txt) as f:
        lines = [ln.strip() for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
    if not lines:
        raise SystemExit("No hubo URLs en el archivo.")

    for url in lines:
        base, var, fname = build_ncss_base_and_fname(url, var=args.var)
        year, _ = parse_fname_year_version(fname)
        if year is None:
            print(f"# Aviso: no se pudo inferir año desde {fname}; se saltó.", flush=True)
            continue

        model = extract_model_from_catalog_url(url)
        out_dir = os.path.join(args.base_dir, model)
        os.makedirs(out_dir, exist_ok=True)

        for m in range(1, 13):
            t0, t1, last = monthly_bounds(year, m, args.hour, args.calendar)
            q = [f"var={var}"]
            if args.bbox:
                west, east, south, north = args.bbox
                q += [f"north={north}", f"west={west}", f"east={east}", f"south={south}", f"horizStride={args.stride}"]
            q += [f"time_start={t0}", f"time_end={t1}"]
            q.append(f"accept={'netcdf4' if args.netcdf4 else 'netcdf3'}")
            if not args.no_add_latlon:
                q.append("addLatLon=true")
            ncss_url = f"{base}?{'&'.join(q)}"

            out_name = make_monthly_fname(fname, year, m)
            out_path = os.path.join(out_dir, out_name)
            if os.path.exists(out_path): 
                #adicional para descarga faltantes
                continue 
            if args.dry_run:
                print(f"# DRY: {out_path}")
                print(ncss_url)
                continue

            try:
                run_wget(out_path, ncss_url, tries=args.tries, timeout=args.timeout, waitretry=args.waitretry)
            except subprocess.CalledProcessError as e:
                # Reintento inteligente para 400 por día fuera de rango (p.ej., feb en noleap)
                if m == 2:
                    # forzar 28 días
                    t0 = f"{year:04d}-02-01T{args.hour:02d}:00:00Z"
                    t1 = f"{year:04d}-02-28T{args.hour:02d}:00:00Z"
                    q2 = [f"var={var}"]
                    if args.bbox:
                        west, east, south, north = args.bbox
                        q2 += [f"north={north}", f"west={west}", f"east={east}", f"south={south}", f"horizStride={args.stride}"]
                    q2 += [f"time_start={t0}", f"time_end={t1}"]
                    q2.append(f"accept={'netcdf4' if args.netcdf4 else 'netcdf3'}")
                    if not args.no_add_latlon:
                        q2.append("addLatLon=true")
                    ncss_url2 = f"{base}?{'&'.join(q2)}"
                    try:
                        run_wget(out_path, ncss_url2, tries=args.tries, timeout=args.timeout, waitretry=args.waitretry)
                        continue
                    except subprocess.CalledProcessError:
                        raise
                # Opcional: si cal=360_day y falla un mes de 31 días, intentar 30 días
                if args.calendar in ("auto","360_day") and last == 31:
                    t1_alt = f"{year:04d}-{m:02d}-30T{args.hour:02d}:00:00Z"
                    q3 = [f"var={var}"]
                    if args.bbox:
                        west, east, south, north = args.bbox
                        q3 += [f"north={north}", f"west={west}", f"east={east}", f"south={south}", f"horizStride={args.stride}"]
                    q3 += [f"time_start={t0}", f"time_end={t1_alt}"]
                    q3.append(f"accept={'netcdf4' if args.netcdf4 else 'netcdf3'}")
                    if not args.no_add_latlon:
                        q3.append("addLatLon=true")
                    ncss_url3 = f"{base}?{'&'.join(q3)}"
                    run_wget(out_path, ncss_url3, tries=args.tries, timeout=args.timeout, waitretry=args.waitretry)
                else:
                    raise

if __name__ == "__main__":
    main()

