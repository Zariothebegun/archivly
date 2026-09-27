"""
main.py
-------
Aplicação principal do Archivly. Aqui juntamos:
- Autenticação (registo / login)
- Upload e processamento de ficheiros
- Geração do site estático (Hugo, ou gerador Python se o Hugo não existir)
- Publicação automática no GitHub Pages (ou localmente, se não houver token)
- Serve também o frontend (HTML/CSS/JS) na raiz do site
"""

import os
import re
import tempfile
import unicodedata
import uuid

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from auth import criar_token, gerar_hash_password, obter_utilizador_atual, verificar_password
from database import get_db, init_db
from github_publisher import (
    ErroPublicacao,
    GITHUB_USERNAME,
    github_configurado,
    publicar_site_completo,
)
from hugo_generator import gerar_site_hugo, hugo_disponivel
from local_publisher import PASTA_SITES, publicar_localmente
from models import LoginUtilizador, PedidoPublicacao, RegistoUtilizador
from processing import processar_ficheiro
from storage import (
    PASTA_MEDIA_LOCAL,
    apagar_ficheiro,
    caminho_local_de,
    enviar_ficheiro,
    modo_armazenamento,
)

app = FastAPI(title="Archivly API", version="1.0.0")

# Permite que o frontend fale com a API sem bloqueios (útil em previews e domínios personalizados)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# URL público da aplicação (o Render define RENDER_EXTERNAL_URL automaticamente).
# Serve para construir links absolutos dos sites publicados localmente.
BASE_URL_PUBLICA = (
    os.getenv("PUBLIC_BASE_URL")
    or os.getenv("RENDER_EXTERNAL_URL")
    or ""
).rstrip("/")

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "100"))

pasta_frontend = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")

init_db()


# ============================================================
# UTILITÁRIOS
# ============================================================

def slugificar(texto: str) -> str:
    """Transforma texto livre num slug seguro para nomes de repositório/pasta
    (ex: 'Foto Família' -> 'foto-familia')."""
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^a-zA-Z0-9]+", "-", texto).strip("-").lower()
    return texto[:50] or "site"


def nome_ficheiro_seguro(nome: str) -> str:
    """
    Remove caminhos de um nome de ficheiro vindo do browser ('../../etc/passwd'
    nunca pode sair da pasta temporária) e limita o tamanho.
    """
    nome = os.path.basename((nome or "").replace("\\", "/")).strip()
    nome = re.sub(r"[\x00-\x1f]", "", nome)
    return nome[:180] or "ficheiro"


def url_absoluto(caminho: str) -> str:
    """Junta o URL público da app a um caminho relativo (se estiver configurado)."""
    if caminho.startswith("http://") or caminho.startswith("https://"):
        return caminho
    return f"{BASE_URL_PUBLICA}{caminho}"


def _ficheiro_de_dentro(pasta_base: str, caminho_pedido: str) -> str:
    """Resolve um caminho dentro de uma pasta, bloqueando fugas com '../'."""
    raiz = os.path.abspath(pasta_base)
    alvo = os.path.abspath(os.path.join(raiz, caminho_pedido))
    if alvo != raiz and not alvo.startswith(raiz + os.sep):
        raise HTTPException(status_code=400, detail="Caminho inválido.")
    return alvo


# ============================================================
# ESTADO / SAÚDE (usado pelo Render e pelo dashboard)
# ============================================================

@app.get("/healthz")
def saude():
    """Health check - o Render usa isto para saber se a app está viva."""
    return {"estado": "ok"}


@app.get("/api/estado")
def estado_configuracao(utilizador: dict = Depends(obter_utilizador_atual)):
    """Diz ao dashboard o que está configurado, para mostrar avisos úteis."""
    return {
        "armazenamento": modo_armazenamento(),          # 'r2' ou 'local'
        "github_pages": github_configurado(),           # True/False
        "hugo": hugo_disponivel(),                      # True/False (senão usa gerador Python)
        "publicacao": "github_pages" if github_configurado() else "local",
        "github_username": GITHUB_USERNAME if github_configurado() else None,
        "max_upload_mb": MAX_UPLOAD_MB,
    }


# ============================================================
# AUTENTICAÇÃO
# ============================================================

