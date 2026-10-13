"""Hash de contraseñas y operaciones de base de datos sobre USUARIOS.

Adaptado de Gestión Cartera. Las dos apps son independientes (cada una
con su propia base de datos); aquí solo se ha copiado la lógica.
"""

from decimal import Decimal

import bcrypt
import reflex as rx
import sqlmodel

from bolsillo.models import TIPO_GASTO, TIPO_INGRESO, Categoria, Cuenta, Usuario

# Lo que recibe cada usuario nuevo para que la app sea usable desde el
# primer minuto. Luego cada uno edita, archiva o añade lo que quiera.
# (nombre, icono Lucide, color)
CATEGORIAS_GASTO_INICIALES: list[tuple[str, str, str]] = [
    ("Comida", "shopping-cart", "#ef4444"),
    ("Restaurantes", "utensils", "#f97316"),
    ("Casa", "house", "#f59e0b"),
    ("Facturas", "zap", "#eab308"),
    ("Transporte", "bus", "#84cc16"),
    ("Coche", "car", "#22c55e"),
    ("Salud", "heart-pulse", "#14b8a6"),
    ("Ropa", "shirt", "#06b6d4"),
    ("Ocio", "clapperboard", "#3b82f6"),
    ("Viajes", "plane", "#6366f1"),
    ("Regalos", "gift", "#8b5cf6"),
    ("Educación", "graduation-cap", "#a855f7"),
    ("Mascotas", "paw-print", "#d946ef"),
    ("Otros", "ellipsis", "#64748b"),
]

CATEGORIAS_INGRESO_INICIALES: list[tuple[str, str, str]] = [
    ("Nómina", "briefcase", "#16a34a"),
    ("Intereses", "piggy-bank", "#0d9488"),
    ("Otros ingresos", "hand-coins", "#65a30d"),
]

# (nombre, icono Lucide)
CUENTAS_INICIALES: list[tuple[str, str]] = [
    ("Efectivo", "wallet"),
    ("Banco", "landmark"),
]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # Hash corrupto o con un formato que no es el esperado.
        return False


def email_existe(email: str) -> bool:
    return obtener_usuario_por_email(email) is not None


def obtener_usuario_por_email(email: str) -> Usuario | None:
    with rx.session() as session:
        return session.exec(sqlmodel.select(Usuario).where(Usuario.email == email)).first()


def _sembrar_datos_iniciales(session: sqlmodel.Session, id_usuario: int) -> None:
    for orden, (nombre, icono, color) in enumerate(CATEGORIAS_GASTO_INICIALES):
        session.add(
            Categoria(
                id_usuario=id_usuario, tipo=TIPO_GASTO, nombre=nombre,
                icono=icono, color=color, orden=orden,
            )
        )
    for orden, (nombre, icono, color) in enumerate(CATEGORIAS_INGRESO_INICIALES):
        session.add(
            Categoria(
                id_usuario=id_usuario, tipo=TIPO_INGRESO, nombre=nombre,
                icono=icono, color=color, orden=orden,
            )
        )
    for orden, (nombre, icono) in enumerate(CUENTAS_INICIALES):
        session.add(
            Cuenta(
                id_usuario=id_usuario, nombre=nombre, icono=icono,
                saldo_inicial=Decimal("0"), orden=orden,
            )
        )


def crear_usuario(email: str, nombre: str, password_inicial: str) -> bool:
    """Da de alta un usuario con una contraseña inicial (que deberá
    cambiar en su primer inicio de sesión) y le crea sus categorías y
    cuentas por defecto."""
    if email_existe(email):
        return False
    with rx.session() as session:
        usuario = Usuario(
            email=email,
            nombre=nombre,
            password_hash=hash_password(password_inicial),
            debe_cambiar_password=True,
            activo=True,
        )
        session.add(usuario)
        session.commit()
        session.refresh(usuario)

        _sembrar_datos_iniciales(session, usuario.id)
        session.commit()
    return True


def listar_usuarios() -> list[Usuario]:
    with rx.session() as session:
        return list(session.exec(sqlmodel.select(Usuario).order_by(Usuario.nombre)).all())


def _actualizar_usuario(email: str, **campos) -> bool:
    with rx.session() as session:
        usuario = session.exec(sqlmodel.select(Usuario).where(Usuario.email == email)).first()
        if usuario is None:
            return False
        for campo, valor in campos.items():
            setattr(usuario, campo, valor)
        session.add(usuario)
        session.commit()
    return True


def establecer_password(email: str, nueva_password: str) -> bool:
    """El propio usuario cambia su contraseña (voluntario o tras el alta)."""
    return _actualizar_usuario(
        email, password_hash=hash_password(nueva_password), debe_cambiar_password=False
    )


def establecer_password_temporal(email: str, password_temporal: str) -> bool:
    """El admin restablece la contraseña de otro usuario que la ha
    olvidado: entra con esta temporal pero se le obliga a cambiarla."""
    return _actualizar_usuario(
        email, password_hash=hash_password(password_temporal), debe_cambiar_password=True
    )


def establecer_nombre(email: str, nuevo_nombre: str) -> bool:
    return _actualizar_usuario(email, nombre=nuevo_nombre)


def establecer_activo(email: str, activo: bool) -> bool:
    return _actualizar_usuario(email, activo=activo)
