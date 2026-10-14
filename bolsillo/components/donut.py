"""Gráfico de anillo con los iconos de categoría alrededor y una línea
que une cada icono con su porción.

Todo se dibuja en un único SVG con `viewBox="0 0 100 100"`, así que las
coordenadas son porcentajes del cuadrado que lo contiene: los iconos se
colocan encima con `position: absolute` usando esos mismos porcentajes y
líneas, anillo e iconos encajan siempre, sea cual sea el tamaño de la
pantalla. (Con recharts no se puede saber desde fuera dónde cae cada
porción, por eso no se dibujaban las líneas.)
"""

import math

import reflex as rx

from bolsillo.pages.categories import ICONOS

# --- Geometría (unidades del viewBox 0-100) -------------------------------

CENTRO = 50.0
R_EXT = 31.0  # radio exterior del anillo
R_INT = 21.0  # radio interior (hueco donde van los importes)
R_LINEA = 33.0  # la línea empieza un poco por fuera del anillo
ICONO = 12.0  # diámetro del círculo de cada icono
_RECORTE = ICONO / 2 + 0.8  # la línea termina en el borde del icono

# 14 huecos en el sentido de las agujas del reloj empezando arriba a la
# izquierda: 4 arriba, 3 a la derecha, 4 abajo y 3 a la izquierda.
_FILA = [11.0, 37.0, 63.0, 89.0]
_COL = [31.0, 50.0, 69.0]
HUECOS: list[tuple[float, float]] = (
    [(x, 7.0) for x in _FILA]
    + [(93.0, y) for y in _COL]
    + [(x, 93.0) for x in reversed(_FILA)]
    + [(7.0, y) for y in reversed(_COL)]
)

COLORES = [
    "#6366F1", "#8B5CF6", "#A855F7", "#D946EF", "#EC4899", "#F43F5E", "#F97316",
    "#EAB308", "#84CC16", "#22C55E", "#14B8A6", "#06B6D4", "#0EA5E9", "#3B82F6",
]

# El anillo empieza en el ángulo del primer hueco (arriba a la izquierda) y
# avanza en el mismo sentido que los huecos: así cada línea sale más o
# menos hacia su icono y casi nunca se cruzan.
_ANG_INICIO = math.degrees(math.atan2(HUECOS[0][1] - CENTRO, HUECOS[0][0] - CENTRO)) - 8


def _punto(r: float, ang: float) -> tuple[float, float]:
    rad = math.radians(ang)
    return CENTRO + r * math.cos(rad), CENTRO + r * math.sin(rad)


def _sector(a0: float, a1: float) -> str:
    """Path SVG de una porción del anillo entre los ángulos a0 y a1 (grados,
    0 = las 3 en punto, sentido horario)."""
    a1 = min(a1, a0 + 359.99)  # un arco de 360º exactos no se dibuja
    grande = 1 if a1 - a0 > 180 else 0
    x0, y0 = _punto(R_EXT, a0)
    x1, y1 = _punto(R_EXT, a1)
    x2, y2 = _punto(R_INT, a1)
    x3, y3 = _punto(R_INT, a0)
    return (
        f"M {x0:.3f} {y0:.3f} A {R_EXT} {R_EXT} 0 {grande} 1 {x1:.3f} {y1:.3f} "
        f"L {x2:.3f} {y2:.3f} A {R_INT} {R_INT} 0 {grande} 0 {x3:.3f} {y3:.3f} Z"
    )


def _linea(ang: float, hueco: tuple[float, float]) -> dict[str, str]:
    xa, ya = _punto(R_LINEA, ang)
    xi, yi = hueco
    dist = math.hypot(xi - xa, yi - ya)
    k = max(dist - _RECORTE, 0) / dist if dist else 0
    return {
        "x1": f"{xa:.3f}",
        "y1": f"{ya:.3f}",
        "x2": f"{xa + (xi - xa) * k:.3f}",
        "y2": f"{ya + (yi - ya) * k:.3f}",
    }


class ResumenState(rx.State):
    # Datos ficticios: gasto de cada uno de los 14 huecos en el periodo
    # elegido. Cuando existan los movimientos se calculará desde la BD.
    gastos: list[float] = [42.5, 0, 18.0, 25.3, 0, 9.9, 60.0, 12.0, 0, 30.0, 7.5, 0, 15.0, 22.0]
    ingresos: float = 35.56

    @rx.var
    def total_gastos(self) -> float:
        return sum(self.gastos)

    @rx.var
    def texto_gastos(self) -> str:
        return _euros(self.total_gastos)

    @rx.var
    def texto_ingresos(self) -> str:
        return _euros(self.ingresos)

    @rx.var
    def activos(self) -> list[bool]:
        return [g > 0 for g in self.gastos]

    @rx.var
    def porciones(self) -> list[dict[str, str]]:
        """Una entrada por categoría con gasto: path de la porción, línea
        hasta su icono y color."""
        total = self.total_gastos
        if total <= 0:
            return []
        res: list[dict[str, str]] = []
        ang = _ANG_INICIO
        for i, gasto in enumerate(self.gastos):
            if gasto <= 0:
                continue
            paso = 360 * gasto / total
            res.append(
                {
                    "d": _sector(ang, ang + paso),
                    "color": COLORES[i],
                    **_linea(ang + paso / 2, HUECOS[i]),
                }
            )
            ang += paso
        return res


def _euros(valor: float) -> str:
    return f"{valor:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def _icono(i: int) -> rx.Component:
    x, y = HUECOS[i]
    color = COLORES[i]
    return rx.box(
        rx.icon(tag=ICONOS[i], color=color, style={"width": "58%", "height": "58%"}),
        position="absolute",
        left=f"{x}%",
        top=f"{y}%",
        width=f"{ICONO}%",
        height=f"{ICONO}%",
        transform="translate(-50%, -50%)",
        display="flex",
        align_items="center",
        justify_content="center",
        border_radius="50%",
        border=f"2px solid {color}",
        background_color=f"{color}1A",
        opacity=rx.cond(ResumenState.activos[i], "1", "0.35"),
        cursor="pointer",
    )


def grafico_categorias() -> rx.Component:
    """Cuadrado que ocupa todo el sitio disponible (el menor de ancho y alto
    del contenedor, que debe tener `container_type="size"`)."""
    return rx.box(
        rx.el.svg(
            rx.foreach(
                ResumenState.porciones,
                lambda p: rx.el.svg.line(
                    x1=p["x1"], y1=p["y1"], x2=p["x2"], y2=p["y2"],
                    stroke=p["color"], stroke_width="0.5", stroke_linecap="round",
                ),
            ),
            rx.foreach(
                ResumenState.porciones,
                lambda p: rx.el.svg.path(
                    d=p["d"], fill=p["color"],
                    stroke="var(--color-background)", stroke_width="0.6",
                ),
            ),
            view_box="0 0 100 100",
            width="100%",
            height="100%",
            position="absolute",
            inset="0",
        ),
        *[_icono(i) for i in range(len(HUECOS))],
        rx.vstack(
            rx.text(ResumenState.texto_ingresos, size="3", weight="bold", color_scheme="green"),
            rx.text(ResumenState.texto_gastos, size="3", weight="bold", color_scheme="red"),
            align="center",
            spacing="1",
            position="absolute",
            top="50%",
            left="50%",
            transform="translate(-50%, -50%)",
        ),
        position="relative",
        width="min(100cqw, 100cqh)",
        height="min(100cqw, 100cqh)",
        flex_shrink="0",
    )