@app.post("/api/registo")
def registar(dados: RegistoUtilizador):
    """Cria uma nova conta de utilizador."""
    if len(dados.password) < 6:
        raise HTTPException(status_code=400, detail="A password tem de ter pelo menos 6 caracteres.")

    conn = get_db()
    cursor = conn.cursor()
    try:
        existente = cursor.execute("SELECT id FROM users WHERE email = ?", (dados.email,)).fetchone()
        if existente:
            raise HTTPException(status_code=400, detail="Já existe uma conta com este email.")

        password_hash, salt = gerar_hash_password(dados.password)
        cursor.execute(
            "INSERT INTO users (email, password_hash, salt) VALUES (?, ?, ?)",
            (dados.email, password_hash, salt),
        )
        conn.commit()
        user_id = cursor.lastrowid
    finally:
        conn.close()

    token = criar_token(user_id, dados.email)
    return {"token": token, "email": dados.email}


@app.post("/api/login")
def login(dados: LoginUtilizador):
    """Autentica um utilizador existente e devolve um token de sessão."""
    conn = get_db()
    utilizador = conn.execute(
        "SELECT * FROM users WHERE email = ?", (dados.email,)
    ).fetchone()
    conn.close()

    if not utilizador or not verificar_password(dados.password, utilizador["password_hash"], utilizador["salt"]):
        raise HTTPException(status_code=401, detail="Email ou password incorretos.")

    token = criar_token(utilizador["id"], utilizador["email"])
    return {"token": token, "email": utilizador["email"]}


# ============================================================
# UPLOAD E PROCESSAMENTO DE FICHEIROS
# ============================================================

@app.post("/api/upload")
async def upload_ficheiros(
    ficheiros: list[UploadFile] = File(...),
    utilizador: dict = Depends(obter_utilizador_atual),
):
    """Recebe vários ficheiros, processa-os (tipo + miniatura) e guarda-os."""
    if not ficheiros:
        raise HTTPException(status_code=400, detail="Nenhum ficheiro recebido.")

    resultados = []
    limite_bytes = MAX_UPLOAD_MB * 1024 * 1024

    with tempfile.TemporaryDirectory() as pasta_temp:
        for ficheiro in ficheiros:
            nome_seguro = nome_ficheiro_seguro(ficheiro.filename)
            caminho_local = os.path.join(pasta_temp, f"{uuid.uuid4().hex}-{nome_seguro}")

            conteudo = await ficheiro.read()
            if len(conteudo) > limite_bytes:
                raise HTTPException(
                    status_code=413,
                    detail=f"'{nome_seguro}' excede o limite de {MAX_UPLOAD_MB} MB.",
                )
            with open(caminho_local, "wb") as f:
                f.write(conteudo)

            info = processar_ficheiro(caminho_local, nome_seguro, pasta_temp)

            # Ficheiro original
            chave_original = f"users/{utilizador['user_id']}/originais/{uuid.uuid4().hex}-{nome_seguro}"
            url_original = enviar_ficheiro(caminho_local, chave_original, info["mime_type"])

            # Miniatura (se foi gerada)
            url_miniatura = None
            chave_miniatura = None
            if info["caminho_miniatura"] and os.path.isfile(info["caminho_miniatura"]):
                chave_miniatura = f"users/{utilizador['user_id']}/miniaturas/{uuid.uuid4().hex}.jpg"
                url_miniatura = enviar_ficheiro(info["caminho_miniatura"], chave_miniatura, "image/jpeg")

            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO files
                   (user_id, original_name, file_type, mime_type, size_bytes,
                    r2_key, r2_url, thumbnail_r2_key, thumbnail_url)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    utilizador["user_id"], nome_seguro, info["tipo"], info["mime_type"],
                    info["size_bytes"], chave_original, url_original, chave_miniatura, url_miniatura,
                ),
            )
            conn.commit()
            novo_id = cursor.lastrowid
            conn.close()

            resultados.append({
                "id": novo_id,
                "nome": nome_seguro,
                "tipo": info["tipo"],
                "tamanho": info["size_bytes"],
                "url": url_original,
                "miniatura": url_miniatura,
            })

    return {"ficheiros_processados": resultados}


@app.get("/api/ficheiros")
def listar_ficheiros(utilizador: dict = Depends(obter_utilizador_atual)):
    """Lista todos os ficheiros do utilizador autenticado."""
    conn = get_db()
    ficheiros = conn.execute(
        "SELECT * FROM files WHERE user_id = ? ORDER BY uploaded_at DESC",
        (utilizador["user_id"],),
    ).fetchall()
    conn.close()
    return {"ficheiros": [dict(f) for f in ficheiros]}


