"""
hugo_generator.py
------------------
Gera o site estático a partir da lista de ficheiros do utilizador.
O site final tem: grid de miniaturas, pesquisa por nome/data e filtro por tipo.

Dois motores, escolhidos automaticamente:

1. **Hugo** (se o binário estiver instalado - é o que o Dockerfile faz).
2. **Gerador próprio em Python** (fallback) - produz exatamente o mesmo HTML/CSS/JS
   sem depender de nada instalado. É o que permite correr o Archivly num
   serviço gratuito sem Docker, ou no telemóvel/PC sem preparar ambiente.

Os ficheiros originais continuam alojados no armazenamento (R2 ou local):
o site gerado só tem as páginas que apontam para lá, o que mantém o
repositório do GitHub leve e rápido.
"""

import json
import os
import shutil
import subprocess


# ============================================================
# Peças partilhadas pelos dois motores (Hugo e Python)
# ============================================================

CSS_SITE = """
:root {
  --preto: #f7f7f5;
  --preto-suave: #ffffff;
  --verde: #37839d;
  --verde-escuro: #e1e4e2;
  --texto: #272a2b;
  --texto-suave: #737a7c;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--preto);
  color: var(--texto);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

.topo {
  padding: 48px 24px 24px;
  text-align: center;
  border-bottom: 1px solid var(--preto-suave);
}

.topo h1 {
  margin: 0;
  color: var(--verde);
  font-size: 2rem;
  letter-spacing: -0.02em;
}

.subtitulo { color: var(--texto-suave); margin-top: 8px; }

main { max-width: 1100px; margin: 0 auto; padding: 24px; }

.controlos { display: flex; gap: 12px; margin-bottom: 24px; flex-wrap: wrap; }

#pesquisa {
  flex: 1;
  min-width: 200px;
  padding: 12px 16px;
  background: var(--preto-suave);
  border: 1px solid var(--verde-escuro);
  border-radius: 8px;
  color: var(--texto);
  font-size: 1rem;
}

#filtro-tipo {
  padding: 12px 16px;
  background: var(--preto-suave);
  border: 1px solid var(--verde-escuro);
  border-radius: 8px;
  color: var(--texto);
}

.contagem { color: var(--texto-suave); font-size: 0.85rem; margin: 0 0 16px; }

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 16px;
}

.card {
  background: var(--preto-suave);
  border: 1px solid var(--verde-escuro);
  border-radius: 10px;
  overflow: hidden;
  text-decoration: none;
  color: var(--texto);
  transition: border-color 0.15s ease;
}

.card:hover { border-color: var(--verde); }

.card img { width: 100%; height: 140px; object-fit: cover; display: block; }

.sem-miniatura {
  height: 140px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 2.5rem;
  background: var(--preto);
}

.card-info { padding: 10px 12px; display: flex; flex-direction: column; gap: 4px; }

.card-nome {
  font-size: 0.9rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-data { font-size: 0.75rem; color: var(--texto-suave); }

.vazio { text-align: center; color: var(--texto-suave); padding: 48px 0; }

footer {
  text-align: center;
  padding: 32px;
  color: var(--texto-suave);
  font-size: 0.85rem;
}

footer a { color: var(--verde); } :root{--verde:#37839d} body{background:#fff;color:#2d302f;font-family:Georgia,'Times New Roman',serif}.topo{max-width:none;min-height:390px;margin:0;padding:280px max(6vw,28px) 28px;text-align:left;background:linear-gradient(to bottom,rgba(0,0,0,.05) 0,rgba(0,0,0,.12) 230px,#fff 231px),url('https://images.unsplash.com/photo-1507842217343-583bb7270b66?auto=format&fit=crop&w=2200&q=85') center top/cover no-repeat;border:0}.topo h1{color:#292b2a;font:600 clamp(2.4rem,4vw,3rem) Georgia,serif;letter-spacing:-.04em}.subtitulo{color:#757b7c;margin-top:8px}main{max-width:1600px;margin:0 auto;padding:24px max(6vw,28px) 72px;display:grid;grid-template-columns:minmax(210px,260px) minmax(0,1fr);grid-template-rows:auto auto 1fr;column-gap:30px;align-items:start}.controlos{grid-column:1;grid-row:1 / span 3;display:flex;flex-direction:column;gap:12px;margin:0;padding:20px;background:#fff;border:1px solid #e8e9e7;border-radius:12px;box-shadow:0 2px 8px #20202008}.controlos:before{content:'Categorias';font:bold 1.05rem Georgia,serif;color:#313636;padding:0 0 12px;border-bottom:1px solid #e6e8e6}#pesquisa,#filtro-tipo{width:100%;min-width:0;min-height:44px;padding:10px 12px;background:#fff;border:1px solid #e2e5e4;border-radius:7px;color:#454a4b;font:14px Arial,sans-serif}#pesquisa:focus,#filtro-tipo:focus{outline:2px solid #c8e1eb;border-color:#6ca7b9}.contagem{grid-column:2;grid-row:1;color:#5c6668;font:13px Arial,sans-serif;letter-spacing:.04em;text-transform:none;margin:4px 0 15px}.grid{grid-column:2;grid-row:2;grid-row-end:4;grid-template-columns:repeat(auto-fill,minmax(min(100%,270px),1fr));gap:18px}.card{background:#fff;border:1px solid #e6e7e5;border-radius:13px;box-shadow:0 2px 8px #1a1a1a0a;color:#303334}.card:hover{border-color:#abcbd5;transform:translateY(-3px);box-shadow:0 9px 24px #192b3018}.card img,.sem-miniatura{height:clamp(190px,19vw,265px)}.card img{object-fit:contain;background:#fafaf9;filter:none}.sem-miniatura{background:#f5f7f6;color:#438ba0}.card-info{padding:13px 15px 16px}.card-nome{font:16px Georgia,serif;color:#333738}.card-data{color:#899194;font:12px Arial,sans-serif}.vazio{grid-column:2;grid-row:2;color:#666;font:20px Georgia,serif}footer{max-width:none;background:#fff;color:#868d8e;border-color:#eceeed}@media(max-width:760px){.topo{min-height:310px;padding:224px 22px 22px;background-size:auto,auto 210px}.topo h1{font-size:2.2rem}main{display:flex;flex-direction:column;padding:18px 16px 50px;gap:16px}.controlos{width:100%;padding:14px;flex-direction:row;flex-wrap:wrap}.controlos:before{width:100%}#pesquisa,#filtro-tipo{width:100%;flex:1 1 100%}.contagem,.grid,.vazio{width:100%}.grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.card img,.sem-miniatura{height:165px}.card-info{padding:10px}.card-nome{font-size:14px}}@media(prefers-reduced-motion:reduce){*,*::before,*::after{scroll-behavior:auto!important;transition:none!important;animation:none!important}}
"""


