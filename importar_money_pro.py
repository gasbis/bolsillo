"""Importa a Bolsillo los movimientos exportados desde Money Pro (CSV).

Uso, desde la raíz del proyecto:
    uv run python importar_money_pro.py --email tu@correo.es export1.csv [export2.csv ...]
    uv run python importar_money_pro.py --email tu@correo.es *.csv --confirmar \
        --activo Bolsa=bolsa.csv --activo Urbanitae=urbanitae.csv \
        --activo "Fondo bk=fondo_bk.csv" --activo "Préstamo Joan=joan.csv"
En Railway, con DATABASE_URL apuntando al Postgres de Bolsillo:
    railway run uv run python importar_money_pro.py --email ... *.csv --confirmar

Sin --confirmar es un ENSAYO: hace todo, valida y deshace (rollback).

Se pueden pasar varios ficheros (p.ej. un export por año): se juntan, se
ordenan por fecha y se descartan las filas repetidas exactamente iguales
(por si dos exports se solapan).

Equivalencias Money Pro -> Bolsillo:
- Gasto / Ingreso          -> gasto / ingreso (los gastos negativos, que
                              son devoluciones, se mantienen negativos).
- Transferencia de dinero  -> transferencia (Cuenta -> Cuenta de destino).
                              Si "Monto recibido" difiere de lo enviado, la
                              diferencia va como Ajuste en el destino.
- Descarga de pasivo       -> transferencia del banco a su tarjeta (el
                              export no trae la tarjeta: DESTINO_DESCARGA_PASIVO)
                              o al préstamo del coche (CUOTAS_PRESTAMO); las
                              cuotas de hipoteca son gasto en la categoría
                              Hipoteca.
- Compra de activo         -> transferencia a su cuenta de inversión (Bolsa,
                              Urbanitae...). El export general no la dice:
                              se saca del export propio de cada cuenta de
                              inversión (--activo). Las que no aparezcan en
                              ninguno van a CUENTA_INVERSIONES, con aviso.
- Venta de activo          -> transferencia desde su cuenta de inversión.
- Ajuste de saldo          -> gasto en la categoría Ajuste (negativo si el
                              saldo subió). El importe se deduce de la
                              columna Saldo, porque Money Pro invierte el
                              signo en las tarjetas.
- Saldo de apertura        -> no es un movimiento; da el saldo inicial.
- Categoría "Padre: Hija"  -> solo "Hija".
- Movimientos repartidos entre varias categorías (el export solo trae el
  total y los nombres pegados) -> la primera categoría, y en las notas
  las demás.
- Descripción              -> notas.
- Agente, N.º de cheque y Clase se ignoran.

Saldos: el saldo inicial de cada cuenta se deduce de la columna Saldo
(saldo de la cuenta tras cada movimiento) y luego se comprueba fila a
fila. Un descuadre que se corrige solo en una fila posterior es una
diferencia de orden entre movimientos del mismo minuto (solo aviso); uno
que llega hasta la última fila de la cuenta aborta la importación. Al
final se comprueba también con la función de saldo de la app
(transacciones_db.saldo_cuenta).

Las tarjetas: Money Pro muestra el crédito disponible (límite - deuda);
Bolsillo muestra lo que se debe, en negativo (LIMITE_CREDITO).
"""

import argparse
import csv
import glob
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

import reflex as rx
import sqlmodel

from bolsillo.auth_db import obtener_usuario_por_email
from bolsillo.models import (
    TIPO_GASTO,
    TIPO_INGRESO,
    TIPO_TRANSFERENCIA,
    Categoria,
    Cuenta,
    Transaccion,
)
from bolsillo.transacciones_db import categoria_ajuste, obtener_o_crear_categoria, saldo_cuenta

# --- Configuración propia de los datos de Gabriel ---------------------------

# Destino de las "Compras de activo" y origen de las "Ventas de activo".
CUENTA_INVERSIONES = "Inversiones"

