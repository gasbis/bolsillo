"""Página de categorías y cuentas (/categorias).

Tres pestañas (PESTANA_*): categorías de gasto, de ingreso y cuentas.
Tocar un elemento abre el diálogo de edición (nombre, icono y botón de
eliminar); el botón "Añadir" del pie abre el mismo diálogo vacío.

Eliminar algo con movimientos lo archiva en vez de borrarlo (ver
categorias_db.py); el aviso lo dice.
"""

import reflex as rx

from bolsillo import calculadora
from bolsillo.categorias_db import (
    borrar_categoria,
    borrar_cuenta,
    crear_cuenta,
    editar_categoria,
    editar_cuenta,
    listar_cuentas,
)
from bolsillo.iconos import ICONOS
from bolsillo.models import TIPO_GASTO, TIPO_INGRESO
from bolsillo.states.auth_state import AuthState
from bolsillo.states.resumen_state import euros
from bolsillo.transacciones_db import categorias, crear_categoria

PESTANA_GASTOS = TIPO_GASTO
PESTANA_INGRESOS = TIPO_INGRESO
PESTANA_CUENTAS = "cuenta"

# Color de los iconos de las cuentas (las categorías tienen el suyo).
COLOR_CUENTA = "#0EA5E9"
# Icono de partida al crear: vacío para obligar a elegir uno.
_SIN_ICONO = ""


