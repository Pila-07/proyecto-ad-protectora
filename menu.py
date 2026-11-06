"""menu.py - Protectora de animales: aplicación de gestión por consola.

Aquí está el menú y todo el SQL a mano (sqlite3). El resto va en otros ficheros:
    ficheros.py -> la carpeta datos, el registro, el JSON, el XML y la copia de seguridad
    orm.py      -> lo del ORM (SQLAlchemy), sobre la misma base
    servidor.py -> lo de PostgreSQL

Se arranca desde la carpeta del trabajo:  python menu.py
"""
import csv
import sqlite3
from contextlib import closing
from dataclasses import dataclass
import time
import orm
import servidor
from ficheros import DATOS, apuntar, copia_de_seguridad, guardar_json, guardar_xml

BASE = "protectora.db"

MENU = """
=== Protectora de Animales ===
 1. Importar los datos de partida (CSV)
 2. Ver o buscar animales
 3. Alta de un animal
 4. Cambiar la edad de un animal
 5. Adoptar un animal
 6. Ver las adopciones
 7. El informe, y guardarlo en JSON
 8. Devolver un animal (ORM)
 9. Los mejores adoptantes, con SQL a mano (ORM)
10. Llevar los animales al servidor (PostgreSQL)
11. Las estrellas: el animal más adoptado y el adoptante que más adopta
12. Las adopciones de un adoptante, a un CSV
13. Las adopciones de un adoptante (ORM)
14. Alta de un adoptante (ORM)
15. Dar de baja un animal
16. El informe, en XML
17. Copia de seguridad
18. El informe con el ORM, y comparar
19. Cómo busca la base las adopciones de un adoptante
 0. Salir
"""


# ---------------------------------------------------------------- las tablas (paso 3)
def conectar():
    conexion = sqlite3.connect(BASE)
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA foreign_keys = ON")     # sin esto SQLite no comprueba las claves ajenas
    return conexion


def crear_tablas():
    """CREATE TABLE IF NOT EXISTS y sin DROP: la aplicación no pierde los datos al arrancar."""
    with closing(conectar()) as cx, cx:
        cx.executescript("""
            CREATE TABLE IF NOT EXISTS adoptantes (
                id     INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                correo TEXT NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS animales (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre     TEXT NOT NULL UNIQUE,
                especie    TEXT NOT NULL,
                edad       INTEGER NOT NULL CHECK (edad >= 0),
                disponible INTEGER NOT NULL DEFAULT 1 CHECK (disponible IN (0, 1))
            );
            CREATE TABLE IF NOT EXISTS adopciones (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                adoptante_id INTEGER NOT NULL REFERENCES adoptantes(id),
                animal_id    INTEGER NOT NULL REFERENCES animales(id),
                devuelto     INTEGER NOT NULL DEFAULT 0 CHECK (devuelto IN (0, 1))
            );
            CREATE INDEX IF NOT EXISTS idx_adopciones_adoptante ON adopciones(adoptante_id);
        """)


# ---------------------------------------------------------------- opción 1 (paso 6)
def importar(nombre, sql):
    """Lee datos/<nombre>, separado por ";" y con cabecera, y mete cada fila con su INSERT."""
    try:
        with open(DATOS / nombre, encoding="utf-8", newline="") as f:
            filas = list(csv.reader(f, delimiter=";"))
    except FileNotFoundError:
        print("   Falta el fichero", DATOS / nombre)
        apuntar(f"importar {nombre}: falta el fichero")
        return
    except UnicodeDecodeError:
        print(f"   {nombre} no está guardado en UTF-8: guardadlo de nuevo desde VS Code")
        apuntar(f"importar {nombre}: no está en UTF-8")
        return
    nuevas = 0
    for numero, fila in enumerate(filas[1:], start=2):
        try:
            if nombre == "animales.csv":
                datos = (fila[0].strip(), fila[1].strip(), int(fila[2]))
            else:
                datos = (fila[0].strip(), fila[1].strip())
            if "" in datos[:2]:
                raise ValueError("campo vacío")
            with closing(conectar()) as cx, cx:
                cx.execute(sql, datos)
            nuevas += 1
        except (IndexError, ValueError):
            print(f"   {nombre}, línea {numero}: viene mal, la salto")
        except sqlite3.IntegrityError as e:
            print(f"   {nombre}, línea {numero}: no entra o ya esta introducido ({e})")
    print(f"   {nombre}: {nuevas} filas nuevas")
    apuntar(f"importar {nombre}: {nuevas} filas nuevas")