# Cuenta que paga cada tarjeta en las "Descargas de pasivo".
DESTINO_DESCARGA_PASIVO = {
    "ING": "Tarj ING",
    "Bankinter": "Tarj Bankinter",
}

# Las cuotas de la hipoteca también salen como "Descarga de pasivo" desde
# ING, pero hasta abril de 2020 con categoría "Deudas: Hipoteca" y después
# sin ella. Se reconocen por el importe de la cuota y se anotan como gasto
# en la categoría Hipoteca (la deuda no es una cuenta en Bolsillo).
CATEGORIA_HIPOTECA = "Hipoteca"
CUOTAS_HIPOTECA = {
    "ING": {Decimal(x) for x in ("325.77", "325.98", "325.34", "325.46", "325.40",
                                 "325.41")},
}

# Cuotas del préstamo del coche: también "Descarga de pasivo" desde ING,
# de 271 € al mes desde mayo de 2021, más un último pago de 805 € el
# 10/01/2025 que salda la deuda. Son transferencias a la cuenta del préstamo.
CUENTA_PRESTAMO_COCHE = "Préstamo coche"
CUOTAS_PRESTAMO = {
    "ING": ({Decimal("271.00")}, CUENTA_PRESTAMO_COCHE),
}
# Pagos sueltos a un préstamo. Clave: (fecha dd/mm/aaaa, cuenta, importe).
DESCARGAS_A_PRESTAMO = {
    ("10/01/2025", "ING", Decimal("805.00")): CUENTA_PRESTAMO_COCHE,
}

# Límite de las tarjetas: se resta del saldo para que en Bolsillo la
# tarjeta muestre la deuda (negativa) en vez del crédito disponible.
LIMITE_CREDITO = {
    "Tarj ING": Decimal("3000.00"),
    "Tarj Bankinter": Decimal("3000.00"),
}

# Préstamos: Money Pro muestra la deuda en positivo; Bolsillo, en negativo.
CUENTAS_DEUDA = {"Préstamo coche"}

# Cuentas de inversión. El export general no dice a cuál de ellas va cada
# "Compra/Venta de activo": hace falta además el export de cada una por
# separado (opción --activo Cuenta=fichero.csv), cuya columna Saldo es el
# de esa cuenta. Las que no tengan fichero no se pueden comprobar.
# "Préstamo Joan" es dinero prestado por Gabriel (lo que le deben): en
# Money Pro se anotó como compra/venta de activo.
CUENTAS_INVERSION = {"Bolsa", "Urbanitae", "Fondo bk", "Coche", "Préstamo Joan",
                     CUENTA_INVERSIONES}

# Compras/ventas de activo de cuentas sin export propio. Clave: (fecha
# dd/mm/aaaa, cuenta de origen, importe).
ACTIVOS_MANUALES = {
    ("28/02/2021", "Ahorro ING", Decimal("20090.00")): "Coche",
}

# Categoría para los gastos/ingresos que en Money Pro no tienen.
SIN_CATEGORIA = "Sin categoría"

# Icono (Lucide) de las cuentas que haya que crear; por defecto "landmark".
ICONOS_CUENTA = {
    "Cartera": "wallet",
    "Cajón": "wallet",
    "Tarj ING": "wallet-cards",
    "Tarj Bankinter": "wallet-cards",
    "Ahorro ING": "piggy-bank",
    "Coche": "wallet",
    "Préstamo Joan": "hand_coins",
    "Trade Republic": "piggy-bank",
    CUENTA_INVERSIONES: "piggy-bank",
}

ZONA = ZoneInfo("Europe/Madrid")
CERO = Decimal("0.00")
COLUMNAS = {"Fecha", "Cantidad", "Cuenta", "Cuenta de destino", "Saldo",
            "Categoría", "Descripción", "Tipo de transacción"}

# --- Lectura del CSV ---------------------------------------------------------


