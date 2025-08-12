#!/usr/bin/env python3
import sys, urllib.request, urllib.error
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET
'''
ejemplo:
python3 p01_make_url.py pr historical (ssp126,ssp245...)
'''
ROOT_XML = "https://ds.nccs.nasa.gov/thredds/catalog/AMES/NEX/GDDP-CMIP6/catalog.xml"

def fetch(url, timeout=30):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()

def catalog_refs(catalog_xml_url):
    """Devolvió lista de (name, abs_url) de <catalogRef> en un catálogo XML."""
    data = fetch(catalog_xml_url)
    # Manejo de namespaces sin hardcodear prefijos
    root = ET.fromstring(data)
    out=[]
    for elem in root.iter():
        if elem.tag.endswith("catalogRef"):
            href=None; name=elem.attrib.get("name","")
            # atributos posibles: xlink:href, href
            for k,v in elem.attrib.items():
                if k.endswith("href"):
                    href=v; break
            if href:
                out.append((name, urljoin(catalog_xml_url, href)))
    return out

def filter_refs_by_depth(urls, depth_end):
    """Filtró catálogos por profundidad relativa a .../GDDP-CMIP6/ (para reconocer niveles)."""
    res=[]
    for name,u in urls:
        parts = urlparse(u).path.split("/")
        # buscar índice del segmento "GDDP-CMIP6"
        try:
            i = parts.index("GDDP-CMIP6")
        except ValueError:
            continue
        # queremos URLs cuyo final coincida con depth_end (lista de segmentos)
        if parts[-len(depth_end):] == depth_end:
            res.append((name,u))
    return res

def main():
    if len(sys.argv)!=3:
        print("Uso: python3 make_urls_by_var_period_fast.py <variable> <periodo>", file=sys.stderr)
        print("Ej.:  python3 make_urls_by_var_period_fast.py pr historical", file=sys.stderr)
        sys.exit(2)
    var, period = sys.argv[1], sys.argv[2]
    outname = f"urls_{var}_{period}.txt"

    # Nivel modelos: .../GDDP-CMIP6/<MODELO>/catalog.xml
    model_refs = []
    for name,u in catalog_refs(ROOT_XML):
        # Filtró catálogos que terminaban en .../<MODEL>/catalog.xml
        if urlparse(u).path.endswith("/catalog.xml"):
            parts = urlparse(u).path.split("/")
            if len(parts)>=2 and parts[-2] != "GDDP-CMIP6":
                model_refs.append((name,u))

    urls_out = []

    for mname, mxml in model_refs:
        # Nivel periodo: .../<MODELO>/<PERIODO>/catalog.xml
        try:
            period_refs = catalog_refs(mxml)
        except urllib.error.URLError:
            continue
        period_xmls = []
        for pname, purl in period_refs:
            if f"/{period}/catalog.xml" in urlparse(purl).path:
                period_xmls.append((pname,purl))
        if not period_xmls:
            continue

        for pname, pxml in period_xmls:
            # Nivel miembro: .../<MODELO>/<PERIODO>/<MIEMBRO>/catalog.xml
            try:
                member_refs = catalog_refs(pxml)
            except urllib.error.URLError:
                continue
            member_xmls = []
            for tname, turl in member_refs:
                # aceptó cualquier miembro (r*i*p*f*)
                if urlparse(turl).path.endswith("/catalog.xml") and f"/{period}/" in urlparse(turl).path:
                    # aseguró que fuese un nivel más profundo
                    if urlparse(turl).path.count("/") == urlparse(pxml).path.count("/") + 1:
                        member_xmls.append((tname,turl))
            if not member_xmls:
                continue

            for memname, memxml in member_xmls:
                # Nivel variable: .../<MODELO>/<PERIODO>/<MIEMBRO>/<VAR>/catalog.xml
                try:
                    var_refs = catalog_refs(memxml)
                except urllib.error.URLError:
                    continue
                for vname, vxml in var_refs:
                    if f"/{var}/catalog.xml" in urlparse(vxml).path:
                        vhtml = vxml.replace("/catalog.xml","/catalog.html")
                        urls_out.append(vhtml)

    urls_out = sorted(set(urls_out))
    if not urls_out:
        print("No se hallaron URLs para esa variable y periodo.", file=sys.stderr)
        sys.exit(1)

    with open(outname,"w") as f:
        f.write("\n".join(urls_out) + "\n")
    print(f"Se escribió {len(urls_out)} URL(s) en {outname}")

if __name__=="__main__":
    main()

