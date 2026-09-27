# Archivly

Envia ficheiros. Recebe um site pesquisável, publicado automaticamente, em menos de 60 segundos.

O utilizador cria conta, envia fotos/vídeos/áudio/documentos, dá um nome ao site e carrega em
**Publicar**. O Archivly gera um site estático (grid de miniaturas + pesquisa + filtro por tipo)
e publica-o — no **GitHub Pages** se houver token, ou **no próprio servidor** (`/sites/<nome>/`)
se não houver. Funciona logo, sem configuração.

---

## Publicar agora (o caminho mais rápido)

👉 **[Guia completo de deploy em DEPLOY.md](DEPLOY.md)**

Resumo, se quiseres só pôr no ar já (Render, grátis, ~10 min):

1. Abre **[render.com/deploy?repo=https://github.com/Zariothebegun/archivly](https://render.com/deploy?repo=https://github.com/Zariothebegun/archivly)**
2. Entra com o GitHub e carrega em **Apply**.
3. O Render lê o `render.yaml` (Docker + health check + `SECRET_KEY` automática) e faz o build.
4. Ficas com um URL tipo `https://archivly.onrender.com`.

Verifica com:

```bash
python smoke_test.py https://archivly.onrender.com
# Resultado: TUDO OK - a aplicação está funcional.
```

> Alternativas (Koyeb, Hugging Face Spaces, Fly.io) e as limitações do plano grátis
> estão comparadas em [DEPLOY.md](DEPLOY.md).

---

## Correr localmente

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
```

Abre `http://127.0.0.1:8000`. **Não precisas de `.env`** — sem variáveis definidas a app
usa o modo local (ficheiros em `data/media`, sites em `data/sites`, base de dados em `data/archivly.db`).

Teste rápido de ponta a ponta (cria conta, envia ficheiro, publica site, confirma o link):

```bash
.venv/bin/python smoke_test.py
```

Opcional, para teres miniaturas de vídeo e build via Hugo:

```bash
cp .env.example .env    # preenche só o que quiseres
bash setup.sh           # instala Hugo, ffmpeg e as dependências Python
```

---

## Modos de funcionamento

A aplicação adapta-se ao que está configurado — não há modo "incompleto":

| O que está configurado | Armazenamento | Publicação dos sites |
|---|---|---|
| Nada | Disco local (`data/media`) | Local, em `/sites/<nome>/` |
| Só `GITHUB_TOKEN` + `GITHUB_USERNAME` | Disco local | GitHub Pages ⚠️ (ver nota) |
| Só `R2_*` | Cloudflare R2 (CDN) | Local, em `/sites/<nome>/` |
| `R2_*` + `GITHUB_TOKEN` | Cloudflare R2 | GitHub Pages ✅ (modo completo) |

⚠️ **Nota:** os sites no GitHub Pages são um domínio diferente, por isso os links para
`/media/...` do teu servidor não funcionam lá. Para publicar no GitHub Pages, configura
também o R2 (grátis até 10 GB) — instruções em [DEPLOY.md](DEPLOY.md#opção-c--ligar-o-github-pages-e-o-cloudflare-r2-quando-quiseres).

O mesmo para o gerador de sites: usa **Hugo** quando o binário existe (o `Dockerfile` instala-o)
e, caso contrário, um **gerador em Python** que produz exatamente o mesmo HTML/CSS/JS.
Podes ver o que está ativo no topo do dashboard ou em `GET /api/estado`.

---

## Estrutura do projeto

```
archivly/
├── main.py               # App FastAPI: API + serve o frontend + /media e /sites
├── database.py           # SQLite (users, files, sites) em data/archivly.db
├── auth.py               # Registo/login, password PBKDF2 + salt, sessão JWT
├── storage.py            # Cloudflare R2 ou disco local (automático)
├── processing.py         # Deteção de tipo + miniaturas (Pillow/ffmpeg)
├── hugo_generator.py     # Gera o site estático (Hugo ou gerador Python)
├── github_publisher.py   # Cria repo, faz push, ativa o GitHub Pages
├── local_publisher.py    # Publica o site no próprio servidor (sem GitHub)
├── models.py             # Modelos Pydantic
├── frontend/
│   ├── index.html          # Login / registo
│   ├── dashboard.html      # Upload + lista + publicar + sites
│   └── static/
│       ├── style.css       # Tema verde/preto, mobile-first
│       ├── app.js          # Sessão, chamadas à API, avisos
│       └── logo.svg        # Logótipo
├── smoke_test.py         # Teste de ponta a ponta (local ou contra o deploy)
├── Dockerfile            # Imagem com Python + git + ffmpeg + Hugo
├── render.yaml           # Blueprint do Render (deploy em 1 clique)
├── setup.sh              # Instalação manual (PC/VPS)
├── requirements.txt
├── .env.example          # Todas as variáveis (nenhuma é obrigatória)
└── DEPLOY.md             # Guia de publicação detalhado
```

## API

| Método | Rota | Descrição |
|---|---|---|
| GET | `/healthz` | Health check (usado pelo Render) |
| GET | `/api/estado` | O que está configurado (armazenamento, GitHub, Hugo) |
| POST | `/api/registo` | Criar conta (`email`, `password`) |
| POST | `/api/login` | Entrar e receber token |
| POST | `/api/upload` | Enviar ficheiros (`multipart`, campo `ficheiros`) |
| GET | `/api/ficheiros` | Listar ficheiros do utilizador |
| DELETE | `/api/ficheiros/{id}` | Apagar ficheiro |
| POST | `/api/publicar` | Gerar e publicar o site (`site_name`) |
| GET | `/api/sites` | Listar sites publicados |
| DELETE | `/api/sites/{id}` | Apagar registo de um site |

Documentação interativa automática em `/docs` (Swagger).

## Erros comuns

| Erro | Causa provável |
|---|---|
| "Token do GitHub inválido" | `GITHUB_TOKEN` errado ou expirado |
| "O token não tem a permissão 'Administration'" | O token precisa de Administration/Contents/Pages em Read and write |
| "Limite de pedidos à API do GitHub atingido" | Muitas publicações seguidas — espera uns minutos |
| Miniaturas de vídeo não aparecem | `ffmpeg` não está instalado (usa o `Dockerfile`, já o inclui) |
| Upload falha | Verifica as chaves do R2 e se o bucket tem "Public Access" ativado |
| Dados desapareceram após um deploy | Plano grátis do Render tem disco efémero — vê "Limitações" em [DEPLOY.md](DEPLOY.md) |
| Primeira visita demora ~40 s | O serviço grátis estava adormecido; acorda sozinho |
