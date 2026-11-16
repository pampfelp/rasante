"use strict";

const $ = (s) => document.querySelector(s);
const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const AEROPORTOS = {
  BEL: "Belém", MAO: "Manaus", STM: "Santarém", MCP: "Macapá", SLZ: "São Luís", THE: "Teresina",
  FOR: "Fortaleza", NAT: "Natal", JPA: "João Pessoa", REC: "Recife", MCZ: "Maceió", AJU: "Aracaju",
  SSA: "Salvador", IOS: "Ilhéus", BPS: "Porto Seguro", IMP: "Imperatriz", MAB: "Marabá", PMW: "Palmas",
  BSB: "Brasília", GYN: "Goiânia", CGB: "Cuiabá", CGR: "Campo Grande", UDI: "Uberlândia",
  CNF: "Belo Horizonte", VIX: "Vitória", GIG: "Rio (Galeão)", SDU: "Rio (Santos Dumont)",
  GRU: "São Paulo (Guarulhos)", CGH: "São Paulo (Congonhas)", VCP: "Campinas", RAO: "Ribeirão Preto",
  LDB: "Londrina", MGF: "Maringá", CWB: "Curitiba", IGU: "Foz do Iguaçu", JOI: "Joinville",
  NVT: "Navegantes", FLN: "Florianópolis", POA: "Porto Alegre", PVH: "Porto Velho", RBR: "Rio Branco",
  BVB: "Boa Vista", EZE: "Buenos Aires", SCL: "Santiago", LIM: "Lima", BOG: "Bogotá", PTY: "Panamá",
  MIA: "Miami", MCO: "Orlando", JFK: "Nova York", LIS: "Lisboa", OPO: "Porto", MAD: "Madri", CDG: "Paris",
};

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const br = (v) => "R$ " + Number(v).toLocaleString("pt-BR", { maximumFractionDigits: 0 });
const ico = (id) => `<svg><use href="#${id}"/></svg>`;
function dataCurta(iso) {
  if (!iso) return "sem volta";
  const [, m, d] = iso.split("-").map(Number);
  return `${d} ${MESES[m - 1]}`;
}
function hojeMais(dias) {
  const d = new Date();
  d.setDate(d.getDate() + dias);
  return d.toISOString().slice(0, 10);
}
const guardar = (k, v) => { try { localStorage.setItem("rasante_" + k, JSON.stringify(v)); } catch (e) { /* sem armazenamento */ } };
const lembrar = (k) => { try { return JSON.parse(localStorage.getItem("rasante_" + k)); } catch (e) { return null; } };

async function api(metodo, caminho, corpo) {
  const r = await fetch(caminho, {
    method: metodo,
    headers: corpo ? { "Content-Type": "application/json" } : {},
    body: corpo ? JSON.stringify(corpo) : undefined,
  });
  const dados = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(dados.erro || `Erro ${r.status}`);
  return dados;
}

/* ---------- toast e modal ---------- */
function toast(msg, erro = false) {
  const t = document.createElement("div");
  t.className = "toast" + (erro ? " erro" : "");
  t.textContent = msg;
  $("#toasts").append(t);
  setTimeout(() => t.remove(), erro ? 6000 : 3500);
}

let fecharModalAtual = null;
function modal(titulo, corpo, acoes) {
  $("#modal-titulo").textContent = titulo;
  $("#modal-corpo").innerHTML = corpo;
  const caixa = $("#modal-acoes");
  caixa.innerHTML = "";
  for (const a of acoes) {
    const b = document.createElement("button");
    b.className = "botao " + (a.classe || "");
    b.textContent = a.rotulo;
    b.addEventListener("click", async () => {
      if (!a.fn) return fecharModal();
      b.disabled = true;
      try { if ((await a.fn(b)) !== false) fecharModal(); } catch (e) { toast(e.message, true); } finally { b.disabled = false; }
    });
    caixa.append(b);
  }
  $("#modal-fundo").hidden = false;
  const foco = $("#modal-corpo input") || caixa.querySelector(".prim") || caixa.lastChild;
  foco && foco.focus();
  return new Promise((ok) => { fecharModalAtual = ok; });
}
function fecharModal(valor) {
  $("#modal-fundo").hidden = true;
  if (fecharModalAtual) { fecharModalAtual(valor); fecharModalAtual = null; }
}
function confirmar(titulo, texto, rotulo = "Confirmar") {
  let sim = false;
  return modal(titulo, `<p>${esc(texto)}</p>`, [
    { rotulo: "Cancelar" },
    { rotulo, classe: "prim", fn: () => { sim = true; } },
  ]).then(() => sim);
}
$("#modal-fundo").addEventListener("click", (e) => { if (e.target.id === "modal-fundo" || e.target.closest("[data-fechar]")) fecharModal(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("#modal-fundo").hidden) fecharModal(); });

