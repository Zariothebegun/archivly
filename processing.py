"""
processing.py
-------------
Processa cada ficheiro enviado:
- Deteta o tipo (imagem, vídeo, áudio, documento)
- Gera miniatura (imagens com Pillow, vídeos com ffmpeg)
- Devolve metadados básicos
"""

import os
import subprocess
import mimetypes
from PIL import Image

TAMANHO_MINIATURA = (400, 400)

EXTENSOES_IMAGEM = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic"}
EXTENSOES_VIDEO = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
EXTENSOES_AUDIO = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}


def detetar_tipo_ficheiro(nome_ficheiro: str) -> str:
    """Devolve 'imagem', 'video', 'audio' ou 'documento' consoante a extensão."""
    extensao = os.path.splitext(nome_ficheiro)[1].lower()
    if extensao in EXTENSOES_IMAGEM:
        return "imagem"
    if extensao in EXTENSOES_VIDEO:
        return "video"
    if extensao in EXTENSOES_AUDIO:
        return "audio"
    return "documento"


def gerar_miniatura_imagem(caminho_origem: str, caminho_destino: str) -> bool:
    """Gera uma miniatura para uma imagem usando Pillow. Devolve True se conseguiu."""
    try:
        with Image.open(caminho_origem) as img:
            img = img.convert("RGB")
            img.thumbnail(TAMANHO_MINIATURA)
            img.save(caminho_destino, "JPEG", quality=85)
        return True
    except Exception as erro:
        print(f"[processing] Erro ao gerar miniatura de imagem: {erro}")
        return False


def gerar_miniatura_video(caminho_origem: str, caminho_destino: str) -> bool:
    """
    Extrai um frame ao segundo 1 do vídeo com ffmpeg e usa-o como miniatura.
    Requer o binário 'ffmpeg' instalado no sistema (ver setup.sh).
    """
    try:
        comando = [
            "ffmpeg", "-y",
            "-i", caminho_origem,
            "-ss", "00:00:01.000",
            "-vframes", "1",
            "-vf", f"scale={TAMANHO_MINIATURA[0]}:-1",
            caminho_destino,
        ]
        resultado = subprocess.run(
            comando, capture_output=True, text=True, timeout=60
        )
        return resultado.returncode == 0 and os.path.exists(caminho_destino)
    except Exception as erro:
        print(f"[processing] Erro ao gerar miniatura de vídeo: {erro}")
        return False


def obter_metadados(caminho_ficheiro: str, nome_original: str) -> dict:
    """Recolhe metadados básicos do ficheiro: tamanho, mime type."""
    tamanho = os.path.getsize(caminho_ficheiro)
    mime_type, _ = mimetypes.guess_type(nome_original)
    return {
        "size_bytes": tamanho,
        "mime_type": mime_type or "application/octet-stream",
    }


def processar_ficheiro(caminho_local: str, nome_original: str, pasta_temp: str) -> dict:
    """
    Função principal: processa um ficheiro e devolve toda a informação
    necessária para o guardar (tipo, metadados, caminho da miniatura se existir).
    """
    tipo = detetar_tipo_ficheiro(nome_original)
    metadados = obter_metadados(caminho_local, nome_original)

    caminho_miniatura = None
    base_nome = os.path.splitext(os.path.basename(caminho_local))[0]

    if tipo == "imagem":
        caminho_miniatura = os.path.join(pasta_temp, f"{base_nome}_thumb.jpg")
        if not gerar_miniatura_imagem(caminho_local, caminho_miniatura):
            caminho_miniatura = None
    elif tipo == "video":
        caminho_miniatura = os.path.join(pasta_temp, f"{base_nome}_thumb.jpg")
        if not gerar_miniatura_video(caminho_local, caminho_miniatura):
            caminho_miniatura = None

    return {
        "tipo": tipo,
        "mime_type": metadados["mime_type"],
        "size_bytes": metadados["size_bytes"],
        "caminho_miniatura": caminho_miniatura,
    }
