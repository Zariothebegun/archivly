"""
storage.py
----------
Comunicação com o Cloudflare R2 (compatível com a API S3), usando boto3.
Guarda os ficheiros originais e as miniaturas geradas.
"""

import os
import boto3
from dotenv import load_dotenv

load_dotenv()

R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY")
R2_SECRET_KEY = os.getenv("R2_SECRET_KEY")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "archivly-files")
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "")


def _obter_cliente_r2():
    """Cria o cliente boto3 apontado para o endpoint da Cloudflare R2."""
    endpoint_url = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=R2_ACCESS_KEY,
        aws_secret_access_key=R2_SECRET_KEY,
        region_name="auto",
    )


def enviar_ficheiro(caminho_local: str, chave_destino: str, content_type: str = None) -> str:
    """
    Envia um ficheiro do disco local para o bucket R2.
    Devolve o URL público final do ficheiro.
    """
    cliente = _obter_cliente_r2()
    extra_args = {"ContentType": content_type} if content_type else {}

    cliente.upload_file(
        Filename=caminho_local,
        Bucket=R2_BUCKET_NAME,
        Key=chave_destino,
        ExtraArgs=extra_args,
    )

    return f"{R2_PUBLIC_URL.rstrip('/')}/{chave_destino}"


def apagar_ficheiro(chave: str):
    """Remove um ficheiro do bucket (usado em limpeza de erros, por exemplo)."""
    cliente = _obter_cliente_r2()
    cliente.delete_object(Bucket=R2_BUCKET_NAME, Key=chave)
