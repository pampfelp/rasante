"""As jogadas do Rasante: monta todas as formas de comprar a mesma viagem,
com o preço, os detalhes ocultos e o procedimento de cada uma.

Base das regras (pesquisa de 2026-11-16, ver LEIA-ME.md):
- Res. ANAC 400, art. 11: desistência sem custo em 24 h do comprovante,
  se a compra foi feita 7 dias ou mais antes do voo.
- Res. ANAC 400, art. 19: no-show na ida pode cancelar a volta, salvo aviso
  até o horário da ida.
- Escala oculta viola o contrato das companhias (American baniu passageiro
  em 2023; júri deu US$ 9,4 mi à American contra o Skiplagged em 2024).

Todos os preços são o total do grupo de passageiros.
"""
import datetime as dt
import time
from concurrent.futures import ThreadPoolExecutor

import aeroportos
import gflights

_CACHE = {}
_VALIDADE_CACHE = 30 * 60

# Custos de chão, estimativas editáveis na engrenagem (servidor guarda em dados/config.json).
CHAO_PADRAO = {
    "carro_km": 0.80,        # combustível + pedágio, por km rodado
    "estacionamento_dia": 40,
    "uber_km": 2.30,         # Uber/táxi intermunicipal, por km
    "raio_km": 450,          # até onde procurar aeroporto vizinho (km de estrada)
}
CONEXAO_MIN = 3 * 60   # minutos entre os dois bilhetes da conexão montada
CONEXAO_MAX = 10 * 60


def _buscar(trechos, ida_e_volta, pax):
    chave = (tuple(trechos), ida_e_volta, pax)
    agora = time.time()
    if chave in _CACHE and agora - _CACHE[chave][0] < _VALIDADE_CACHE:
        return _CACHE[chave][1]
    resultado = gflights.buscar(list(trechos), ida_e_volta, pax)
    if not resultado[0] and pax[1]:
        # Em alguns trechos o Google não cota criança e devolve vazio (CAC-GRU,
        # 2026-11-16: 5 voos para adultos, 0 com criança). Refaz cotando a
        # criança como adulto e marca o preço como estimado.
        voos, url = gflights.buscar(list(trechos), ida_e_volta, (pax[0] + pax[1], 0, pax[2]))
        for v in voos:
            v["estimado"] = True
        resultado = (voos, url)
    _CACHE[chave] = (agora, resultado)
    return resultado


def _br(valor):
    return "R$ " + f"{valor:,.0f}".replace(",", ".")


def descrever_pax(pax):
    a, c, b = pax
    partes = [f"{a} adulto" + ("s" if a > 1 else "")]
    if c:
        partes.append(f"{c} criança" + ("s" if c > 1 else ""))
    if b:
        partes.append(f"{b} bebê" + ("s" if b > 1 else "") + " de colo")
    return ", ".join(partes[:-1]) + (" e " if len(partes) > 1 else "") + partes[-1]


def _desc_voo(v):
    voos = ", ".join(t["voo"] for t in v["trechos"] if t["voo"])
    return f"{' + '.join(v['companhias'])} {voos}, saída {v['saida'][11:]} de {v['origem']}"


def _paradas(v):
    n = len(v["trechos"]) - 1
    return "Direto" if n == 0 else f"{n} escala" + ("s" if n > 1 else "")


def _perna(rotulo, v, desce_em=None):
    p = {"rotulo": rotulo, "voo": v}
    if desce_em:
        p["desce_em"] = desce_em
    return p


def _minutos(texto):
    return dt.datetime.fromisoformat(texto)


def _regra_24h(data_ida):
    dias = (dt.date.fromisoformat(data_ida) - dt.date.today()).days
    if dias >= 7:
        return ("Dá para desistir sem multa em até 24 horas depois de receber o comprovante, "
                "porque o voo é daqui a 7 dias ou mais (Res. ANAC 400, art. 11). Compre e continue caçando.")
    return ("O voo é daqui a menos de 7 dias: a desistência grátis de 24 horas da ANAC não vale. "
            "Compre só quando tiver certeza.")