def importe(texto: str) -> Decimal | None:
    """'25.238,73 €' -> Decimal('25238.73'); '' -> None."""
    limpio = (texto.replace("€", "").replace("\xa0", "").replace(" ", "")
              .replace(".", "").replace(",", "."))
    if not limpio:
        return None
    try:
        return Decimal(limpio).quantize(CERO)
    except InvalidOperation:
        raise ValueError(f"Importe no válido: {texto!r}") from None


def fecha_hora(texto: str) -> datetime:
    """'4/8/26, 8:42' -> datetime con zona Europe/Madrid."""
    return datetime.strptime(texto.strip(), "%d/%m/%y, %H:%M").replace(tzinfo=ZONA)


@dataclass
class Movimiento:
    origen: str          # "fichero.csv:línea" para los mensajes de error
    momento: datetime
    tipo_mp: str         # tipo de transacción en Money Pro
    tipo: str | None     # tipo en Bolsillo (None = saldo de apertura)
    cuenta: str          # cuenta del movimiento en Bolsillo (origen si es transferencia)
    importe: Decimal
    cuenta_mp: str       # columna Cuenta de Money Pro, a la que se refiere saldo_mp
    saldo_mp: Decimal | None  # saldo de cuenta_mp tras el movimiento (None = no comprobar)
    destino: str | None = None
    categoria: tuple[str, str] | None = None   # (tipo, nombre); None en gasto = Ajuste
    notas: str = ""
    efectos: dict[str, Decimal] = field(default_factory=dict)
    # Saldos de otras cuentas tras el movimiento (los de las cuentas de
    # inversión, sacados de su export propio).
    controles: list[tuple[str, Decimal]] = field(default_factory=list)


# (Fecha, Cantidad, Cuenta, Tipo) tal cual vienen en el CSV -> lista de
# (cuenta de inversión, saldo de esa cuenta tras el movimiento, cambio de
# ese saldo). Lista porque podría haber dos filas idénticas.
Activos = dict[tuple[str, str, str, str], list[tuple[str, Decimal, Decimal]]]


def clave_fila(fila: dict) -> tuple[str, str, str, str]:
    return (fila["Fecha"].strip(), fila["Cantidad"].strip(), fila["Cuenta"].strip(),
            fila["Tipo de transacción"].strip())


def leer_activos(ficheros: dict[str, Path]) -> Activos:
    """Lee el export propio de cada cuenta de inversión y apunta, para cada
    compra o venta, a qué cuenta fue y cuánto cambió su saldo."""
    activos: Activos = defaultdict(list)
    for cuenta, fichero in ficheros.items():
        with fichero.open(encoding="utf-8-sig", newline="") as f:
            anterior = CERO
            for fila in csv.DictReader(f, delimiter=";"):
                saldo = importe(fila.get("Saldo") or "")
                if saldo is None:
                    continue
                if fila["Tipo de transacción"].strip() in ("Compra de activo", "Venta de activo"):
                    activos[clave_fila(fila)].append((cuenta, saldo, saldo - anterior))
                anterior = saldo
    return activos


def hoja(categoria: str) -> str:
    """'Casa: Otros' -> 'Otros'."""
    return categoria.split(":")[-1].strip()


def segmentar(texto: str, conocidas: set[str]) -> list[str] | None:
    """Money Pro exporta los movimientos repartidos entre varias
    categorías juntando sus nombres con espacios ('Alimentos Regalos',
    'Gastos en servicios: Teléfono Gastos en servicios: Electricidad Ropa').
    Devuelve las partes (>= 2) si `texto` se puede trocear en categorías
    conocidas; None si es una categoría normal."""
    palabras = texto.split(" ")
    n = len(palabras)
    mejor: dict[int, list[str]] = {0: []}
    for i in range(n):
        if i not in mejor:
            continue
        for j in range(i + 1, n + 1):
            trozo = " ".join(palabras[i:j])
            if trozo in conocidas and trozo != texto and j not in mejor:
                mejor[j] = mejor[i] + [trozo]
    partes = mejor.get(n)
    return partes if partes and len(partes) >= 2 else None