def _script_site(expressao_dados: str) -> str:
    """
    JavaScript da página gerada. `expressao_dados` é o JSON dos ficheiros
    (no Hugo é `{{ .Site.Data.files | jsonify }}`, no fallback é o JSON literal).
    Usa textContent em vez de innerHTML nos dados do utilizador: um nome de
    ficheiro com HTML nunca é executado como código.
    """
    return """
  const ficheiros = """ + expressao_dados + """;

  const grid = document.getElementById("grid");
  const inputPesquisa = document.getElementById("pesquisa");
  const selectTipo = document.getElementById("filtro-tipo");
  const vazio = document.getElementById("vazio");
  const contagem = document.getElementById("contagem");

  function iconePorTipo(tipo) {
    if (tipo === "video") return "\\u{1F3AC}";
    if (tipo === "audio") return "\\u{1F3B5}";
    if (tipo === "documento") return "\\u{1F4C4}";
    return "\\u{1F5BC}\\uFE0F";
  }

  function renderizar() {
    const termo = inputPesquisa.value.trim().toLowerCase();
    const tipo = selectTipo.value;

    const filtrados = ficheiros.filter(f => {
      const nome = (f.nome || "").toLowerCase();
      const data = (f.data || "").toLowerCase();
      const correspondeTermo = !termo || nome.includes(termo) || data.includes(termo);
      const correspondeTipo = tipo === "todos" || f.tipo === tipo;
      return correspondeTermo && correspondeTipo;
    });

    grid.innerHTML = "";
    vazio.style.display = filtrados.length === 0 ? "block" : "none";
    contagem.textContent = filtrados.length === 1
      ? "1 ficheiro"
      : filtrados.length + " ficheiros";

    filtrados.forEach(f => {
      const card = document.createElement("a");
      card.className = "card";
      card.href = f.url || "#";
      card.target = "_blank";
      card.rel = "noopener";

      if (f.miniatura) {
        const img = document.createElement("img");
        img.src = f.miniatura;
        img.alt = f.nome || "";
        img.loading = "lazy";
        img.onerror = () => {
          const fallback = document.createElement("div");
          fallback.className = "sem-miniatura";
          fallback.textContent = iconePorTipo(f.tipo);
          img.replaceWith(fallback);
        };
        card.appendChild(img);
      } else {
        const semMiniatura = document.createElement("div");
        semMiniatura.className = "sem-miniatura";
        semMiniatura.textContent = iconePorTipo(f.tipo);
        card.appendChild(semMiniatura);
      }

      const info = document.createElement("div");
      info.className = "card-info";

      const nome = document.createElement("span");
      nome.className = "card-nome";
      nome.textContent = f.nome || "sem nome";

      const data = document.createElement("span");
      data.className = "card-data";
      data.textContent = f.data || "";

      info.appendChild(nome);
      info.appendChild(data);
      card.appendChild(info);
      grid.appendChild(card);
    });
  }

  inputPesquisa.addEventListener("input", renderizar);
  selectTipo.addEventListener("change", renderizar);
  renderizar();
"""


