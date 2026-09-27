"""Recupera metadados de uploads que ficaram no R2 sem registo SQLite.

O Render pode recriar o disco local. Neste caso, os objetos sobrevivem no R2,
mas as linhas da tabela files desaparecem. Este módulo reconstrói essas linhas
a partir das chaves originais guardadas no bucket.
"""
import mimetypes
import os
from datetime import datetime
from urllib.parse import quote

import boto3

R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY")
R2_SECRET_KEY = os.getenv("R2_SECRET_KEY")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "archivly-files")
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "").rstrip("/")

def listar_objetos_usuario_r2(user_id: int) -> list[dict]:
    """Devolve metadados recuperáveis para os originais de um utilizador."""
    if not (R2_ACCOUNT_ID and R2_ACCESS_KEY and R2_SECRET_KEY):
        return []

    prefixo = f"users/{user_id}/originais/"
    cliente = boto3.client(
        "s3",
        endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=R2_ACCESS_KEY,
        aws_secret_access_key=R2_SECRET_KEY,
        region_name="auto",
    )
    paginator = cliente.get_paginator("list_objects_v2")
    recuperados = []

    for pagina in paginator.paginate(Bucket=R2_BUCKET_NAME, Prefix=prefixo):
        for objeto in pagina.get("Contents", []):
            chave = objeto["Key"]
            nome = chave.rsplit("/", 1)[-1]
            # Os uploads guardam UUID hexadecimal + hífen antes do nome original.
            if len(nome) > 33 and nome[32] == "-" and all(c in "0123456789abcdef" for c in nome[:32].lower()):
                nome = nome[33:]
            mime_type = mimetypes.guess_type(nome)[0] or "application/octet-stream"
            if mime_type.startswith("image/"):
                tipo = "imagem"
            elif mime_type.startswith("video/"):
                tipo = "video"
            elif mime_type.startswith("audio/"):
                tipo = "audio"
            else:
                tipo = "documento"

            url = f"{R2_PUBLIC_URL}/{quote(chave, safe='/')}" if R2_PUBLIC_URL else ""
            last_modified = objeto.get("LastModified")
            data_upload = (
                last_modified.strftime("%Y-%m-%d %H:%M:%S")
                if isinstance(last_modified, datetime)
                else None
            )
            recuperados.append({
                "original_name": nome,
                "file_type": tipo,
                "mime_type": mime_type,
                "size_bytes": int(objeto.get("Size", 0)),
                "r2_key": chave,
                "r2_url": url,
                # Sem associação guardada entre miniatura e original, usar o
                # original como capa para imagens recuperadas.
                "thumbnail_r2_key": None,
                "thumbnail_url": url if tipo == "imagem" else None,
                "uploaded_at": data_upload,
            })
    return recuperados