def convertir(fila: dict, origen: str, conocidas: set[str], activos: Activos,
              sin_asignar: list[str]) -> list[Movimiento]:
    tipo_mp = fila["Tipo de transacción"].strip()
    cuenta = fila["Cuenta"].strip()
    cantidad = importe(fila["Cantidad"])
    saldo = importe(fila["Saldo"])
    if cantidad is None or saldo is None or not cuenta:
        raise ValueError(f"{origen}: faltan cantidad, saldo o cuenta")
    notas = fila["Descripción"].strip()
    categoria_mp = fila["Categoría"].strip()
    nombre_cat = hoja(categoria_mp) if categoria_mp else ""
    partes = segmentar(categoria_mp, conocidas) if categoria_mp else None
    if partes:
        hojas = list(dict.fromkeys(hoja(p) for p in partes))
        nombre_cat = hojas[0]
        if len(hojas) > 1:
            nota = f"[Repartido en Money Pro: {' + '.join(hojas)}]"
            notas = f"{notas} {nota}".strip()

    m = Movimiento(origen, fecha_hora(fila["Fecha"]), tipo_mp, None, cuenta, cantidad,
                   cuenta, saldo, notas=notas)
    extra: list[Movimiento] = []

    if tipo_mp == "Descarga de pasivo" and not nombre_cat:
        if cantidad in CUOTAS_HIPOTECA.get(cuenta, ()):
            nombre_cat = CATEGORIA_HIPOTECA
    if tipo_mp in ("Gasto", "Ingreso") or (tipo_mp == "Descarga de pasivo" and nombre_cat):
        # Una descarga de pasivo con categoría (Deudas: Hipoteca) paga una
        # deuda que no es una cuenta: es un gasto más.
        m.tipo = TIPO_INGRESO if tipo_mp == "Ingreso" else TIPO_GASTO
        if m.tipo == TIPO_INGRESO and cantidad < 0:
            raise ValueError(f"{origen}: ingreso negativo ({cantidad}); revisar a mano")
        m.categoria = (m.tipo, nombre_cat or SIN_CATEGORIA)
        m.efectos = {cuenta: -cantidad if m.tipo == TIPO_GASTO else cantidad}
    elif tipo_mp in ("Transferencia de dinero", "Descarga de pasivo", "Compra de activo",
                     "Venta de activo"):
        recibido = cantidad
        if tipo_mp == "Transferencia de dinero":
            destino = fila["Cuenta de destino"].strip()
            recibido = importe(fila.get("Monto recibido") or "") or cantidad
        elif tipo_mp == "Descarga de pasivo":
            cuotas, prestamo = CUOTAS_PRESTAMO.get(cuenta, (set(), ""))
            clave = (f"{m.momento:%d/%m/%Y}", cuenta, cantidad)
            if cantidad in cuotas:
                destino = prestamo
            else:
                destino = (DESCARGAS_A_PRESTAMO.get(clave)
                           or DESTINO_DESCARGA_PASIVO.get(cuenta, ""))
            if not destino:
                raise ValueError(
                    f"{origen}: descarga de pasivo desde {cuenta!r}, que no está en "
                    "DESTINO_DESCARGA_PASIVO; añade a qué tarjeta corresponde"
                )
        else:
            asignados = activos.get(clave_fila(fila))
            manual = ACTIVOS_MANUALES.get((f"{m.momento:%d/%m/%Y}", cuenta, cantidad))
            if asignados:
                activo, saldo_activo, cambio_activo = asignados.pop(0)
            elif manual:
                activo, saldo_activo, cambio_activo = manual, None, None
            else:
                activo, saldo_activo, cambio_activo = CUENTA_INVERSIONES, None, None
                sin_asignar.append(f"{fila['Fecha']} {tipo_mp} {cantidad} {notas}".strip())
            if tipo_mp == "Compra de activo":
                destino = activo
            else:  # Venta de activo: el dinero vuelve de la inversión a la cuenta
                m.cuenta, destino = activo, cuenta
        if tipo_mp in ("Compra de activo", "Venta de activo") and cantidad < 0:
            # Compra negativa (p.ej. un spin-off que ingresa efectivo): va
            # en sentido contrario.
            m.cuenta, destino = destino, m.cuenta
            cantidad = recibido = m.importe = -cantidad
        if not destino or destino == m.cuenta or cantidad <= 0:
            raise ValueError(f"{origen}: transferencia no válida ({m.cuenta} -> {destino}, {cantidad})")
        m.tipo, m.destino = TIPO_TRANSFERENCIA, destino
        m.efectos = {m.cuenta: -cantidad, destino: cantidad}
        if tipo_mp in ("Compra de activo", "Venta de activo") and saldo_activo is not None:
            ultimo = m
            sobra = cambio_activo - m.efectos[activo]
            if sobra:
                # El saldo de la inversión no cambió lo mismo que el dinero
                # que salió (pasa alguna vez en Money Pro): la diferencia va
                # como ajuste en la inversión.
                ultimo = Movimiento(
                    origen, m.momento, "Diferencia en inversión", TIPO_GASTO, activo,
                    -sobra, activo, None, notas=f"Diferencia {tipo_mp.lower()} {notas}".strip(),
                    efectos={activo: sobra},
                )
                extra.append(ultimo)
            ultimo.controles.append((activo, saldo_activo))
        if recibido != cantidad:
            # Llegó una cantidad distinta de la enviada (comisión, redondeo):
            # la diferencia se anota como ajuste en la cuenta de destino.
            extra.append(Movimiento(
                origen, m.momento, "Diferencia en transferencia", TIPO_GASTO, destino,
                cantidad - recibido, destino, None,
                notas=f"Diferencia transferencia desde {cuenta}",
                efectos={destino: recibido - cantidad},
            ))
    elif tipo_mp == "Ajuste de saldo":
        # En Money Pro la cantidad es lo que cambia el saldo (+ sube, - baja).
        m.tipo, m.importe = TIPO_GASTO, -cantidad
        m.notas = m.notas or "Ajuste de saldo"
        m.efectos = {cuenta: cantidad}
    elif tipo_mp == "Saldo de apertura":
        m.efectos = {}
    else:
        raise ValueError(f"{origen}: tipo de transacción desconocido {tipo_mp!r}")
    return [m, *extra]


