"""
github_publisher.py
--------------------
Trata da parte "mágica" do Archivly: pegar na pasta do site já gerado
(pasta 'public' do Hugo) e publicá-la automaticamente no GitHub Pages.

Passos:
1. Criar um repositório público novo via API do GitHub.
2. Fazer 'git push' de todo o conteúdo gerado para a branch 'main'.
3. Ativar o GitHub Pages via API para esse repositório.
"""

import os
import time
import subprocess
import requests
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")
GITHUB_API = "https://api.github.com"


class ErroPublicacao(Exception):
    """Erro genérico durante o processo de publicação no GitHub."""
    pass


def _headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def criar_repositorio(nome_repo: str) -> dict:
    """
    Cria um repositório público novo na conta do utilizador.
    Trata os erros mais comuns: repo já existe, token inválido, limite de taxa.
    """
    resposta = requests.post(
        f"{GITHUB_API}/user/repos",
        headers=_headers(),
        json={
            "name": nome_repo,
            "description": "Site gerado automaticamente pelo Archivly",
            "private": False,
            "auto_init": False,
        },
        timeout=30,
    )

    if resposta.status_code == 201:
        return resposta.json()

    if resposta.status_code == 401:
        raise ErroPublicacao(
            "Token do GitHub inválido ou expirado. Verifica o GITHUB_TOKEN no .env."
        )

    if resposta.status_code == 403:
        raise ErroPublicacao(
            "Limite de pedidos à API do GitHub atingido (rate limit). Tenta novamente daqui a alguns minutos."
        )

    if resposta.status_code == 422:
        # Nome já existe -> adiciona sufixo com timestamp e tenta de novo, uma vez
        novo_nome = f"{nome_repo}-{int(time.time())}"
        return criar_repositorio(novo_nome)

    raise ErroPublicacao(
        f"Erro inesperado ao criar repositório ({resposta.status_code}): {resposta.text}"
    )


def enviar_ficheiros_para_repo(pasta_site: str, nome_repo: str):
    """
    Faz o push do conteúdo da pasta 'public' (site gerado pelo Hugo)
    para a branch 'main' do repositório, usando git com o token embutido no URL.
    """
    url_com_token = (
        f"https://{GITHUB_USERNAME}:{GITHUB_TOKEN}@github.com/"
        f"{GITHUB_USERNAME}/{nome_repo}.git"
    )

    comandos = [
        ["git", "init", "-b", "main"],
        ["git", "config", "user.email", "archivly-bot@archivly.app"],
        ["git", "config", "user.name", "Archivly Bot"],
        ["git", "add", "."],
        ["git", "commit", "-m", "Publicação automática via Archivly"],
        ["git", "remote", "add", "origin", url_com_token],
        ["git", "push", "-u", "origin", "main", "--force"],
    ]

    for comando in comandos:
        resultado = subprocess.run(
            comando, cwd=pasta_site, capture_output=True, text=True
        )
        if resultado.returncode != 0 and "push" in comando:
            raise ErroPublicacao(f"Erro ao enviar ficheiros para o GitHub: {resultado.stderr}")


def ativar_github_pages(nome_repo: str) -> str:
    """
    Ativa o GitHub Pages para o repositório, a servir a partir da branch 'main' / raiz.
    Devolve o URL final do site.
    """
    resposta = requests.post(
        f"{GITHUB_API}/repos/{GITHUB_USERNAME}/{nome_repo}/pages",
        headers=_headers(),
        json={"source": {"branch": "main", "path": "/"}},
        timeout=30,
    )

    # 201 = criado agora, 409 = já estava ativo (não é erro para nós)
    if resposta.status_code not in (201, 409):
        raise ErroPublicacao(
            f"Erro ao ativar o GitHub Pages ({resposta.status_code}): {resposta.text}"
        )

    return f"https://{GITHUB_USERNAME}.github.io/{nome_repo}/"


def publicar_site_completo(pasta_site: str, nome_repo_sugerido: str) -> dict:
    """
    Função principal chamada pelo backend: junta os 3 passos e devolve
    o resultado final (nome do repo criado + URL do site).
    """
    if not GITHUB_TOKEN or not GITHUB_USERNAME:
        raise ErroPublicacao(
            "GITHUB_TOKEN ou GITHUB_USERNAME não configurados no ficheiro .env."
        )

    repo_info = criar_repositorio(nome_repo_sugerido)
    nome_repo_final = repo_info["name"]

    enviar_ficheiros_para_repo(pasta_site, nome_repo_final)

    # Pequena espera para o GitHub processar o push antes de ativar o Pages
    time.sleep(3)
    url_final = ativar_github_pages(nome_repo_final)

    return {"repo_name": nome_repo_final, "site_url": url_final}
