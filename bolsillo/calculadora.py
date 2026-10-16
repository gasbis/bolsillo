"""Teclado numérico del alta de gastos: qué pasa al pulsar cada tecla y
cuánto vale lo que se ve escrito en el importe.

Funciones puras (sin Reflex ni base de datos) para poder probarlas
sueltas, igual que periodos.py.

El campo del importe guarda una EXPRESIÓN tal y como se ve en pantalla,
p.ej. "12,50+3×2". Al aceptar se guarda su valor (`evaluar`), que el
formulario muestra en todo momento debajo del campo; la tecla "=" solo
sustituye la expresión por su resultado. Reglas:

- Coma decimal (formato español) y como mucho 2 decimales por número.
- × y ÷ antes que + y − (como en cualquier calculadora de móvil).
- Un "-" al principio hace el importe negativo (devoluciones).
- Un operador al final se ignora: "12+" vale 12.
"""

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext

CERO = Decimal("0.00")
# Límite de NUMERIC(12, 2).
MAXIMO = Decimal("9999999999.99")
LARGO_MAXIMO = 30

SUMA, RESTA, POR, ENTRE = "+", "-", "×", "÷"
OPERADORES = SUMA + RESTA + POR + ENTRE
COMA = ","
BORRAR = "<"  # tecla ⌫
LIMPIAR = "C"
IGUAL = "="

# Equivalencias al escribir con teclado físico.
_EQUIVALENTES = {"*": POR, "x": POR, "X": POR, "/": ENTRE, ":": ENTRE, "−": RESTA, ".": COMA}
_PERMITIDOS = set("0123456789" + COMA + OPERADORES)
_ULTIMO_NUMERO = re.compile(r"[0-9,]*$")
_TOKEN = re.compile(r"(\d+(?:,\d*)?|,\d+)|([+\-×÷])")


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


def formatear(valor: Decimal) -> str:
    """Decimal → texto para el campo: '15,50', '-3,00' (sin miles)."""
    return f"{valor:.2f}".replace(".", ",")


def _ultimo_numero(expresion: str) -> str:
    return _ULTIMO_NUMERO.search(expresion).group(0)


def limpiar(texto: str) -> str:
    """Lo escrito a mano (teclado físico): pasa '*', '/', '.' a sus
    equivalentes y quita cualquier otro carácter."""
    res = "".join(_EQUIVALENTES.get(c, c) for c in (texto or ""))
    return "".join(c for c in res if c in _PERMITIDOS)[:LARGO_MAXIMO]


def pulsar(expresion: str, tecla: str) -> str:
    """Nueva expresión tras pulsar `tecla` en el teclado numérico."""
    expresion = expresion or ""
    if tecla == LIMPIAR:
        return ""
    if tecla == BORRAR:
        return expresion[:-1]
    if tecla == IGUAL:
        valor = evaluar(expresion)
        return formatear(valor) if valor is not None else expresion
    if len(expresion) >= LARGO_MAXIMO:
        return expresion

    if tecla in OPERADORES:
        if not expresion:
            # Solo se puede empezar por "-" (devolución).
            return RESTA if tecla == RESTA else ""
        if expresion == RESTA:
            return expresion
        if expresion[-1] == COMA:
            expresion = expresion[:-1]
        if expresion[-1] in OPERADORES:
            # Cambiar de operador: el último pulsado sustituye al anterior.
            return expresion[:-1] + tecla
        return expresion + tecla

    numero = _ultimo_numero(expresion)
    if tecla == COMA:
        if COMA in numero:
            return expresion
        return expresion + ("0," if numero == "" else COMA)

    if tecla.isdigit() and len(tecla) == 1:
        if COMA in numero and len(numero.split(COMA)[1]) >= 2:
            return expresion  # céntimos: como mucho 2 decimales
        if numero == "0":
            return expresion[:-1] + tecla  # sin ceros a la izquierda
        return expresion + tecla

    return expresion


def tiene_operacion(expresion: str) -> bool:
    """True si hay alguna operación (para enseñar el resultado debajo)."""
    return any(c in OPERADORES for c in (expresion or "")[1:])


def evaluar(expresion: str) -> Decimal | None:
    """Valor de la expresión redondeado a céntimos, o None si no se puede
    calcular (vacía, mal formada, división entre 0 o desbordamiento)."""
    texto = limpiar(expresion)
    if not texto:
        return None

    # Separar en números y operadores; cualquier resto = mal formada.
    tokens: list[str] = []
    pos = 0
    while pos < len(texto):
        m = _TOKEN.match(texto, pos)
        if m is None:
            return None
        tokens.append(m.group(0))
        pos = m.end()

    while tokens and tokens[-1] in OPERADORES:
        tokens.pop()  # "12+" vale 12
    signo = Decimal(1)
    if tokens and tokens[0] in (SUMA, RESTA):
        signo = Decimal(-1) if tokens.pop(0) == RESTA else signo
    if not tokens:
        return None

    # Tienen que alternar número, operador, número...
    numeros = tokens[0::2]
    operadores = tokens[1::2]
    if any(t in OPERADORES for t in numeros) or any(t not in OPERADORES for t in operadores):
        return None
    valores = [leer_importe(n) for n in numeros]
    if any(v is None for v in valores):
        return None

    try:
        with localcontext() as ctx:
            ctx.prec = 28
            total = Decimal(0)
            termino = signo * valores[0]
            for op, valor in zip(operadores, valores[1:]):
                if op == POR:
                    termino *= valor
                elif op == ENTRE:
                    if valor == 0:
                        return None
                    termino /= valor
                elif op == SUMA:
                    total += termino
                    termino = valor
                else:
                    total += termino
                    termino = -valor
            total += termino
            return total.quantize(CERO, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None