def leer(ficheros: list[Path], activos: Activos | None = None) -> list[Movimiento]:
    activos = activos or {}
    sin_asignar: list[str] = []
    filas, vistas, repetidas = [], set(), 0
    for fichero in ficheros:
        with fichero.open(encoding="utf-8-sig", newline="") as f:
            lector = csv.DictReader(f, delimiter=";")
            faltan = COLUMNAS - set(lector.fieldnames or [])
            if faltan:
                raise ValueError(f"{fichero.name}: faltan columnas {sorted(faltan)}")
            for n, fila in enumerate(lector, start=2):
                if not any((v or "").strip() for v in fila.values() if isinstance(v, str)):
                    continue
                clave = tuple((fila.get(c) or "").strip() for c in sorted(COLUMNAS))
                if clave in vistas:
                    repetidas += 1
                    continue
                vistas.add(clave)
                filas.append((fila, f"{fichero.name}:{n}"))
    if repetidas:
        print(f"Aviso: {repetidas} filas repetidas entre ficheros, descartadas.")
    # Categorías "simples": las que no son a su vez varias pegadas. Se
    # construyen de las más cortas a las más largas.
    conocidas: set[str] = set()
    todas = {f["Categoría"].strip() for f, _ in filas if f["Categoría"].strip()}
    for cat in sorted(todas, key=lambda t: len(t.split(" "))):
        if segmentar(cat, conocidas) is None:
            conocidas.add(cat)
    movimientos = [m for fila, origen in filas
                   for m in convertir(fila, origen, conocidas, activos, sin_asignar)]
    if sin_asignar:
        print(f"Aviso: {len(sin_asignar)} compras/ventas de activo no aparecen en ningún "
              f"export de inversión (--activo); van a '{CUENTA_INVERSIONES}':")
        for linea in sin_asignar:
            print("   ", linea)
    # Orden estable: a igual minuto se respeta el orden de los ficheros.
    movimientos.sort(key=lambda m: m.momento)
    return movimientos


