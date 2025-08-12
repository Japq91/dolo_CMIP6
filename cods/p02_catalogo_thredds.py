#!/usr/bin/env python3
# test_p02.py  (actualizado)
import argparse, sys, os, urllib.request, urllib.error, re
from urllib.parse import urlparse, parse_qs, unquote, urljoin
from html.parser import HTMLParser
from collections import defaultdict, deque
'''#
ejemplo:
python3 p02_catalogo_thredds.py urls_tas_ssp126.txt
#'''
class LinkGrab(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []
    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.hrefs.append(href)

def fetch(url, timeout=60):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")

def has_dataset_nc(url):
    qs = parse_qs(urlparse(url).query)
    ds = qs.get("dataset", [None])[0]
    return bool(ds and ds.endswith(".nc"))

def is_subcatalog(url):
    p = urlparse(url)
    return p.path.endswith("catalog.html") and not has_dataset_nc(url)

def extract_year_and_version(url):
    qs = parse_qs(urlparse(url).query)
    ds = qs.get("dataset", [None])[0]
    if not ds:
        return None, (0, 0)
    name = os.path.basename(unquote(ds))
    # ..._YYYY.nc   o ..._YYYY_vM.m.nc
    m = re.search(r'_(\d{4})(?:_v(\d+)\.(\d+))?\.nc$', name)
    if not m:
        return None, (0, 0)
    year = int(m.group(1))
    version = (int(m.group(2) or 0), int(m.group(3) or 0))
    return year, version

def crawl_catalog(start_url, recursive=True, timeout=60):
    start_p = urlparse(start_url)
    q = deque([start_url])
    seen = set([start_url])
    out = set()
    while q:
        cur = q.popleft()
        try:
            html = fetch(cur, timeout=timeout)
        except urllib.error.URLError as e:
            print(f"# Aviso: no se leyó {cur} ({e})", file=sys.stderr)
            continue
        p = LinkGrab(); p.feed(html)
        for href in p.hrefs:
            absu = urljoin(cur, href)
            if urlparse(absu).netloc != start_p.netloc:
                continue
            if has_dataset_nc(absu):
                out.add(absu)
            elif recursive and is_subcatalog(absu) and absu not in seen:
                seen.add(absu); q.append(absu)
    return sorted(out)

def extract_metadata_from_url(url):
    """Extrajo variable, modelo y periodo desde la ruta estándar GDDP-CMIP6."""
    parts = url.strip().split('/')
    try:
        modelo  = parts[8]
        periodo = parts[9]
        variable = parts[11]
        return variable, modelo, periodo
    except IndexError:
        print(f"Error: URL con formato inesperado - {url}", file=sys.stderr)
        return None, None, None

def main():
    ap = argparse.ArgumentParser(
        description="Extraer ?dataset=...*.nc por catálogo, filtrando años por periodo y eligiendo la última versión"
    )
    ap.add_argument("input_file", help="Archivo .txt con URLs de catálogos THREDDS (una por línea)")
    ap.add_argument("--no-recursive", action="store_true")
    ap.add_argument("--timeout", type=int, default=60)
    # Rango “fallback” si no es historical ni ssp*
    ap.add_argument("--year-min", type=int, default=1980)
    ap.add_argument("--year-max", type=int, default=2014)
    args = ap.parse_args()

    output_dir = "enlaces"
    os.makedirs(output_dir, exist_ok=True)

    with open(args.input_file, 'r') as f:
        urls = [line.strip() for line in f if line.strip()]

    total_urls = 0

    for url in urls:
        variable, modelo, periodo = extract_metadata_from_url(url)
        if not all([variable, modelo, periodo]):
            continue

        per_low = periodo.lower()
        # Reglas pedidas:
        if per_low.startswith("ssp"):
            y_min, y_max = 2015, 2100
        elif per_low == "historical":
            y_min, y_max = 1980, 2014
        else:
            y_min, y_max = args.year_min, args.year_max  # respaldo

        output_file = os.path.join(output_dir, f"{variable}_{modelo}_{periodo}.txt")

        try:
            nc_urls = crawl_catalog(url, recursive=not args.no_recursive, timeout=args.timeout)

            grouped_files = defaultdict(list)
            for u in nc_urls:
                year, version = extract_year_and_version(u)
                if year is None:
                    continue
                if y_min <= year <= y_max:
                    parsed = urlparse(u)
                    qs = parse_qs(parsed.query)
                    ds_name = unquote(qs.get("dataset", [""])[0])
                    base_name = re.sub(r'_v\d+\.\d+\.nc$', '.nc', ds_name)
                    grouped_files[(year, base_name)].append((version, u))

            filtered_urls = []
            for (year, base_name), versions in grouped_files.items():
                versions.sort(key=lambda x: x[0], reverse=True)
                filtered_urls.append(versions[0][1])

            if not filtered_urls:
                print(f"# Aviso: sin datasets {y_min}-{y_max} para {modelo}/{periodo}/{variable}")
                continue

            with open(output_file, 'w') as f_out:
                f_out.write("\n".join(sorted(filtered_urls)) + "\n")

            total_urls += len(filtered_urls)
            print(f"Se escribió {len(filtered_urls)} enlaces en {output_file}")

        except Exception as e:
            print(f"Error procesando {url}: {e}", file=sys.stderr)

    print(f"\nProceso completado. Total de enlaces guardados: {total_urls}")
    print(f"Carpeta de salida: {output_dir}")

if __name__ == "__main__":
    main()

