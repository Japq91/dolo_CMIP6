# NEX-GDDP-CMIP6 — Descarga diaria a NetCDF (pipeline)
`https://www.nccs.nasa.gov/services/data-collections/land-based-products/nex-gddp-cmip6`
`https://ds.nccs.nasa.gov/thredds/catalog/AMES/NEX/GDDP-CMIP6/catalog.html`
- Este repositorio automatizó la **obtención de datos diarios** de modelos **CMIP6** (NEX‑GDDP‑CMIP6, NASA NCCS) vía **THREDDS**. El flujo produjo **NetCDF** recortados opcionalmente por caja espacial y guardados por **modelo** y **mes**.

## Alcance
- Los datos en esta version son **datos diarios** (e.g., `tas_day`, `pr_day`) en NetCDF,las varaibles disponibles son: [hurs, huss, pr, rlds, rsds, sfcWind, tas, tasmax, tasmin]
- Se trabajó con escenarios **históricos** y **SSP** [126,245,370,585] #(depende del modelo).
- Se usó **NCSS** (NetCDF Subset Service) para subsetting espacial/temporal.

## Requisitos
- Python 3.7+.
- `wget` en PATH.
- Conectividad HTTPS a `ds.nccs.nasa.gov`.

## Estructura
```
cods/
  p00_make_url.py
  p01_lista_comunes.py
  p02_catalogo_thredds.py
  p03_thredds_ncss.py
data/
  <MODELO>/
README.md
```

---

## Pipeline general

1) **Enumeración de catálogos por variable y periodo**  
   Se generó un archivo `urls_<variable>_<periodo>.txt` con las URLs de **catálogo por modelo/miembro**.
   ```bash
   # Ejemplos
   python3 cods/p00_make_url.py pr historical
   python3 cods/p00_make_url.py tas ssp126
   # Salida: urls_pr_historical.txt, urls_tas_ssp126.txt
   ```

2) **Extracción de datasets por año y versión (filtro temporal)**  
   A partir de `urls_<variable>_<periodo>.txt`, se listaron los datasets `?dataset=...*.nc` de cada modelo,
   se filtraron años por periodo (**historical: 1980–2014**, **ssp*: 2015–2100**) y se eligió la **versión más reciente** por año.  
   ```bash
   python3 cods/p02_catalogo_thredds.py urls_pr_historical.txt
   # Salida: enlaces/pr_<MODELO>_historical.txt   (uno por modelo)
   ```

3) **(Opcional) Detección de modelos “completos” entre conjuntos**  
   Se identificaron modelos presentes en **todos** los archivos `urls_*` elegidos (útil para cruzar variables/escenarios).  
   ```bash
   python3 cods/p01_lista_comunes.py
   # Imprimió modelos completos e incompletos
   ```

4) **Descarga mensual vía NCSS**  
   Para cada archivo `enlaces/<variable>_<modelo>_<periodo>.txt`, se descargó **un NetCDF por mes** respetando el calendario
   (manejo automático de `noleap`/`360_day` y reintentos de fin de mes) y se guardó en `../data/<MODELO>/`.
   ```bash
   # Ejemplo con recorte para Sudamérica y compresión NetCDF4
   python3 cods/p03_thredds_ncss.py enlaces/pr_ACCESS-CM2_historical.txt      --bbox -90 -30 -60 15 --netcdf4
   # Salida: ../data/ACCESS-CM2/pr_day_ACCESS-CM2_..._YYYYMM.nc  (12/archivos por año)
   ```

---

## Detalle de scripts

### `p00_make_url.py`
- **Qué hizo:** Listó, desde el catálogo raíz XML, las URLs de **nivel variable** por **modelo/periodo/miembro** y construyó `urls_<variable>_<periodo>.txt`.  
- **Entrada:** `variable` (p.ej. `pr`, `tas`), `periodo` (p.ej. `historical`, `ssp126`, `ssp245`, `ssp585`).  
- **Salida:** `urls_<variable>_<periodo>.txt` con enlaces tipo:  
  `https://.../GDDP-CMIP6/<MODELO>/<PERIODO>/<MIEMBRO>/<VARIABLE>/catalog.html`