@app.delete("/api/ficheiros/{ficheiro_id}")
def apagar_ficheiro_api(ficheiro_id: int, utilizador: dict = Depends(obter_utilizador_atual)):
    """Apaga um ficheiro do utilizador (disco/R2 e base de dados)."""
    conn = get_db()
    registo = conn.execute(
        "SELECT * FROM files WHERE id = ? AND user_id = ?", (ficheiro_id, utilizador["user_id"])
    ).fetchone()
    if not registo:
        conn.close()
        raise HTTPException(status_code=404, detail="Ficheiro não encontrado.")

    conn.execute("DELETE FROM files WHERE id = ?", (ficheiro_id,))
    conn.commit()
    conn.close()

    apagar_ficheiro(registo["r2_key"])
    apagar_ficheiro(registo["thumbnail_r2_key"])
    return {"apagado": ficheiro_id}


# ============================================================
# PUBLICAÇÃO DO SITE (GitHub Pages ou local)
# ============================================================

@app.post("/api/publicar")
def publicar_site(pedido: PedidoPublicacao, utilizador: dict = Depends(obter_utilizador_atual)):
    """
    O coração do Archivly:
    1. Vai buscar os ficheiros do utilizador à base de dados.
    2. Gera o site estático (Hugo ou gerador Python).
    3. Publica no GitHub Pages - ou localmente, se não houver token.
    4. Guarda o resultado na tabela 'sites'.
    """
    nome_site = (pedido.site_name or "").strip()
    if not nome_site:
        raise HTTPException(status_code=400, detail="Indica um nome para o site.")

    conn = get_db()
    cursor = conn.cursor()

    ficheiros_db = cursor.execute(
        "SELECT * FROM files WHERE user_id = ?", (utilizador["user_id"],)
    ).fetchall()

    if not ficheiros_db:
        conn.close()
        raise HTTPException(status_code=400, detail="Ainda não tens ficheiros enviados para publicar.")

    slug = slugificar(nome_site)
    usar_github = github_configurado()
    nome_repo = f"archivly-{slug}"

    # Regista o site como "a processar" já para o utilizador ver progresso no dashboard
    cursor.execute(
        "INSERT INTO sites (user_id, site_name, repo_name, status) VALUES (?, ?, ?, 'a_processar')",
        (utilizador["user_id"], nome_site, nome_repo if usar_github else slug),
    )
    conn.commit()
    site_id = cursor.lastrowid

    # Prepara os dados no formato que o template do site espera
    lista_ficheiros = [
        {
            "nome": f["original_name"],
            "tipo": f["file_type"],
            "url": url_absoluto(f["r2_url"]),
            "miniatura": url_absoluto(f["thumbnail_url"]) if f["thumbnail_url"] else None,
            "data": (f["uploaded_at"] or "")[:10],
        }
        for f in ficheiros_db
    ]

    try:
        with tempfile.TemporaryDirectory() as pasta_trabalho:
            pasta_projeto = os.path.join(pasta_trabalho, "site")

            if usar_github:
                base_url = f"https://{GITHUB_USERNAME}.github.io/{nome_repo}/"
                pasta_public = gerar_site_hugo(pasta_projeto, nome_site, base_url, lista_ficheiros)
                resultado = publicar_site_completo(pasta_public, nome_repo)
                url_final = resultado["site_url"]
                repo_final = resultado["repo_name"]
                destino = "github_pages"
            else:
                # Sem GitHub: publica na própria app e usa URLs absolutos se soubermos o domínio
                pasta_public = gerar_site_hugo(pasta_projeto, nome_site, url_absoluto(f"/sites/{slug}/"), lista_ficheiros)
                caminho_relativo = publicar_localmente(pasta_public, slug)
                url_final = url_absoluto(caminho_relativo)
                repo_final = slug
                destino = "local"

        cursor.execute(
            "UPDATE sites SET status = 'publicado', site_url = ?, repo_name = ? WHERE id = ?",
            (url_final, repo_final, site_id),
        )
        conn.commit()
        conn.close()
        resposta = {
            "site_url": url_final,
            "repo_name": repo_final,
            "destino": destino,
            "total_ficheiros": len(lista_ficheiros),
        }
        if destino == "local":
            resposta["caminho_relativo"] = caminho_relativo
        return resposta

    except ErroPublicacao as erro:
        _marcar_erro(cursor, conn, site_id, str(erro))
        raise HTTPException(status_code=502, detail=f"Falha ao publicar: {erro}")
    except HTTPException:
        raise
    except Exception as erro:  # qualquer outra falha (Hugo, disco, rede)
        _marcar_erro(cursor, conn, site_id, str(erro))
        raise HTTPException(status_code=500, detail=f"Falha ao publicar: {erro}")


