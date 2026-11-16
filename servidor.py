"""Servidor local do Rasante: entrega a tela, roda as caçadas e vigia as rotas.

Uso: python servidor.py  (abre em http://127.0.0.1:8740)
Só escuta no próprio computador. Os dados ficam em dados/ (fora do git).
"""
import datetime as dt
import json
import mimetypes
import threading
import time
import urllib.parse
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import gflights
import jogadas

PORTA = 8740
RAIZ = Path(__file__).resolve().parent
WEB = RAIZ / "web"
DADOS = RAIZ / "dados"
ARQ_VIGIAS = DADOS / "vigias.json"
ARQ_CONFIG = DADOS / "config.json"
TRAVA = threading.Lock()
CACADAS = {}  # id -> estado da caçada em andamento


# ---------- armazenamento ----------

def _ler(arq, padrao):
    try:
        return json.loads(arq.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return padrao


def _gravar(arq, dados):
    DADOS.mkdir(exist_ok=True)
    tmp = arq.with_suffix(".tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(arq)


def config():
    c = _ler(ARQ_CONFIG, {})
    c.setdefault("intervalo_horas", 6)
    return c


def config_publica():
    c = config()
    return {
        "telegram_bot": c.get("telegram_bot"),
        "telegram_token_salvo": bool(c.get("telegram_token")),
        "telegram_conectado": bool(c.get("telegram_chat_id")),
        "intervalo_horas": c["intervalo_horas"],
    }


# ---------- Telegram ----------

def _telegram(metodo, **params):
    token = config().get("telegram_token")
    if not token:
        raise ValueError("Telegram ainda não configurado.")
    url = f"https://api.telegram.org/bot{token}/{metodo}"
    dados = urllib.parse.urlencode(params).encode() if params else None
    with urllib.request.urlopen(url, data=dados, timeout=20) as r:
        resp = json.loads(r.read().decode())
    if not resp.get("ok"):
        raise ValueError(resp.get("description", "Telegram recusou."))
    return resp["result"]


def enviar_telegram(texto):
    chat = config().get("telegram_chat_id")
    if not chat:
        raise ValueError("Telegram sem conversa conectada.")
    _telegram("sendMessage", chat_id=chat, text=texto, disable_web_page_preview="true")


# ---------- vigia ----------

def _br(v):
    return "R$ " + f"{v:,.0f}".replace(",", ".")


def conferir_vigia(vid):
    with TRAVA:
        vigias = _ler(ARQ_VIGIAS, [])
        v = next((x for x in vigias if x["id"] == vid), None)
    if not v:
        raise KeyError(vid)
    r = jogadas.cacar(v["origem"], v["destino"], v["ida"], v.get("volta"))
    opcoes = r["opcoes"]
    if not opcoes:
        return v
    melhor = opcoes[0]
    seguras = [o for o in opcoes if o["risco"] == "baixo"]
    seguro = seguras[0] if seguras else None
    agora = dt.datetime.now().isoformat(timespec="minutes")
    with TRAVA:
        vigias = _ler(ARQ_VIGIAS, [])
        v = next((x for x in vigias if x["id"] == vid), None)
        if not v:
            raise KeyError(vid)
        v["ultimo"] = melhor["preco"]
        v["ultimo_seguro"] = seguro["preco"] if seguro else None
        v["ultima_conferencia"] = agora
        v["historico"] = (v.get("historico", []) + [{"quando": agora, "preco": melhor["preco"]}])[-60:]
        avisar = (melhor["preco"] <= v["meta"] and
                  (v.get("avisado_em_preco") is None or melhor["preco"] < v["avisado_em_preco"]))
        if avisar:
            v["avisado_em_preco"] = melhor["preco"]
        _gravar(ARQ_VIGIAS, vigias)
    if avisar and config().get("telegram_chat_id"):
        linhas = [
            f"Rasante: {v['origem']} > {v['destino']} caiu para {_br(melhor['preco'])} (meta {_br(v['meta'])}).",
            f"Jogada: {melhor['jogada']} ({melhor['paradas']}).",
        ]
        if seguro and seguro is not melhor:
            linhas.append(f"Compra normal mais barata: {_br(seguro['preco'])}.")
        linhas.append(f"Ida {v['ida']}" + (f", volta {v['volta']}" if v.get("volta") else ""))
        linhas.append(melhor.get("link", ""))
        try:
            enviar_telegram("\n".join(linhas))
        except Exception as e:
            print("aviso no Telegram falhou:", e, flush=True)
    return v


def laco_vigia():
    while True:
        try:
            horas = float(config()["intervalo_horas"])
            hoje = dt.date.today().isoformat()
            for v in _ler(ARQ_VIGIAS, []):
                if v["ida"] < hoje:
                    continue
                ultima = v.get("ultima_conferencia")
                if ultima and (dt.datetime.now() - dt.datetime.fromisoformat(ultima)).total_seconds() < horas * 3600:
                    continue
                try:
                    conferir_vigia(v["id"])
                except gflights.Bloqueado as e:
                    print("vigia pausada:", e, flush=True)
                    break
                except Exception as e:
                    print("vigia falhou em", v["id"], e, flush=True)
                time.sleep(20)  # espaça as caçadas para não pesar no Google
        except Exception as e:
            print("laço da vigia:", e, flush=True)
        time.sleep(300)


# ---------- caçada em segundo plano ----------

def iniciar_cacada(origem, destino, ida, volta):
    cid = uuid.uuid4().hex[:10]
    CACADAS[cid] = {"feitos": 0, "total": 0, "resultado": None, "erro": None}

    def progresso(f, t):
        CACADAS[cid].update(feitos=f, total=t)

    def rodar():
        try:
            CACADAS[cid]["resultado"] = jogadas.cacar(origem, destino, ida, volta, progresso)
        except gflights.Bloqueado as e:
            CACADAS[cid]["erro"] = str(e)
        except Exception as e:
            CACADAS[cid]["erro"] = f"A caçada falhou: {e}"

    threading.Thread(target=rodar, daemon=True).start()
    return cid


# ---------- HTTP ----------

def _codigo(x):
    x = (x or "").strip().upper()
    if len(x) != 3 or not x.isalpha():
        raise ValueError("Use o código de 3 letras do aeroporto (ex.: BEL).")
    return x


def _data(x, obrigatoria=True):
    if not x:
        if obrigatoria:
            raise ValueError("Informe a data de ida.")
        return None
    dt.date.fromisoformat(x)
    return x


class Rasante(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, codigo, dados):
        corpo = json.dumps(dados, ensure_ascii=False).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def _corpo(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def _estatico(self, caminho):
        if caminho in ("", "/"):
            caminho = "/index.html"
        arq = (WEB / caminho.lstrip("/")).resolve()
        if WEB not in arq.parents or not arq.is_file():
            self.send_error(404)
            return
        corpo = arq.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", (mimetypes.guess_type(arq.name)[0] or "application/octet-stream")
                         + ("; charset=utf-8" if arq.suffix in (".html", ".css", ".js") else ""))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        try:
            if u.path.startswith("/api/cacar/"):
                c = CACADAS.get(u.path.rsplit("/", 1)[1])
                return self._json(200, c) if c else self._json(404, {"erro": "Caçada não encontrada."})
            if u.path == "/api/vigias":
                return self._json(200, _ler(ARQ_VIGIAS, []))
            if u.path == "/api/config":
                return self._json(200, config_publica())
            if u.path.startswith("/api/"):
                return self._json(404, {"erro": "Rota desconhecida."})
            return self._estatico(u.path)
        except Exception as e:
            return self._json(500, {"erro": str(e)})

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        try:
            b = self._corpo()
            if u.path == "/api/cacar":
                origem, destino = _codigo(b.get("origem")), _codigo(b.get("destino"))
                ida, volta = _data(b.get("ida")), _data(b.get("volta"), False)
                if volta and volta < ida:
                    raise ValueError("A volta é antes da ida.")
                if ida < dt.date.today().isoformat():
                    raise ValueError("A data de ida já passou.")
                return self._json(200, {"id": iniciar_cacada(origem, destino, ida, volta)})
            if u.path == "/api/vigias":
                meta = int(b.get("meta") or 0)
                if meta <= 0:
                    raise ValueError("Informe a meta de preço em reais.")
                v = {"id": uuid.uuid4().hex[:8], "origem": _codigo(b.get("origem")),
                     "destino": _codigo(b.get("destino")), "ida": _data(b.get("ida")),
                     "volta": _data(b.get("volta"), False), "meta": meta,
                     "ultimo": b.get("ultimo"), "historico": [], "criada": dt.datetime.now().isoformat(timespec="minutes")}
                if v["ultimo"]:
                    v["historico"].append({"quando": v["criada"], "preco": v["ultimo"]})
                    v["ultima_conferencia"] = v["criada"]
                with TRAVA:
                    vigias = _ler(ARQ_VIGIAS, [])
                    vigias.append(v)
                    _gravar(ARQ_VIGIAS, vigias)
                return self._json(200, v)
            if u.path.startswith("/api/vigias/") and u.path.endswith("/conferir"):
                vid = u.path.split("/")[3]
                return self._json(200, conferir_vigia(vid))
            if u.path == "/api/config":
                with TRAVA:
                    c = config()
                    if "intervalo_horas" in b:
                        h = float(b["intervalo_horas"])
                        if not 1 <= h <= 48:
                            raise ValueError("O intervalo vai de 1 a 48 horas.")
                        c["intervalo_horas"] = h
                    if b.get("telegram_token"):
                        c["telegram_token"] = b["telegram_token"].strip()
                        c.pop("telegram_chat_id", None)
                        _gravar(ARQ_CONFIG, c)
                        try:
                            c["telegram_bot"] = _telegram("getMe")["username"]
                        except Exception:
                            c.pop("telegram_token", None)
                            _gravar(ARQ_CONFIG, c)
                            raise ValueError("O Telegram não reconheceu esse código do bot.")
                    _gravar(ARQ_CONFIG, c)
                return self._json(200, config_publica())
            if u.path == "/api/telegram/conectar":
                updates = _telegram("getUpdates")
                chats = [x["message"]["chat"]["id"] for x in updates if "message" in x]
                if not chats:
                    raise ValueError("Mande /start para o bot no Telegram e tente de novo.")
                with TRAVA:
                    c = config()
                    c["telegram_chat_id"] = chats[-1]
                    _gravar(ARQ_CONFIG, c)
                enviar_telegram("Rasante conectado. Os avisos de preço vão chegar aqui.")
                return self._json(200, config_publica())
            if u.path == "/api/telegram/testar":
                enviar_telegram("Rasante: aviso de teste.")
                return self._json(200, {"ok": True})
            return self._json(404, {"erro": "Rota desconhecida."})
        except gflights.Bloqueado as e:
            return self._json(429, {"erro": str(e)})
        except (ValueError, KeyError) as e:
            return self._json(400, {"erro": str(e).strip("'")})
        except Exception as e:
            return self._json(500, {"erro": str(e)})

    def do_DELETE(self):
        u = urllib.parse.urlparse(self.path)
        if u.path.startswith("/api/vigias/"):
            vid = u.path.rsplit("/", 1)[1]
            with TRAVA:
                vigias = [v for v in _ler(ARQ_VIGIAS, []) if v["id"] != vid]
                _gravar(ARQ_VIGIAS, vigias)
            return self._json(200, {"ok": True})
        return self._json(404, {"erro": "Rota desconhecida."})


if __name__ == "__main__":
    threading.Thread(target=laco_vigia, daemon=True).start()
    servidor = ThreadingHTTPServer(("127.0.0.1", PORTA), Rasante)
    print(f"Rasante em http://127.0.0.1:{PORTA}", flush=True)
    servidor.serve_forever()