class CategoriasState(rx.State):
    pestana: str = PESTANA_GASTOS

    # [{"id", "nombre", "icono", "color", "detalle", "negativo"}]
    # "detalle": texto a la derecha (saldo en las cuentas, "" en categorías).
    gastos: list[dict[str, str]] = []
    ingresos: list[dict[str, str]] = []
    cuentas: list[dict[str, str]] = []
    cargado: bool = False

    # --- Diálogo de alta / edición ----------------------------------------
    abierto: bool = False
    id_edicion: str = ""  # "" = alta nueva
    nombre: str = ""
    icono: str = _SIN_ICONO
    color: str = ""
    saldo_inicial: str = ""  # solo al crear una cuenta
    error: str = ""
    confirmar_borrado: bool = False

    # --- Vars derivadas ---------------------------------------------------

    @rx.var
    def lista(self) -> list[dict[str, str]]:
        if self.pestana == PESTANA_CUENTAS:
            return self.cuentas
        if self.pestana == PESTANA_INGRESOS:
            return self.ingresos
        return self.gastos

    @rx.var
    def es_cuenta(self) -> bool:
        return self.pestana == PESTANA_CUENTAS

    @rx.var
    def es_edicion(self) -> bool:
        return self.id_edicion != ""

    @rx.var
    def texto_vacio(self) -> str:
        if self.pestana == PESTANA_CUENTAS:
            return "Aún no tienes cuentas."
        que = "ingreso" if self.pestana == PESTANA_INGRESOS else "gasto"
        return f"Aún no tienes categorías de {que}."

    @rx.var
    def texto_anadir(self) -> str:
        return "Añadir cuenta" if self.pestana == PESTANA_CUENTAS else "Añadir categoría"

    @rx.var
    def titulo(self) -> str:
        if self.pestana == PESTANA_CUENTAS:
            que = "cuenta"
        elif self.pestana == PESTANA_INGRESOS:
            que = "categoría de ingreso"
        else:
            que = "categoría de gasto"
        return f"Editar {que}" if self.id_edicion else f"Nueva {que}"

    @rx.var
    def puede_guardar(self) -> bool:
        return self.nombre.strip() != "" and self.icono != ""

    # --- Internos -----------------------------------------------------------

    async def _id_usuario(self) -> int | None:
        return (await self.get_state(AuthState)).current_user["id"] or None

    def _recargar(self, id_usuario: int):
        def de_categorias(tipo: str) -> list[dict[str, str]]:
            return [
                {**c, "detalle": "", "negativo": ""} for c in categorias(id_usuario, tipo)
            ]

        self.gastos = de_categorias(TIPO_GASTO)
        self.ingresos = de_categorias(TIPO_INGRESO)
        self.cuentas = [
            {
                "id": str(c["id"]),
                "nombre": c["nombre"],
                "icono": c["icono"],
                "color": COLOR_CUENTA,
                "detalle": euros(c["saldo"]),
                "negativo": "1" if c["saldo"] < 0 else "",
            }
            for c in listar_cuentas(id_usuario)
        ]
        self.cargado = True

    def _cerrar(self):
        self.abierto = False
        self.error = ""
        self.confirmar_borrado = False

    # --- Eventos ------------------------------------------------------------

    @rx.event
    async def cargar(self):
        """on_mount de la página (ya con el usuario identificado)."""
        id_usuario = await self._id_usuario()
        if id_usuario:
            self._recargar(id_usuario)

    @rx.event
    def set_pestana(self, valor: str | list[str]):
        valor = valor[0] if isinstance(valor, list) else valor
        if valor in (PESTANA_GASTOS, PESTANA_INGRESOS, PESTANA_CUENTAS):
            self.pestana = valor

    @rx.event
    def abrir_nueva(self):
        self.id_edicion = ""
        self.nombre = ""
        self.icono = _SIN_ICONO
        self.color = ""
        self.saldo_inicial = ""
        self.error = ""
        self.confirmar_borrado = False
        self.abierto = True

    @rx.event
    def abrir_edicion(self, id_elemento: str):
        elemento = next((e for e in self.lista if e["id"] == id_elemento), None)
        if elemento is None:
            return
        self.id_edicion = id_elemento
        self.nombre = elemento["nombre"]
        self.icono = elemento["icono"]
        self.color = elemento["color"]
        self.saldo_inicial = ""
        self.error = ""
        self.confirmar_borrado = False
        self.abierto = True

    @rx.event
    def set_abierto(self, valor: bool):
        if valor:
            self.abierto = True
        else:
            self._cerrar()

    @rx.event
    def set_nombre(self, valor: str):
        self.nombre = valor[:40]
        self.error = ""
        self.confirmar_borrado = False

    @rx.event
    def set_icono(self, icono: str):
        if icono in ICONOS:
            self.icono = icono
            self.error = ""
            self.confirmar_borrado = False

    @rx.event
    def set_saldo_inicial(self, valor: str):
        self.saldo_inicial = valor[:20]
        self.error = ""

    @rx.event
    async def guardar(self):
        id_usuario = await self._id_usuario()
        if not id_usuario:
            return
        es_cuenta = self.pestana == PESTANA_CUENTAS
        try:
            if self.id_edicion:
                if es_cuenta:
                    editar_cuenta(id_usuario, int(self.id_edicion), self.nombre, self.icono)
                else:
                    editar_categoria(id_usuario, int(self.id_edicion), self.nombre, self.icono)
            elif es_cuenta:
                saldo = calculadora.leer_importe(self.saldo_inicial or "0")
                if saldo is None:
                    self.error = "El saldo inicial no es un número válido."
                    return
                crear_cuenta(id_usuario, self.nombre, self.icono, saldo)
            else:
                crear_categoria(id_usuario, self.pestana, self.nombre, self.icono)
        except ValueError as e:
            self.error = str(e)
            return

        que = "Cuenta" if es_cuenta else "Categoría"
        hecho = "guardada" if self.id_edicion else "creada"
        self._recargar(id_usuario)
        self._cerrar()
        return rx.toast.success(f"{que} {hecho}", duration=2500)

    @rx.event
    async def borrar(self):
        """El primer toque pide confirmación y el segundo elimina."""
        if not self.id_edicion:
            return
        if not self.confirmar_borrado:
            self.confirmar_borrado = True
            return
        id_usuario = await self._id_usuario()
        if not id_usuario:
            return
        es_cuenta = self.pestana == PESTANA_CUENTAS
        try:
            if es_cuenta:
                archivada = borrar_cuenta(id_usuario, int(self.id_edicion))
            else:
                archivada = borrar_categoria(id_usuario, int(self.id_edicion))
        except ValueError as e:
            self.error = str(e)
            self.confirmar_borrado = False
            return

        que = "Cuenta" if es_cuenta else "Categoría"
        self._recargar(id_usuario)
        self._cerrar()
        if archivada:
            return rx.toast.info(
                f"{que} archivada: tiene movimientos, que se conservan.", duration=4000
            )
        return rx.toast.success(f"{que} eliminada", duration=2500)