def _detalhe_pax(pax):
    a, c, b = pax
    if a + c + b == 1:
        return []
    linhas = [("info", f"Preço total para {descrever_pax(pax)}. Compre todos na mesma reserva.")]
    if c or b:
        linhas.append(("info", "Criança e bebê viajam com documento com foto (ou certidão de nascimento no voo doméstico)."))
    return linhas


# ---------- lados de uma viagem (ida ou volta) ----------
# Cada lado é um dict: preco, pernas, detalhes, passos, link, tipo, risco, rotulo_paradas.

def _lado_normal(rotulo, v, url):
    return {
        "tipo": "normal", "risco": "baixo", "preco": v["preco"],
        "pernas": [_perna(rotulo, v)], "paradas": _paradas(v), "link": url,
        "detalhes": [],
        "passos": [f"{rotulo}: compre só de ida {_desc_voo(v)} ({_br(v['preco'])})."],
    }


def _lado_oculto(rotulo, achado):
    preco, v, desce, url, usados = achado
    jogados = v["trechos"][len(usados):]
    return {
        "tipo": "oculta", "risco": "alto", "preco": preco,
        "pernas": [_perna(rotulo, v, desce)], "paradas": f"desce em {desce}", "link": url,
        "detalhes": [
            ("risco", "Só bagagem de mão. Mala despachada segue para o destino final do bilhete, não para onde você desce."),
            ("risco", "Mala pequena: se o voo lotar, a companhia pode mandar sua mala de mão para o porão, e aí ela segue para o destino final."),
            ("risco", "Não informe número de fidelidade (milhas). Violar o contrato pode custar a conta e as milhas."),
            ("risco", "Só funciona em passagem só de ida: depois do trecho que você não usa, tudo o que vier na mesma reserva é cancelado."),
            ("risco", "Viola o contrato da companhia. A American baniu um passageiro por isso em 2023. Não repita na mesma companhia com frequência."),
            ("aviso", f"Se a companhia mudar o voo e tirar a escala em {desce}, você pode acabar voando até o destino final."),
        ],
        "passos": [
            f"{rotulo}: compre só de ida {v['origem']} → {v['destino']} ({aeroportos.cidade(v['destino'])}): {_desc_voo(v)}, sem número de fidelidade e sem mala despachada.",
            f"{rotulo}: faça o check-in normalmente; o cartão de embarque mostra os dois trechos.",
            f"{rotulo}: em {desce} ({aeroportos.cidade(desce)}), saia pelo desembarque. Não embarque em {', '.join(t['voo'] for t in jogados)} para {v['destino']}.",
        ],
    }


def _lado_conexao(rotulo, par, url1, url2):
    preco, v1, v2, hub, espera = par
    h, m = divmod(espera, 60)
    return {
        "tipo": "conexao", "risco": "medio", "preco": preco,
        "pernas": [_perna(rotulo + " 1", v1), _perna(rotulo + " 2", v2)],
        "paradas": f"conexão em {hub}", "link": url1, "link_2": url2, "hub": hub,
        "detalhes": [
            ("risco", f"São dois bilhetes separados. Se o primeiro atrasar e você perder o segundo, a companhia do segundo não tem obrigação de te levar; você compra outro."),
            ("aviso", f"Espera de {h}h{m:02d} em {hub} ({aeroportos.cidade(hub)}). O Rasante só monta conexão com 3 h ou mais."),
            ("aviso", f"Mala despachada não segue direto: retire na esteira em {hub}, saia e despache de novo no segundo voo."),
            ("info", "Prefira voos cedo no primeiro trecho: se der problema, ainda sobra voo no mesmo dia."),
        ],
        "passos": [
            f"{rotulo}: compre só de ida {v1['origem']} → {hub}: {_desc_voo(v1)} ({_br(v1['preco'])}).",
            f"{rotulo}: compre só de ida {hub} → {v2['destino']}: {_desc_voo(v2)} ({_br(v2['preco'])}).",
            f"{rotulo}: faça o check-in das duas reservas.",
            f"{rotulo}: em {hub}, saia do desembarque, pegue a mala se tiver e vá ao embarque do segundo voo.",
        ],
    }


