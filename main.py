"""
main.py
-------
Aplicação principal do Archivly. Aqui juntamos:
- Autenticação (registo / login)
- Upload e processamento de ficheiros
- Geração do site com Hugo
- Publicação automática no GitHub Pages
- Serve também o frontend (HTML/CSS/JS) na raiz do site
"""

import os
import re
import shutil
import tempfile
import unicodedata
from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from database import init_db, get_db
from models import RegistoUtilizador, LoginUtilizador, PedidoPublicacao
from auth import gerar_hash_password, verificar_password, criar_token, obter_utilizador_atual
from processing import processar_ficheiro
from storage import enviar_ficheiro
from hugo_generator import gerar_site_hugo
from github_publisher import publicar_site_completo, ErroPublicacao, GITHUB_USERNAME

app = FastAPI(title="Archivly API")

# Permite que o frontend (mesmo em ficheiro estático) fale com a API sem bloqueios
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()


def slugificar(texto: str) -> str:
    """Transforma texto livre num slug seguro para nomes de repositório (ex: 'Foto Família' -> 'foto-familia')."""
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^a-zA-Z0-9]+", "-", texto).strip("-").lower()
    return texto or "site"


# ============================================================
# AUTENTICAÇÃO
# ============================================================

@app.post("/api/registo")
def registar(dados: RegistoUtilizador):
    """Cria uma nova conta de utilizador."""
    conn = get_db()
    cursor = conn.cursor()

    existente = cursor.execute("SELECT id FROM users WHERE email = ?", (dados.email,)).fetchone()
    if existente:
        conn.close()
        raise HTTPException(status_code=400, detail="Já existe uma conta com este email.")

    password_hash, salt = gerar_hash_password(dados.password)
    cursor.execute(
        "INSERT INTO users (email, password_hash, salt) VALUES (?, ?, ?)",
        (dados.email, password_hash, salt),
    )
    conn.commit()
    user_id = cursor.lastrowid
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
    """Recebe vários ficheiros, processa-os e guarda-os no R2 + SQLite."""
    resultados = []

    with tempfile.TemporaryDirectory() as pasta_temp:
        for ficheiro in ficheiros:
            caminho_local = os.path.join(pasta_temp, ficheiro.filename)
            conteudo = await ficheiro.read()
            with open(caminho_local, "wb") as f:
                f.write(conteudo)

            info = processar_ficheiro(caminho_local, ficheiro.filename, pasta_temp)

            # Envia o ficheiro original para o R2
            chave_r2 = f"users/{utilizador['user_id']}/originais/{ficheiro.filename}"
            url_original = enviar_ficheiro(caminho_local, chave_r2, info["mime_type"])

            # Envia a miniatura (se foi gerada)
            url_miniatura = None
            chave_miniatura = None
            if info["caminho_miniatura"]:
                chave_miniatura = f"users/{utilizador['user_id']}/miniaturas/{os.path.basename(info['caminho_miniatura'])}"
                url_miniatura = enviar_ficheiro(info["caminho_miniatura"], chave_miniatura, "image/jpeg")

            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO files
                   (user_id, original_name, file_type, mime_type, size_bytes,
                    r2_key, r2_url, thumbnail_r2_key, thumbnail_url)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    utilizador["user_id"], ficheiro.filename, info["tipo"], info["mime_type"],
                    info["size_bytes"], chave_r2, url_original, chave_miniatura, url_miniatura,
                ),
            )
            conn.commit()
            conn.close()

            resultados.append({
                "nome": ficheiro.filename,
                "tipo": info["tipo"],
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


# ============================================================
# PUBLICAÇÃO DO SITE (HUGO + GITHUB PAGES)
# ============================================================

@app.post("/api/publicar")
def publicar_site(pedido: PedidoPublicacao, utilizador: dict = Depends(obter_utilizador_atual)):
    """
    O coração do Archivly:
    1. Vai buscar os ficheiros do utilizador à base de dados.
    2. Gera o site estático com Hugo.
    3. Publica no GitHub Pages.
    4. Guarda o resultado na tabela 'sites'.
    """
    conn = get_db()
    cursor = conn.cursor()

    ficheiros_db = cursor.execute(
        "SELECT * FROM files WHERE user_id = ?", (utilizador["user_id"],)
    ).fetchall()

    if not ficheiros_db:
        conn.close()
        raise HTTPException(status_code=400, detail="Ainda não tens ficheiros enviados para publicar.")

    slug = slugificar(pedido.site_name)
    nome_repo = f"archivly-{slug}"
    base_url = f"https://{GITHUB_USERNAME}.github.io/{nome_repo}/"

    # Regista o site como "a processar" já para o utilizador ver progresso no dashboard
    cursor.execute(
        "INSERT INTO sites (user_id, site_name, repo_name, status) VALUES (?, ?, ?, 'a_processar')",
        (utilizador["user_id"], pedido.site_name, nome_repo),
    )
    conn.commit()
    site_id = cursor.lastrowid

    # Prepara os dados no formato que o template Hugo espera
    lista_ficheiros_hugo = [
        {
            "nome": f["original_name"],
            "tipo": f["file_type"],
            "url": f["r2_url"],
            "miniatura": f["thumbnail_url"],
            "data": (f["uploaded_at"] or "")[:10],
        }
        for f in ficheiros_db
    ]

    try:
        with tempfile.TemporaryDirectory() as pasta_trabalho:
            pasta_projeto = os.path.join(pasta_trabalho, "site")
            pasta_public = gerar_site_hugo(pasta_projeto, pedido.site_name, base_url, lista_ficheiros_hugo)

            resultado = publicar_site_completo(pasta_public, nome_repo)

        cursor.execute(
            "UPDATE sites SET status = 'publicado', site_url = ?, repo_name = ? WHERE id = ?",
            (resultado["site_url"], resultado["repo_name"], site_id),
        )
        conn.commit()
        conn.close()
        return {"site_url": resultado["site_url"], "repo_name": resultado["repo_name"]}

    except (ErroPublicacao, Exception) as erro:
        cursor.execute(
            "UPDATE sites SET status = 'erro', error_message = ? WHERE id = ?",
            (str(erro), site_id),
        )
        conn.commit()
        conn.close()
        raise HTTPException(status_code=500, detail=f"Falha ao publicar: {erro}")


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


# ============================================================
# FRONTEND (HTML/CSS/JS servidos diretamente pela mesma app)
# ============================================================

pasta_frontend = os.path.join(os.path.dirname(__file__), "frontend")
app.mount("/static", StaticFiles(directory=os.path.join(pasta_frontend, "static")), name="static")


@app.get("/")
def pagina_inicial():
    return FileResponse(os.path.join(pasta_frontend, "index.html"))


@app.get("/dashboard")
def pagina_dashboard():
    return FileResponse(os.path.join(pasta_frontend, "dashboard.html"))