# --- Cálculo de saldos iniciales ---------------------------------------------


def calcular_saldos(movs: list[Movimiento], sin_comprobar: set[str]
                    ) -> tuple[dict[str, Decimal], dict[str, Decimal], list[str]]:
    """Devuelve (saldo inicial, saldo final, avisos) por cuenta, ya en el
    criterio de Bolsillo (tarjetas y préstamos en negativo). Fija además
    el importe de los ajustes a partir de la columna Saldo. Aborta si
    alguna cuenta comprobable no cuadra al final. `sin_comprobar`: cuentas
    cuyo saldo no se puede comprobar."""
    acumulado: dict[str, Decimal] = defaultdict(lambda: CERO)
    inicial: dict[str, Decimal] = {}
    pendientes: dict[str, list[str]] = defaultdict(list)
    avisos: list[str] = []

    def real(cuenta: str, saldo_mp: Decimal) -> Decimal:
        if cuenta in CUENTAS_DEUDA:
            return -saldo_mp
        return saldo_mp - LIMITE_CREDITO.get(cuenta, CERO)

    for m in movs:
        c = m.cuenta_mp
        if (m.tipo_mp == "Ajuste de saldo" and m.saldo_mp is not None
                and c not in sin_comprobar and c in inicial):
            delta = real(c, m.saldo_mp) - inicial[c] - acumulado[c]
            if abs(delta) != abs(m.importe):
                avisos.append(f"{m.origen}: ajuste de {-m.importe} en {c}, pero el saldo "
                              f"cambia {delta}; se usa {delta}")
            m.importe, m.efectos = -delta, {c: delta}
        for cuenta, d in m.efectos.items():
            acumulado[cuenta] += d
        controles = list(m.controles)
        if m.saldo_mp is not None:
            controles.insert(0, (c, m.saldo_mp))
        for c, saldo_mp in controles:
            if c not in inicial:
                inicial[c] = real(c, saldo_mp) - acumulado[c]
                continue
            if c in sin_comprobar:
                continue
            calculado = inicial[c] + acumulado[c]
            if calculado != real(c, saldo_mp):
                pendientes[c].append(
                    f"  {m.origen} ({m.momento:%d/%m/%y %H:%M}, {c}, {m.tipo_mp} {m.importe}): "
                    f"Money Pro {real(c, saldo_mp)}, calculado {calculado} "
                    f"(diferencia {real(c, saldo_mp) - calculado})"
                )
            elif pendientes[c]:
                avisos.append(f"Descuadre temporal en {c} (orden dentro del mismo minuto):")
                avisos.extend(pendientes.pop(c))

    errores = [linea for lineas in pendientes.values() for linea in lineas]
    if errores:
        raise ValueError("La columna Saldo no cuadra (hasta el final) en:\n" + "\n".join(errores[:40]))
    for cuenta in acumulado:  # cuentas que solo reciben (p.ej. Inversiones)
        inicial.setdefault(cuenta, CERO)
    final = {c: inicial[c] + acumulado[c] for c in inicial}
    return inicial, final, avisos


# --- Escritura en la base de datos -------------------------------------------


