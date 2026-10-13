import os

from dotenv import load_dotenv
load_dotenv()
import reflex as rx


def _resolver_db_url() -> str:
    """En Railway la cadena de conexión del Postgres propio de Bolsillo
    llega en DATABASE_URL. En local, si no está definida, se usa SQLite
    para poder desarrollar sin montar nada.

    Se fuerza el driver psycopg (v3): SQLAlchemy no lo elige por defecto
    aunque esté instalado, hay que pedirlo con `postgresql+psycopg://`.
    Railway puede dar la URL como `postgres://` o `postgresql://`; ambas
    se normalizan aquí.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        return "sqlite:///bolsillo.db"
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


config = rx.Config(
    app_name="bolsillo",
    show_built_with_reflex=False,
    db_url=_resolver_db_url(),
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
        rx.plugins.RadixThemesPlugin(),
    ],
)
