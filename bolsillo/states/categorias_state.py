"""Página de categorías y cuentas (/categorias).

Tres pestañas (PESTANA_*): categorías de gasto, de ingreso y cuentas.
Tocar un elemento abre el diálogo; el botón "Añadir" del pie abre el
mismo diálogo vacío. El diálogo tiene tres vistas (VISTA_*):

- VISTA_EDITAR: nombre e icono; en las cuentas también el saldo (al
  crearla, el saldo inicial; al editarla, el saldo actual, cuyo cambio
  anota un movimiento en la categoría "Ajuste").
- VISTA_BORRAR: aviso de que se borrarán definitivamente los movimientos,
  con la alternativa de FUSIONAR (categorías) o ARCHIVAR (cuentas).
- VISTA_ARCHIVADA: una cuenta archivada solo sale aquí, atenuada; al
  tocarla se ofrece restaurarla (o eliminarla).

Ver categorias_db.py para las reglas de cada operación.
"""

from datetime import date

import reflex as rx

from bolsillo import calculadora
from bolsillo.categorias_db import (
    archivar_cuenta,
    borrar_categoria,
    borrar_cuenta,
    categorias_editables,
    crear_cuenta,
    editar_categoria,
    editar_cuenta,
    fusionar_categoria,
    listar_cuentas,
    movimientos_categoria,
    movimientos_cuenta,
)
from bolsillo.iconos import ICONOS
from bolsillo.models import CATEGORIA_AJUSTE, TIPO_GASTO, TIPO_INGRESO
from bolsillo.states.auth_state import AuthState
from bolsillo.states.resumen_state import euros
from bolsillo.transacciones_db import ajustar_saldo, crear_categoria

PESTANA_GASTOS = TIPO_GASTO
PESTANA_INGRESOS = TIPO_INGRESO
PESTANA_CUENTAS = "cuenta"

VISTA_EDITAR = "editar"
VISTA_BORRAR = "borrar"
VISTA_ARCHIVADA = "archivada"

# Color de los iconos de las cuentas (las categorías tienen el suyo).
COLOR_CUENTA = "#0EA5E9"


def _plural(n: int) -> str:
    return "1 movimiento" if n == 1 else f"{n} movimientos"


