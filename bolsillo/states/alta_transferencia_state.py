"""Formulario de alta de una transferencia entre dos cuentas.

Se abre con el botón de transferencia (flechas ⇄) de la cabecera.
Solo pide fecha, importe (con el mismo teclado de calculadora que el
gasto), cuenta de origen y cuenta de destino. Propone las cuentas de la
última transferencia anotada.

Es un substate de ResumenState para poder usar sus cuentas y recargar
el saldo (`_recargar`) en cuanto se guarda.
"""

from datetime import date

import reflex as rx

from bolsillo import calculadora, periodos
from bolsillo.states.auth_state import AuthState
from bolsillo.states.resumen_state import ResumenState, euros
from bolsillo.transacciones_db import (
    crear_transferencia,
    cuentas_transferencia_por_defecto,
)


class AltaTransferenciaState(ResumenState):
    abierto: bool = False

    fecha_alta: str = ""  # ISO 'AAAA-MM-DD' (formato de <input type="date">)
    # Ids como texto, que es lo que maneja rx.select.
    id_origen: str = ""
    id_destino: str = ""
    # Lo que se ve en el campo del importe, p.ej. "100+50" (ver calculadora.py).
    expresion: str = ""
    error: str = ""

    # --- Vars derivadas para la interfaz ----------------------------------

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
        self.error = ""
        self.abierto = True

    @rx.event
    def set_abierto(self, valor: bool):
        self.abierto = valor

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
            anotado = crear_transferencia(
                id_usuario, int(self.id_origen), int(self.id_destino), fecha, importe
            )
        except ValueError as e:
            self.error = str(e)
            return

        self.abierto = False
        self.error = ""
        await self._recargar()
        return rx.toast.success(f"Transferencia anotada: {euros(anotado)}", duration=2500)
