"""Formulario de alta de una transferencia entre dos cuentas.

Se abre con el botón de transferencia (flechas ⇄) de la cabecera.
Pide fecha, importe (con el mismo teclado de calculadora que el
gasto), cuenta de origen, cuenta de destino y notas. Propone las cuentas
de la última transferencia anotada.

Editar: tocar una transferencia en el listado de movimientos la abre
aquí (`editar`) con sus datos; el título pasa a "Editar transferencia"
y aparece el botón de borrarla. Al guardar, borrar o cerrar se vuelve
al listado.

Es un substate de ResumenState para poder usar sus cuentas y recargar
el saldo (`_recargar`) en cuanto se guarda.
"""

from datetime import date

import reflex as rx

from bolsillo import calculadora, periodos
from bolsillo.states.auth_state import AuthState
from bolsillo.states.resumen_state import ResumenState, euros
from bolsillo.states.volver import volver_a
from bolsillo.models import TIPO_TRANSFERENCIA
from bolsillo.transacciones_db import (
    borrar_movimiento,
    crear_transferencia,
    cuentas_transferencia_por_defecto,
    editar_transferencia,
    obtener_movimiento,
)


class AltaTransferenciaState(ResumenState):
    abierto: bool = False

    fecha_alta: str = ""  # ISO 'AAAA-MM-DD' (formato de <input type="date">)
    # Ids como texto, que es lo que maneja rx.select.
    id_origen: str = ""
    id_destino: str = ""
    # Lo que se ve en el campo del importe, p.ej. "100+50" (ver calculadora.py).
    expresion: str = ""
    notas: str = ""
    error: str = ""

    # --- Edición ------------------------------------------------------------
    id_edicion: str = ""  # "" = alta nueva
    confirmar_borrado: bool = False
    # Desde dónde se abrió para editar (ORIGEN_MOVIMIENTOS u
    # ORIGEN_BUSCADOR): al terminar se vuelve a él. "" = alta normal.
    _volver_a: str = ""

    # --- Vars derivadas para la interfaz ----------------------------------

    @rx.var
    def es_edicion(self) -> bool:
        return self.id_edicion != ""

    @rx.var
    def titulo(self) -> str:
        return "Editar transferencia" if self.id_edicion else "Nueva transferencia"

    @rx.var
    def pocas_cuentas(self) -> bool:
        """Hacen falta al menos dos cuentas para transferir."""
        return len(self.cuentas) < 2

    @rx.var
    def misma_cuenta(self) -> bool:
        return self.id_origen != "" and self.id_origen == self.id_destino

    @rx.var
    def se_puede_guardar(self) -> bool:
        valor = calculadora.evaluar(self.expresion)
        return (
            valor is not None
            and 0 < valor <= calculadora.MAXIMO
            and self.id_origen != ""
            and self.id_destino != ""
            and self.id_origen != self.id_destino
        )

    @rx.var
    def texto_resultado(self) -> str:
        """Debajo del importe: el valor que se va a guardar si hay
        operaciones a medias ('= 150,00 €') o el aviso si es negativo."""
        valor = calculadora.evaluar(self.expresion)
        if valor is None:
            return ""
        texto = f"= {euros(valor)}" if calculadora.tiene_operacion(self.expresion) else ""
        if valor < 0:
            texto = f"{texto}  (no puede ser negativo)".strip()
        return texto

    # --- Internos -----------------------------------------------------------

    async def _id_usuario(self) -> int | None:
        return (await self.get_state(AuthState)).current_user["id"] or None

    def _terminar(self) -> list:
        """Cierra el diálogo. Si se abrió desde el listado de movimientos
        o desde el buscador, devuelve el evento para volver a él (si no,
        una lista vacía)."""
        self.abierto = False
        self.error = ""
        self.confirmar_borrado = False
        origen, self._volver_a = self._volver_a, ""
        return volver_a(origen)

    # --- Abrir / cerrar ---------------------------------------------------

    @rx.event
    async def abrir(self):
        id_usuario = await self._id_usuario()
        if not id_usuario:
            return
        if not self.cuentas:
            await self._recargar()
        ids = [c["id"] for c in self.cuentas]
        origen, destino = cuentas_transferencia_por_defecto(id_usuario)
        self.id_origen = str(origen) if origen and str(origen) in ids else ""
        self.id_destino = str(destino) if destino and str(destino) in ids else ""
        self.fecha_alta = date.today().isoformat()
        self.expresion = ""
        self.notas = ""
        self.error = ""
        self.id_edicion = ""
        self.confirmar_borrado = False
        self._volver_a = ""
        self.abierto = True

    @rx.event
    async def editar(self, id_movimiento: str, origen: str):
        """Desde el listado de movimientos o el buscador (`origen`, ver
        states/volver.py): abre la transferencia con sus datos para
        modificarla o borrarla."""
        id_usuario = await self._id_usuario()
        if not id_usuario or not id_movimiento.isdigit():
            return
        mov = obtener_movimiento(id_usuario, int(id_movimiento))
        if mov is None or mov["tipo"] != TIPO_TRANSFERENCIA:
            return [rx.toast.error("Ese movimiento ya no existe."), *volver_a(origen)]
        if not self.cuentas:
            await self._recargar()
        self.id_origen = str(mov["id_cuenta"])
        self.id_destino = str(mov["id_cuenta_destino"] or "")
        self.fecha_alta = mov["fecha"].isoformat()
        self.expresion = calculadora.formatear(mov["importe"])
        self.notas = mov["notas"]
        self.error = ""
        self.id_edicion = id_movimiento
        self.confirmar_borrado = False
        self._volver_a = origen
        self.abierto = True

    @rx.event
    def set_abierto(self, valor: bool):
        if valor:
            self.abierto = True
            return
        return self._terminar()

    # --- Campos -------------------------------------------------------------

    @rx.event
    def set_fecha_alta(self, valor: str):
        if periodos.a_fecha(valor):
            self.fecha_alta = valor

    @rx.event
    def set_id_origen(self, valor: str):
        self.id_origen = valor
        self.error = ""

    @rx.event
    def set_id_destino(self, valor: str):
        self.id_destino = valor
        self.error = ""

    @rx.event
    def intercambiar(self):
        """Tocar la flecha entre las dos cuentas les da la vuelta."""
        self.id_origen, self.id_destino = self.id_destino, self.id_origen
        self.error = ""

    @rx.event
    def set_expresion(self, valor: str):
        """Escribir en el campo con un teclado físico (ordenador)."""
        self.expresion = calculadora.limpiar(valor)
        self.error = ""

    @rx.event
    def set_notas(self, valor: str):
        self.notas = valor[:200]

    @rx.event
    def tecla(self, tecla: str):
        """Teclado numérico del formulario."""
        self.expresion = calculadora.pulsar(self.expresion, tecla)
        self.error = ""

    # --- Guardar ----------------------------------------------------------

    @rx.event
    async def guardar(self):
        importe = calculadora.evaluar(self.expresion)
        fecha = periodos.a_fecha(self.fecha_alta)
        if importe is None or importe <= 0:
            self.error = "Escribe un importe mayor que 0."
            return
        if importe > calculadora.MAXIMO:
            self.error = "El importe es demasiado grande."
            return
        if not self.id_origen or not self.id_destino:
            self.error = "Elige la cuenta de origen y la de destino."
            return
        if self.id_origen == self.id_destino:
            self.error = "La cuenta de origen y la de destino tienen que ser distintas."
            return
        if fecha is None:
            self.error = "La fecha no es válida."
            return

        id_usuario = await self._id_usuario()
        if not id_usuario:
            return
        try:
            if self.id_edicion:
                anotado = editar_transferencia(
                    id_usuario,
                    int(self.id_edicion),
                    int(self.id_origen),
                    int(self.id_destino),
                    fecha,
                    importe,
                    self.notas,
                )
            else:
                anotado = crear_transferencia(
                    id_usuario, int(self.id_origen), int(self.id_destino), fecha, importe, self.notas
                )
        except ValueError as e:
            self.error = str(e)
            return

        hecho = "modificada" if self.id_edicion else "anotada"
        await self._recargar()
        return [
            rx.toast.success(f"Transferencia {hecho}: {euros(anotado)}", duration=2500),
            *self._terminar(),
        ]

    @rx.event
    async def borrar(self):
        """Botón "Eliminar" de la edición: el primer toque pide
        confirmación y el segundo borra."""
        if not self.id_edicion:
            return
        if not self.confirmar_borrado:
            self.confirmar_borrado = True
            return
        id_usuario = await self._id_usuario()
        if not id_usuario:
            return
        try:
            borrar_movimiento(id_usuario, int(self.id_edicion))
        except ValueError as e:
            self.error = str(e)
            self.confirmar_borrado = False
            return
        await self._recargar()
        return [rx.toast.success("Transferencia eliminada", duration=2500), *self._terminar()]
