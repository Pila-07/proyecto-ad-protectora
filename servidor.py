"""servidor.py - Lo de PostgreSQL: el servidor de la protectora.

Parte de los ejemplos 27 (arrancar el servidor), 29 (el pool) y 30 (función y procedimiento).
Los parámetros en PostgreSQL son %s (no ?), y los errores son de psycopg.
"""
import pgserver
import psycopg
from psycopg_pool import ConnectionPool

TABLA = """
    CREATE TABLE IF NOT EXISTS animales (
        id         INTEGER PRIMARY KEY,
        nombre     TEXT    NOT NULL UNIQUE,
        especie    TEXT    NOT NULL,
        edad       INTEGER NOT NULL CHECK (edad >= 0),
        disponible INTEGER NOT NULL CHECK (disponible IN (0, 1))
    )
"""

# Una FUNCIÓN devuelve algo y se llama dentro de un SELECT.
FUNCION = """
    CREATE OR REPLACE FUNCTION total_disponibles() RETURNS BIGINT
    LANGUAGE plpgsql AS $$
    BEGIN
        RETURN (SELECT COUNT(*) FROM animales WHERE disponible = 1);
    END; $$
"""

# Esta usa AVG: devuelve NUMERIC, que en Python llega como Decimal (hay que pasarlo a float).
FUNCION_EDAD = """
    CREATE OR REPLACE FUNCTION edad_media() RETURNS NUMERIC
    LANGUAGE plpgsql AS $$
    BEGIN
        RETURN (SELECT COALESCE(AVG(edad), 0) FROM animales);
    END; $$
"""

# Un PROCEDIMIENTO hace algo y se llama con CALL.
PROCEDIMIENTO = """
    CREATE OR REPLACE PROCEDURE cumplir_anios(p_anios INT)
    LANGUAGE plpgsql AS $$
    BEGIN
        UPDATE animales SET edad = edad + p_anios;
    END; $$
"""


def llevar_al_servidor(animales):
    """Copia los animales (los objetos Animal de menu.py) a PostgreSQL y usa su función y su procedimiento."""
    print("   Arrancando PostgreSQL... (la primera vez tarda)")
    servidor = pgserver.get_server("pgdatos")
    pool = ConnectionPool(servidor.get_uri(), min_size=1, max_size=2, open=True)
    try:
        with pool.connection() as cx:
            cx.execute(TABLA)
            cx.execute("DELETE FROM animales")      # así se puede usar la opción las veces que haga falta
            for a in animales:
                cx.execute("INSERT INTO animales VALUES (%s, %s, %s, %s, %s)",
                           (a.id, a.nombre, a.especie, a.edad, a.disponible))
            cx.execute(FUNCION)
            cx.execute(FUNCION_EDAD)
        with pool.connection() as cx:
            total = cx.execute("SELECT total_disponibles()").fetchone()[0]
            media = float(cx.execute("SELECT edad_media()").fetchone()[0])
        print(f"   En el servidor: {len(animales)} animales, {total} disponibles")
        print(f"   Edad media: {media:.2f} años")

        # Los grupos de 3: un procedimiento, en otro with del pool.
        with pool.connection() as cx:
            cx.execute(PROCEDIMIENTO)
            cx.execute("CALL cumplir_anios(%s)", (1,))
        with pool.connection() as cx:
            media = float(cx.execute("SELECT edad_media()").fetchone()[0])
        print(f"   Tras CALL cumplir_anios(1): edad media {media:.2f} años")
    except psycopg.Error as e:
        print("   Error de PostgreSQL:", e)
    finally:
        pool.close()
        servidor.cleanup()