def _achar_ocultas(destino, buscas):
    """buscas: {destino_alem: (voos, url)}. Voos com escala no destino pedido."""
    achados = []
    for alem, (voos, url) in buscas.items():
        for v in voos:
            if not any(aeroportos.mesma_cidade(e, destino) for e in v["escalas"]):
                continue
            desce = next(e for e in v["escalas"] if aeroportos.mesma_cidade(e, destino))
            usados = []
            for t in v["trechos"]:
                usados.append(t)
                if t["para"] == desce:
                    break
            achados.append((v["preco"], v, desce, url, usados))
    achados.sort(key=lambda a: a[0])
    return achados


def _achar_conexoes(hub, primeiros, segundos):
    """Pares (1º voo até o hub, 2º voo do hub) com 3 h a 10 h de espera."""
    pares = []
    for v1 in primeiros[:6]:
        for v2 in segundos[:6]:
            espera = (_minutos(v2["saida"]) - _minutos(v1["chegada"])).total_seconds() / 60
            if CONEXAO_MIN <= espera <= CONEXAO_MAX and v1["destino"] == v2["origem"]:
                pares.append((v1["preco"] + v2["preco"], v1, v2, hub, int(espera)))
    pares.sort(key=lambda p: p[0])
    return pares[:2]


def _opcao(lados, jogada, data_ida, pax, extra_detalhes=(), extra_passos=()):
    detalhes, passos, pernas = [], [], []
    for lado in lados:
        pernas += lado["pernas"]
        passos += lado["passos"]
        for d in lado["detalhes"]:
            if d not in detalhes:
                detalhes.append(d)
    detalhes += list(extra_detalhes) + _detalhe_pax(pax) + [("info", _regra_24h(data_ida))]
    riscos = [l["risco"] for l in lados]
    risco = "alto" if "alto" in riscos else "medio" if "medio" in riscos else "baixo"
    op = {
        "tipo": "+".join(sorted({l["tipo"] for l in lados})), "jogada": jogada,
        "preco": sum(l["preco"] for l in lados), "risco": risco,
        "paradas": " + ".join(l["paradas"] for l in lados),
        "pernas": pernas, "detalhes": detalhes, "passos": passos + list(extra_passos),
        "links": [],
    }
    for lado, rot in zip(lados, ("Ida", "Volta")):
        nome = rot if len(lados) > 1 else "Abrir"
        if lado.get("link_2"):
            op["links"].append({"rotulo": f"{rot} trecho 1", "url": lado["link"]})
            op["links"].append({"rotulo": f"{rot} trecho 2", "url": lado["link_2"]})
        elif lado.get("link"):
            op["links"].append({"rotulo": nome, "url": lado["link"]})
    return op


def _nome_jogada(lados):
    tipos = {l["tipo"] for l in lados}
    if "oculta" in tipos:
        return "Escala oculta"
    if "conexao" in tipos:
        return "Conexão montada"
    return "Trechos separados"


# ---------- jogadas que não se montam por lados ----------

