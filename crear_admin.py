"""Crea un usuario desde la línea de comandos (pensado para el primer
administrador, cuando la base de datos está vacía y nadie puede entrar
aún a la página /usuarios).

Uso, desde la raíz del proyecto:
    uv run python crear_admin.py
En Railway, con DATABASE_URL apuntando al Postgres de Bolsillo:
    railway run uv run python crear_admin.py

El usuario se crea con `debe_cambiar_password=True`: en el primer
inicio de sesión se le pide una contraseña nueva.
"""

from getpass import getpass

from bolsillo.auth_db import crear_usuario, email_existe
from bolsillo.states.auth_state import ADMIN_EMAIL, LONGITUD_MINIMA_PASSWORD


def main() -> None:
    email = (input(f"Correo [{ADMIN_EMAIL}]: ").strip() or ADMIN_EMAIL).lower()
    if email_existe(email):
        print(f"Ya existe un usuario con el correo {email}.")
        return
    nombre = input("Nombre: ").strip() or email
    password = getpass("Contraseña inicial: ")
    if len(password) < LONGITUD_MINIMA_PASSWORD:
        print(f"La contraseña debe tener al menos {LONGITUD_MINIMA_PASSWORD} caracteres.")
        return
    if crear_usuario(email, nombre, password):
        print(f"Usuario {email} creado, con sus categorías y cuentas por defecto.")
    else:
        print("No se ha podido crear el usuario.")


if __name__ == "__main__":
    main()
