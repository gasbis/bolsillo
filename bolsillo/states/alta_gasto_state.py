"""Formulario de alta de un gasto o de un ingreso (`tipo`).

Los dos formularios son el mismo; un ingreso solo cambia el título, las
categorías que se ofrecen (las de ingreso) y que el importe tiene que
ser positivo (un gasto puede ser negativo: devoluciones).

Un gasto se abre de dos formas:
- Pulsación corta sobre el icono de una categoría en la pantalla
  principal: la categoría ya viene elegida y el botón final la muestra
  e invita a aceptar.
- Botón de gasto (flecha roja) del pie: sin categoría; el botón final
  ("Elegir categoría") abre el selector de categorías, desde el que
  también se puede crear una nueva.
Un ingreso se abre con el botón de ingreso (flecha verde) del pie, sin
categoría, y funciona igual que el segundo caso.

El diálogo tiene tres vistas (VISTA_*): el formulario, el selector de
categorías y la creación de una categoría nueva.

Es un substate de ResumenState para poder usar sus cuentas y recargar el
donut (`_recargar`) en cuanto se guarda el gasto.
"""

from datetime import date

import reflex as rx

from bolsillo import calculadora, periodos
from bolsillo.iconos import ICONOS
from bolsillo.models import TIPO_GASTO, TIPO_INGRESO
from bolsillo.states.auth_state import AuthState
from bolsillo.states.resumen_state import ResumenState, euros
from bolsillo.transacciones_db import (
    categorias,
    crear_categoria,
    crear_movimiento,
    cuentas_por_defecto,
)

VISTA_FORMULARIO = "formulario"
VISTA_CATEGORIAS = "categorias"
VISTA_NUEVA = "nueva"