/* ---------- cena do voo rasante ---------- */
function desenharCena() {
  const W = 1376, H = 135;
  let s = 7;
  const rnd = () => ((s = (s * 9301 + 49297) % 233280) / 233280);
  let predios = "";
  // horizonte de prédios concentrado no meio, como na imagem
  for (let x = 170; x < 1376; ) {
    const meio = Math.exp(-Math.pow((x - 700) / 330, 2));
    const w = 14 + rnd() * 34;
    const h = 8 + (rnd() * 70 + 12) * (0.25 + meio);
    if (rnd() > 0.15) predios += `<rect class="predio" x="${x.toFixed(0)}" y="${(H - h).toFixed(0)}" width="${w.toFixed(0)}" height="${h.toFixed(0)}"/>`;
    if (meio > 0.5 && rnd() > 0.82) predios += `<rect class="predio" x="${(x + w / 2 - 2).toFixed(0)}" y="${(H - h - 22).toFixed(0)}" width="4" height="22"/>`;
    x += w + rnd() * 6;
  }
  const rota = `M0 22 C 380 40, 760 88, 1110 112`;
  $("#cena").innerHTML = `
    ${predios}
    <path class="brilho" d="${rota}"/>
    <path class="rota-verde" d="${rota}"/>
    <path class="rota-laranja" d="M1126 112 C 1220 112, 1300 108, 1376 104"/>
    <g transform="translate(1104 100) rotate(90 12 12)"><use href="#i-aviao" width="24" height="24" style="color:var(--accent)"/></g>`;
}

/* ---------- busca ---------- */
const campos = { origem: $("#origem"), destino: $("#destino"), ida: $("#ida"), volta: $("#volta") };

function mostrarDatas() {
  $("#ida-btn").textContent = dataCurta(campos.ida.value);
  $("#volta-btn").textContent = dataCurta(campos.volta.value);
  $("#busca").classList.toggle("tem-volta", !!campos.volta.value);
}
for (const b of [$("#ida-btn"), $("#volta-btn")]) {
  b.addEventListener("click", () => {
    const alvo = campos[b.dataset.alvo];
    alvo.min = hojeMais(0);
    if (b.dataset.alvo === "volta" && !alvo.value) alvo.value = campos.ida.value;
    try { alvo.showPicker(); } catch (e) { alvo.focus(); }
  });
}
campos.ida.addEventListener("change", () => {
  if (campos.volta.value && campos.volta.value < campos.ida.value) campos.volta.value = campos.ida.value;
  mostrarDatas();
});
campos.volta.addEventListener("change", mostrarDatas);
$("#volta-limpar").addEventListener("click", () => { campos.volta.value = ""; mostrarDatas(); });
for (const c of [campos.origem, campos.destino]) {
  c.addEventListener("focus", () => c.select());
  c.addEventListener("input", () => { c.value = c.value.toUpperCase().replace(/[^A-Z]/g, ""); });
}
$("#aeroportos").innerHTML = Object.entries(AEROPORTOS).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("");