def _pagina(titulo: str, css_href: str, expressao_dados: str) -> str:
    """HTML da página inicial, partilhado pelos dois motores."""
    return f"""<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{titulo}</title>
<link rel="stylesheet" href="{css_href}">
</head>
<body>
  <header class="topo">
    <h1>{titulo}</h1>
    <p class="subtitulo">Arquivo digital gerado com Archivly</p>
  </header>

  <main>
    <div class="controlos">
      <input type="text" id="pesquisa" placeholder="Pesquisar por nome ou data...">
      <select id="filtro-tipo">
        <option value="todos">Todos os tipos</option>
        <option value="imagem">Imagens</option>
        <option value="video">Vídeos</option>
        <option value="audio">Áudio</option>
        <option value="documento">Documentos</option>
      </select>
    </div>

    <p id="contagem" class="contagem"></p>
    <div id="grid" class="grid"></div>
    <p id="vazio" class="vazio" style="display:none;">Nenhum ficheiro encontrado.</p>
  </main>

  <footer>
    <p>Publicado com Archivly</p>
  </footer>

<script>{_script_site(expressao_dados)}</script>
</body>
</html>
"""


def hugo_disponivel() -> bool:
    """True se o binário 'hugo' existir no sistema."""
    return shutil.which("hugo") is not None