class CategoriasState(rx.State):
    pestana: str = PESTANA_GASTOS

    # [{"id", "nombre", "icono", "color", "detalle", "negativo",
    #   "archivada", "saldo"}]
    # "detalle": texto a la derecha (saldo en las cuentas, "" en categorías).
    # "saldo": saldo actual de la cuenta tal como se edita ("12,50").
    # Los booleanos van como "1" / "".
    gastos: list[dict[str, str]] = []
    ingresos: list[dict[str, str]] = []
    cuentas: list[dict[str, str]] = []
    cargado: bool = False

    # --- Diálogo ----------------------------------------------------------
    abierto: bool = False
    vista: str = VISTA_EDITAR
    id_edicion: str = ""  # "" = alta nueva
    nombre: str = ""
    icono: str = ""
    color: str = ""
    # Cuentas: saldo inicial (alta) o actual (edición), como se escribe.
    saldo: str = ""
    error: str = ""

    # --- Vista de borrado -------------------------------------------------
    n_movimientos: int = 0
    # Categorías del mismo tipo con las que se puede fusionar.
    opciones_fusion: list[dict[str, str]] = []
    id_fusion: str = ""

    # Saldo de la cuenta al abrirla, para saber si se ha cambiado.
    saldo_original: str = ""

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
    def elemento(self) -> dict[str, str]:
        """El elemento que se está editando ({} si es un alta)."""
        for e in self.lista:
            if e["id"] == self.id_edicion:
                return e
        return {}

    @rx.var
    def es_archivada(self) -> bool:
        return self.elemento.get("archivada", "") != ""

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
        if self.vista == VISTA_BORRAR:
            return "Eliminar cuenta" if self.es_cuenta else "Eliminar categoría"
        if self.vista == VISTA_ARCHIVADA:
            return "Cuenta archivada"
        if self.pestana == PESTANA_CUENTAS:
            que = "cuenta"
        elif self.pestana == PESTANA_INGRESOS:
            que = "categoría de ingreso"
        else:
            que = "categoría de gasto"
        return f"Editar {que}" if self.id_edicion else f"Nueva {que}"

    @rx.var
    def etiqueta_saldo(self) -> str:
        return "Saldo actual" if self.id_edicion else "Saldo inicial"

    @rx.var
    def aviso_saldo(self) -> str:
        """Debajo del saldo, al editar: qué ajuste se va a anotar."""
        if not self.id_edicion or self.pestana != PESTANA_CUENTAS:
            return ""
        nuevo = calculadora.leer_importe(self.saldo or "0")
        antes = calculadora.leer_importe(self.saldo_original or "0")
        if nuevo is None or antes is None or nuevo == antes:
            return ""
        return f"Se anotará un ajuste de {euros(nuevo - antes)} en «{CATEGORIA_AJUSTE}»."

    @rx.var
    def puede_guardar(self) -> bool:
        return self.nombre.strip() != "" and self.icono != ""

    @rx.var
    def aviso_borrado(self) -> str:
        n = self.n_movimientos
        if self.pestana == PESTANA_CUENTAS:
            if n == 0:
                return "La cuenta no tiene movimientos."
            texto = (
                f"Se borrarán definitivamente sus {_plural(n)}, incluidas las "
                "transferencias con otras cuentas (lo que cambiará su saldo). "
                "No se podrán recuperar."
            )
            if not self.es_archivada:
                texto += (
                    " Si quieres conservarlos, archívala: dejará de aparecer en "
                    "la app, pero podrás restaurarla desde esta pantalla."
                )
            return texto
        if n == 0:
            return "La categoría no tiene movimientos."
        texto = (
            f"Se borrarán definitivamente sus {_plural(n)} (y cambiará el saldo "
            "de las cuentas). No se podrán recuperar."
        )
        if self.opciones_fusion:
            texto += (
                " Si quieres conservarlos, fusiónala con otra categoría: sus "
                "movimientos pasarán a ella."
            )
        return texto

    @rx.var
    def puede_fusionar(self) -> bool:
        return (
            self.pestana != PESTANA_CUENTAS
            and self.n_movimientos > 0
            and len(self.opciones_fusion) > 0
        )

    @rx.var
    def puede_archivar(self) -> bool:
        return self.pestana == PESTANA_CUENTAS and not self.es_archivada

    # --- Internos -----------------------------------------------------------

    async def _id_usuario(self) -> int | None:
        return (await self.get_state(AuthState)).current_user["id"] or None

    def _recargar(self, id_usuario: int):
        def de_categorias(tipo: str) -> list[dict[str, str]]:
            return [
                {**c, "detalle": "", "negativo": "", "archivada": "", "saldo": ""}
                for c in categorias_editables(id_usuario, tipo)
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
                "archivada": "" if c["activa"] else "1",
                "saldo": calculadora.formatear(c["saldo"]),
            }
            for c in listar_cuentas(id_usuario)
        ]
        self.cargado = True

    def _cerrar(self):
        self.abierto = False
        self.error = ""

    def _hecho(self, id_usuario: int, mensaje: str, aviso: bool = False):
        self._recargar(id_usuario)
        self._cerrar()
        if aviso:
            return rx.toast.info(mensaje, duration=4000)
        return rx.toast.success(mensaje, duration=2500)

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
        self.icono = ""
        self.color = ""
        self.saldo = ""
        self.saldo_original = ""
        self.error = ""
        self.vista = VISTA_EDITAR
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
        self.saldo = elemento["saldo"]
        self.saldo_original = elemento["saldo"]
        self.error = ""
        self.vista = VISTA_ARCHIVADA if elemento["archivada"] else VISTA_EDITAR
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

    @rx.event
    def set_icono(self, icono: str):
        if icono in ICONOS:
            self.icono = icono
            self.error = ""

    @rx.event
    def set_saldo(self, valor: str):
        self.saldo = valor[:20]
        self.error = ""

    @rx.event
    def cambiar_signo_saldo(self):
        """El teclado decimal del móvil no siempre tiene el signo menos."""
        texto = self.saldo.strip()
        self.saldo = texto[1:] if texto.startswith("-") else f"-{texto or '0'}"
        self.error = ""

    @rx.event
    def set_id_fusion(self, valor: str):
        self.id_fusion = valor
        self.error = ""

    @rx.event
    def volver(self):
        """Desde la vista de borrado, a la anterior."""
        self.error = ""
        self.vista = VISTA_ARCHIVADA if self.es_archivada else VISTA_EDITAR

    # --- Guardar ----------------------------------------------------------

    @rx.event
    async def guardar(self):
        id_usuario = await self._id_usuario()
        if not id_usuario:
            return
        es_cuenta = self.pestana == PESTANA_CUENTAS
        saldo = None
        if es_cuenta:
            saldo = calculadora.leer_importe(self.saldo or "0")
            if saldo is None:
                self.error = "El saldo no es un número válido."
                return
            if abs(saldo) > calculadora.MAXIMO:
                self.error = "El saldo es demasiado grande."
                return
        elif (
            self.pestana == PESTANA_GASTOS
            and self.nombre.strip().lower() == CATEGORIA_AJUSTE.lower()
        ):
            self.error = f"«{CATEGORIA_AJUSTE}» es un nombre reservado."
            return

        ajuste = None
        try:
            if not self.id_edicion:
                if es_cuenta:
                    crear_cuenta(id_usuario, self.nombre, self.icono, saldo)
                else:
                    crear_categoria(id_usuario, self.pestana, self.nombre, self.icono)
            elif es_cuenta:
                editar_cuenta(id_usuario, int(self.id_edicion), self.nombre, self.icono)
                if saldo != calculadora.leer_importe(self.saldo_original or "0"):
                    ajuste = ajustar_saldo(id_usuario, int(self.id_edicion), saldo, date.today())
            else:
                editar_categoria(id_usuario, int(self.id_edicion), self.nombre, self.icono)
        except ValueError as e:
            self.error = str(e)
            return

        que = "Cuenta" if es_cuenta else "Categoría"
        mensaje = f"{que} {'guardada' if self.id_edicion else 'creada'}"
        if ajuste:
            # ajustar_saldo devuelve el gasto anotado: positivo si el saldo baja.
            mensaje += f" · ajuste de {euros(-ajuste)}"
        return self._hecho(id_usuario, mensaje)

    # --- Borrar, fusionar, archivar ---------------------------------------

    @rx.event
    async def ver_borrar(self):
        """Botón "Eliminar": muestra el aviso con cuántos movimientos se
        perderían y las alternativas."""
        id_usuario = await self._id_usuario()
        if not id_usuario or not self.id_edicion:
            return
        id_elemento = int(self.id_edicion)
        if self.pestana == PESTANA_CUENTAS:
            self.n_movimientos = movimientos_cuenta(id_usuario, id_elemento)
            self.opciones_fusion = []
        else:
            self.n_movimientos = movimientos_categoria(id_usuario, id_elemento)
            self.opciones_fusion = [
                {"id": c["id"], "nombre": c["nombre"]}
                for c in self.lista
                if c["id"] != self.id_edicion
            ]
        self.id_fusion = ""
        self.error = ""
        self.vista = VISTA_BORRAR

    @rx.event
    async def borrar(self):
        """Elimina definitivamente el elemento y sus movimientos."""
        id_usuario = await self._id_usuario()
        if not id_usuario or not self.id_edicion:
            return
        es_cuenta = self.pestana == PESTANA_CUENTAS
        try:
            if es_cuenta:
                n = borrar_cuenta(id_usuario, int(self.id_edicion))
            else:
                n = borrar_categoria(id_usuario, int(self.id_edicion))
        except ValueError as e:
            self.error = str(e)
            return
        que = "Cuenta eliminada" if es_cuenta else "Categoría eliminada"
        if n:
            que += f" con sus {_plural(n)}"
        return self._hecho(id_usuario, que)

    @rx.event
    async def fusionar(self):
        id_usuario = await self._id_usuario()
        if not id_usuario or not self.id_edicion:
            return
        if not self.id_fusion:
            self.error = "Elige la categoría con la que fusionarla."
            return
        destino = next((c["nombre"] for c in self.opciones_fusion if c["id"] == self.id_fusion), "")
        try:
            n = fusionar_categoria(id_usuario, int(self.id_edicion), int(self.id_fusion))
        except ValueError as e:
            self.error = str(e)
            return
        return self._hecho(id_usuario, f"Fusionada con «{destino}» ({_plural(n)})")

    @rx.event
    async def archivar(self):
        id_usuario = await self._id_usuario()
        if not id_usuario or not self.id_edicion:
            return
        try:
            archivar_cuenta(id_usuario, int(self.id_edicion), archivar=True)
        except ValueError as e:
            self.error = str(e)
            return
        return self._hecho(id_usuario, "Cuenta archivada. Puedes restaurarla desde aquí.", aviso=True)

    @rx.event
    async def restaurar(self):
        id_usuario = await self._id_usuario()
        if not id_usuario or not self.id_edicion:
            return
        try:
            archivar_cuenta(id_usuario, int(self.id_edicion), archivar=False)
        except ValueError as e:
            self.error = str(e)
            return
        return self._hecho(id_usuario, "Cuenta restaurada")
