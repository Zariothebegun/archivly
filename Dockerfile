# Dockerfile - permite correr o Archivly em qualquer serviço que suporte Docker
# (Render, Koyeb, Hugging Face Spaces, Fly.io), sem precisares de PC:
# basta ligar o teu repositório GitHub a esse serviço pelo browser do telemóvel.
#
# Nota: o Hugo e o ffmpeg são opcionais. Se falharem, a aplicação continua a
# funcionar (usa o gerador de sites em Python e simplesmente não gera
# miniaturas de vídeo).

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HUGO_VERSION=0.135.0

# Dependências de sistema + Hugo (falha tolerada) + ffmpeg (miniaturas de vídeo)
RUN apt-get update \
    && apt-get install -y --no-install-recommends wget git ffmpeg ca-certificates \
    && (wget -q "https://github.com/gohugoio/hugo/releases/download/v${HUGO_VERSION}/hugo_extended_${HUGO_VERSION}_linux-amd64.deb" -O /tmp/hugo.deb \
        && apt-get install -y /tmp/hugo.deb \
        && rm /tmp/hugo.deb \
        || echo "AVISO: Hugo não instalado - será usado o gerador Python") \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Pasta onde ficam a base de dados, os ficheiros e os sites publicados localmente
RUN mkdir -p /app/data

EXPOSE 8000

# O Render injeta PORT; usamos 8000 por omissão
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