def _titulo_seguro(texto: str) -> str:
    """Escapa o título para não rebentar com o HTML/TOML."""
    return (
        texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def _json_seguro(lista: list) -> str:
    """JSON para injetar num <script>, sem permitir fechar a tag."""
    return json.dumps(lista, ensure_ascii=False).replace("</", "<\\/")


# ============================================================
# Motor 1 - Hugo
# ============================================================

def _gerar_com_hugo(pasta_projeto: str, nome_site: str, base_url: str, lista_ficheiros: list) -> str:
    """Cria um projeto Hugo completo e faz o build. Devolve a pasta 'public'."""
    if os.path.exists(pasta_projeto):
        shutil.rmtree(pasta_projeto)

    subprocess.run(
        ["hugo", "new", "site", pasta_projeto, "--force"],
        check=True, capture_output=True, text=True,
    )

    titulo_toml = nome_site.replace('"', "'")
    with open(os.path.join(pasta_projeto, "hugo.toml"), "w", encoding="utf-8") as f:
        f.write(
            f'baseURL = "{base_url}"\n'
            f'languageCode = "pt-pt"\n'
            f'title = "{titulo_toml}"\n'
        )

    os.makedirs(os.path.join(pasta_projeto, "content"), exist_ok=True)
    with open(os.path.join(pasta_projeto, "content", "_index.md"), "w", encoding="utf-8") as f:
        f.write(f'---\ntitle: "{titulo_toml}"\n---\n')

    pasta_layouts = os.path.join(pasta_projeto, "layouts")
    os.makedirs(pasta_layouts, exist_ok=True)
    with open(os.path.join(pasta_layouts, "index.html"), "w", encoding="utf-8") as f:
        f.write(_pagina("{{ .Site.Title }}", '{{ "css/style.css" | relURL }}',
                        "{{ .Site.Data.files | jsonify }}"))

    pasta_css = os.path.join(pasta_projeto, "static", "css")
    os.makedirs(pasta_css, exist_ok=True)
    with open(os.path.join(pasta_css, "style.css"), "w", encoding="utf-8") as f:
        f.write(CSS_SITE)

    pasta_data = os.path.join(pasta_projeto, "data")
    os.makedirs(pasta_data, exist_ok=True)
    with open(os.path.join(pasta_data, "files.json"), "w", encoding="utf-8") as f:
        json.dump(lista_ficheiros, f, ensure_ascii=False)

    resultado = subprocess.run(
        ["hugo", "--minify", "-d", "public"],
        cwd=pasta_projeto, capture_output=True, text=True,
    )
    if resultado.returncode != 0:
        raise RuntimeError(f"Erro ao gerar o site com Hugo: {resultado.stderr}")

    return os.path.join(pasta_projeto, "public")


# ============================================================
# Motor 2 - Gerador em Python puro (sem dependências externas)
# ============================================================

def _gerar_com_python(pasta_public: str, nome_site: str, lista_ficheiros: list) -> str:
    """Escreve diretamente o site estático. Devolve a pasta com o conteúdo final."""
    if os.path.exists(pasta_public):
        shutil.rmtree(pasta_public)
    os.makedirs(os.path.join(pasta_public, "css"), exist_ok=True)

    with open(os.path.join(pasta_public, "index.html"), "w", encoding="utf-8") as f:
        f.write(_pagina(_titulo_seguro(nome_site), "css/style.css", _json_seguro(lista_ficheiros)))

    with open(os.path.join(pasta_public, "css", "style.css"), "w", encoding="utf-8") as f:
        f.write(CSS_SITE)

    return pasta_public


# ============================================================
# Função principal
# ============================================================

def gerar_site_hugo(pasta_projeto: str, nome_site: str, base_url: str, lista_ficheiros: list) -> str:
    """
    Gera o site estático e devolve o caminho da pasta pronta a publicar.
    Usa Hugo quando existe; caso contrário usa o gerador em Python.
    """
    if hugo_disponivel():
        try:
            pasta_public = _gerar_com_hugo(pasta_projeto, nome_site, base_url, lista_ficheiros)
            # Rede de segurança: confirma que o Hugo produziu mesmo a página inicial
            if os.path.isfile(os.path.join(pasta_public, "index.html")):
                return pasta_public
            print("[hugo_generator] O Hugo não gerou index.html; a usar o gerador Python.")
        except Exception as erro:
            print(f"[hugo_generator] Hugo falhou ({erro}); a usar o gerador Python.")

    return _gerar_com_python(os.path.join(pasta_projeto, "public"), nome_site, lista_ficheiros)


# Nome mais honesto para quem não quer saber do motor usado
gerar_site = gerar_site_hugo