def _compra_normal(lista, url, data_ida, tem_volta, pax):
    opcoes = []
    for v in lista[:6]:
        detalhes = [
            ("info", "Compra comum, sem violar regra nenhuma da companhia."),
            ("info", "Tarifa básica costuma não incluir mala despachada; confira antes de pagar."),
        ]
        if len(v["trechos"]) > 1:
            detalhes.append(("info", f"Conexão em {', '.join(v['escalas'])}, na mesma reserva: se atrasar, a companhia te reacomoda."))
        if tem_volta:
            detalhes.append(("info", "O preço é o total de ida e volta na mesma reserva; a volta você escolhe na tela seguinte do Google Flights."))
        detalhes += _detalhe_pax(pax) + [("info", _regra_24h(data_ida))]
        passos = ["Abra a busca no Google Flights pelo link desta opção.", f"Escolha o voo de ida: {_desc_voo(v)}."]
        if tem_volta:
            passos.append("Na tela seguinte, escolha a volta mais barata.")
        passos += [
            "Em \"Opções de reserva\", prefira comprar direto no site da companhia (remarcação e reembolso mais fáceis).",
            "Guarde o comprovante: as 24 horas de desistência contam a partir dele.",
        ]
        opcoes.append({
            "tipo": "normal", "jogada": "Compra normal", "preco": v["preco"], "paradas": _paradas(v),
            "risco": "baixo", "pernas": [_perna("Ida", v)], "detalhes": detalhes, "passos": passos,
            "links": [{"rotulo": "Abrir", "url": url}],
        })
    return opcoes


def _jogar_fora_volta(rt, url, data_ida, data_volta_falsa, pax):
    opcoes = []
    for v in rt[:3]:
        detalhes = [
            ("aviso", "Você compra ida e volta e não usa a volta. Como é o último trecho, nada mais é cancelado."),
            ("aviso", "Algumas companhias proíbem isso no contrato; em voo doméstico no Brasil a cobrança da diferença é rara, mas não use número de fidelidade."),
            ("info", f"A volta fica marcada para {data_volta_falsa}; não precisa fazer nada nesse dia."),
        ] + _detalhe_pax(pax) + [("info", _regra_24h(data_ida))]
        passos = [
            "Abra a busca de ida e volta no Google Flights pelo link desta opção.",
            f"Escolha a ida: {_desc_voo(v)}.",
            "Escolha a volta mais barata (você não vai usá-la).",
            "Compre sem informar número de fidelidade.",
            "Voe a ida normalmente e não apareça na volta.",
        ]
        opcoes.append({
            "tipo": "jogar_volta", "jogada": "Ida e volta jogando fora a volta",
            "preco": v["preco"], "paradas": _paradas(v), "risco": "medio",
            "pernas": [_perna("Ida", v)], "detalhes": detalhes, "passos": passos,
            "links": [{"rotulo": "Abrir", "url": url}],
        })
    return opcoes