- **Ejemplo:**  
  ```bash
  python3 cods/p00_make_url.py pr historical
  ```

### `p02_catalogo_thredds.py`
- **Qué hizo:** Recorrió cada URL de `urls_<variable>_<periodo>.txt`, extrajo los `?dataset=...*.nc`, filtró **años** según el periodo
  (historical: 1980–2014; ssp*: 2015–2100) y eligió la **última versión** por año cuando existieron múltiples (`_vM.m`).  
- **Entrada:** `urls_<variable>_<periodo>.txt`.  
- **Salida:** un archivo por modelo en `enlaces/`, con nombre `enlaces/<variable>_<modelo>_<periodo>.txt`.  
- **Notas:** Gestionó errores HTTP y continuó procesando otros modelos.

### `p01_lista_comunes.py` (opcional)
- **Qué hizo:** Detectó **modelos comunes** entre múltiples archivos `urls_*` (lista editable al inicio del script) e informó modelos incompletos.  
- **Entrada:** archivos `urls_*` existentes en el directorio actual.  
- **Salida:** impresión en consola (modelos completos / incompletos y detalle por variable/escenario).

### `p03_thredds_ncss.py`
- **Qué hizo:** Descargó **mensualmente** vía NCSS, respetando el **calendario** (`--calendar auto|noleap|gregorian|360_day`) y reintentando automáticamente cuando el día final fue inválido (ej., febrero en `noleap`).  
- **Entrada:** archivo de **enlaces con `?dataset=...`** (los emitidos por `p02`), p.ej.: `enlaces/pr_ACCESS-CM2_historical.txt`.  
- **Parámetros clave:**
  - `--bbox W E S N` (subconjunto lon/lat, grados; omitido ⇒ sin recorte).
  - `--netcdf4` (usa `accept=netcdf4`).
  - `--hour` (hora UTC para límites de mes, por defecto 12).
  - `--base-dir` (directorio base de salida; por defecto `../data`).
- **Salida:** `../data/<MODELO>/<archivo>_YYYYMM.nc` (12 archivos por año y por ruta `dataset`).
- **Ejemplo:**
  ```bash
  python3 cods/p03_thredds_ncss.py enlaces/pr_TaiESM1_ssp126.txt     --bbox -83 -30 -58 14 --netcdf4
  ```

---

## Buenas prácticas y notas
- El **nombre mensual** fue insertado como `_YYYYMM_` antes del sufijo de versión del dataset.
- `wget --continue` permitió **reanudar** descargas; el script evitó sobrescribir si el archivo ya existía.
- **Errores 400** típicos se debieron a calendarios `noleap`/`360_day`; el script reintentó con fin de mes válido.
- Las longitudes del THREDDS estuvieron en **−180..180**; verificar `--bbox` si la petición devuelve 400 por límites inválidos.
- Los catálogos y datasets pueden **cambiar**; se recomendó repetir **pasos 1–2** cuando se actualicen versiones.

## Ejemplos rápidos

Histórico precipitación (global sin recorte):
```bash
python3 cods/p00_make_url.py pr historical
python3 cods/p02_catalogo_thredds.py urls_pr_historical.txt
python3 cods/p03_thredds_ncss.py enlaces/pr_ACCESS-CM2_historical.txt --netcdf4
```

SSP126 temperatura (Sudamérica):
```bash
python3 cods/p00_make_url.py tas ssp126
python3 cods/p02_catalogo_thredds.py urls_tas_ssp126.txt
python3 cods/p03_thredds_ncss.py enlaces/tas_TaiESM1_ssp126.txt --bbox -83 -30 -58 14 --netcdf4
```

---

## Créditos
- Jonathan-APQ
- NEX‑GDDP‑CMIP6 (NASA NCCS).  
- THREDDS / NetCDF Subset Service (UCAR/Unidata).