class AltaGastoState(ResumenState):
    abierto: bool = False
    vista: str = VISTA_FORMULARIO
    tipo: str = TIPO_GASTO  # TIPO_GASTO | TIPO_INGRESO

    # --- Formulario ---------------------------------------------------------
    fecha_alta: str = ""  # ISO 'AAAA-MM-DD' (formato de <input type="date">)
    # Ids como texto, que es lo que maneja rx.select.
    id_cuenta_alta: str = ""
    # Lo que se ve en el campo del importe, p.ej. "12,50+3" (ver calculadora.py).
    expresion: str = ""
    notas: str = ""
    error: str = ""

    # --- Categorías -------------------------------------------------------
    # [{"id": "3", "nombre": "Comida", "icono": "utensils", "color": "#F97316"}]
    opciones_categorias: list[dict[str, str]] = []
    id_categoria: str = ""

    # --- Categoría nueva --------------------------------------------------
    nuevo_nombre: str = ""
    nuevo_icono: str = ""
    error_nueva: str = ""

    # --- Solo en el servidor (no viajan al navegador) ---------------------
    # Cuenta más usada últimamente y {id_categoria: id_cuenta} de las
    # categorías que siempre se pagan con la misma (transacciones_db.py).
    _cuenta_habitual: str = ""
    _cuentas_fijas: dict[str, str] = {}
    # Si el usuario cambia la cuenta a mano, elegir después una categoría
    # ya no se la cambia.
    _cuenta_elegida_a_mano: bool = False

    # --- Vars derivadas para la interfaz ----------------------------------

    @rx.var
    def es_ingreso(self) -> bool:
        return self.tipo == TIPO_INGRESO

    @rx.var
    def sin_cuentas(self) -> bool:
        return len(self.cuentas) == 0

    @rx.var
    def importe_valido(self) -> bool:
        """Activa el botón de categoría / aceptar."""
        valor = calculadora.evaluar(self.expresion)
        if valor is None or valor == 0 or abs(valor) > calculadora.MAXIMO:
            return False
        # Un ingreso no puede ser negativo.
        return valor > 0 or self.tipo == TIPO_GASTO

    @rx.var
    def texto_resultado(self) -> str:
        """Debajo del importe: el valor que se va a guardar si hay
        operaciones a medias ('= 18,50 €') y si es una devolución (en un
        ingreso, que no puede ser negativo)."""
        valor = calculadora.evaluar(self.expresion)
        if valor is None:
            return ""
        texto = f"= {euros(valor)}" if calculadora.tiene_operacion(self.expresion) else ""
        if valor < 0:
            aviso = "(no puede ser negativo)" if self.tipo == TIPO_INGRESO else "(devolución)"
            texto = f"{texto}  {aviso}".strip()
        return texto

    @rx.var
    def texto_importe(self) -> str:
        """Importe que se guardará, para la cabecera del selector."""
        valor = calculadora.evaluar(self.expresion)
        return euros(valor) if valor is not None else ""

    @rx.var
    def categoria_elegida(self) -> dict[str, str]:
        for c in self.opciones_categorias:
            if c["id"] == self.id_categoria:
                return c
        return {}

    @rx.var
    def hay_categoria(self) -> bool:
        return any(c["id"] == self.id_categoria for c in self.opciones_categorias)

    @rx.var
    def titulo(self) -> str:
        if self.vista == VISTA_CATEGORIAS:
            return "Elegir categoría"
        if self.vista == VISTA_NUEVA:
            return "Nueva categoría"
        return "Nuevo ingreso" if self.tipo == TIPO_INGRESO else "Nuevo gasto"

    # --- Internos -----------------------------------------------------------

    async def _id_usuario(self) -> int | None:
        return (await self.get_state(AuthState)).current_user["id"] or None

    def _cuenta_propuesta(self, id_categoria: str) -> str:
        """La cuenta fija de la categoría si la tiene; si no, la habitual;
        y si tampoco, la primera de la lista."""
        ids = [c["id"] for c in self.cuentas]
        for candidata in (self._cuentas_fijas.get(id_categoria, ""), self._cuenta_habitual):
            if candidata in ids:
                return candidata
        return ids[0] if ids else ""

    def _elegir_categoria(self, id_categoria: str):
        self.id_categoria = id_categoria
        if not self._cuenta_elegida_a_mano:
            self.id_cuenta_alta = self._cuenta_propuesta(id_categoria)
        self.error = ""
        self.vista = VISTA_FORMULARIO

    # --- Abrir / cerrar ---------------------------------------------------

    @rx.event
    async def abrir(self, id_categoria: str):
        """Alta de un GASTO: pulsación corta sobre un icono, o botón de
        gasto del pie con `id_categoria` vacío (también el hueco "Otros"
        del donut)."""
        await self._abrir(TIPO_GASTO, id_categoria)

    @rx.event
    async def abrir_ingreso(self, id_categoria: str):
        """Alta de un INGRESO: botón de ingreso del pie (sin categoría)."""
        await self._abrir(TIPO_INGRESO, id_categoria)

    async def _abrir(self, tipo: str, id_categoria: str):
        id_usuario = await self._id_usuario()
        if not id_usuario:
            return
        if not self.cuentas:
            await self._recargar()
        self.tipo = tipo
        self.vista = VISTA_FORMULARIO
        self.opciones_categorias = categorias(id_usuario, tipo)
        habitual, fijas = cuentas_por_defecto(id_usuario, tipo=tipo)
        self._cuenta_habitual = str(habitual) if habitual else ""
        self._cuentas_fijas = {str(k): str(v) for k, v in fijas.items()}
        self._cuenta_elegida_a_mano = False

        # Una categoría archivada (sale en el donut por tener movimientos
        # en el periodo) no admite movimientos nuevos: se deja sin elegir.
        ids_categorias = {c["id"] for c in self.opciones_categorias}
        self._elegir_categoria(id_categoria if id_categoria in ids_categorias else "")

        self.fecha_alta = date.today().isoformat()
        self.expresion = ""
        self.notas = ""
        self.error = ""
        self.abierto = True

    @rx.event
    def set_abierto(self, valor: bool):
        self.abierto = valor

    # --- Campos del formulario --------------------------------------------

    @rx.event
    def set_fecha_alta(self, valor: str):
        if periodos.a_fecha(valor):
            self.fecha_alta = valor

    @rx.event
    def set_id_cuenta_alta(self, valor: str):
        self.id_cuenta_alta = valor
        self._cuenta_elegida_a_mano = True

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

    @rx.event
    def set_notas(self, valor: str):
        self.notas = valor[:200]

    # --- Selector y creación de categorías --------------------------------

    @rx.event
    def ver_categorias(self):
        self.vista = VISTA_CATEGORIAS

    @rx.event
    def ver_formulario(self):
        self.vista = VISTA_FORMULARIO

    @rx.event
    def elegir_categoria(self, id_categoria: str):
        """Vuelve al formulario con la categoría elegida: el botón final
        pasa a mostrarla e invita a aceptar."""
        self._elegir_categoria(id_categoria)

    @rx.event
    def ver_nueva(self):
        self.nuevo_nombre = ""
        self.nuevo_icono = ""
        self.error_nueva = ""
        self.vista = VISTA_NUEVA

    @rx.event
    def set_nuevo_nombre(self, valor: str):
        self.nuevo_nombre = valor
        self.error_nueva = ""

    @rx.event
    def set_nuevo_icono(self, icono: str):
        if icono in ICONOS:
            self.nuevo_icono = icono
            self.error_nueva = ""

    @rx.event
    async def crear_categoria(self):
        id_usuario = await self._id_usuario()
        if not id_usuario:
            return
        try:
            nuevo_id = crear_categoria(id_usuario, self.tipo, self.nuevo_nombre, self.nuevo_icono)
        except ValueError as e:
            self.error_nueva = str(e)
            return
        self.opciones_categorias = categorias(id_usuario, self.tipo)
        self._elegir_categoria(str(nuevo_id))
        # El donut tiene que enseñar ya la categoría nueva.
        await self._recargar()

    # --- Guardar ----------------------------------------------------------

    @rx.event
    async def guardar(self):
        importe = calculadora.evaluar(self.expresion)
        fecha = periodos.a_fecha(self.fecha_alta)
        es_ingreso = self.tipo == TIPO_INGRESO
        if importe is None or importe == 0:
            self.error = (
                "Escribe un importe."
                if es_ingreso
                else "Escribe un importe (negativo si es una devolución)."
            )
            return
        if es_ingreso and importe < 0:
            self.error = "Un ingreso no puede ser negativo."
            return
        if abs(importe) > calculadora.MAXIMO:
            self.error = "El importe es demasiado grande."
            return
        if not self.id_categoria:
            self.vista = VISTA_CATEGORIAS
            return
        if not self.id_cuenta_alta:
            self.error = "Elige una cuenta."
            return
        if fecha is None:
            self.error = "La fecha no es válida."
            return

        id_usuario = await self._id_usuario()
        if not id_usuario:
            return
        try:
            anotado = crear_movimiento(
                id_usuario,
                self.tipo,
                int(self.id_categoria),
                int(self.id_cuenta_alta),
                fecha,
                importe,
                self.notas,
            )
        except ValueError as e:
            self.error = str(e)
            return

        self.abierto = False
        self.error = ""
        await self._recargar()
        que = "Ingreso" if es_ingreso else "Gasto"
        return rx.toast.success(f"{que} anotado: {euros(anotado)}", duration=2500)
