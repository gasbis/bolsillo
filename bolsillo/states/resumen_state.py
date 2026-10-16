"""Filtros (fecha y cuenta) de la pantalla principal y los datos que se
muestran según ellos.

Cada cambio de filtro vuelve a consultar la base de datos (`_recargar`).
La geometría del donut vive en components/donut.py (`DonutState`, un
substate de este) para no mezclar dibujo y datos.
"""

from datetime import date

import reflex as rx

from bolsillo import periodos
from bolsillo.resumen_db import CERO, cuentas_usuario, resumen
from bolsillo.states.auth_state import AuthState

TODAS_CUENTAS = "Todas"


def euros(valor) -> str:
    """1234.5 → '1.234,50 €'."""
    return f"{valor:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


class ResumenState(rx.State):
    # --- Filtros -----------------------------------------------------------
    periodo: str = periodos.PERIODO_MES
    # Un día cualquiera del periodo que se está viendo (ISO 'AAAA-MM-DD').
    # Vacío = hoy (se rellena al cargar, para que "hoy" sea el del
    # momento de abrir la app y no el de arrancar el servidor).
    referencia: str = ""
    # Solo para el periodo "Intervalo" (formato de <input type="date">).
    desde: str = ""
    hasta: str = ""
    # Nombre de la cuenta elegida o TODAS_CUENTAS. Se guarda el nombre
    # (único por usuario) porque es lo que maneja rx.select.
    cuenta: str = TODAS_CUENTAS
    cuentas: list[dict[str, str]] = []  # [{"id": "3", "nombre": "Banco"}]

    # --- Datos del periodo ------------------------------------------------
    # Categorías de gasto en su orden: id, nombre, icono, color e importe
    # (float solo para el dibujo; los textos se formatean desde Decimal).
    categorias: list[dict[str, str | float]] = []
    texto_gastos: str = euros(CERO)
    texto_ingresos: str = euros(CERO)
    # Saldo del periodo: ingresos - gastos (no el saldo de las cuentas).
    texto_saldo: str = euros(CERO)
    saldo_negativo: bool = False

    # --- Vars derivadas para la interfaz ----------------------------------

    @rx.var
    def nombres_cuentas(self) -> list[str]:
        return [TODAS_CUENTAS] + [c["nombre"] for c in self.cuentas]

    @rx.var
    def texto_periodo(self) -> str:
        return periodos.etiqueta(self.periodo, self._fecha_referencia(), self.desde, self.hasta)

    @rx.var
    def navegable(self) -> bool:
        return self.periodo in periodos.PERIODOS_NAVEGABLES

    @rx.var
    def es_intervalo(self) -> bool:
        return self.periodo == periodos.PERIODO_INTERVALO

    @rx.var
    def es_elegir_dia(self) -> bool:
        return self.periodo == periodos.PERIODO_ELEGIR_DIA

    @rx.var
    def filtro_activo(self) -> bool:
        """Para resaltar el botón del embudo si el filtro no es el de
        partida (mes actual, todas las cuentas)."""
        return (
            self.cuenta != TODAS_CUENTAS
            or self.periodo != periodos.PERIODO_MES
            or self._fecha_referencia().replace(day=1) != date.today().replace(day=1)
        )

    # --- Internos -----------------------------------------------------------

    def _fecha_referencia(self) -> date:
        return periodos.a_fecha(self.referencia) or date.today()

    def _id_cuenta(self) -> int | None:
        for c in self.cuentas:
            if c["nombre"] == self.cuenta:
                return int(c["id"])
        return None

    async def _recargar(self):
        id_usuario = (await self.get_state(AuthState)).current_user["id"]
        if not id_usuario:
            return
        self.cuentas = cuentas_usuario(id_usuario)
        if self.cuenta != TODAS_CUENTAS and self._id_cuenta() is None:
            # La cuenta elegida ya no existe o se ha archivado.
            self.cuenta = TODAS_CUENTAS

        inicio, fin = periodos.rango(
            self.periodo, self._fecha_referencia(), self.desde, self.hasta
        )
        datos = resumen(id_usuario, inicio, fin, self._id_cuenta())

        self.categorias = [
            {
                "id": str(g.id),
                "nombre": g.nombre,
                "icono": g.icono,
                "color": g.color,
                "importe": float(g.importe),
                "texto": euros(g.importe),
            }
            for g in datos.gastos
        ]
        self.texto_gastos = euros(datos.total_gastos)
        self.texto_ingresos = euros(datos.total_ingresos)
        self.texto_saldo = euros(datos.saldo)
        self.saldo_negativo = datos.saldo < 0

    # --- Eventos ------------------------------------------------------------

    @rx.event
    async def cargar(self):
        """on_mount de la pantalla principal: se dispara al entrar ya
        identificado y también justo después de iniciar sesión."""
        if not self.referencia:
            self.referencia = date.today().isoformat()
        await self._recargar()

    @rx.event
    async def set_periodo(self, periodo: str):
        if periodo not in periodos.PERIODOS:
            return
        self.periodo = periodo
        if periodo == periodos.PERIODO_INTERVALO and not (self.desde or self.hasta):
            # Por defecto, el intervalo que se estaba viendo.
            inicio, fin = periodos.rango(
                periodos.PERIODO_MES, self._fecha_referencia()
            )
            self.desde, self.hasta = inicio.isoformat(), fin.isoformat()
        await self._recargar()

    @rx.event
    async def set_cuenta(self, cuenta: str):
        self.cuenta = cuenta
        await self._recargar()

    @rx.event
    async def set_referencia(self, valor: str):
        """Día elegido en "Elegir día"."""
        if periodos.a_fecha(valor):
            self.referencia = valor
            await self._recargar()

    @rx.event
    async def set_desde(self, valor: str):
        self.desde = valor
        await self._recargar()

    @rx.event
    async def set_hasta(self, valor: str):
        self.hasta = valor
        await self._recargar()

    @rx.event
    async def mover(self, pasos: int):
        """Flechas ‹ ›: periodo anterior (-1) o siguiente (+1)."""
        self.referencia = periodos.desplazar(
            self.periodo, self._fecha_referencia(), pasos
        ).isoformat()
        await self._recargar()

    @rx.event
    async def ir_a_hoy(self):
        self.referencia = date.today().isoformat()
        await self._recargar()

    @rx.event
    async def restablecer(self):
        """Vuelve al filtro de partida: mes actual y todas las cuentas."""
        self.periodo = periodos.PERIODO_MES
        self.referencia = date.today().isoformat()
        self.cuenta = TODAS_CUENTAS
        await self._recargar()