def opcion_1():
    importar("adoptantes.csv", "INSERT INTO adoptantes (nombre, correo) VALUES (?, ?)")
    importar("animales.csv", "INSERT INTO animales (nombre, especie, edad) VALUES (?, ?, ?)")


# ---------------------------------------------------------------- opción 2 (paso 7)
@dataclass
class Animal:
    id: int
    nombre: str
    especie: str
    edad: int
    disponible: int

    def estado(self):
        return "disponible" if self.disponible else "adoptado"


def buscar_animales(texto):
    """Con el texto vacío (Intro), LIKE '%%' los da todos: sirve para ver y para buscar."""
    with closing(conectar()) as cx:
        filas = cx.execute("""SELECT id, nombre, especie, edad, disponible
                              FROM animales
                              WHERE nombre LIKE ? OR especie LIKE ?
                              ORDER BY nombre""",
                           (f"%{texto}%", f"%{texto}%")).fetchall()
    return [Animal(*fila) for fila in filas]


def opcion_2():
    texto = input("Buscar por nombre o especie (Intro para verlos todos): ").strip()
    animales = buscar_animales(texto)
    for a in animales:
        print(f"   {a.id:3d}  {a.nombre:12s} {a.especie:8s} {a.edad:2d} años  {a.estado()}")
    if not animales:
        print("   (ninguno)")


# ---------------------------------------------------------------- opciones 3 y 4 (paso 8)
def alta_animal(nombre, especie, edad):
    if not nombre or not especie:
        return "El nombre y la especie son obligatorios"
    try:
        with closing(conectar()) as cx, cx:
            cursor = cx.execute("INSERT INTO animales (nombre, especie, edad) VALUES (?, ?, ?)",
                                (nombre, especie, edad))
            numero = cursor.lastrowid
    except sqlite3.IntegrityError as e:         # el UNIQUE (nombre repetido) o el CHECK (edad negativa)
        return f"No se puede: {e}"
    return f"Dado de alta con el número {numero}"


def opcion_3():
    nombre = input("Nombre: ").strip()
    especie = input("Especie: ").strip()
    edad = int(input("Edad (años): "))
    mensaje = alta_animal(nombre, especie, edad)
    print("  ", mensaje)
    apuntar(f"alta de animal '{nombre}': {mensaje}")


def cambiar_edad(numero, edad):
    try:
        with closing(conectar()) as cx, cx:
            cursor = cx.execute("UPDATE animales SET edad = ? WHERE id = ?", (edad, numero))
            cambiadas = cursor.rowcount          # cuántas filas ha cambiado: si es 0, no existía
    except sqlite3.IntegrityError as e:
        return f"No se puede: {e}"
    if cambiadas == 0:
        return "Ese animal no existe"
    return "Edad cambiada"


def opcion_4():
    numero = int(input("Número del animal: "))
    edad = int(input("Edad nueva (años): "))
    mensaje = cambiar_edad(numero, edad)
    print("  ", mensaje)
    apuntar(f"cambiar edad del animal {numero} a {edad}: {mensaje}")


# ---------------------------------------------------------------- opción 5 (paso 9)
def adoptar(adoptante_id, animal_id):
    """Adoptar un animal: dejarlo no disponible y apuntar la adopción. Las dos cosas, o ninguna."""
    try:
        with closing(conectar()) as cx, cx:
            fila = cx.execute("SELECT disponible FROM animales WHERE id = ?", (animal_id,)).fetchone()
            if fila is None:
                return "Ese animal no existe"
            if fila["disponible"] == 0:
                return "Ese animal ya no está disponible"
            cx.execute("UPDATE animales SET disponible = 0 WHERE id = ?", (animal_id,))
            cx.execute("INSERT INTO adopciones (adoptante_id, animal_id) VALUES (?, ?)",
                       (adoptante_id, animal_id))
        return "Adoptado"
    except sqlite3.IntegrityError as e:
        return f"Rechazado: {e}"


def opcion_5():
    adoptante_id = int(input("Número del adoptante: "))
    animal_id = int(input("Número del animal: "))
    mensaje = adoptar(adoptante_id, animal_id)
    print("  ", mensaje)
    apuntar(f"adoptar animal {animal_id} (adoptante {adoptante_id}): {mensaje}")


