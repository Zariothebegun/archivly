"""
smoke_test.py
--------------
Teste rápido de ponta a ponta: cria conta, envia ficheiros, publica o site
e confirma que tudo responde. Serve tanto para testar localmente como para
verificar que o deploy ficou a funcionar.

Uso:
    python smoke_test.py                          # testa http://127.0.0.1:8000
    python smoke_test.py https://a-tua-app.onrender.com

Não precisa de pytest nem de dependências extra (usa apenas 'requests').
"""

import io
import sys
import uuid

import requests

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
EMAIL = f"smoke-{uuid.uuid4().hex[:8]}@archivly.app"
PASSWORD = "teste123456"
FALHAS = []


def passo(nome: str, ok: bool, detalhe: str = ""):
    simbolo = "OK  " if ok else "FALHA"
    print(f"[{simbolo}] {nome}" + (f" -> {detalhe}" if detalhe else ""))
    if not ok:
        FALHAS.append(nome)


def imagem_png() -> bytes:
    """Gera um PNG minúsculo sem depender do Pillow."""
    import base64
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmM"
        "IQAAAABJRU5ErkJggg=="
    )


def main():
    print(f"\nA testar {BASE}\n" + "-" * 46)

    r = requests.get(f"{BASE}/healthz", timeout=90)
    passo("health check (/healthz)", r.status_code == 200, r.text[:80])

    r = requests.get(f"{BASE}/", timeout=30)
    passo("frontend (/)", r.status_code == 200 and "Archivly" in r.text, f"HTTP {r.status_code}")

    r = requests.get(f"{BASE}/static/style.css", timeout=30)
    passo("css (/static/style.css)", r.status_code == 200, f"HTTP {r.status_code}")

    r = requests.post(f"{BASE}/api/registo", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    passo("registo (/api/registo)", r.status_code == 200 and "token" in r.text, r.text[:120])
    if r.status_code != 200:
        return finalizar()

    token = r.json()["token"]
    cabecalhos = {"Authorization": f"Bearer {token}"}

    r = requests.post(f"{BASE}/api/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    passo("login (/api/login)", r.status_code == 200, f"HTTP {r.status_code}")

    r = requests.get(f"{BASE}/api/estado", headers=cabecalhos, timeout=30)
    passo("estado (/api/estado)", r.status_code == 200, r.text[:140])
    estado = r.json() if r.status_code == 200 else {}

    ficheiro = {"ficheiros": ("teste.png", io.BytesIO(imagem_png()), "image/png")}
    r = requests.post(f"{BASE}/api/upload", headers=cabecalhos, files=ficheiro, timeout=120)
    passo("upload (/api/upload)", r.status_code == 200, r.text[:140])
    if r.status_code != 200:
        return finalizar()

    r = requests.get(f"{BASE}/api/ficheiros", headers=cabecalhos, timeout=30)
    ok = r.status_code == 200 and len(r.json()["ficheiros"]) >= 1
    passo("listar ficheiros (/api/ficheiros)", ok, f"HTTP {r.status_code}")

    nome_site = f"Smoke {uuid.uuid4().hex[:6]}"
    r = requests.post(f"{BASE}/api/publicar", headers=cabecalhos, json={"site_name": nome_site}, timeout=300)
    passo("publicar (/api/publicar)", r.status_code == 200, r.text[:200])
    if r.status_code != 200:
        return finalizar()

    url_site = r.json()["site_url"]
    if url_site.startswith("/"):
        url_site = f"{BASE}{url_site}"
    r = requests.get(url_site, timeout=60)
    passo("site publicado acessível", r.status_code == 200 and "teste.png" in r.text, f"{url_site} HTTP {r.status_code}")

    r = requests.get(f"{BASE}/api/sites", headers=cabecalhos, timeout=30)
    passo("listar sites (/api/sites)", r.status_code == 200, f"HTTP {r.status_code}")

    if estado.get("armazenamento") == "local":
        passo("modo de armazenamento", True, "local (sem R2 configurado)")
    if not estado.get("github_pages"):
        passo("modo de publicação", True, "local (sem GITHUB_TOKEN configurado)")

    return finalizar()


def finalizar():
    print("-" * 46)
    if FALHAS:
        print(f"Resultado: {len(FALHAS)} falha(s): {', '.join(FALHAS)}")
        return 1
    print("Resultado: TUDO OK - a aplicação está funcional.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
