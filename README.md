# Archivly

Envia ficheiros. Recebe um site pesquisável, publicado automaticamente no GitHub Pages, em menos de 60 segundos.

> **Importante:** esta aplicação precisa de um servidor ligado (não corre "dentro" do telemóvel).
> As instruções abaixo usam apenas serviços **gratuitos** e são feitas 100% pelo browser do telemóvel — não precisas de PC nem de instalar nada localmente.

---

## Passo 1 — Colocar o código no GitHub

1. Cria conta em [github.com](https://github.com) (se ainda não tiveres).
2. Cria um repositório novo (botão **New**), ex: `archivly-app`. Pode ser público.
3. No teu telemóvel, abre o repositório → **Add file → Upload files** → seleciona todos os ficheiros e pastas desta entrega (`backend/` completo) → **Commit changes**.

## Passo 2 — Gerar o token do GitHub (para publicar os sites dos clientes)

Este token é diferente da tua conta — é o que a aplicação usa para criar repositórios automaticamente.

1. Vai a **github.com/settings/tokens?type=beta**
2. **Generate new token**
3. Em "Repository access" escolhe **All repositories** (para poder criar novos repos)
4. Em "Permissions" ativa:
   - **Administration**: Read and write
   - **Contents**: Read and write
   - **Pages**: Read and write
5. Gera o token e **copia-o já** (só aparece uma vez).

## Passo 3 — Criar a conta gratuita na Cloudflare R2 (armazenamento dos ficheiros)

1. Cria conta grátis em [dash.cloudflare.com/sign-up](https://dash.cloudflare.com/sign-up)
2. No menu lateral: **R2 Object Storage → Create bucket**. Nome: `archivly-files`.
3. Dentro do bucket: **Settings → Public Access → Allow Access** (para os ficheiros terem um URL público). Copia o URL público que aparece (algo como `https://pub-xxxx.r2.dev`).
4. Volta a **R2 → Manage API Tokens → Create API Token**. Permissões: **Object Read & Write**. Copia o **Access Key ID** e a **Secret Access Key**.
5. O "Account ID" aparece no canto direito da página principal da Cloudflare.

Isto é gratuito até 10 GB de armazenamento e cobre confortavelmente um MVP.

## Passo 4 — Publicar a aplicação num serviço gratuito (Render.com)

1. Cria conta grátis em [render.com](https://render.com) (podes entrar com o GitHub).
2. **New → Web Service**.
3. Escolhe o repositório `archivly-app` que criaste no Passo 1.
4. Render vai detetar o `Dockerfile` automaticamente — deixa como está.
5. Em **Environment Variables**, adiciona todas as variáveis do ficheiro `.env.example`:
   - `SECRET_KEY` → qualquer texto aleatório longo
   - `GITHUB_TOKEN` → o token do Passo 2
   - `GITHUB_USERNAME` → o teu username do GitHub
   - `R2_ACCOUNT_ID`, `R2_ACCESS_KEY`, `R2_SECRET_KEY`, `R2_BUCKET_NAME`, `R2_PUBLIC_URL` → do Passo 3
6. Escolhe o plano **Free** e clica **Create Web Service**.
7. Espera o build terminar (uns minutos) — no final tens um URL tipo `https://archivly-app.onrender.com`. É esse o link da tua aplicação.

> Nota sobre o plano Free do Render: o serviço "adormece" após 15 min sem uso e demora ~30s a acordar no pedido seguinte. Para um MVP é normal e não custa nada.

## Passo 5 — Usar

1. Abre o URL da tua aplicação no telemóvel.
2. Cria conta (email + password).
3. Envia os ficheiros (arrastar ou escolher).
4. Dá um nome ao site e carrega em **Publicar site**.
5. Em menos de um minuto tens o link `https://<o-teu-username>.github.io/archivly-nome-do-site/` a funcionar.

---

## Estrutura do projeto

```
backend/
├── main.py              # App FastAPI - liga tudo
├── database.py          # SQLite (users, files, sites)
├── auth.py               # Registo/login/tokens de sessão
├── storage.py            # Upload para Cloudflare R2
├── processing.py         # Deteção de tipo + miniaturas (Pillow/ffmpeg)
├── hugo_generator.py      # Gera o site estático com Hugo
├── github_publisher.py    # Cria repo, faz push, ativa GitHub Pages
├── models.py              # Modelos Pydantic
├── frontend/
│   ├── index.html         # Login / registo
│   ├── dashboard.html      # Upload + lista + publicar
│   └── static/
│       ├── style.css       # Tema verde/preto
│       ├── app.js          # Funções partilhadas (token, API)
│       └── logo.png        # O teu logo (a imagem que enviaste)
├── Dockerfile
├── setup.sh               # Instalação manual (se preferires correr num PC/VPS)
├── requirements.txt
└── .env.example
```

## Correr num PC/VPS em vez de usar o Render (opcional)

```bash
cp .env.example .env      # depois edita o .env com os teus valores
bash setup.sh             # instala hugo, ffmpeg e as dependências Python
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Erros comuns

| Erro | Causa provável |
|---|---|
| "Token do GitHub inválido" | O `GITHUB_TOKEN` no `.env`/Render está errado ou expirou |
| "Limite de pedidos à API do GitHub atingido" | Muitas publicações seguidas — espera alguns minutos |
| Miniaturas de vídeo não aparecem | O `ffmpeg` não está instalado (usa o Dockerfile fornecido, já o inclui) |
| Upload falha silenciosamente | Verifica as chaves do R2 e se o bucket tem "Public Access" ativado |
