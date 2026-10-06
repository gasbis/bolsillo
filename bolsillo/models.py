import reflex as rx
import sqlmodel
from datetime import date

class Usuario(rx.Model, table=True):
    __tablename__ = "usuarios"
    
    nombre: str
    email: str = sqlmodel.Field(unique=True, index=True)
    password_hash: str
    change_password: bool = True
    activo: bool = True
    
class Categoria(rx.Model, table=True):
    __tablename__ = "categorias"
    __table_args__ = (
        sqlmodel.UniqueConstraint(
            "id_usuario", "nombre", name="uq_nombrecategoria_usuario"
        ),
    )
    
    tipo: str #Ingreso | Gasto | Cuenta
    nombre: str
    icono: str
    id_usuario: int = sqlmodel.Field(foreign_key="usuarios.id")
    
class Transaccion(rx.Model, table=True):
    __tablename__ = "transacciones"
    
    tipo: str #Ingreso | Gasto | Cuenta
    importe: float
    fecha: date
    notas: str
    id_categoria: int = sqlmodel.Field(foreign_key="categorias.id")
    id_usuario: int = sqlmodel.Field(foreign_key="usuarios.id")