"""Formulario de alta rápida de un gasto, que se abre con una pulsación
corta sobre el icono de una categoría en la pantalla principal.

Es un substate de ResumenState para poder usar sus cuentas y su filtro, y
recargar el donut (`_recargar`) en cuanto se guarda el gasto.
"""

from datetime import date
from decimal import Decimal, InvalidOperation

import reflex as rx

from bolsillo import periodos
from bolsillo.states.auth_state import AuthState
from bolsillo.states.resumen_state import ResumenState, euros
from bolsillo.transacciones_db import categorias_gasto, crear_gasto

# Límite de NUMERIC(12, 2).
_MAXIMO = Decimal("9999999999.99")


def leer_importe(texto: str) -> Decimal | None:
    """Acepta '12,5', '12.50', '1.234,56' o '-3,20' (devolución).
    Devuelve None si no es un número válido."""
    texto = (texto or "").strip().replace(" ", "").replace("€", "")
    if "," in texto:
        # Formato español: el punto es separador de miles.
        texto = texto.replace(".", "").replace(",", ".")
    try:
        valor = Decimal(texto)
    except InvalidOperation:
        return None
    if not valor.is_finite():
        return None
    return valor


class AltaGastoState(ResumenState):
    abierto: bool = False
    # Opciones de los selectores: [{"id": "3", "nombre": "Comida"}].
    opciones_categorias: list[dict[str, str]] = []
    # Valores elegidos (ids como texto, que es lo que maneja rx.select).
    id_categoria: str = ""
    # Se recuerda la última cuenta usada mientras dure la sesión.
    id_cuenta_alta: str = ""
    fecha_alta: str = ""
    error: str = ""

    @rx.var
    def sin_cuentas(self) -> bool:
        return len(self.cuentas) == 0

    def _fecha_por_defecto(self) -> str:
        """Hoy, salvo que se esté viendo un día concreto: entonces ese día
        (útil para anotar algo que se olvidó)."""
        if self.periodo in (periodos.PERIODO_DIA, periodos.PERIODO_ELEGIR_DIA):
            return self._fecha_referencia().isoformat()
        return date.today().isoformat()

    @rx.event
    async def abrir(self, id_categoria: str):
        """Pulsación corta sobre un icono. `id_categoria` vacío (el hueco
        "Otros") abre el formulario sin categoría elegida."""
        id_usuario = (await self.get_state(AuthState)).current_user["id"]
        if not id_usuario:
            return
        self.opciones_categorias = categorias_gasto(id_usuario)
        ids_categorias = {c["id"] for c in self.opciones_categorias}
        # Una categoría archivada (sale en el donut por tener movimientos
        # en el periodo) no admite gastos nuevos: se deja sin elegir.
        self.id_categoria = id_categoria if id_categoria in ids_categorias else ""

        ids_cuentas = [c["id"] for c in self.cuentas]
        filtro = self._id_cuenta()
        if filtro is not None:
            # Si se está viendo una cuenta concreta, el gasto va a ella.
            self.id_cuenta_alta = str(filtro)
        elif self.id_cuenta_alta not in ids_cuentas:
            self.id_cuenta_alta = ids_cuentas[0] if ids_cuentas else ""

        self.fecha_alta = self._fecha_por_defecto()
        self.error = ""
        self.abierto = True

    @rx.event
    def set_abierto(self, valor: bool):
        self.abierto = valor

    @rx.event
    def set_id_categoria(self, valor: str):
        self.id_categoria = valor

    @rx.event
    def set_id_cuenta_alta(self, valor: str):
        self.id_cuenta_alta = valor

    @rx.event
    async def guardar(self, datos: dict):
        importe = leer_importe(datos.get("importe", ""))
        fecha = periodos.a_fecha(datos.get("fecha", ""))
        if importe is None or importe == 0:
            self.error = "Escribe un importe (negativo si es una devolución)."
            return
        if abs(importe) > _MAXIMO:
            self.error = "El importe es demasiado grande."
            return
        if not self.id_categoria:
            self.error = "Elige una categoría."
            return
        if not self.id_cuenta_alta:
            self.error = "Elige una cuenta."
            return
        if fecha is None:
            self.error = "La fecha no es válida."
            return

        id_usuario = (await self.get_state(AuthState)).current_user["id"]
        if not id_usuario:
            return
        try:
            anotado = crear_gasto(
                id_usuario,
                int(self.id_categoria),
                int(self.id_cuenta_alta),
                fecha,
                importe,
                str(datos.get("notas", "")),
            )
        except ValueError as e:
            self.error = str(e)
            return

        self.abierto = False
        self.error = ""
        await self._recargar()
        return rx.toast.success(f"Gasto anotado: {euros(anotado)}", duration=2500)
