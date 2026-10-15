"""Gráfico de anillo con los iconos de categoría alrededor y una línea
que une cada icono con su porción.

Todo se dibuja en un único SVG con `viewBox="0 0 100 100"`, así que las
coordenadas son porcentajes del cuadrado que lo contiene: los iconos se
colocan encima con `position: absolute` usando esos mismos porcentajes y
líneas, anillo e iconos encajan siempre, sea cual sea el tamaño de la
pantalla. (Con recharts no se puede saber desde fuera dónde cae cada
porción, por eso no se dibujaban las líneas.)

Interacción con los iconos (pensada para el dedo, también va con ratón):
- Debajo de cada icono se ve siempre su % sobre el gasto del periodo.
- Mantener pulsado: el centro del anillo muestra el nombre y el total de
  esa categoría y su porción se resalta; al soltar vuelve a lo normal.
  Es puro navegador (`_JS_PULSACION`), sin ir al servidor, para que
  responda al instante.
- Pulsación corta: abre el alta de gasto con esa categoría elegida.
"""

import math

import reflex as rx

from bolsillo.states.alta_gasto_state import AltaGastoState
from bolsillo.states.resumen_state import ResumenState, euros

# --- Geometría (unidades del viewBox 0-100) -------------------------------

CENTRO = 50.0
R_EXT = 31.0  # radio exterior del anillo
R_INT = 21.0  # radio interior (hueco donde van los importes)
R_LINEA = 33.0  # la línea empieza un poco por fuera del anillo
ICONO = 12.0  # diámetro del círculo de cada icono
_RECORTE = ICONO / 2 + 0.8  # la línea termina en el borde del icono

