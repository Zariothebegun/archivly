"""
github_publisher.py
--------------------
Trata da parte "mágica" do Archivly: pegar na pasta do site já gerado
e publicá-la automaticamente no GitHub Pages.

Passos:
1. Criar um repositório público novo via API do GitHub.
2. Fazer 'git push' de todo o conteúdo gerado para a branch 'main'.
3. Ativar o GitHub Pages via API para esse repositório.

Se o GITHUB_TOKEN não estiver configurado, o main.py usa antes o
local_publisher.py (publicação servida pela própria aplicação).
"""

import os
import shutil
import subprocess
import time

import requests
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME")
GITHUB_API = "https://api.github.com"


class ErroPublicacao(Exception):
    """Erro genérico durante o processo de publicação no GitHub."""
    pass


def github_configurado() -> bool:
    """True se houver token e username para publicar no GitHub Pages."""
    return bool(GITHUB_TOKEN and GITHUB_USERNAME)


def _headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _git(comando: list, pasta: str, obrigatorio: bool = True):
    """Corre um comando git na pasta do site e levanta erro claro se falhar."""
    if shutil.which("git") is None:
        raise ErroPublicacao("O 'git' não está instalado no servidor.")
    resultado = subprocess.run(comando, cwd=pasta, capture_output=True, text=True)
    if resultado.returncode != 0 and obrigatorio:
        raise ErroPublicacao(
            f"Erro ao executar '{comando[0]} {comando[1] if len(comando) > 1 else ''}': "
            f"{resultado.stderr.strip() or resultado.stdout.strip()}"
        )
    return resultado


def criar_repositorio(nome_repo: str) -> dict:
    """
    Cria um repositório público novo na conta do utilizador.
    Trata os erros mais comuns: repo já existe, token inválido, sem permissões, rate limit.
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
            "Token do GitHub inválido ou expirado. Verifica o GITHUB_TOKEN."
        )

    if resposta.status_code == 403:
        raise ErroPublicacao(
            "Sem permissão para criar repositórios ou limite de pedidos atingido. "
            "O token precisa de 'Administration: Read and write'."
        )

    if resposta.status_code == 404:
        raise ErroPublicacao(
            "O token não tem a permissão 'Administration: Read and write' "
            "(necessária para criar repositórios)."
        )

    if resposta.status_code == 422:
        # Nome já existe -> adiciona sufixo com timestamp e tenta de novo, uma vez
        if nome_repo.endswith(f"-{int(time.time())}"):
            raise ErroPublicacao("Não foi possível criar o repositório (nome em uso).")
        return criar_repositorio(f"{nome_repo}-{int(time.time())}")

    raise ErroPublicacao(
        f"Erro inesperado ao criar repositório ({resposta.status_code}): {resposta.text}"
    )


def enviar_ficheiros_para_repo(pasta_site: str, nome_repo: str):
    """
    Faz o push do conteúdo da pasta gerada para a branch 'main' do repositório,
    usando git com o token embutido no URL (o token nunca fica no conteúdo publicado).
    """
    url_com_token = (
        f"https://{GITHUB_USERNAME}:{GITHUB_TOKEN}@github.com/"
        f"{GITHUB_USERNAME}/{nome_repo}.git"
    )

    init = _git(["git", "init", "-b", "main"], pasta_site, obrigatorio=False)
    if init.returncode != 0:  # git antigo sem suporte a '-b'
        _git(["git", "init"], pasta_site)
        _git(["git", "checkout", "-b", "main"], pasta_site, obrigatorio=False)

    _git(["git", "config", "user.email", "archivly-bot@archivly.app"], pasta_site)
    _git(["git", "config", "user.name", "Archivly Bot"], pasta_site)
    _git(["git", "add", "."], pasta_site)
    _git(["git", "commit", "-m", "Publicação automática via Archivly"], pasta_site)
    _git(["git", "remote", "add", "origin", url_com_token], pasta_site, obrigatorio=False)
    _git(["git", "push", "-u", "origin", "main", "--force"], pasta_site)


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
        if resposta.status_code in (401, 403, 404):
            raise ErroPublicacao(
                "Sem permissão para ativar o GitHub Pages. "
                "O token precisa de 'Pages: Read and write'."
            )
        raise ErroPublicacao(
            f"Erro ao ativar o GitHub Pages ({resposta.status_code}): {resposta.text}"
        )

    return f"https://{GITHUB_USERNAME}.github.io/{nome_repo}/"


def publicar_site_completo(pasta_site: str, nome_repo_sugerido: str) -> dict:
    """
    Função principal chamada pelo backend: junta os 3 passos e devolve
    o resultado final (nome do repo criado + URL do site).
    """
    if not github_configurado():
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
