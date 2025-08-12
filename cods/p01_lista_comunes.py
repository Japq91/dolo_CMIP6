import os

# Lista de todos los archivos
archivos = [
    "urls_pr_historical.txt", "urls_pr_ssp126.txt", "urls_pr_ssp245.txt", "urls_pr_ssp585.txt",
    "urls_tas_historical.txt", "urls_tas_ssp126.txt", "urls_tas_ssp245.txt", "urls_tas_ssp585.txt"
]

# Paso 1: Extraer modelos de cada archivo
modelos_por_archivo = {}
modelos_totales = set()

for archivo in archivos:
    modelos = set()
    with open(archivo, 'r') as f:
        for linea in f:
            partes = linea.strip().split('/')
            # El modelo siempre está en la posición 8 (index 8)
            modelo = partes[8]
            modelos.add(modelo)
            modelos_totales.add(modelo)
    modelos_por_archivo[archivo] = modelos

# Paso 2: Encontrar modelos comunes (presentes en todos los archivos)
modelos_comunes = set(modelos_por_archivo[archivos[0]])
for archivo in archivos[1:]:
    modelos_comunes &= modelos_por_archivo[archivo]
print('COMPLETOS\n%s'%list(modelos_comunes))
# Paso 3: Encontrar modelos incompletos (faltan en al menos un archivo)
modelos_incompletos = modelos_totales - modelos_comunes
print('*********\nINCOMPLETOS\n%s'%list(modelos_incompletos))
''' #comentar o descomentar aqui
# Paso 4: Imprimir resultados
print("Modelos presentes en TODOS los archivos:")
for modelo in sorted(modelos_comunes):
    print(f"- {modelo}")

print("\nModelos FALTANTES en al menos un archivo:")
for modelo in sorted(modelos_incompletos):
    print(f"- {modelo}")

# Paso 5: Identificar exactamente dónde faltan los modelos incompletos
print("\nDetalle de ausencias:")
for modelo in sorted(modelos_incompletos):
    ausencias = []
    for archivo in archivos:
        if modelo not in modelos_por_archivo[archivo]:
            # Extraer variable y escenario del nombre del archivo
            partes_nombre = os.path.splitext(archivo)[0].split('_')
            variable = partes_nombre[1]
            escenario = partes_nombre[2]
            ausencias.append(f"{variable} ({escenario})")
    
    print(f"{modelo} falta en: {', '.join(ausencias)}")
#'''
