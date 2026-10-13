"""Tablas de la base de datos de Bolsillo.

Solo definiciones de tablas: la lógica sobre ellas vive en los módulos
`*_db.py` (p.ej. auth_db.py).

Convenciones:
- Todas las tablas de datos llevan `id_usuario`: cada usuario solo ve y
  toca lo suyo. Toda consulta debe filtrar por él.
- Los importes son `Decimal` con 2 decimales (columna NUMERIC(12, 2)),
  nunca `float`: con float las sumas acumulan errores de redondeo
  (0.1 + 0.2 != 0.3). Siempre en euros y siempre POSITIVOS -- el signo
  lo da `Transaccion.tipo`.
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
