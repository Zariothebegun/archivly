"""
models.py
---------
Modelos Pydantic usados para validar o que chega nos pedidos à API.
"""

from pydantic import BaseModel, EmailStr


class RegistoUtilizador(BaseModel):
    email: EmailStr
    password: str


class LoginUtilizador(BaseModel):
    email: EmailStr
    password: str


class PedidoPublicacao(BaseModel):
    site_name: str
