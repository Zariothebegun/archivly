# Publicar o Archivly — guia rápido

A aplicação **funciona sem configuração nenhuma**: sem R2, sem token do GitHub, sem Hugo.
Nesse "modo local" os ficheiros ficam no servidor e os sites publicados ficam em
`/sites/<nome>/` — ou seja, podes pôr no ar hoje e configurar o resto depois.

---

## Opção A — Render (recomendada, ~10 minutos, grátis)

**Caminho mais rápido (1 clique):**

1. Abre **[https://render.com/deploy?repo=https://github.com/Zariothebegun/archivly](https://render.com/deploy?repo=https://github.com/Zariothebegun/archivly)**
2. Entra com a tua conta GitHub (**Sign in with GitHub**).
3. Carrega em **Apply** / **Create** — o Render lê o `render.yaml` e configura tudo sozinho
   (Docker, health check em `/healthz`, `SECRET_KEY` gerada automaticamente).
4. Espera o build (3–8 min no plano grátis). No fim tens um URL
   `https://archivly.onrender.com`.

**Se o link acima não funcionar**, faz manualmente:
Render → **New +** → **Blueprint** → escolhe o repositório `archivly` → **Apply**.
(Alternativa: **New +** → **Web Service** → repositório → deteta o `Dockerfile` →
**Health Check Path**: `/healthz` → plano **Free**.)

### Se o build Docker falhar (ou se quiseres um build mais rápido)

O `render.yaml` usa Docker porque traz o Hugo e o ffmpeg (miniaturas de vídeo).
Se o build der erro ou preferires algo mais simples, troca para o runtime Python:

1. No Render: o teu serviço → **Settings** → **Runtime** → **Python 3**
2. **Build Command**: `pip install -r requirements.txt`
3. **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. **Health Check Path**: `/healthz`

Perdes apenas as miniaturas de vídeo (o ffmpeg não vem instalado) — o resto funciona
na mesma, porque o gerador de sites em Python substitui o Hugo automaticamente.

### Verificar que ficou a funcionar

```bash
python smoke_test.py https://a-tua-app.onrender.com
```

Deve terminar com `Resultado: TUDO OK`.

### Limitações do plano grátis (é mesmo assim, não é erro)

| Limitação | O que acontece |
|---|---|
| Adormece após 15 min sem uso | O primeiro pedido demora ~30–50 s a acordar |
| Disco **efémero** | A base de dados e os uploads em `data/` são limpos em cada deploy/restart |
| 512 MB RAM | Chega bem para um MVP |

Para deixar de perder dados: **Render → o teu serviço → Disk → Add Disk**,
monta em `/opt/render/project/src/data` (custa ~1 USD/mês) — o código já usa a
pasta `data/`, por isso não precisas de mudar mais nada.
Ou então configura o Cloudflare R2 (opção C), que é grátis até 10 GB e não depende do disco.

---

## Opção B — Outros serviços grátis

| Serviço | Como | Prós | Contras |
|---|---|---|---|
| **Render** | Blueprint/`render.yaml` (Opção A) | 1 clique, Docker, plano grátis | Adormece, disco efémero |
| **Koyeb** | Ligas o repo GitHub → deteta o `Dockerfile` | Não adormece tão depressa | 1 serviço grátis, 512 MB |
| **Hugging Face Spaces** | New Space → **Docker** → `docker/sdk` em branco → carrega os ficheiros | Grátis, 2 vCPU/16 GB, raramente adormece | Espaço público por omissão; URL longo |
| **Fly.io** | `fly launch` (precisa de CLI + cartão) | Sempre ligado, rápido | Já não tem plano grátis a sério |
| **Railway** | Ligas o repo | Muito simples | Só crédito de teste, depois pago |

Para qualquer um deles: **build** = `Dockerfile`, **start** = o `CMD` do Dockerfile
(uvicorn na porta `$PORT`), **health check** = `/healthz`,
e define `SECRET_KEY` nas variáveis de ambiente.

---

## Opção C — Ligar o GitHub Pages e o Cloudflare R2 (quando quiseres)

Isto são melhorias, **não são requisitos** para publicar.

### C.1 — Publicar os sites dos clientes no GitHub Pages

1. **github.com/settings/tokens?type=beta** → **Generate new token**
2. Repository access: **All repositories** (é preciso para poder criar repos novos)
3. Permissions:
   - **Administration**: Read and write
   - **Contents**: Read and write
   - **Pages**: Read and write
4. Copia o token (só aparece uma vez)
5. No Render: o teu serviço → **Environment** → preenche `GITHUB_TOKEN` e
   `GITHUB_USERNAME` → **Save changes** (faz redeploy)

A partir daí, cada publicação cria o repositório `archivly-<nome>`, faz push e ativa
o Pages — o link final fica `https://<username>.github.io/archivly-<nome>/`.

> **Importante:** com GitHub Pages os ficheiros têm de ter URL público absoluto.
> Se não configurares o R2 (C.2), os links apontam para `/media/...` do teu servidor
> e **não funcionam** no github.io. Ou seja: GitHub Pages ⇒ configura também o R2.

### C.2 — Cloudflare R2 (armazenamento dos ficheiros, grátis até 10 GB)

1. **dash.cloudflare.com/sign-up** → cria conta
2. **R2 Object Storage → Create bucket** → nome `archivly-files`
3. No bucket: **Settings → Public Access → Allow Access** → copia o URL (`https://pub-xxxx.r2.dev`)
4. **R2 → Manage API Tokens → Create API Token** → permissão **Object Read & Write**
   → copia **Access Key ID** e **Secret Access Key**
5. O **Account ID** está no canto direito da página principal da Cloudflare
6. No Render, preenche: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY`, `R2_SECRET_KEY`,
   `R2_BUCKET_NAME`, `R2_PUBLIC_URL` → **Save changes**

### Como sei o que está ativo?

No dashboard aparecem avisos no topo, ou pergunta à API:

```bash
curl https://a-tua-app.onrender.com/api/estado -H "Authorization: Bearer <token>"
# {"armazenamento":"local|r2","github_pages":true|false,"hugo":true|false,...}
```

---

## Correr localmente (para testar antes de publicar)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
# noutro terminal:
.venv/bin/python smoke_test.py
```

Abre `http://127.0.0.1:8000`. Não precisas de `.env` para nada.
Com `bash setup.sh` instalas também o Hugo e o ffmpeg (opcional: miniaturas de vídeo
e build via Hugo).
