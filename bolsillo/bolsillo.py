import reflex as rx

# Import necesario aunque no se use nada directamente: es lo que hace que
# `reflex db makemigrations` detecte las tablas.
from bolsillo import models  # noqa: F401
from bolsillo.components.auth_guard import requiere_login
from bolsillo.pages.categories import categorias
from bolsillo.pages.index import index
from bolsillo.pages.usuarios import usuarios
from bolsillo.states.auth_state import AuthState

_META_PRIVADA = [{"name": "robots", "content": "noindex, nofollow"}]


def pagina_inicio() -> rx.Component:
    return requiere_login(index())


def pagina_categorias() -> rx.Component:
    return requiere_login(categorias())


app = rx.App(
    html_lang="es",
)

app.add_page(
    pagina_inicio,
    route="/",
    title="Bolsillo",
    meta=_META_PRIVADA,
    on_load=AuthState.restaurar_sesion,
)
app.add_page(
    pagina_categorias,
    route="/categorias",
    title="Bolsillo · Categorías",
    meta=_META_PRIVADA,
    on_load=AuthState.restaurar_sesion,
)
app.add_page(
    usuarios,
    route="/usuarios",
    title="Bolsillo · Usuarios",
    meta=_META_PRIVADA,
    # restaurar_sesion SIEMPRE primero: los siguientes eventos ya ven al
    # usuario identificado.
    on_load=[AuthState.restaurar_sesion, AuthState.cargar_usuarios],
)