# 14 huecos en el sentido de las agujas del reloj empezando arriba a la
# izquierda: 4 arriba, 3 a la derecha, 4 abajo y 3 a la izquierda.
# Cada hueco es el centro del icono; el % va debajo, por eso la fila de
# abajo está más arriba (89) que simétrica a la de arriba (7): así el %
# de los iconos de abajo cabe dentro del cuadrado.
_FILA = [11.0, 37.0, 63.0, 89.0]
_COL = [30.0, 49.0, 68.0]
_ARRIBA, _ABAJO = 7.0, 89.0
HUECOS: list[tuple[float, float]] = (
    [(x, _ARRIBA) for x in _FILA]
    + [(93.0, y) for y in _COL]
    + [(x, _ABAJO) for x in reversed(_FILA)]
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


# Color por defecto de `Categoria.color`: si el usuario no ha elegido
# uno, se usa el de la paleta según el hueco para que el anillo no salga
# todo gris.
_COLOR_POR_DEFECTO = "#64748b"
_ICONO_OTROS = "ellipsis"
_COLOR_OTROS = "#94a3b8"


def _huecos(categorias: list[dict]) -> list[dict]:
    """Asigna las categorías de gasto (ya en su orden) a los 14 huecos.
    Si hay más de 14, el último hueco agrupa el resto como "Otros"."""
    n = len(HUECOS)
    if len(categorias) > n:
        resto = sum(float(c["importe"]) for c in categorias[n - 1:])
        categorias = categorias[: n - 1] + [
            {
                "id": "",  # no es una categoría: el alta se abre sin elegir
                "nombre": "Otros",
                "icono": _ICONO_OTROS,
                "color": _COLOR_OTROS,
                "importe": resto,
                "texto": euros(resto),
            }
        ]
    res = []
    for i, c in enumerate(categorias):
        color = str(c["color"])
        if not color or color.lower() == _COLOR_POR_DEFECTO:
            color = COLORES[i]
        res.append({**c, "color": color, "importe": float(c["importe"]), "hueco": i})
    return res


def _porcentaje(importe: float, total: float) -> str:
    """'23 %', '<1 %' o '0 %' (sin gasto o gasto neto negativo)."""
    if importe <= 0 or total <= 0:
        return "0\u00a0%"
    p = 100 * importe / total
    if p < 1:
        return "<1\u00a0%"
    return f"{round(p)}\u00a0%"


class DonutState(ResumenState):
    """Geometría del anillo a partir de `ResumenState.categorias`."""

    @rx.var
    def iconos(self) -> list[dict[str, str]]:
        """Un icono por categoría, en su hueco, con su % del gasto y los
        textos que se ven en el centro al mantenerlo pulsado. Las que no
        tienen gasto en el periodo se ven atenuadas."""
        huecos = _huecos(self.categorias)
        # Mismo total que el anillo (solo gasto neto positivo), para que
        # los % cuadren con el tamaño de las porciones y sumen 100.
        total = sum(c["importe"] for c in huecos if c["importe"] > 0)
        res = []
        for c in huecos:
            x, y = HUECOS[c["hueco"]]
            res.append(
                {
                    "i": str(c["hueco"]),
                    "id": str(c.get("id", "")),
                    "nombre": str(c["nombre"]),
                    "texto": str(c.get("texto", "")),
                    "porcentaje": _porcentaje(c["importe"], total),
                    "icono": str(c["icono"]),
                    "color": c["color"],
                    "fondo": f"{c['color']}1A",
                    "borde": f"2px solid {c['color']}",
                    "left": f"{x}%",
                    "top": f"{y}%",
                    "opacidad": "1" if c["importe"] > 0 else "0.35",
                }
            )
        return res

    @rx.var
    def porciones(self) -> list[dict[str, str]]:
        """Una entrada por categoría con gasto: path de la porción, línea
        hasta su icono y color. Las de gasto neto negativo (más
        devoluciones que gastos) no se dibujan."""
        con_gasto = [c for c in _huecos(self.categorias) if c["importe"] > 0]
        total = sum(c["importe"] for c in con_gasto)
        if total <= 0:
            return []
        res: list[dict[str, str]] = []
        ang = _ANG_INICIO
        for c in con_gasto:
            paso = 360 * c["importe"] / total
            res.append(
                {
                    "i": str(c["hueco"]),
                    "d": _sector(ang, ang + paso),
                    "color": c["color"],
                    **_linea(ang + paso / 2, HUECOS[c["hueco"]]),
                }
            )
            ang += paso
        return res


# --- Pulsación larga ---------------------------------------------------
#
# Reflex no tiene eventos de "mantener pulsado" y hacerlo con eventos al
# servidor iría con retraso, así que se resuelve en el navegador: al
# cumplirse ESPERA ms con el dedo quieto sobre un icono se pone
# `data-sel="<hueco>"` en el cuadrado del gráfico y el CSS de `_CSS` hace
# el resto (muestra el centro de esa categoría y atenúa las demás
# porciones). Al soltar se quita. Si hubo pulsación larga (o el dedo se
# movió) se anula el click, para que no se abra además el formulario.
# React no toca `data-sel` porque no es una prop suya.

_ESPERA_MS = 450

_JS_PULSACION = """
(function () {
  if (window.__bolsilloPulsacion) return;
  window.__bolsilloPulsacion = true;
  var ESPERA = %d, MARGEN = 10;
  var temporizador = null, icono = null, bloquear = false, x0 = 0, y0 = 0;

  function cuadrado(el) { return el && el.closest('.donut-categorias'); }
  function terminar() {
    clearTimeout(temporizador);
    temporizador = null;
    var d = cuadrado(icono);
    if (d) d.removeAttribute('data-sel');
    icono = null;
  }

  document.addEventListener('pointerdown', function (e) {
    var ic = e.target.closest && e.target.closest('.icono-categoria');
    terminar();
    bloquear = false;
    if (!ic || (e.pointerType === 'mouse' && e.button !== 0)) return;
    icono = ic; x0 = e.clientX; y0 = e.clientY;
    temporizador = setTimeout(function () {
      temporizador = null;
      bloquear = true;
      var d = cuadrado(ic);
      if (d) d.setAttribute('data-sel', ic.getAttribute('data-i'));
      if (navigator.vibrate) { try { navigator.vibrate(15); } catch (_) {} }
    }, ESPERA);
  });

  document.addEventListener('pointermove', function (e) {
    // Si el dedo se desplaza antes de tiempo no es ni corta ni larga.
    if (temporizador && Math.hypot(e.clientX - x0, e.clientY - y0) > MARGEN) {
      bloquear = true;
      terminar();
    }
  });

  document.addEventListener('pointerup', terminar);
  document.addEventListener('pointercancel', function () { bloquear = true; terminar(); });

  // En fase de captura: llega antes que el on_click de React y lo anula.
  document.addEventListener('click', function (e) {
    if (bloquear && e.target.closest && e.target.closest('.icono-categoria')) {
      e.stopPropagation();
      e.preventDefault();
    }
    bloquear = false;
  }, true);

  // Sin menú contextual (Android / ratón derecho) sobre los iconos.
  document.addEventListener('contextmenu', function (e) {
    if (e.target.closest && e.target.closest('.icono-categoria')) e.preventDefault();
  });
})();
""" % _ESPERA_MS


def _css() -> str:
    reglas = [
        # Que una pulsación larga no seleccione texto ni saque el menú de
        # iOS, y que el toque no espere al doble toque.
        ".icono-categoria { -webkit-touch-callout: none; -webkit-user-select: none;"
        " user-select: none; touch-action: manipulation;"
        " -webkit-tap-highlight-color: transparent; }",
        ".centro-cat { visibility: hidden; }",
        ".porcion { transition: opacity 120ms; }",
        ".donut-categorias[data-sel] .centro-totales { visibility: hidden; }",
        ".donut-categorias[data-sel] .porcion { opacity: 0.25; }",
    ]
    for i in range(len(HUECOS)):
        sel = f'.donut-categorias[data-sel="{i}"]'
        reglas += [
            f'{sel} .centro-cat[data-i="{i}"] {{ visibility: visible; }}',
            f'{sel} .porcion[data-i="{i}"] {{ opacity: 1; }}',
            f'{sel} .icono-categoria[data-i="{i}"] {{ box-shadow: 0 0 0 0.3em var(--gray-a5); }}',
        ]
    return "\n".join(reglas)


# --- Componentes ----------------------------------------------------------


def _icono(item: rx.Var) -> rx.Component:
    return rx.box(
        rx.icon(tag=item["icono"].to(str), color=item["color"], style={"width": "58%", "height": "58%"}),
        # % justo debajo del círculo. El fondo tapa la línea que llega a
        # los iconos de la fila de arriba (que entra por debajo).
        rx.text(
            item["porcentaje"],
            position="absolute",
            top="calc(100% + 0.15em)",
            left="50%",
            transform="translateX(-50%)",
            font_size="3cqw",
            line_height="1.1",
            font_weight="600",
            white_space="nowrap",
            color="var(--gray-12)",
            background_color="var(--color-background)",
            padding_x="0.25em",
            border_radius="0.3em",
            pointer_events="none",
        ),
        class_name="icono-categoria",
        custom_attrs={"data-i": item["i"], "aria-label": item["nombre"]},
        role="button",
        on_click=AltaGastoState.abrir(item["id"]),
        position="absolute",
        left=item["left"],
        top=item["top"],
        width=f"{ICONO}%",
        height=f"{ICONO}%",
        transform="translate(-50%, -50%)",
        display="flex",
        align_items="center",
        justify_content="center",
        border_radius="50%",
        border=item["borde"],
        background_color=item["fondo"],
        opacity=item["opacidad"],
        cursor="pointer",
    )


_CENTRO = dict(
    align="center",
    spacing="1",
    position="absolute",
    top="50%",
    left="50%",
    transform="translate(-50%, -50%)",
    # Que quepa en el hueco del anillo (diámetro 2*R_INT = 42%).
    max_width=f"{2 * R_INT - 6}%",
    text_align="center",
    pointer_events="none",
)


def _centro_categoria(item: rx.Var) -> rx.Component:
    """Lo que se ve en el centro mientras se mantiene pulsado un icono.
    Hay uno por icono, ocultos; el CSS enseña el del icono pulsado."""
    return rx.vstack(
        rx.text(
            item["nombre"],
            size="3",
            weight="bold",
            color=item["color"],
            style={
                "display": "-webkit-box",
                "-webkit-line-clamp": "2",
                "-webkit-box-orient": "vertical",
                "overflow": "hidden",
                "word-break": "break-word",
            },
        ),
        rx.text(item["texto"], size="3", weight="bold"),
        class_name="centro-cat",
        custom_attrs={"data-i": item["i"]},
        **_CENTRO,
    )


def grafico_categorias() -> rx.Component:
    """Cuadrado que ocupa todo el sitio disponible (el menor de ancho y alto
    del contenedor, que debe tener `container_type="size"`)."""
    return rx.box(
        rx.el.style(_css()),
        rx.script(_JS_PULSACION),
        rx.el.svg(
            rx.foreach(
                DonutState.porciones,
                lambda p: rx.el.svg.line(
                    x1=p["x1"], y1=p["y1"], x2=p["x2"], y2=p["y2"],
                    stroke=p["color"], stroke_width="0.5", stroke_linecap="round",
                    class_name="porcion",
                    custom_attrs={"data-i": p["i"]},
                ),
            ),
            rx.foreach(
                DonutState.porciones,
                lambda p: rx.el.svg.path(
                    d=p["d"], fill=p["color"],
                    stroke="var(--color-background)", stroke_width="0.6",
                    class_name="porcion",
                    custom_attrs={"data-i": p["i"]},
                ),
            ),
            view_box="0 0 100 100",
            width="100%",
            height="100%",
            position="absolute",
            inset="0",
        ),
        rx.foreach(DonutState.iconos, _icono),
        rx.vstack(
            rx.text(DonutState.texto_ingresos, size="3", weight="bold", color_scheme="green"),
            rx.text(DonutState.texto_gastos, size="3", weight="bold", color_scheme="red"),
            class_name="centro-totales",
            **_CENTRO,
        ),
        rx.foreach(DonutState.iconos, _centro_categoria),
        class_name="donut-categorias",
        position="relative",
        width="min(100cqw, 100cqh)",
        height="min(100cqw, 100cqh)",
        flex_shrink="0",
        # Contenedor propio: el % de los iconos se mide en cqw del cuadrado
        # y así escala con el gráfico.
        container_type="size",
    )
