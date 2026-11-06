"""orm.py - Lo del ORM (SQLAlchemy 2.0), sobre la misma base que menu.py.

Parte de las clases del ejemplo 48 (Socio, Libro y Prestamo) cambiando los nombres:
Adoptante, Animal y Adopcion (la que une, como clase, con sus dos relaciones).

Ni create_all ni drop_all: las tablas ya las crea menu.py (con sus CHECK).
El ORM solo las mapea: cada clase con el nombre de su tabla y sus columnas.
"""
from sqlalchemy import ForeignKey, create_engine, event, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import (DeclarativeBase, Mapped, Session, mapped_column,
                            relationship, selectinload)
from pathlib import Path


class Base(DeclarativeBase):
    pass


class Adoptante(Base):
    __tablename__ = "adoptantes"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str]
    correo: Mapped[str] = mapped_column(unique=True)
    adopciones: Mapped[list["Adopcion"]] = relationship(back_populates="adoptante",
                                                        order_by="Adopcion.id")

    def __repr__(self):
        return f"Adoptante({self.nombre!r})"


class Animal(Base):
    __tablename__ = "animales"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(unique=True)
    especie: Mapped[str]
    edad: Mapped[int]
    disponible: Mapped[bool] = mapped_column(default=True)
    adopciones: Mapped[list["Adopcion"]] = relationship(back_populates="animal")
    
    def __repr__(self):
        return f"Animal({self.nombre!r})"


class Adopcion(Base):
    __tablename__ = "adopciones"
    id: Mapped[int] = mapped_column(primary_key=True)
    adoptante_id: Mapped[int] = mapped_column(ForeignKey("adoptantes.id"))
    animal_id: Mapped[int] = mapped_column(ForeignKey("animales.id"))
    devuelto: Mapped[bool] = mapped_column(default=False)
    adoptante: Mapped["Adoptante"] = relationship(back_populates="adopciones")
    animal: Mapped["Animal"] = relationship(back_populates="adopciones")


RUTA = Path(__file__).resolve().parent / "protectora.db"
motor = create_engine(f"sqlite:///{RUTA.as_posix()}")


@event.listens_for(motor, "connect")
def claves_ajenas(conexion, _):
    conexion.execute("PRAGMA foreign_keys = ON")     # en cada conexión, como en el 48


# ------------------------------------------------------------ opción 8
def devolver(numero):
    """Devolver un animal: la adopción pasa a devuelta y el animal vuelve a estar disponible.

    La sesión ES la transacción: los dos cambios van en el mismo commit.
    """
    with Session(motor) as s:
        adopcion = s.get(Adopcion, numero)
        if adopcion is None:
            return "Esa adopción no existe"
        if adopcion.devuelto:
            return "Esa adopción ya estaba devuelta"
        adopcion.devuelto = True
        adopcion.animal.disponible = True        # se navega con puntos, sin escribir SQL
        try:
            s.commit()
        except IntegrityError as e:
            s.rollback()
            return f"Rechazado: {e.orig}"
    return "Devuelto"


# ------------------------------------------------------------ opción 9
def mejores_adoptantes(minimo):
    """SQL a mano desde la misma sesión, con text() y su parámetro (:minimo)."""
    with Session(motor) as s:
        return s.execute(text("""
            SELECT a.nombre AS adoptante, COUNT(*) AS cuantos
            FROM adopciones p JOIN adoptantes a ON a.id = p.adoptante_id
            GROUP BY a.id
            HAVING COUNT(*) >= :minimo
            ORDER BY cuantos DESC, a.nombre
        """), {"minimo": minimo}).all()


# ------------------------------------------------------------ opción 13
def adopciones_de(numero):
    """Las adopciones de un adoptante, navegando por la relación uno a muchos.

    Devuelve None si el adoptante no existe, o una lista de (número, animal, devuelto).
    El selectinload trae las adopciones y sus animales de golpe: sin él, cada
    a.animal sería una consulta más (el problema N+1).
    """
    with Session(motor) as s:
        adoptante = s.get(Adoptante, numero, options=[
            selectinload(Adoptante.adopciones).selectinload(Adopcion.animal)])
        if adoptante is None:
            return None
        return [(a.id, a.animal.nombre, a.devuelto) for a in adoptante.adopciones]


# ------------------------------------------------------------ opción 14
def alta_adoptante(nombre, correo):
    """Alta de un adoptante con el ORM: add + commit. Si el correo ya está, IntegrityError."""
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
def informe():
    """Los grupos de 3: el informe de la opción 7, con select() en vez de SQL."""
    veces = func.count(Adopcion.id)
    consulta = (select(Animal.especie, veces)
                .outerjoin(Adopcion)
                .group_by(Animal.especie)
                .order_by(veces.desc(), Animal.especie))
    with Session(motor) as s:
        return [{"especie": especie, "adopciones": n} for especie, n in s.execute(consulta)]
