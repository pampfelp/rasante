"""Raspador próprio do Google Flights, sem biblioteca de terceiros.

Monta a busca do jeito que a página monta (parâmetro `tfs`, um protobuf em
base64), baixa o HTML e lê o bloco de dados `ds:1` que a página usa para
desenhar a lista. Se o Google mudar esse formato, é aqui que se ajusta.
"""
import base64
import json
import re
import time
import urllib.parse
import urllib.request

URL_BUSCA = "https://www.google.com/travel/flights/search"
AGENTE = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/140.0 Safari/537.36")


class Bloqueado(Exception):
    """O Google pediu verificação (captcha). O Rasante para, não contorna."""


# ---------- protobuf mínimo ----------

def _varint(n):
    out = b""
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out += bytes([b | 0x80])
        else:
            return out + bytes([b])


def _str(num, valor):
    b = valor.encode() if isinstance(valor, str) else valor
    return _varint((num << 3) | 2) + _varint(len(b)) + b


def _int(num, valor):
    return _varint(num << 3) + _varint(valor)


PAX_PADRAO = (1, 0, 0)  # adultos, crianças (2 a 11 anos), bebês de colo


def montar_tfs(trechos, ida_e_volta, pax=PAX_PADRAO):
    """trechos: lista de (data AAAA-MM-DD, origem, destino).

    pax: (adultos, crianças, bebês de colo). Cada passageiro é uma entrada do
    campo 8 (1 adulto, 2 criança, 4 bebê de colo). O preço que volta é o
    total do grupo (conferido em 2026-11-16: 1 adulto R$ 822, 2 adultos R$ 1.643).
    """
    adultos, criancas, bebes = pax
    msg = b""
    for data, origem, destino in trechos:
        t = _str(2, data) + _str(13, _str(2, origem)) + _str(14, _str(2, destino))
        msg += _str(3, t)
    for tipo, n in ((1, adultos), (2, criancas), (4, bebes)):
        msg += _int(8, tipo) * n
    msg += _int(9, 1)                       # classe econômica
    msg += _int(19, 1 if ida_e_volta else 2)
    return base64.urlsafe_b64encode(msg).decode().rstrip("=")


def url_busca(trechos, ida_e_volta, pax=PAX_PADRAO):
    q = {"tfs": montar_tfs(trechos, ida_e_volta, pax), "hl": "pt-BR", "curr": "BRL", "gl": "BR"}
    return URL_BUSCA + "?" + urllib.parse.urlencode(q)


# ---------- leitura ----------

def _baixar(url, tentativas=2):
    req = urllib.request.Request(url, headers={"User-Agent": AGENTE,
                                               "Accept-Language": "pt-BR,pt;q=0.9"})
    for i in range(tentativas):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                final = r.geturl()
                html = r.read().decode("utf-8", "replace")
            if "/sorry/" in final or "unusual traffic" in html[:20000].lower():
                raise Bloqueado("O Google pediu verificação. Espere algumas horas antes de caçar de novo.")
            return html
        except Bloqueado:
            raise
        except Exception:
            if i == tentativas - 1:
                raise
            time.sleep(2)


def _bloco_ds1(html):
    m = re.search(r"AF_initDataCallback\(\{key: 'ds:1'.*?data:(.*?), sideChannel", html, re.S)
    if not m:
        return None
    return json.loads(m.group(1))


def _hora(h):
    if not h:
        return "00:00"
    return f"{(h[0] if len(h) > 0 and h[0] is not None else 0):02d}:{(h[1] if len(h) > 1 and h[1] is not None else 0):02d}"


def _data(d):
    return f"{d[0]:04d}-{d[1]:02d}-{d[2]:02d}" if d else None


def _voo(item):
    info, preco = item[0], item[1]
    try:
        valor = preco[0][1]
    except (TypeError, IndexError):
        valor = None
    if not valor:
        return None
    trechos = []
    for s in info[2] or []:
        cod = s[22] or []
        trechos.append({
            "de": s[3], "de_nome": s[4], "para": s[6], "para_nome": s[5],
            "saida": f"{_data(s[20])} {_hora(s[8])}",
            "chegada": f"{_data(s[21])} {_hora(s[10])}",
            "duracao_min": s[11],
            "voo": f"{cod[0]} {cod[1]}" if len(cod) > 1 else "",
            "companhia": s[2],
            "aviao": s[17] if len(s) > 17 else None,
        })
    if not trechos:
        return None
    return {
        "preco": int(valor),
        "companhias": info[1] or [],
        "origem": trechos[0]["de"],
        "destino": trechos[-1]["para"],
        "saida": trechos[0]["saida"],
        "chegada": trechos[-1]["chegada"],
        "duracao_min": info[9],
        "escalas": [t["para"] for t in trechos[:-1]],
        "trechos": trechos,
    }


def buscar(trechos, ida_e_volta=False, pax=PAX_PADRAO):
    """Devolve a lista de voos da primeira tela do Google Flights.

    Só ida: preço da passagem só de ida.
    Ida e volta: cada item é um voo de ida com o menor preço total de ida e volta.
    Lista vazia quando o Google não tem itinerário montado (ex.: CAC-BEL em
    jun/2027, mesmo com CAC-GRU e GRU-BEL à venda).
    """
    url = url_busca(trechos, ida_e_volta, pax)
    data = _bloco_ds1(_baixar(url))
    voos = []
    if data:
        for idx in (2, 3):
            bloco = data[idx] if len(data) > idx else None
            if bloco and bloco[0]:
                for item in bloco[0]:
                    v = _voo(item)
                    if v:
                        voos.append(v)
    vistos, unicos = set(), []
    for v in sorted(voos, key=lambda v: v["preco"]):
        chave = (v["saida"], tuple(t["voo"] for t in v["trechos"]))
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(v)
    return unicos, url


if __name__ == "__main__":
    import sys
    origem, destino, data = sys.argv[1:4]
    voos, url = buscar([(data, origem, destino)])
    print(url)
    for v in voos:
        print(v["preco"], v["companhias"], v["saida"], "->", v["chegada"], "escalas", v["escalas"])