def importar(email: str, ficheros: list[Path], ficheros_activos: dict[str, Path],
             confirmar: bool, reemplazar: bool, archivar_sobrantes: bool) -> None:
    usuario = obtener_usuario_por_email(email.lower())
    if usuario is None:
        sys.exit(f"No existe el usuario {email}.")
    movs = leer(ficheros, leer_activos(ficheros_activos))
    sin_comprobar = CUENTAS_INVERSION - set(ficheros_activos)
    if not movs:
        sys.exit("No hay movimientos que importar.")
    inicial, final, avisos = calcular_saldos(movs, sin_comprobar)
    for aviso in avisos:
        print("Aviso:", aviso)
    uid = usuario.id

    with rx.session() as session:
        previas = session.exec(
            sqlmodel.select(Transaccion).where(Transaccion.id_usuario == uid)
        ).all()
        if previas and not reemplazar:
            sys.exit(f"{email} ya tiene {len(previas)} movimientos. Usa --reemplazar para "
                     "borrarlos antes de importar.")
        for t in previas:
            session.delete(t)
        session.flush()

        # Cuentas: se reutilizan por nombre o se crean.
        cuentas = {c.nombre: c for c in session.exec(
            sqlmodel.select(Cuenta).where(Cuenta.id_usuario == uid)).all()}
        orden = max((c.orden for c in cuentas.values()), default=-1)
        for nombre in sorted(inicial, key=lambda n: (n == CUENTA_INVERSIONES, n)):
            cuenta = cuentas.get(nombre)
            if cuenta is None:
                orden += 1
                cuenta = Cuenta(id_usuario=uid, nombre=nombre,
                                icono=ICONOS_CUENTA.get(nombre, "landmark"), orden=orden)
                cuentas[nombre] = cuenta
            cuenta.saldo_inicial = inicial[nombre]
            cuenta.activa = True
            session.add(cuenta)
        session.flush()

        # Categorías.
        cats: dict[tuple[str, str], Categoria] = {}
        for m in movs:
            if m.categoria and m.categoria not in cats:
                cats[m.categoria] = obtener_o_crear_categoria(session, uid, *m.categoria)
        ajuste = categoria_ajuste(session, uid)

        # Movimientos. `creado_en` lleva la hora de Money Pro (en UTC) más
        # unos microsegundos según la posición, para que los de un mismo
        # minuto conserven su orden.
        n = 0
        for i, m in enumerate(movs):
            if m.tipo is None:
                continue
            if m.tipo == TIPO_TRANSFERENCIA:
                id_cat = None
            else:
                id_cat = (cats[m.categoria] if m.categoria else ajuste).id
            session.add(Transaccion(
                id_usuario=uid,
                tipo=m.tipo,
                fecha=m.momento.date(),
                importe=m.importe,
                id_cuenta=cuentas[m.cuenta].id,
                id_categoria=id_cat,
                id_cuenta_destino=cuentas[m.destino].id if m.destino else None,
                notas=m.notas,
                creado_en=m.momento.astimezone(timezone.utc) + timedelta(microseconds=i),
            ))
            n += 1
        session.flush()

        if archivar_sobrantes:
            usadas_cat = {c.id for c in cats.values()} | {ajuste.id}
            for c in session.exec(sqlmodel.select(Categoria).where(Categoria.id_usuario == uid)).all():
                if c.id not in usadas_cat and c.activa:
                    c.activa = False
                    session.add(c)
            for c in cuentas.values():
                if c.nombre not in inicial and c.activa:
                    c.activa = False
                    session.add(c)
            session.flush()

        # Comprobación final con la misma función que usará la app.
        print(f"\n{'Cuenta':<18}{'Saldo inicial':>15}{'Saldo final':>15}  Money Pro")
        descuadres = 0
        for nombre in sorted(inicial):
            calculado = saldo_cuenta(session, uid, cuentas[nombre].id)
            ok = calculado == final[nombre]
            descuadres += not ok
            estado = "OK" if ok else f"DESCUADRE {final[nombre]}"
            if ok and nombre in sin_comprobar:
                estado = "sin comprobar"
            print(f"{nombre:<18}{inicial[nombre]:>15}{calculado:>15}  {estado}")

        por_tipo = defaultdict(int)
        for m in movs:
            por_tipo[m.tipo_mp] += 1
        print(f"\n{len(movs)} filas leídas ({movs[0].momento:%d/%m/%Y} - "
              f"{movs[-1].momento:%d/%m/%Y}); {n} movimientos creados.")
        for tipo, cuenta_n in sorted(por_tipo.items(), key=lambda x: -x[1]):
            print(f"  {tipo:<28}{cuenta_n:>5}")
        print(f"{len(cats)} categorías usadas, {len(inicial)} cuentas.")
        repartidos = [m for m in movs if "[Repartido en Money Pro" in m.notas]
        sin_cat = [m for m in movs if m.categoria and m.categoria[1] == SIN_CATEGORIA]
        if repartidos:
            print(f"\n{len(repartidos)} movimientos repartidos entre varias categorías "
                  "(asignados a la primera; revísalos si quieres):")
            for m in repartidos:
                print(f"  {m.momento:%d/%m/%Y} {m.cuenta:<14}{m.importe:>10}  "
                      f"{m.categoria[1]:<14}{m.notas}")
        if sin_cat:
            print(f"\n{len(sin_cat)} movimientos sin categoría en Money Pro "
                  f"(van a '{SIN_CATEGORIA}'):")
            for m in sin_cat:
                print(f"  {m.momento:%d/%m/%Y} {m.cuenta:<14}{m.importe:>10}  {m.tipo}  {m.notas}")

        if descuadres:
            session.rollback()
            sys.exit(f"\n{descuadres} cuentas no cuadran: no se ha guardado nada.")
        if confirmar:
            session.commit()
            print("\nImportación GUARDADA.")
        else:
            session.rollback()
            print("\nENSAYO: no se ha guardado nada. Repite con --confirmar para guardar.")


