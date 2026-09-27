/* ============================================================
   app.js - funções partilhadas do frontend do Archivly
   (sessão, chamadas à API, formatação e avisos ao utilizador)
   ============================================================ */

const CHAVE_TOKEN = "archivly_token";
const CHAVE_EMAIL = "archivly_email";

/* ---------- Sessão ---------- */

function obterToken() {
  return localStorage.getItem(CHAVE_TOKEN);
}

function guardarSessao(token, email) {
  localStorage.setItem(CHAVE_TOKEN, token);
  localStorage.setItem(CHAVE_EMAIL, email || "");
}

function terminarSessao() {
  localStorage.removeItem(CHAVE_TOKEN);
  localStorage.removeItem(CHAVE_EMAIL);
  window.location.href = "/";
}

function exigirSessao() {
  if (!obterToken()) {
    window.location.href = "/";
    return false;
  }
  return true;
}

/* ---------- API ---------- */

async function api(caminho, opcoes = {}) {
  const cabecalhos = Object.assign({}, opcoes.headers || {});
  const token = obterToken();
  if (token) cabecalhos["Authorization"] = "Bearer " + token;

  // Só definimos Content-Type para JSON; para FormData o browser põe o boundary
  if (opcoes.body && !(opcoes.body instanceof FormData) && !cabecalhos["Content-Type"]) {
    cabecalhos["Content-Type"] = "application/json";
  }

  const resposta = await fetch(caminho, Object.assign({}, opcoes, { headers: cabecalhos }));

  let dados = null;
  try {
    dados = await resposta.json();
  } catch (e) {
    dados = null;
  }

  if (resposta.status === 401 && window.location.pathname !== "/") {
    terminarSessao();
    throw new Error("Sessão expirada. Faz login novamente.");
  }

  if (!resposta.ok) {
    const detalhe = dados && dados.detail ? dados.detail : "Erro " + resposta.status;
    throw new Error(typeof detalhe === "string" ? detalhe : JSON.stringify(detalhe));
  }

  return dados;
}

/* ---------- Helpers de interface ---------- */

function toast(mensagem, tipoErro = false) {
  let caixa = document.getElementById("toast");
  if (!caixa) {
    caixa = document.createElement("div");
    caixa.id = "toast";
    document.body.appendChild(caixa);
  }
  caixa.textContent = mensagem;
  caixa.className = tipoErro ? "visivel erro" : "visivel";
  clearTimeout(caixa._temporizador);
  caixa._temporizador = setTimeout(() => { caixa.className = tipoErro ? "erro" : ""; }, 4000);
}

function formatoTamanho(bytes) {
  if (!bytes && bytes !== 0) return "";
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(0) + " KB";
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  return (bytes / (1024 * 1024 * 1024)).toFixed(2) + " GB";
}

function iconePorTipo(tipo) {
  if (tipo === "video") return "\u{1F3AC}";
  if (tipo === "audio") return "\u{1F3B5}";
  if (tipo === "documento") return "\u{1F4C4}";
  return "\u{1F5BC}\uFE0F";
}

function nomeTipo(tipo) {
  return { imagem: "Imagem", video: "Vídeo", audio: "Áudio", documento: "Doc" }[tipo] || tipo;
}

function dataCurta(texto) {
  if (!texto) return "";
  return String(texto).slice(0, 10);
}