def _marcar_erro(cursor, conn, site_id: int, mensagem: str):
    """Guarda a mensagem de erro do site e fecha a ligação."""
    try:
        cursor.execute(
            "UPDATE sites SET status = 'erro', error_message = ? WHERE id = ?",
            (mensagem[:500], site_id),
        )
        conn.commit()
    finally:
        conn.close()


@app.get("/api/sites")
def listar_sites(utilizador: dict = Depends(obter_utilizador_atual)):
    """Lista os sites publicados (ou em progresso) pelo utilizador."""
    conn = get_db()
    sites = conn.execute(
        "SELECT * FROM sites WHERE user_id = ? ORDER BY created_at DESC",
        (utilizador["user_id"],),
    ).fetchall()
    conn.close()
    return {"sites": [dict(s) for s in sites]}


@app.delete("/api/sites/{site_id}")
def apagar_site(site_id: int, utilizador: dict = Depends(obter_utilizador_atual)):
    """Apaga um site publicado localmente (os do GitHub Pages ficam na tua conta)."""
    conn = get_db()
    registo = conn.execute(
        "SELECT * FROM sites WHERE id = ? AND user_id = ?", (site_id, utilizador["user_id"])
    ).fetchone()
    if not registo:
        conn.close()
        raise HTTPException(status_code=404, detail="Site não encontrado.")

    conn.execute("DELETE FROM sites WHERE id = ?", (site_id,))
    conn.commit()
    conn.close()

    from local_publisher import apagar_site_local
    apagar_site_local(slugificar(registo["repo_name"]))
    return {"apagado": site_id}


# ============================================================
# FICHEIROS GUARDADOS LOCALMENTE (modo sem R2)
# ============================================================

@app.get("/media/{chave:path}")
def servir_media(chave: str):
    """Serve um ficheiro guardado no disco local (miniaturas e originais)."""
    caminho = _ficheiro_de_dentro(PASTA_MEDIA_LOCAL, chave)
    if not os.path.isfile(caminho):
        raise HTTPException(status_code=404, detail="Ficheiro não encontrado.")
    return FileResponse(caminho)


@app.get("/sites/{slug}")
def site_sem_barra(slug: str):
    """'/sites/nome' -> '/sites/nome/' (necessário para os links relativos do CSS)."""
    return RedirectResponse(url=f"/sites/{slug}/")


@app.get("/sites/{slug}/{caminho:path}")
def servir_site_local(slug: str, caminho: str):
    """Serve um site publicado localmente."""
    slug_seguro = slugificar(slug)
    pasta = _ficheiro_de_dentro(PASTA_SITES, slug_seguro)
    alvo = _ficheiro_de_dentro(pasta, caminho or "index.html")
    if os.path.isdir(alvo):
        alvo = os.path.join(alvo, "index.html")
    if not os.path.isfile(alvo):
        raise HTTPException(status_code=404, detail="Site não encontrado.")
    return FileResponse(alvo)


# ============================================================
# FRONTEND (HTML/CSS/JS servidos diretamente pela mesma app)
# ============================================================

pasta_static = os.path.join(pasta_frontend, "static")
if os.path.isdir(pasta_static):
    app.mount("/static", StaticFiles(directory=pasta_static), name="static")


@app.get("/")
def pagina_inicial():
    return FileResponse(os.path.join(pasta_frontend, "index.html"))


@app.get("/dashboard")
def pagina_dashboard():
    return FileResponse(os.path.join(pasta_frontend, "dashboard.html"))


@app.get("/favicon.ico")
def favicon():
    caminho = os.path.join(pasta_static, "logo.svg")
    if os.path.isfile(caminho):
        return FileResponse(caminho, media_type="image/svg+xml")
    return JSONResponse({}, status_code=204)