# ---------------------------------------------------------------- opción 6 (paso 10)
def adopciones():
    with closing(conectar()) as cx:
        return cx.execute("""
            SELECT p.id, a.nombre AS adoptante, n.nombre AS animal, p.devuelto
            FROM adopciones p
            JOIN adoptantes a ON a.id = p.adoptante_id
            JOIN animales n ON n.id = p.animal_id
            ORDER BY p.id
        """).fetchall()


def opcion_6():
    filas = adopciones()
    for f in filas:
        estado = "devuelto" if f["devuelto"] else "lo tiene"
        print(f"   {f['id']:3d}  {f['adoptante']:15s} {f['animal']:12s} {estado}")
    if not filas:
        print("   (ninguna)")


# ---------------------------------------------------------------- opción 7 (paso 11)
def informe():
    """Cuántas adopciones ha habido de cada especie, de más a menos."""
    with closing(conectar()) as cx:
        filas = cx.execute("""
            SELECT a.especie, COUNT(p.id) AS veces
            FROM animales a LEFT JOIN adopciones p ON p.animal_id = a.id
            GROUP BY a.especie
            ORDER BY veces DESC, a.especie
        """).fetchall()
    return [{"especie": f["especie"], "adopciones": f["veces"]} for f in filas]


def opcion_7():
    datos = informe()
    print("   Adopciones por especie:")
    for fila in datos:
        print(f"   {fila['especie']:10s} {fila['adopciones']}")
    guardar_json("informe.json", datos)
    print("   Guardado en", DATOS / "informe.json")
    apuntar("informe guardado en informe.json")


# ---------------------------------------------------------------- opciones 8, 9 y 10 (ORM y servidor)
def opcion_8():
    numero = int(input("Número de la adopción (el que sale en la opción 6): "))
    mensaje = orm.devolver(numero)
    print("  ", mensaje)
    apuntar(f"devolver adopción {numero}: {mensaje}")


def opcion_9():
    minimo = int(input("Mínimo de adopciones: "))
    filas = orm.mejores_adoptantes(minimo)
    for fila in filas:
        print(f"   {fila.adoptante:15s} {fila.cuantos}")
    if not filas:
        print("   (ninguno)")
    apuntar(f"mejores adoptantes con al menos {minimo}: {len(filas)}")


def opcion_10():
    servidor.llevar_al_servidor(buscar_animales(""))
    apuntar("animales llevados al servidor PostgreSQL")


# ---------------------------------------------------------------- opción 11 (paso 16)
def estrellas():
    """El animal más adoptado y el adoptante que más adopta: LIMIT 1 y fetchone()."""
    with closing(conectar()) as cx:
        animal = cx.execute("""
            SELECT n.nombre, COUNT(*) AS veces
            FROM adopciones p JOIN animales n ON n.id = p.animal_id
            GROUP BY n.id
            ORDER BY COUNT(*) DESC, n.nombre
            LIMIT 1
        """).fetchone()
        adoptante = cx.execute("""
            SELECT a.nombre, COUNT(*) AS veces
            FROM adopciones p JOIN adoptantes a ON a.id = p.adoptante_id
            GROUP BY a.id
            ORDER BY COUNT(*) DESC, a.nombre
            LIMIT 1
        """).fetchone()
    return animal, adoptante


def opcion_11():
    animal, adoptante = estrellas()
    if animal is None:                           # fetchone() da None si no hay adopciones
        print("   Todavía no hay adopciones")
        return
    print(f"   El animal más adoptado: {animal['nombre']} ({animal['veces']} adopciones)")
    print(f"   El adoptante que más adopta: {adoptante['nombre']} ({adoptante['veces']} adopciones)")


# ---------------------------------------------------------------- opción 12 (paso 17)
def adopciones_del_adoptante(numero):
    """None si el adoptante no existe; si existe, sus adopciones con un JOIN."""
    with closing(conectar()) as cx:
        if cx.execute("SELECT id FROM adoptantes WHERE id = ?", (numero,)).fetchone() is None:
            return None
        return cx.execute("""
            SELECT p.id, n.nombre AS animal, p.devuelto
            FROM adopciones p JOIN animales n ON n.id = p.animal_id
            WHERE p.adoptante_id = ?
            ORDER BY p.id
        """, (numero,)).fetchall()


