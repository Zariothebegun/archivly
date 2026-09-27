#!/bin/bash
# ============================================================
# setup.sh - Instala tudo o que o Archivly precisa para correr:
# Hugo (gerador de sites), ffmpeg (miniaturas de vídeo) e as
# dependências Python.
# Testado em Ubuntu/Debian (é o que a maioria dos serviços gratuitos usa).
# ============================================================

set -e  # para o script se algum comando falhar

echo "1/3 - A instalar o Hugo (versão extended, necessária para alguns temas)..."
HUGO_VERSAO="0.135.0"
wget -q "https://github.com/gohugoio/hugo/releases/download/v${HUGO_VERSAO}/hugo_extended_${HUGO_VERSAO}_linux-amd64.deb" -O /tmp/hugo.deb
sudo dpkg -i /tmp/hugo.deb || sudo apt-get install -f -y
rm /tmp/hugo.deb

echo "2/3 - A instalar o ffmpeg..."
sudo apt-get update -y
sudo apt-get install -y ffmpeg git

echo "3/3 - A instalar as dependências Python..."
pip install --no-cache-dir -r requirements.txt

echo ""
echo "Tudo pronto! Agora:"
echo "  1. Copia o ficheiro .env.example para .env e preenche os valores."
echo "  2. Corre: uvicorn main:app --host 0.0.0.0 --port 8000"