/* ---------- pessoas ---------- */
let pax = [1, 0, 0]; // adultos, crianças, bebês de colo
const PAX_TIPOS = [
  ["Adultos", "12 anos ou mais"],
  ["Crianças", "2 a 11 anos"],
  ["Bebês de colo", "até 2 anos, no colo de um adulto"],
];
function paxCurto(p) {
  return [`${p[0]}a`, p[1] ? `${p[1]}c` : "", p[2] ? `${p[2]}b` : ""].filter(Boolean).join(" ");
}
function paxLongo(p) {
  const s = (n, um, varios) => `${n} ${n > 1 ? varios : um}`;
  const partes = [s(p[0], "adulto", "adultos")];
  if (p[1]) partes.push(s(p[1], "criança", "crianças"));
  if (p[2]) partes.push(s(p[2], "bebê de colo", "bebês de colo"));
  return partes.length > 1 ? partes.slice(0, -1).join(", ") + " e " + partes.at(-1) : partes[0];
}
function mostrarPax() {
  const b = $("#pax-btn");
  b.textContent = paxCurto(pax);
  b.title = paxLongo(pax);
  b.setAttribute("aria-label", "Pessoas: " + paxLongo(pax));
}
function paxValido(p) {
  return p[0] >= 1 && p[1] >= 0 && p[2] >= 0 && p[2] <= p[0] && p[0] + p[1] + p[2] <= 9;
}
$("#pax-btn").addEventListener("click", () => {
  const rascunho = [...pax];
  const desenhar = () => {
    $("#modal-corpo").querySelectorAll(".passo-pax").forEach((linha, i) => {
      linha.querySelector("output").textContent = rascunho[i];
      const menos = [...rascunho]; menos[i]--;
      const mais = [...rascunho]; mais[i]++;
      linha.querySelector("[data-d='-1']").disabled = !paxValido(menos);
      linha.querySelector("[data-d='1']").disabled = !paxValido(mais);
    });
  };
  modal("Pessoas", PAX_TIPOS.map(([nome, idade], i) => `
    <div class="passo-pax" data-i="${i}">
      <span><b>${nome}</b><small>${idade}</small></span>
      <button type="button" data-d="-1" aria-label="Menos ${nome.toLowerCase()}">−</button>
      <output>${rascunho[i]}</output>
      <button type="button" data-d="1" aria-label="Mais ${nome.toLowerCase()}">+</button>
    </div>`).join("") + `<p>Até 9 pessoas. Cada bebê de colo precisa de um adulto. O preço mostrado é o total do grupo.</p>`,
  [
    { rotulo: "Cancelar" },
    { rotulo: "Aplicar", classe: "prim", fn: () => { pax = rascunho; mostrarPax(); } },
  ]);
  $("#modal-corpo").addEventListener("click", (e) => {
    const b = e.target.closest("[data-d]");
    if (!b || b.disabled) return;
    const i = Number(b.closest(".passo-pax").dataset.i);
    rascunho[i] += Number(b.dataset.d);
    desenhar();
  });
  desenhar();
});

let ultimaCacada = null;
let cacando = false;

async function cacar(pedido) {
  if (cacando) return;
  pedido = pedido || {
    origem: campos.origem.value, destino: campos.destino.value,
    ida: campos.ida.value, volta: campos.volta.value || null, passageiros: [...pax],
  };
  if (pedido.origem.length !== 3) return toast("Origem: use o código de 3 letras do aeroporto (ex.: BEL).", true);
  if (pedido.destino.length !== 3) return toast("Destino: use o código de 3 letras do aeroporto (ex.: GRU).", true);
  if (!pedido.ida) return toast("Ida: escolha a data.", true);
  guardar("pedido", pedido);
  cacando = true;
  document.body.classList.add("cacando");
  $("#cacar").disabled = true;
  $("#resumo").hidden = true;
  $("#lista").innerHTML = `<div class="estado">Caçando <b>${esc(pedido.origem)} → ${esc(pedido.destino)}</b>, ${dataCurta(pedido.ida)}${pedido.volta ? " a " + dataCurta(pedido.volta) : ", só ida"}, ${esc(paxLongo(pedido.passageiros || [1, 0, 0]))}: compra normal, trechos separados, conexão montada, escala oculta e ida e volta jogando fora a volta.<br><span id="prog-txt">Preparando as buscas...</span><div class="progresso"><i id="prog"></i></div></div>`;
  try {
    const { id } = await api("POST", "/api/cacar", pedido);
    let estado;
    do {
      await new Promise((r) => setTimeout(r, 700));
      estado = await api("GET", "/api/cacar/" + id);
      if (estado.total) {
        $("#prog").style.width = (100 * estado.feitos / estado.total) + "%";
        $("#prog-txt").textContent = `${estado.feitos} de ${estado.total} buscas no Google Flights`;
      }
    } while (!estado.resultado && !estado.erro);
    if (estado.erro) throw new Error(estado.erro);
    ultimaCacada = estado.resultado;
    guardar("ultima", ultimaCacada);
    mostrarResultado(ultimaCacada);
  } catch (e) {
    $("#lista").innerHTML = `<div class="estado erro">${esc(e.message)}</div>`;
  } finally {
    cacando = false;
    document.body.classList.remove("cacando");
    $("#cacar").disabled = false;
  }
}
$("#busca").addEventListener("submit", (e) => { e.preventDefault(); cacar(); });

