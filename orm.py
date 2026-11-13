"""orm.py - Clase que se dedica a convertir las tablas de la base de datos en 
clases y objetos de python
"""
from sqlalchemy import ForeignKey, create_engine, event, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import (DeclarativeBase, Mapped, Session, mapped_column,
                            relationship, selectinload)
from pathlib import Path

# Definición de clases de la base de datos
class Base(DeclarativeBase):
    pass


class Adoptante(Base):
    __tablename__ = "adoptantes"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str]
    correo: Mapped[str] = mapped_column(unique=True)
    adopciones: Mapped[list["Adopcion"]] = relationship(back_populates="adoptante",
                                                        order_by="Adopcion.id")

    def __repr__(self):     #Como se muestra el adoptante por consola
        return f"Adoptante({self.nombre!r})"


class Animal(Base):         
    __tablename__ = "animales"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(unique=True)
    especie: Mapped[str]
    edad: Mapped[int]
    disponible: Mapped[bool] = mapped_column(default=True)
    adopciones: Mapped[list["Adopcion"]] = relationship(back_populates="animal")
    
    def __repr__(self):     #Como se muestra el animal por consola
        return f"Animal({self.nombre!r})"


class Adopcion(Base):
    __tablename__ = "adopciones"
    id: Mapped[int] = mapped_column(primary_key=True)
    adoptante_id: Mapped[int] = mapped_column(ForeignKey("adoptantes.id"))
    animal_id: Mapped[int] = mapped_column(ForeignKey("animales.id"))
    devuelto: Mapped[bool] = mapped_column(default=False)
    adoptante: Mapped["Adoptante"] = relationship(back_populates="adopciones")
    animal: Mapped["Animal"] = relationship(back_populates="adopciones")


# Obtención de la ruta de la base de datos SQLite para la creación del objeto motor
RUTA = Path(__file__).resolve().parent / "protectora.db"    
motor = create_engine(f"sqlite:///{RUTA.as_posix()}")


@event.listens_for(motor, "connect")    # Se activa cuando la base de datos se conecta
def claves_ajenas(conexion, _):
    conexion.execute("PRAGMA foreign_keys = ON")    # Activación de claves ajenas


# ------------------------------------------------------------ opción 8
# Registra la devolución de un animal: marca la adopción como devuelta
# y cambia el estado del animal a disponible dentro de la misma transacción.
def devolver(numero):
    with Session(motor) as s:
        adopcion = s.get(Adopcion, numero)
        if adopcion is None:
            return "Esa adopción no existe"
        if adopcion.devuelto:
            return "Esa adopción ya estaba devuelta"
        adopcion.devuelto = True
        adopcion.animal.disponible = True       
        try:
            s.commit()
        except IntegrityError as e:
            s.rollback()
            return f"Rechazado: {e.orig}"
    return "Devuelto"


# ------------------------------------------------------------ opción 9
# Busca los adoptantes que tienen un número mínimo de adopciones
# mediante una consulta SQL directa y devuelve el total de cada uno.
def mejores_adoptantes(minimo):
    with Session(motor) as s:
        return s.execute(text("""
            SELECT a.nombre AS adoptante, COUNT(*) AS cuantos
            FROM adopciones p JOIN adoptantes a ON a.id = p.adoptante_id
            GROUP BY a.id
            HAVING COUNT(*) >= :minimo
            ORDER BY cuantos DESC, a.nombre
        """), {"minimo": minimo}).all()


# ------------------------------------------------------------ opción 13
# Obtiene el historial de adopciones de una persona cargando todos sus
# datos de golpe para evitar consultas repetidas a la base de datos.
def adopciones_de(numero):
    with Session(motor) as s:
        adoptante = s.get(Adoptante, numero, options=[
            selectinload(Adoptante.adopciones).selectinload(Adopcion.animal)])
        if adoptante is None:
            return None
        return [(a.id, a.animal.nombre, a.devuelto) for a in adoptante.adopciones]


# ------------------------------------------------------------ opción 14
# Crea y guarda un nuevo adoptante en la base de datos; si el correo
# está repetido, cancela la operación y devuelve un mensaje de error.
def alta_adoptante(nombre, correo):
    with Session(motor) as s:
        adoptante = Adoptante(nombre=nombre, correo=correo)
        s.add(adoptante)
        try:
            s.commit()
        except IntegrityError as e:
            s.rollback()
            return f"No se puede: {e.orig}"
        return f"Dado de alta con el número {adoptante.id}"


# ------------------------------------------------------------ opción 18
# Genera un resumen que cuenta cuántas adopciones se han hecho por cada
# especie de animal, incluyendo las especies que aún no tienen adopciones.
def informe():
    veces = func.count(Adopcion.id)
    consulta = (select(Animal.especie, veces)
                .outerjoin(Adopcion)
                .group_by(Animal.especie)
                .order_by(veces.desc(), Animal.especie))
    with Session(motor) as s:
        return [{"especie": especie, "adopciones": n} for especie, n in s.execute(consulta)]