def opcion_12():
    numero = int(input("Número del adoptante: "))
    filas = adopciones_del_adoptante(numero)
    if filas is None:
        print("   Ese adoptante no existe")
        apuntar(f"adopciones del adoptante {numero} a CSV: no existe")
        return
    ruta = DATOS / f"adopciones_adoptante_{numero}.csv"
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        escritor = csv.writer(f, delimiter=";")
        escritor.writerow(["numero", "animal", "devuelto"])
        for fila in filas:
            escritor.writerow([fila["id"], fila["animal"], "sí" if fila["devuelto"] else "no"])
    print(f"   {len(filas)} adopciones guardadas en {ruta}")
    apuntar(f"adopciones del adoptante {numero} guardadas en {ruta.name}")


# ---------------------------------------------------------------- opciones 13 a 19 (los grupos de 3)
def opcion_13():
    numero = int(input("Número del adoptante: "))
    filas = orm.adopciones_de(numero)
    if filas is None:
        print("   Ese adoptante no existe")
        return
    for numero_adopcion, animal, devuelto in filas:
        print(f"   {numero_adopcion:3d}  {animal:12s} {'devuelto' if devuelto else 'lo tiene'}")
    if not filas:
        print("   (ninguna)")


def opcion_14():
    nombre = input("Nombre: ").strip()
    correo = input("Correo: ").strip()
    if not nombre or not correo:
        print("   El nombre y el correo son obligatorios")
        return
    mensaje = orm.alta_adoptante(nombre, correo)
    print("  ", mensaje)
    apuntar(f"alta de adoptante '{nombre}' (ORM): {mensaje}")


def dar_de_baja(numero):
    try:
        with closing(conectar()) as cx, cx:
            cursor = cx.execute("DELETE FROM animales WHERE id = ?", (numero,))
            borrados = cursor.rowcount
    except sqlite3.IntegrityError:               # la clave ajena no deja borrar si tiene adopciones
        return "No se puede: ese animal tiene adopciones"
    if borrados == 0:
        return "Ese animal no existe"
    return "Dado de baja"


def opcion_15():
    numero = int(input("Número del animal: "))
    mensaje = dar_de_baja(numero)
    print("  ", mensaje)
    apuntar(f"dar de baja el animal {numero}: {mensaje}")


def opcion_16():
    guardar_xml("informe.xml", informe())
    print("   Guardado en", DATOS / "informe.xml")
    apuntar("informe guardado en informe.xml")


def opcion_17():
    destino = copia_de_seguridad(BASE)
    print("   Copia guardada en", destino)
    apuntar(f"copia de seguridad en {destino}")


def opcion_18():
    con_orm = orm.informe()
    for fila in con_orm:
        print(f"   {fila['especie']:10s} {fila['adopciones']}")
    print("   ¿Sale igual que el de la opción 7 (SQL a mano)?", con_orm == informe())


def opcion_19():
    numero = int(input("Número del adoptante: "))
    with closing(conectar()) as cx:
        plan = cx.execute("EXPLAIN QUERY PLAN SELECT * FROM adopciones WHERE adoptante_id = ?",
                          (numero,)).fetchall()
    for fila in plan:
        print("   ", fila["detail"])
    print("   (SEARCH ... USING INDEX: va directo; SCAN: recorre la tabla entera)")


OPCIONES = {"1": opcion_1, "2": opcion_2, "3": opcion_3, "4": opcion_4, "5": opcion_5,
            "6": opcion_6, "7": opcion_7, "8": opcion_8, "9": opcion_9, "10": opcion_10,
            "11": opcion_11, "12": opcion_12, "13": opcion_13, "14": opcion_14,
            "15": opcion_15, "16": opcion_16, "17": opcion_17, "18": opcion_18,
            "19": opcion_19}


# ---------------------------------------------------------------- el menú (paso 5)
esperar =False
if __name__ == "__main__":
    
    crear_tablas()
    
    while True:
        if esperar == True:
            time.sleep(2)
            print("Pulsa ENTER para continuar:")
            input()
        esperar=True
        print(MENU)
        opcion = input("Opción: ").strip()

        if opcion == "0":
            print("Hasta pronto")
            break
        try:
            if opcion in OPCIONES:
                OPCIONES[opcion]()
            else:
                print("Esa opción no existe")
        except ValueError:
            print("Eso no es un número")
        except sqlite3.Error as e:
            print("Error de la base de datos:", e)
            apuntar(f"error de la base de datos: {e}")