/* ---------- lista de possibilidades ---------- */
function horario(v) {
  const [d, h] = v.saida.split(" ");
  return `${h} ${dataCurta(d)}`;
}
function campo(rotulo, valores) {
  return `<span class="campo"><span class="rot">${rotulo}</span>${valores.map((v) => `<span class="val">${esc(v)}</span>`).join("")}</span>`;
}
function descPerna(p) {
  const v = p.voo;
  const voos = v.trechos.map((t) => `${t.voo} ${t.de}→${t.para} ${t.saida.slice(11)}`).join(", ");
  const desce = p.desce_em ? ` · <b>você desce em ${esc(p.desce_em)}</b>, bilhete até ${esc(v.destino)}` : "";
  return `<b>${esc(p.rotulo)}:</b> ${esc(v.companhias.join(" + "))} · ${esc(voos)} · chega ${esc(v.chegada.slice(11))}${desce}`;
}

function mostrarResultado(r) {
  const n = r.opcoes.length;
  const resumo = $("#resumo");
  resumo.hidden = false;
  const p = r.passageiros || [1, 0, 0];
  resumo.innerHTML = `<span><b>${n}</b> possibilidades para <b>${esc(r.origem)} → ${esc(r.destino)}</b>${p.reduce((a, b) => a + b, 0) > 1 ? `, ${esc(paxLongo(p))}` : ""}</span>
    ${r.referencia ? `<span>compra normal mais barata <b>${br(r.referencia)}</b></span>` : ""}
    ${r.direto_vazio && n ? `<span>o Google não monta esse voo; só conexão feita pelo Rasante</span>` : ""}
    <span>${r.buscas} buscas${r.falhas ? `, ${r.falhas} sem resposta` : ""} · ${esc(r.quando.slice(11))}</span>
    <button class="acao" id="vigiar">${ico("i-olho")} Vigiar esta rota</button>`;
  $("#vigiar").addEventListener("click", () => novaVigia(r));
  if (!n) {
    $("#lista").innerHTML = `<div class="estado">O Google Flights não mostrou voo de <b>${esc(r.origem)}</b> para <b>${esc(r.destino)}</b> em ${dataCurta(r.ida)}${r.hubs && r.hubs.length ? `, nem montando conexão em ${esc(r.hubs.join(" ou "))}` : ""}.<br>
      Pode ser data longe demais (as companhias abrem a venda cerca de 330 dias antes), código de aeroporto errado ou rota sem voo nesse dia. Tente outra data ou um aeroporto próximo.</div>`;
    return;
  }
  $("#lista").innerHTML = r.opcoes.map((o, i) => {
    const ida = o.pernas[0].voo;
    const pernas = o.pernas;
    const cias = pernas.map((p) => p.voo.companhias.join("+"));
    const horas = pernas.map((p) => horario(p.voo));
    const escalas = pernas.map((p) => p.desce_em ? `desce ${p.desce_em}` : (p.voo.escalas.length ? p.voo.escalas.join(", ") : "Direto"));
    const ocultos = o.detalhes.map(([nivel, txt]) => `<li class="${nivel}">${esc(txt)}</li>`).join("");
    const passos = o.passos.map((p) => `<li>${esc(p)}</li>`).join("");
    const links = (o.links || []).map((l) => `<a href="${esc(l.url)}" target="_blank" rel="noopener">${ico("i-externo")} ${esc(l.rotulo)} no Google Flights</a>`).join("");
    return `<article class="linha${i === 0 ? " aberta" : ""}">
      <button class="linha-topo" aria-expanded="${i === 0}">
        <span class="preco">${br(o.preco)}${o.economia ? `<span class="economia">${br(o.economia)} a menos</span>` : ""}${o.por_pessoa ? `<span class="por-pessoa">${br(o.por_pessoa)} por pessoa</span>` : ""}${o.estimado ? `<span class="estimado">estimado</span>` : ""}</span>
        ${campo("Cia", cias)}
        ${campo("Horário", horas)}
        ${campo("Escala", escalas)}
        <span class="etiqueta">${esc(o.jogada)}</span>
        <span class="direita"><span class="etiqueta">${esc(pernas.some((p) => p.rotulo.startsWith("Volta")) || o.tipo === "normal" && r.volta ? "Ida e volta" : pernas.length > 1 ? "Conexão" : (ida.escalas.length ? ida.escalas.length + " escala" + (ida.escalas.length > 1 ? "s" : "") : "Direto"))}</span><svg class="seta"><use href="#i-seta"/></svg></span>
      </button>
      <div class="detalhe">
        <p class="pernas">${pernas.map(descPerna).join("<br>")}</p>
        <div class="barra ocultos">1. Detalhes ocultos</div>
        <ul>${ocultos}</ul>
        <div class="barra proc">2. Procedimento</div>
        <ol>${passos}</ol>
        <div class="links">${links}</div>
      </div>
    </article>`;
  }).join("");
}
$("#lista").addEventListener("click", (e) => {
  const topo = e.target.closest(".linha-topo");
  if (!topo) return;
  const linha = topo.parentElement;
  linha.classList.toggle("aberta");
  topo.setAttribute("aria-expanded", linha.classList.contains("aberta"));
});

