"""
auth.py
-------
Autenticação simples com email + password.
Sem dependências externas complicadas: password guardada com hash + salt (PBKDF2)
e sessão feita com um token JWT simples.
"""

import os
import hashlib
import secrets
import jwt  # PyJWT
from datetime import datetime, timedelta, timezone
from fastapi import Header, HTTPException
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "chave-insegura-muda-isto")
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 30


def gerar_hash_password(password: str, salt: str = None) -> tuple[str, str]:
    """Gera um hash seguro da password usando PBKDF2 com salt aleatório."""
    if salt is None:
        salt = secrets.token_hex(16)
    hash_final = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000
    ).hex()
    return hash_final, salt


def verificar_password(password: str, hash_guardado: str, salt: str) -> bool:
    """Confirma se a password introduzida corresponde ao hash guardado."""
    novo_hash, _ = gerar_hash_password(password, salt)
    return secrets.compare_digest(novo_hash, hash_guardado)


def criar_token(user_id: int, email: str) -> str:
    """Cria um token de sessão (JWT) válido por 30 dias."""
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def obter_utilizador_atual(authorization: str = Header(None)) -> dict:
    """
    Dependência do FastAPI: lê o cabeçalho "Authorization: Bearer <token>",
    valida o token e devolve os dados do utilizador autenticado.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Sessão inválida. Faz login novamente.")

    token = authorization.replace("Bearer ", "")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {"user_id": payload["user_id"], "email": payload["email"]}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Sessão expirada. Faz login novamente.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Sessão inválida. Faz login novamente.")
