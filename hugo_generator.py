"""
hugo_generator.py
------------------
Gera um site estático com o Hugo a partir da lista de ficheiros do utilizador.
O site final tem: grid de miniaturas, pesquisa por nome/data e filtro por tipo.
Os ficheiros originais continuam alojados no R2 - o Hugo só gera as páginas
que apontam para lá, o que mantém o repositório do GitHub leve e rápido.
"""

import os
import json
import shutil
import subprocess


TEMPLATE_INDEX_HTML = """<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ .Site.Title }}</title>
<link rel="stylesheet" href="{{ "css/style.css" | relURL }}">
</head>
<body>
  <header class="topo">
    <h1>{{ .Site.Title }}</h1>
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

    <div id="grid" class="grid"></div>
    <p id="vazio" class="vazio" style="display:none;">Nenhum ficheiro encontrado.</p>
  </main>

  <footer>
    <p>Publicado com <a href="https://github.com" target="_blank">Archivly</a></p>
  </footer>

<script>
  const ficheiros = {{ .Site.Data.files | jsonify }};

  const grid = document.getElementById("grid");
  const inputPesquisa = document.getElementById("pesquisa");
  const selectTipo = document.getElementById("filtro-tipo");
  const vazio = document.getElementById("vazio");

  function iconePorTipo(tipo) {
    if (tipo === "video") return "🎬";
    if (tipo === "audio") return "🎵";
    if (tipo === "documento") return "📄";
    return "🖼️";
  }

  function renderizar() {
    const termo = inputPesquisa.value.trim().toLowerCase();
    const tipo = selectTipo.value;

    const filtrados = ficheiros.filter(f => {
      const correspondeTermo = f.nome.toLowerCase().includes(termo) || f.data.includes(termo);
      const correspondeTipo = tipo === "todos" || f.tipo === tipo;
      return correspondeTermo && correspondeTipo;
    });

    grid.innerHTML = "";
    vazio.style.display = filtrados.length === 0 ? "block" : "none";

    filtrados.forEach(f => {
      const card = document.createElement("a");
      card.className = "card";
      card.href = f.url;
      card.target = "_blank";
      card.rel = "noopener";

      const miniatura = f.miniatura
        ? `<img src="${f.miniatura}" alt="${f.nome}" loading="lazy">`
        : `<div class="sem-miniatura">${iconePorTipo(f.tipo)}</div>`;

      card.innerHTML = `
        ${miniatura}
        <div class="card-info">
          <span class="card-nome">${f.nome}</span>
          <span class="card-data">${f.data}</span>
        </div>
      `;
      grid.appendChild(card);
    });
  }

  inputPesquisa.addEventListener("input", renderizar);
  selectTipo.addEventListener("change", renderizar);
  renderizar();
</script>
</body>
</html>
"""

TEMPLATE_STYLE_CSS = """
:root {
  --preto: #0b0f0c;
  --preto-suave: #141a15;
  --verde: #39d353;
  --verde-escuro: #1a5c2a;
  --texto: #e6f4ea;
  --texto-suave: #9db8a4;
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

.subtitulo {
  color: var(--texto-suave);
  margin-top: 8px;
}

main {
  max-width: 1100px;
  margin: 0 auto;
  padding: 24px;
}

.controlos {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}

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

.card:hover {
  border-color: var(--verde);
}

.card img {
  width: 100%;
  height: 140px;
  object-fit: cover;
  display: block;
}

.sem-miniatura {
  height: 140px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 2.5rem;
  background: var(--preto);
}

.card-info {
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.card-nome {
  font-size: 0.9rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-data {
  font-size: 0.75rem;
  color: var(--texto-suave);
}

.vazio {
  text-align: center;
  color: var(--texto-suave);
  padding: 48px 0;
}

footer {
  text-align: center;
  padding: 32px;
  color: var(--texto-suave);
  font-size: 0.85rem;
}

footer a { color: var(--verde); }
"""


def gerar_site_hugo(pasta_projeto: str, nome_site: str, base_url: str, lista_ficheiros: list) -> str:
    """
    Cria um projeto Hugo completo numa pasta temporária, com os dados do
    utilizador, e faz o build. Devolve o caminho da pasta 'public' gerada
    (pronta a ser publicada no GitHub Pages).
    """
    if os.path.exists(pasta_projeto):
        shutil.rmtree(pasta_projeto)

    # 1. Cria o esqueleto do site com o binário do Hugo
    subprocess.run(
        ["hugo", "new", "site", pasta_projeto, "--force"],
        check=True, capture_output=True, text=True,
    )

    # 2. Ficheiro de configuração
    config_toml = f"""
baseURL = "{base_url}"
languageCode = "pt-pt"
title = "{nome_site}"
"""
    with open(os.path.join(pasta_projeto, "hugo.toml"), "w", encoding="utf-8") as f:
        f.write(config_toml.strip() + "\n")

    # 3. Conteúdo da página inicial (obrigatório para o Hugo gerar a home)
    os.makedirs(os.path.join(pasta_projeto, "content"), exist_ok=True)
    with open(os.path.join(pasta_projeto, "content", "_index.md"), "w", encoding="utf-8") as f:
        f.write(f"---\ntitle: \"{nome_site}\"\n---\n")

    # 4. Layout personalizado (verde/preto, grid, pesquisa e filtro)
    pasta_layouts = os.path.join(pasta_projeto, "layouts")
    os.makedirs(pasta_layouts, exist_ok=True)
    with open(os.path.join(pasta_layouts, "index.html"), "w", encoding="utf-8") as f:
        f.write(TEMPLATE_INDEX_HTML)

    # 5. CSS estático
    pasta_css = os.path.join(pasta_projeto, "static", "css")
    os.makedirs(pasta_css, exist_ok=True)
    with open(os.path.join(pasta_css, "style.css"), "w", encoding="utf-8") as f:
        f.write(TEMPLATE_STYLE_CSS)

    # 6. Dados dos ficheiros (o Hugo lê isto e injeta no HTML como JSON)
    pasta_data = os.path.join(pasta_projeto, "data")
    os.makedirs(pasta_data, exist_ok=True)
    with open(os.path.join(pasta_data, "files.json"), "w", encoding="utf-8") as f:
        json.dump(lista_ficheiros, f, ensure_ascii=False)

    # 7. Build do site estático
    resultado = subprocess.run(
        ["hugo", "--minify", "-d", "public"],
        cwd=pasta_projeto, capture_output=True, text=True,
    )
    if resultado.returncode != 0:
        raise RuntimeError(f"Erro ao gerar o site com Hugo: {resultado.stderr}")

    return os.path.join(pasta_projeto, "public")