function estadoVazio() {
  $("#lista").innerHTML = `<div class="estado">Digite a <b>origem</b>, o <b>destino</b> e as datas e clique em <b>Caçar</b>.<br>
    O Rasante testa a compra normal, trechos separados, conexão montada, escala oculta e ida e volta jogando fora a volta,
    e lista tudo do mais barato para o mais caro, com os riscos e o passo a passo de cada jogada.<br>
    Sem data de volta, ele caça só a ida.</div>`;
}

/* ---------- vigia ---------- */
let configAtual = {};

function faisca(hist, meta) {
  const pts = (hist || []).map((h) => h.preco);
  if (pts.length < 2) pts.unshift(pts[0] ?? meta);
  const min = Math.min(...pts, meta), max = Math.max(...pts, meta);
  const y = (v) => (max === min ? 13 : 23 - ((v - min) / (max - min)) * 20);
  const passo = 240 / (pts.length - 1);
  const d = pts.map((v, i) => `${i ? "L" : "M"}${(i * passo).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");
  const cor = pts[pts.length - 1] <= meta ? "var(--accent)" : "var(--debit)";
  return `<svg class="faisca" viewBox="0 0 240 26" preserveAspectRatio="none"><line x1="0" x2="240" y1="${y(meta).toFixed(1)}" y2="${y(meta).toFixed(1)}" stroke="#55585c" stroke-dasharray="3 4"/><path d="${d}" fill="none" stroke="${cor}" stroke-width="1.8"/></svg>`;
}

async function carregarVigias() {
  let vigias = [];
  try { vigias = await api("GET", "/api/vigias"); } catch (e) { toast("Não consegui ler as rotas vigiadas: " + e.message, true); }
  const caixa = $("#vigias");
  if (!vigias.length) {
    caixa.innerHTML = `<p class="vazio-vigia">Nenhuma rota vigiada. Depois de caçar, clique em "Vigiar esta rota" e defina a meta de preço.</p>`;
    return;
  }
  caixa.innerHTML = vigias.map((v) => `<div class="rota" data-id="${esc(v.id)}">
      <button class="rota-txt" data-acao="cacar">${esc(v.origem)} - ${esc(v.destino)} | Meta ${br(v.meta)} |<br>${v.ultimo ? br(v.ultimo) + " (Último)" : "sem preço ainda"}</button>
      ${faisca(v.historico, v.meta)}
      <div class="acoes">
        <span class="quando">${dataCurta(v.ida)}${v.volta ? " a " + dataCurta(v.volta) : ""} · ${paxCurto(v.passageiros || [1, 0, 0])}${v.ultima_conferencia ? " · visto " + esc(v.ultima_conferencia.slice(5, 16).replace("T", " ")) : ""}</span>
        <button class="icone-btn" data-acao="conferir" title="Conferir agora" aria-label="Conferir agora">${ico("i-atualizar")}</button>
        <button class="icone-btn" data-acao="remover" title="Parar de vigiar" aria-label="Parar de vigiar">${ico("i-fechar")}</button>
      </div>
    </div>`).join("");
  caixa._vigias = vigias;
}
$("#vigias").addEventListener("click", async (e) => {
  const b = e.target.closest("[data-acao]");
  if (!b) return;
  const v = ($("#vigias")._vigias || []).find((x) => x.id === b.closest(".rota").dataset.id);
  if (!v) return;
  if (b.dataset.acao === "cacar") {
    campos.origem.value = v.origem; campos.destino.value = v.destino;
    campos.ida.value = v.ida; campos.volta.value = v.volta || "";
    pax = v.passageiros || [1, 0, 0];
    mostrarDatas();
    mostrarPax();
    cacar();
  } else if (b.dataset.acao === "conferir") {
    b.disabled = true;
    toast(`Conferindo ${v.origem} - ${v.destino}...`);
    try { await api("POST", `/api/vigias/${v.id}/conferir`); await carregarVigias(); toast("Preço atualizado."); }
    catch (err) { toast(err.message, true); } finally { b.disabled = false; }
  } else if (b.dataset.acao === "remover") {
    if (await confirmar("Parar de vigiar", `Parar de vigiar ${v.origem} - ${v.destino} (${dataCurta(v.ida)})? O histórico de preço dessa rota será apagado.`, "Parar de vigiar")) {
      try { await api("DELETE", "/api/vigias/" + v.id); await carregarVigias(); toast("Rota removida da vigia."); }
      catch (err) { toast(err.message, true); }
    }
  }
});

function novaVigia(r) {
  const melhor = r.opcoes[0]?.preco;
  const sugestao = melhor ? Math.round(melhor * 0.9) : "";
  modal("Vigiar esta rota", `
    <p>${esc(r.origem)} → ${esc(r.destino)}, ${dataCurta(r.ida)}${r.volta ? " a " + dataCurta(r.volta) : ", só ida"}.
    O Rasante caça de novo a cada ${configAtual.intervalo_horas || 6} horas enquanto este computador estiver ligado e avisa no Telegram quando o preço chegar na meta.</p>
    <label for="meta">Meta de preço (R$) *</label>
    <input id="meta" type="number" min="1" step="1" value="${sugestao}">
    ${configAtual.telegram_conectado ? "" : `<p>O Telegram ainda não está conectado: a rota fica vigiada, mas o aviso só chega depois de configurar.</p>`}`,
  [
    { rotulo: "Cancelar" },
    { rotulo: "Vigiar", classe: "prim", fn: async () => {
      const meta = Number($("#meta").value);
      if (!meta || meta <= 0) { toast("Meta de preço: informe um valor em reais.", true); return false; }
      await api("POST", "/api/vigias", { origem: r.origem, destino: r.destino, ida: r.ida, volta: r.volta, passageiros: r.passageiros || [1, 0, 0], meta, ultimo: melhor });
      await carregarVigias();
      toast("Rota vigiada.");
    } },
  ]);
}

/* ---------- configurações ---------- */
function mostrarTelegram() {
  const p = $("#aviso-tg");
  p.classList.toggle("desligado", !configAtual.telegram_conectado);
  $("#aviso-tg-txt").textContent = configAtual.telegram_conectado ? "Notificar no Telegram" : "Telegram desligado (configurar)";
}
async function carregarConfig() {
  try { configAtual = await api("GET", "/api/config"); } catch (e) { configAtual = {}; }
  mostrarTelegram();
}
function abrirConfig() {
  const c = configAtual;
  modal("Configurações", `
    <p><b>Aviso no Telegram</b></p>
    <ol>
      <li>No Telegram, abra o <b>@BotFather</b>, mande <b>/newbot</b>, dê um nome e copie o código que ele devolver.</li>
      <li>Cole o código abaixo e salve.</li>
      <li>Abra o seu bot no Telegram, mande <b>/start</b> e clique em Conectar.</li>
    </ol>
    <label for="tg-token">Código do bot ${c.telegram_token_salvo ? `<span class="ok">(salvo${c.telegram_bot ? ": @" + esc(c.telegram_bot) : ""})</span>` : ""}</label>
    <div class="fila"><input id="tg-token" type="password" placeholder="${c.telegram_token_salvo ? "deixe vazio para manter" : "123456:ABC..."}"><button class="botao" id="tg-salvar">Salvar</button></div>
    <p>${c.telegram_conectado ? `<span class="ok">Conversa conectada.</span>` : "Conversa ainda não conectada."}</p>
    <div class="fila"><button class="botao" id="tg-conectar" ${c.telegram_token_salvo ? "" : "disabled"}>Conectar</button><button class="botao" id="tg-testar" ${c.telegram_conectado ? "" : "disabled"}>Mandar aviso de teste</button></div>
    <label for="intervalo">Conferir as rotas vigiadas a cada (horas)</label>
    <input id="intervalo" type="number" min="1" max="48" value="${c.intervalo_horas || 6}">
    <p>A vigia só roda com o Rasante aberto neste computador. O código do bot fica só em <code>dados/config.json</code>, neste PC.</p>`,
  [
    { rotulo: "Fechar" },
    { rotulo: "Salvar intervalo", classe: "prim", fn: async () => {
      configAtual = await api("POST", "/api/config", { intervalo_horas: Number($("#intervalo").value) });
      toast("Intervalo salvo.");
    } },
  ]);
  const acao = (id, fn) => $(id).addEventListener("click", async (e) => {
    e.target.disabled = true;
    try { await fn(); } catch (err) { toast(err.message, true); } finally { e.target.disabled = false; }
  });
  acao("#tg-salvar", async () => {
    const token = $("#tg-token").value.trim();
    if (!token) return toast("Código do bot: cole o código que o BotFather mandou.", true);
    configAtual = await api("POST", "/api/config", { telegram_token: token });
    mostrarTelegram();
    toast("Bot reconhecido: @" + configAtual.telegram_bot);
    abrirConfig();
  });
  acao("#tg-conectar", async () => {
    configAtual = await api("POST", "/api/telegram/conectar");
    mostrarTelegram();
    toast("Telegram conectado. Mandei uma mensagem de confirmação.");
    abrirConfig();
  });
  acao("#tg-testar", async () => { await api("POST", "/api/telegram/testar"); toast("Aviso de teste enviado."); });
}
$("#abrir-config").addEventListener("click", abrirConfig);
$("#aviso-tg").addEventListener("click", () => { if (!configAtual.telegram_conectado) abrirConfig(); });

/* ---------- início ---------- */
(function iniciar() {
  desenharCena();
  const p = lembrar("pedido");
  const hoje = hojeMais(0);
  if (p && p.ida >= hoje) {
    campos.origem.value = p.origem; campos.destino.value = p.destino;
    campos.ida.value = p.ida; campos.volta.value = p.volta || "";
    if (Array.isArray(p.passageiros) && paxValido(p.passageiros)) pax = p.passageiros;
  } else {
    campos.ida.value = hojeMais(30); campos.volta.value = hojeMais(37);
  }
  mostrarDatas();
  mostrarPax();
  const u = lembrar("ultima");
  if (u && u.ida >= hoje && Array.isArray(u.opcoes) && u.opcoes.every((o) => o.links)) { ultimaCacada = u; mostrarResultado(u); } else estadoVazio();
  carregarConfig();
  carregarVigias();
  setInterval(carregarVigias, 5 * 60 * 1000);
})();
