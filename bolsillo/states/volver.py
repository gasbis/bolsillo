"""A dónde vuelven los formularios de gasto/ingreso y de transferencia
cuando se abrieron para editar un movimiento.

Se pueden abrir desde el listado de movimientos o desde el buscador.
Como en el móvil los diálogos uno encima de otro se comportan mal, el
que los abre se cierra y, al terminar con el formulario (guardar, borrar
o cerrar), se vuelve a abrir recargado con `volver_a(origen)`.
"""

ORIGEN_MOVIMIENTOS = "movimientos"
ORIGEN_BUSCADOR = "buscador"


def volver_a(origen: str) -> list:
    """Evento para reabrir el diálogo de `origen` (lista vacía si no se
    abrió desde ninguno)."""
    # Imports aquí: esos states importan los formularios para editar.
    if origen == ORIGEN_MOVIMIENTOS:
        from bolsillo.states.movimientos_state import MovimientosState

        return [MovimientosState.reabrir]
    if origen == ORIGEN_BUSCADOR:
        from bolsillo.states.buscador_state import BuscadorState

        return [BuscadorState.reabrir]
    return []
