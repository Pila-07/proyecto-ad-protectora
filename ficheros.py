"""ficheros.py - Todo lo que toca ficheros: la carpeta datos, el registro, el JSON, el XML
y la copia de seguridad.

Parte de los ejemplos 10 (el registro que crece), 17 (JSON), 15 (XML) y 9 (copiar).
"""
import json
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

DATOS = Path("datos")
DATOS.mkdir(exist_ok=True)

COPIAS = Path("copias")


def apuntar(texto):
    """Una línea en el registro de operaciones, con la fecha y la hora."""
    momento = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    with open(DATOS / "registro.txt", "a", encoding="utf-8") as f:
        f.write(f"{momento} {texto}\n")


def guardar_json(nombre, datos):
    """Guarda una lista de diccionarios en datos/<nombre>, con las tildes como tildes."""
    with open(DATOS / nombre, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=2, ensure_ascii=False)


def guardar_xml(nombre, datos):
    """El informe en XML: un elemento <especie> por fila, con su nombre y sus adopciones."""
    raiz = ET.Element("informe", titulo="Adopciones por especie")
    for fila in datos:
        especie = ET.SubElement(raiz, "especie")
        ET.SubElement(especie, "nombre").text = fila["especie"]
        ET.SubElement(especie, "adopciones").text = str(fila["adopciones"])
    arbol = ET.ElementTree(raiz)
    ET.indent(arbol, space="  ")
    arbol.write(DATOS / nombre, encoding="utf-8", xml_declaration=True)


def copia_de_seguridad(base):
    """Copia el fichero de la base a copias/, con la fecha y la hora en el nombre.

    Sin ':' en el nombre: Windows no los admite.
    """
    COPIAS.mkdir(exist_ok=True)
    origen = Path(base)
    momento = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    destino = COPIAS / f"{origen.stem}_{momento}{origen.suffix}"
    shutil.copy2(origen, destino)
    return destino
