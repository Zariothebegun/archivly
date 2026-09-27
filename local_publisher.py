"""
local_publisher.py
-------------------
Plano B de publicação: quando o GITHUB_TOKEN não está configurado (ou quando
só queres ver o site a funcionar já), o site gerado é copiado para
`data/sites/<slug>/` e servido pela própria aplicação em `/sites/<slug>/`.

Vantagens: zero configuração, link imediato, funciona em qualquer hosting.
Limitação: o site vive no mesmo serviço da app (se o serviço for reiniciado
num plano gratuito sem disco persistente, é regenerado na publicação seguinte).
"""

import os
import shutil

PASTA_SITES = os.getenv("LOCAL_SITES_DIR", os.path.join("data", "sites"))


def publicar_localmente(pasta_public: str, slug: str) -> str:
    """
    Copia o conteúdo gerado para a pasta de sites locais.
    Devolve o caminho relativo onde o site ficou ('/sites/<slug>/').
    """
    destino = os.path.join(PASTA_SITES, slug)
    if os.path.exists(destino):
        shutil.rmtree(destino)
    os.makedirs(PASTA_SITES, exist_ok=True)
    shutil.copytree(pasta_public, destino)
    return f"/sites/{slug}/"


def apagar_site_local(slug: str):
    """Remove um site publicado localmente."""
    destino = os.path.join(PASTA_SITES, slug)
    raiz = os.path.abspath(PASTA_SITES)
    caminho = os.path.abspath(destino)
    if caminho.startswith(raiz + os.sep) and os.path.isdir(caminho):
        shutil.rmtree(caminho, ignore_errors=True)