def main() -> None:
    p = argparse.ArgumentParser(description="Importa exports CSV de Money Pro a Bolsillo.")
    p.add_argument("ficheros", nargs="+", type=Path,
                   help="exports generales de Money Pro; admite comodines (exports/*.csv)")
    p.add_argument("--email", required=True, help="usuario de Bolsillo que recibe los datos")
    p.add_argument("--activo", action="append", default=[], metavar="CUENTA=FICHERO",
                   help="export de Money Pro de una sola cuenta de inversión "
                        "(p.ej. Bolsa=bolsa.csv); se puede repetir")
    p.add_argument("--confirmar", action="store_true", help="guardar (sin esto es un ensayo)")
    p.add_argument("--reemplazar", action="store_true",
                   help="borrar antes los movimientos que ya tenga el usuario")
    p.add_argument("--archivar-sobrantes", action="store_true",
                   help="archivar las categorías y cuentas por defecto que no se usen")
    a = p.parse_args()
    # PowerShell (Windows) no expande comodines como *.csv: se hace aquí.
    ficheros: list[Path] = []
    for patron in a.ficheros:
        encontrados = sorted(glob.glob(str(patron)))
        if not encontrados:
            p.error(f"no se encuentra ningún fichero: {patron}")
        ficheros.extend(Path(f) for f in encontrados)
    activos: dict[str, Path] = {}
    for opcion in a.activo:
        cuenta, _, fichero = opcion.partition("=")
        if not cuenta or not fichero:
            p.error(f"--activo {opcion!r}: el formato es CUENTA=FICHERO")
        if not Path(fichero).is_file():
            p.error(f"--activo {opcion!r}: no se encuentra el fichero {fichero}")
        activos[cuenta.strip()] = Path(fichero)
    try:
        importar(a.email, ficheros, activos, a.confirmar, a.reemplazar, a.archivar_sobrantes)
    except ValueError as e:
        sys.exit(f"Error: {e}")


if __name__ == "__main__":
    main()