def _custo_chao(km, lado, ida, volta, pax, chao):
    """Custo de ir e voltar do aeroporto vizinho. lado: 'origem' ou 'destino'.

    Na origem dá para ir de carro (deixando no estacionamento) ou de Uber; no
    destino só Uber/táxi. Uber leva até 4 pessoas por carro.
    """
    dias = (dt.date.fromisoformat(volta) - dt.date.fromisoformat(ida)).days if volta else 0
    pessoas = pax[0] + pax[1]  # bebê de colo vai no colo
    carros_uber = -(-pessoas // 4)
    viagens = 2 if volta else 1
    uber = km * chao["uber_km"] * viagens * carros_uber
    def reais(x):
        return f"R$ {x:.2f}".replace(".", ",")
    escolhas = [("Uber/táxi", uber,
                 f"{viagens}× {km} km de Uber/táxi a {reais(chao['uber_km'])}/km"
                 + (f", {carros_uber} carros" if carros_uber > 1 else ""))]
    if lado == "origem":
        if volta:
            n_dias = max(dias, 1)
            carro = 2 * km * chao["carro_km"] + chao["estacionamento_dia"] * n_dias
            como = (f"2× {km} km de carro a {reais(chao['carro_km'])}/km + estacionamento de "
                    f"{n_dias} dia{'s' if n_dias > 1 else ''} a R$ {chao['estacionamento_dia']:.0f}")
        else:
            carro = 2 * km * chao["carro_km"]  # alguém leva e volta com o carro
            como = f"{km} km para ir e {km} para o carro voltar, a {reais(chao['carro_km'])}/km"
        escolhas.append(("Carro", carro, como))
    meio, valor, como = min(escolhas, key=lambda e: e[1])
    horas = km / 75
    return {"meio": meio, "valor": round(valor), "como": como, "km": km,
            "horas": f"{int(horas)}h{round((horas % 1) * 60):02d}",
            "alternativas": [(m, round(v)) for m, v, _ in escolhas]}


def _aplicar_chao(op, lado, cod, km, origem, destino, ida, volta, pax, chao):
    """Soma o custo de estrada até o aeroporto vizinho e explica no detalhe."""
    c = _custo_chao(km, lado, ida, volta, pax, chao)
    perto = origem if lado == "origem" else destino
    alt = " / ".join(f"{m} {_br(x)}" for m, x in c["alternativas"])
    linhas = [
        ("aviso", f"{'Sai de' if lado == 'origem' else 'Chega em'} {cod} ({aeroportos.cidade(cod)}), não {'de' if lado == 'origem' else 'em'} {perto}: cerca de {km} km de estrada, umas {c['horas']}."),
        ("aviso", f"Estrada estimada: {_br(c['valor'])} de {c['meio'].lower()} ({c['como']}). Comparado: {alt}."),
        ("info", "Distância estimada pela linha reta × 1,3. Custo por km e estacionamento se ajustam na engrenagem."),
    ]
    if lado == "origem":
        linhas.append(("aviso", f"Saia de casa com folga: {c['horas']} de estrada mais 2 h de antecedência do voo."))
        op["passos"].insert(0, f"Vá de {c['meio'].lower()} até {cod} ({aeroportos.cidade(cod)}), {km} km.")
        if volta:
            op["passos"].append(f"Na volta, desça em {cod} e siga de {c['meio'].lower()} até {aeroportos.cidade(origem)}.")
    else:
        op["passos"].append(f"Ao chegar em {cod} ({aeroportos.cidade(cod)}), siga de Uber/táxi até {aeroportos.cidade(destino)}, {km} km."
                            + (" Na volta, faça o caminho inverso." if volta else ""))
    op["detalhes"] = linhas + op["detalhes"]
    op["passagem"] = op["preco"]
    op["preco"] += c["valor"]
    op["chao"] = c
    op["tipo"] = "vizinho"
    op["jogada"] = f"Aeroporto vizinho {cod}"
    op["paradas"] = f"via {cod}" + (f" + {op['paradas']}" if op.get("paradas") else "")
    return op


def _opcoes_vizinho(lado, cod, km, lista, url, origem, destino, ida, volta, pax, chao):
    opcoes = []
    for v in lista[:2]:
        detalhes = [("info", "A passagem em si é compra normal, sem violar regra nenhuma.")] \
            + _detalhe_pax(pax) + [("info", _regra_24h(ida))]
        passos = [
            "Abra a busca no Google Flights pelo link desta opção.",
            f"Escolha o voo: {_desc_voo(v)}." + (" Na tela seguinte, escolha a volta." if volta else ""),
            "Prefira comprar direto no site da companhia.",
        ]
        op = {"preco": v["preco"], "paradas": "", "risco": "baixo",
              "pernas": [_perna("Ida", v)], "detalhes": detalhes, "passos": passos,
              "links": [{"rotulo": "Abrir", "url": url}]}
        opcoes.append(_aplicar_chao(op, lado, cod, km, origem, destino, ida, volta, pax, chao))
    return opcoes


# ---------- caçada ----------

def cacar(origem, destino, ida, volta=None, pax=gflights.PAX_PADRAO, ao_progresso=None, chao=None):
    origem, destino = origem.upper().strip(), destino.upper().strip()
    pax = tuple(pax)
    chao = {**CHAO_PADRAO, **(chao or {})}
    viz_o = aeroportos.vizinhos(origem, chao["raio_km"])
    viz_d = aeroportos.vizinhos(destino, chao["raio_km"])
    falsa = (dt.date.fromisoformat(ida) + dt.timedelta(days=7)).isoformat()
    hubs_ida = aeroportos.hubs_entre(origem, destino)
    hubs_volta = aeroportos.hubs_entre(destino, origem) if volta else []

    tarefas = {"ida": ([(ida, origem, destino)], False)}
    if volta:
        tarefas["volta"] = ([(volta, destino, origem)], False)
        tarefas["rt"] = ([(ida, origem, destino), (volta, destino, origem)], True)
    else:
        tarefas["rt_falsa"] = ([(ida, origem, destino), (falsa, destino, origem)], True)
    for x in aeroportos.alem_de(origem, destino):
        tarefas[("oculta_ida", x)] = ([(ida, origem, x)], False)
    for h in hubs_ida:
        tarefas[("con_ida_1", h)] = ([(ida, origem, h)], False)
        tarefas[("con_ida_2", h)] = ([(ida, h, destino)], False)
    for x, _ in viz_o:
        tarefas[("viz_o", x)] = (([(ida, x, destino), (volta, destino, x)], True) if volta else ([(ida, x, destino)], False))
    for x, _ in viz_d:
        tarefas[("viz_d", x)] = (([(ida, origem, x), (volta, x, origem)], True) if volta else ([(ida, origem, x)], False))
    if volta:
        for x in aeroportos.alem_de(destino, origem):
            tarefas[("oculta_volta", x)] = ([(volta, destino, x)], False)
        for h in hubs_volta:
            tarefas[("con_volta_1", h)] = ([(volta, destino, h)], False)
            tarefas[("con_volta_2", h)] = ([(volta, h, origem)], False)

    resultados, falhas = {}, []
    estado = {"total": 0, "feitos": 0, "bloqueio": None}

    def executar(lote):
        estado["total"] += len(lote)
        with ThreadPoolExecutor(max_workers=4) as ex:
            futuros = {ex.submit(_buscar, tuple(t), rt, pax): k for k, (t, rt) in lote.items()}
            for f, k in futuros.items():
                try:
                    resultados[k] = f.result()
                except gflights.Bloqueado as e:
                    estado["bloqueio"] = str(e)
                except Exception as e:  # rede, formato mudou
                    falhas.append(f"{k}: {e}")
                estado["feitos"] += 1
                if ao_progresso:
                    ao_progresso(estado["feitos"], estado["total"])

    executar(tarefas)
    bloqueio = estado["bloqueio"]
    if bloqueio and not resultados:
        raise gflights.Bloqueado(bloqueio)

    def res(k):
        return resultados.get(k, ([], None))

    # 2ª rodada: vizinho sem voo montado pelo Google ganha conexão montada
    # pelos mesmos hubs (o Google só monta conexão até uns meses à frente:
    # IGU-BEL tem voo em dez/26 e mar/27, nada em jun/27).
    vazios_o = [x for x, _ in viz_o if not res(("viz_o", x))[0]]
    vazios_d = [x for x, _ in viz_d if not res(("viz_d", x))[0]]
    lote2 = {}
    for x in vazios_o:
        for h in hubs_ida:
            lote2[("vc_o_ida", x, h)] = ([(ida, x, h)], False)
        for h in hubs_volta:
            lote2[("vc_o_volta", x, h)] = ([(volta, h, x)], False)
    for x in vazios_d:
        for h in hubs_ida:
            lote2[("vc_d_ida", x, h)] = ([(ida, h, x)], False)
        for h in hubs_volta:
            lote2[("vc_d_volta", x, h)] = ([(volta, x, h)], False)
    if lote2:
        executar(lote2)
    total = estado["total"]

    def por_tipo(prefixo):
        return {k[1]: v for k, v in resultados.items() if isinstance(k, tuple) and k[0] == prefixo}

    def conexoes(prefixo, hubs, rotulo):
        lados = []
        for h in hubs:
            (p, u1), (s, u2) = res((prefixo + "_1", h)), res((prefixo + "_2", h))
            for par in _achar_conexoes(h, p, s):
                lados.append(_lado_conexao(rotulo, par, u1, u2))
        return lados

    opcoes = []
    idas, url_ida = res("ida")
    teto_ida = idas[0]["preco"] if idas else None
    ocultas_ida = [a for a in _achar_ocultas(destino, por_tipo("oculta_ida")) if teto_ida is None or a[0] < teto_ida][:3]
    lados_ida = ([_lado_normal("Ida", idas[0], url_ida)] if idas else []) \
        + [_lado_oculto("Ida", a) for a in ocultas_ida] + conexoes("con_ida", hubs_ida, "Ida")

    if volta:
        voltas, url_volta = res("volta")
        rt, url_rt = res("rt")
        opcoes += _compra_normal(rt, url_rt, ida, True, pax)
        teto_volta = voltas[0]["preco"] if voltas else None
        ocultas_volta = [a for a in _achar_ocultas(origem, por_tipo("oculta_volta")) if teto_volta is None or a[0] < teto_volta][:3]
        lados_volta = [_lado_normal("Volta", v, url_volta) for v in voltas[:3]] \
            + [_lado_oculto("Volta", a) for a in ocultas_volta] + conexoes("con_volta", hubs_volta, "Volta")
        normais_ida = [_lado_normal("Ida", v, url_ida) for v in idas[:3]]
        combos = []
        for li in normais_ida + lados_ida[1:] if idas else lados_ida:
            for lv in lados_volta:
                combos.append((li["preco"] + lv["preco"], li, lv))
        combos.sort(key=lambda c: c[0])
        vistos, n_sep = set(), 0
        for _, li, lv in combos:
            nome = _nome_jogada([li, lv])
            chave = (nome, li["preco"], lv["preco"])
            if chave in vistos:
                continue
            if nome == "Trechos separados":
                if n_sep >= 3:
                    continue
                n_sep += 1
                extra = [("info", "São duas passagens só de ida, em reservas separadas. Nenhuma regra é violada."),
                         ("aviso", "Mala despachada é cobrada em cada reserva.")]
            else:
                extra = [("info", "Ida e volta em reservas separadas: o que acontecer numa não afeta a outra.")]
            vistos.add(chave)
            opcoes.append(_opcao([li, lv], nome, ida, pax, extra))
    else:
        opcoes += _compra_normal(idas, url_ida, ida, False, pax)
        rt, url_rt = res("rt_falsa")
        if rt and (teto_ida is None or rt[0]["preco"] < teto_ida):
            opcoes += _jogar_fora_volta(rt, url_rt, ida, falsa, pax)
        for lado in lados_ida:
            if lado["tipo"] != "normal":
                opcoes.append(_opcao([lado], _nome_jogada([lado]), ida, pax))
    for lado, viz, prefixo in (("origem", viz_o, "viz_o"), ("destino", viz_d, "viz_d")):
        for cod, km in viz:
            lista, url = res((prefixo, cod))
            if lista:
                opcoes += _opcoes_vizinho(lado, cod, km, lista, url, origem, destino, ida, volta, pax, chao)
                continue
            # sem voo montado pelo Google: conexão montada saindo/chegando no vizinho
            def lados_con(rotulo, hubs, primeiro, segundo):
                lados = []
                for h in hubs:
                    (p, u1), (s, u2) = res(primeiro(h)), res(segundo(h))
                    lados += [_lado_conexao(rotulo, par, u1, u2) for par in _achar_conexoes(h, p, s)]
                return sorted(lados, key=lambda l: l["preco"])
            if lado == "origem":
                l_ida = lados_con("Ida", hubs_ida, lambda h: ("vc_o_ida", cod, h), lambda h: ("con_ida_2", h))
                l_volta = lados_con("Volta", hubs_volta, lambda h: ("con_volta_1", h), lambda h: ("vc_o_volta", cod, h))
            else:
                l_ida = lados_con("Ida", hubs_ida, lambda h: ("con_ida_1", h), lambda h: ("vc_d_ida", cod, h))
                l_volta = lados_con("Volta", hubs_volta, lambda h: ("vc_d_volta", cod, h), lambda h: ("con_volta_2", h))
            if not l_ida or (volta and not l_volta):
                continue
            lados = [l_ida[0]] + ([l_volta[0]] if volta else [])
            op = _opcao(lados, "Aeroporto vizinho", ida, pax,
                        [("info", "Ida e volta em reservas separadas: o que acontecer numa não afeta a outra.")] if volta else [])
            opcoes.append(_aplicar_chao(op, lado, cod, km, origem, destino, ida, volta, pax, chao))
    opcoes.sort(key=lambda o: o["preco"])

    # referência: a compra normal mais barata (mesma reserva ou trechos separados)
    normais = [o["preco"] for o in opcoes if o["risco"] == "baixo" and o["tipo"] != "vizinho"]
    ref = min(normais) if normais else None
    # aeroporto vizinho só aparece se, com a estrada, sair mais barato que a
    # melhor opção do aeroporto pedido (normal ou, sem ela, qualquer jogada)
    proprias = [o["preco"] for o in opcoes if o["tipo"] != "vizinho"]
    ref_viz = ref or (min(proprias) if proprias else None)
    opcoes = [o for o in opcoes if o["tipo"] != "vizinho" or ref_viz is None or o["preco"] < ref_viz]
    # jogada arriscada que não sai mais barata que a compra normal não serve
    opcoes = [o for o in opcoes if o["risco"] == "baixo" or o["tipo"] == "vizinho"
              or ref is None or o["preco"] < ref][:25]
    n_pessoas = sum(pax)
    for o in opcoes:
        base = ref_viz if o["tipo"] == "vizinho" else ref
        o["economia"] = (base - o["preco"]) if base and o["preco"] < base else 0
        o["por_pessoa"] = round(o["preco"] / n_pessoas) if n_pessoas > 1 else None
        if any(p["voo"].get("estimado") for p in o["pernas"]):
            o["estimado"] = True
            o["detalhes"].insert(0, ("aviso", "Preço estimado: o Google não cotou criança em algum trecho, então a criança foi contada como adulto. Nas companhias brasileiras a tarifa de criança costuma ser igual à de adulto; confira o total no site antes de pagar."))
        if o["risco"] != "baixo" and ref and o["economia"] < ref * 0.05:
            o["detalhes"].insert(0, ("aviso", f"Economia de só {_br(o['economia'])} sobre a compra normal: pouco para o risco."))
    return {
        "origem": origem, "destino": destino, "ida": ida, "volta": volta,
        "passageiros": list(pax), "passageiros_txt": descrever_pax(pax),
        "cidade_origem": aeroportos.cidade(origem), "cidade_destino": aeroportos.cidade(destino),
        "referencia": ref, "opcoes": opcoes, "buscas": total,
        "hubs": sorted(set(hubs_ida) | set(hubs_volta)),
        "vizinhos": [c for c, _ in viz_o + viz_d],
        "direto_vazio": not idas,
        "falhas": len(falhas), "aviso_bloqueio": bloqueio,
        "quando": dt.datetime.now().isoformat(timespec="minutes"),
    }


if __name__ == "__main__":
    import json
    import sys
    a = sys.argv[1:]
    pax = tuple(int(x) for x in a[4].split(",")) if len(a) > 4 else gflights.PAX_PADRAO
    r = cacar(a[0], a[1], a[2], a[3] if len(a) > 3 and a[3] != "-" else None, pax,
              lambda f, t: print(f"{f}/{t}", end="\r"))
    print()
    print("referência", r["referencia"], "buscas", r["buscas"], "falhas", r["falhas"], "hubs", r["hubs"], r["passageiros_txt"])
    for o in r["opcoes"]:
        print(o["preco"], o["jogada"], "|", o["paradas"], "| economia", o["economia"], "| risco", o["risco"])
    open("ultima_cacada.json", "w", encoding="utf-8").write(json.dumps(r, ensure_ascii=False, indent=1))
