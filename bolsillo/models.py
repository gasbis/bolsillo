"""Tablas de la base de datos de Bolsillo.

Solo definiciones de tablas: la lógica sobre ellas vive en los módulos
`*_db.py` (p.ej. auth_db.py).

Convenciones:
- Todas las tablas de datos llevan `id_usuario`: cada usuario solo ve y
  toca lo suyo. Toda consulta debe filtrar por él.
- Los importes son `Decimal` con 2 decimales (columna NUMERIC(12, 2)),
  nunca `float`: con float las sumas acumulan errores de redondeo
  (0.1 + 0.2 != 0.3). Siempre en euros. El sentido del movimiento lo da
  `Transaccion.tipo`, no el signo (ver reglas de signo en `Transaccion`).
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

import reflex as rx
import sqlmodel

# Valores válidos para `Categoria.tipo`.
TIPO_GASTO = "gasto"
TIPO_INGRESO = "ingreso"
# Valor adicional válido solo para `Transaccion.tipo`.
TIPO_TRANSFERENCIA = "transferencia"

# Categoría de gasto que usa la función "ajustar saldo" de una cuenta:
# el ajuste se anota como un gasto (negativo si el saldo sube). Se crea
# automáticamente la primera vez que hace falta (ver transacciones_db.py).
CATEGORIA_AJUSTE = "Ajuste"


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


class Usuario(rx.Model, table=True):
    __tablename__ = "usuarios"

    nombre: str
    email: str = sqlmodel.Field(unique=True, index=True)
    password_hash: str
    # True al crear el usuario: se le obliga a cambiarla en su primer
    # inicio de sesión (ver components/auth_guard.py).
    debe_cambiar_password: bool = True
    # Permite revocar el acceso de un usuario sin borrar sus datos.
    activo: bool = True


class Cuenta(rx.Model, table=True):
    """Dónde está el dinero: banco, efectivo, tarjeta... Cada usuario
    gestiona su propia lista."""

    __tablename__ = "cuentas"
    __table_args__ = (
        sqlmodel.UniqueConstraint("id_usuario", "nombre", name="uq_cuenta_usuario_nombre"),
    )

    id_usuario: int = sqlmodel.Field(foreign_key="usuarios.id", index=True)
    nombre: str
    icono: str
    # Saldo de la cuenta antes del primer movimiento anotado en la app.
    # Saldo actual = saldo_inicial + ingresos - gastos ± transferencias.
    saldo_inicial: Decimal = sqlmodel.Field(default=Decimal("0"), max_digits=12, decimal_places=2)
    orden: int = 0
    # Archivar en vez de borrar: una cuenta con movimientos no se puede
    # borrar sin perder historial.
    activa: bool = True


class Categoria(rx.Model, table=True):
    """Categoría de gasto o de ingreso. Cada usuario edita su lista."""

    __tablename__ = "categorias"
    __table_args__ = (
        sqlmodel.UniqueConstraint(
            "id_usuario", "tipo", "nombre", name="uq_categoria_usuario_tipo_nombre"
        ),
    )

    id_usuario: int = sqlmodel.Field(foreign_key="usuarios.id", index=True)
    tipo: str  # TIPO_GASTO | TIPO_INGRESO
    nombre: str
    icono: str  # nombre de icono Lucide, p.ej. "shopping-cart"
    # Color del sector en el donut y del icono, en formato "#RRGGBB".
    color: str = "#64748b"
    orden: int = 0
    activa: bool = True


class Transaccion(rx.Model, table=True):
    """Un movimiento: gasto, ingreso o transferencia entre cuentas.

    - gasto / ingreso: `id_categoria` obligatorio, `id_cuenta_destino` None.
    - transferencia: `id_cuenta` es el origen, `id_cuenta_destino` el
      destino e `id_categoria` None. No cuenta ni como gasto ni como
      ingreso en los totales; solo mueve saldo entre cuentas.

    Signo de `importe`:
    - gasto: normalmente positivo; NEGATIVO para devoluciones o reintegros,
      que así restan del gasto de su categoría en vez de inflar los
      ingresos (y las estadísticas de la categoría siguen siendo reales).
    - ingreso y transferencia: siempre positivo.

    Pagar una tarjeta de crédito es una transferencia del banco a la
    cuenta de la tarjeta; invertir (comprar acciones) es una transferencia
    a una cuenta "Inversiones". No hay tipos especiales para ello.
    """

    __tablename__ = "transacciones"

    id_usuario: int = sqlmodel.Field(foreign_key="usuarios.id", index=True)
    tipo: str  # TIPO_GASTO | TIPO_INGRESO | TIPO_TRANSFERENCIA
    fecha: date = sqlmodel.Field(index=True)
    importe: Decimal = sqlmodel.Field(max_digits=12, decimal_places=2)
    id_cuenta: int = sqlmodel.Field(foreign_key="cuentas.id", index=True)
    id_categoria: Optional[int] = sqlmodel.Field(
        default=None, foreign_key="categorias.id", index=True
    )
    id_cuenta_destino: Optional[int] = sqlmodel.Field(default=None, foreign_key="cuentas.id")
    notas: str = ""
    # Para ordenar los movimientos de un mismo día por orden de alta.
    creado_en: datetime = sqlmodel.Field(default_factory=_ahora)


class SesionDispositivo(rx.Model, table=True):
    """Un dispositivo (navegador) en el que el usuario dejó la sesión
    recordada, para no pedirle la contraseña cada vez que abre la app.

    El navegador guarda un token aleatorio en localStorage; aquí solo se
    guarda su hash SHA-256, de modo que una copia de la base de datos no
    permite suplantar a nadie. Ver sesiones_db.py.
    """

    __tablename__ = "sesiones_dispositivo"

    id_usuario: int = sqlmodel.Field(foreign_key="usuarios.id", index=True)
    token_hash: str = sqlmodel.Field(unique=True, index=True)
    # Texto orientativo del navegador/sistema (User-Agent), para que el
    # usuario reconozca sus dispositivos si algún día se listan.
    dispositivo: str = ""
    creado_en: datetime = sqlmodel.Field(default_factory=_ahora)
    # La sesión caduca tras DIAS_CADUCIDAD sin usarse (ver sesiones_db.py);
    # cada uso la renueva.
    ultimo_uso: datetime = sqlmodel.Field(default_factory=_ahora)
