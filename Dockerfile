# Dockerfile - permite correr o Archivly em qualquer serviço gratuito
# que suporte Docker (Render, Railway, Fly.io), sem precisares de PC:
# basta ligar o teu repositório GitHub a esse serviço pelo browser do telemóvel.

FROM python:3.11-slim

# Instala as dependências de sistema: git, ffmpeg e o binário do Hugo
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget git ffmpeg ca-certificates \
    && wget -q https://github.com/gohugoio/hugo/releases/download/v0.135.0/hugo_extended_0.135.0_linux-amd64.deb -O /tmp/hugo.deb \
    && apt-get install -y /tmp/hugo.deb \
    && rm /tmp/hugo.deb \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
