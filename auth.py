"""
auth.py — autenticação por JWT e recuperação de sessão quando o SQLite é recriado.
"""
import os
import hashlib
import secrets
import jwt
import sqlite3
from datetime import datetime, timedelta, timezone
from fastapi import Header, HTTPException
from dotenv import load_dotenv
from database import get_db

load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY", "chave-insegura-muda-isto")
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 30

def gerar_hash_password(password: str, salt: str = None) -> tuple[str, str]:
    """Gera hash de password PBKDF2 com salt aleatório."""
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000).hex()
    return digest, salt

def verificar_password(password: str, hash_guardado: str, salt: str) -> bool:
    novo_hash, _ = gerar_hash_password(password, salt)
    return secrets.compare_digest(novo_hash, hash_guardado)

def criar_token(user_id: int, email: str) -> str:
    payload = {"user_id": user_id, "email": email, "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def obter_utilizador_atual(authorization: str = Header(None)) -> dict:
    """Valida o token e reconstitui o utilizador se o SQLite volátil foi recriado.

    O token só é assinado após login/registo. O id preservado mantém o fluxo de
    upload funcional após reinícios em alojamentos sem disco persistente.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Sessão inválida. Faz login novamente.")
    try:
        payload = jwt.decode(authorization[7:], SECRET_KEY, algorithms=[ALGORITHM])
        user_id, email = int(payload["user_id"]), str(payload["email"])
        if not email or "@" not in email:
            raise ValueError("email inválido")
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada. Entra novamente.")

    conn = get_db()
    try:
        user = conn.execute("SELECT id, email FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            # Restaura a identidade associada ao JWT assinado; ficheiros antigos
            # não podem ser recuperados se o alojamento apagou o SQLite.
            existente = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if existente:
                user_id = existente["id"]
            else:
                password_hash, salt = gerar_hash_password(secrets.token_urlsafe(32))
                conn.execute(
                    "INSERT INTO users (id, email, password_hash, salt) VALUES (?, ?, ?, ?)",
                    (user_id, email, password_hash, salt),
                )
                conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=401, detail="Não foi possível recuperar a sessão. Entra novamente.")
    finally:
        conn.close()
    return {"user_id": user_id, "email": email}
