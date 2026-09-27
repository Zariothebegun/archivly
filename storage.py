"""
storage.py
----------
Guarda os ficheiros enviados pelos utilizadores.

Dois modos, escolhidos automaticamente:

1. **Cloudflare R2** (compatível com a API S3, via boto3) - usado quando as
   variáveis R2_ACCOUNT_ID / R2_ACCESS_KEY / R2_SECRET_KEY estão definidas.
   É o modo de produção: os ficheiros ficam num CDN público e os sites
   publicados no GitHub Pages conseguem linkar para eles.

2. **Disco local** - usado quando o R2 não está configurado. Os ficheiros
   ficam em `data/media/` e são servidos pela própria aplicação em `/media/...`.
   Permite que o Archivly funcione logo, sem conta na Cloudflare
   (ideal para testar e para publicação local dos sites).
"""

import os
import shutil

from dotenv import load_dotenv

load_dotenv()

R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY = os.getenv("R2_ACCESS_KEY")
R2_SECRET_KEY = os.getenv("R2_SECRET_KEY")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "archivly-files")
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "")

# Pasta usada no modo local (relativa ao projeto, ou absoluta se definido no env)
PASTA_MEDIA_LOCAL = os.getenv("LOCAL_MEDIA_DIR", os.path.join("data", "media"))

_cliente_r2 = None


def r2_configurado() -> bool:
    """True se houver credenciais R2 suficientes para usar o modo de produção."""
    return bool(R2_ACCOUNT_ID and R2_ACCESS_KEY and R2_SECRET_KEY)


def modo_armazenamento() -> str:
    """Devolve 'r2' ou 'local' - útil para mostrar no dashboard."""
    return "r2" if r2_configurado() else "local"


def _obter_cliente_r2():
    """Cria (uma vez só) o cliente boto3 apontado para o endpoint da Cloudflare R2."""
    global _cliente_r2
    if _cliente_r2 is None:
        import boto3  # importado aqui para o modo local não precisar de credenciais

        endpoint_url = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
        _cliente_r2 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=R2_ACCESS_KEY,
            aws_secret_access_key=R2_SECRET_KEY,
            region_name="auto",
        )
    return _cliente_r2


def _caminho_local_seguro(chave_destino: str) -> str:
    """
    Converte uma chave (ex: 'users/3/originais/foto.jpg') num caminho dentro
    de PASTA_MEDIA_LOCAL, impedindo fugas com '../'.
    """
    caminho = os.path.normpath(os.path.join(PASTA_MEDIA_LOCAL, chave_destino))
    raiz = os.path.abspath(PASTA_MEDIA_LOCAL)
    if not os.path.abspath(caminho).startswith(raiz + os.sep) and os.path.abspath(caminho) != raiz:
        raise ValueError(f"Chave de armazenamento inválida: {chave_destino}")
    return caminho


def enviar_ficheiro(caminho_local: str, chave_destino: str, content_type: str = None) -> str:
    """
    Guarda um ficheiro (original ou miniatura) e devolve o URL onde fica acessível.
    - Modo R2: URL público absoluto do bucket.
    - Modo local: URL relativo '/media/<chave>' (funciona em qualquer domínio/preview).
    """
    if r2_configurado():
        cliente = _obter_cliente_r2()
        extra_args = {"ContentType": content_type} if content_type else {}
        cliente.upload_file(
            Filename=caminho_local,
            Bucket=R2_BUCKET_NAME,
            Key=chave_destino,
            ExtraArgs=extra_args,
        )
        return f"{R2_PUBLIC_URL.rstrip('/')}/{chave_destino}"

    destino = _caminho_local_seguro(chave_destino)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    shutil.copyfile(caminho_local, destino)
    return f"/media/{chave_destino}"


def apagar_ficheiro(chave: str):
    """Remove um ficheiro do bucket R2 (ou do disco local). Ignora erros de 'não existe'."""
    if not chave:
        return
    try:
        if r2_configurado():
            _obter_cliente_r2().delete_object(Bucket=R2_BUCKET_NAME, Key=chave)
        else:
            caminho = _caminho_local_seguro(chave)
            if os.path.isfile(caminho):
                os.remove(caminho)
    except Exception as erro:  # nunca deixar uma limpeza rebentar com o pedido
        print(f"[storage] Não foi possível apagar '{chave}': {erro}")


def caminho_local_de(chave: str) -> str:
    """Caminho absoluto no disco para uma chave (modo local). Usado pela rota /media."""
    return _caminho_local_seguro(chave)
