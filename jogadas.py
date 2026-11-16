"""As jogadas do Rasante: monta todas as formas de comprar a mesma viagem,
com o preço, os detalhes ocultos e o procedimento de cada uma.

Base das regras (pesquisa de 2026-11-16, ver LEIA-ME.md):
- Res. ANAC 400, art. 11: desistência sem custo em 24 h do comprovante,
  se a compra foi feita 7 dias ou mais antes do voo.
- Res. ANAC 400, art. 19: no-show na ida pode cancelar a volta, salvo aviso
  até o horário da ida.
- Escala oculta viola o contrato das companhias (American baniu passageiro
  em 2023; júri deu US$ 9,4 mi à American contra o Skiplagged em 2024).
"""
import datetime as dt
import time
from concurrent.futures import ThreadPoolExecutor

import aeroportos
import gflights

_CACHE = {}
_VALIDADE_CACHE = 30 * 60


def _buscar(trechos, ida_e_volta=False):
    chave = (tuple(trechos), ida_e_volta)
    agora = time.time()
    if chave in _CACHE and agora - _CACHE[chave][0] < _VALIDADE_CACHE:
        return _CACHE[chave][1]
    resultado = gflights.buscar(list(trechos), ida_e_volta)
    _CACHE[chave] = (agora, resultado)
    return resultado


def _br(valor):
    return "R$ " + f"{valor:,.0f}".replace(",", ".")


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


def _regra_24h(data_ida):
    dias = (dt.date.fromisoformat(data_ida) - dt.date.today()).days
    if dias >= 7:
        return ("Dá para desistir sem multa em até 24 horas depois de receber o comprovante, "
                "porque o voo é daqui a 7 dias ou mais (Res. ANAC 400, art. 11). Compre e continue caçando.")
    return ("O voo é daqui a menos de 7 dias: a desistência grátis de 24 horas da ANAC não vale. "
            "Compre só quando tiver certeza.")


# ---------- jogadas ----------

def _compra_normal(ida_e_volta, url, data_ida, tem_volta):
    opcoes = []
    for v in ida_e_volta[:6]:
        detalhes = [
            ("info", "Compra comum, sem violar regra nenhuma da companhia."),
            ("info", "Tarifa básica costuma não incluir mala despachada; confira antes de pagar."),
        ]
        if len(v["trechos"]) > 1:
            detalhes.append(("info", f"Conexão em {', '.join(v['escalas'])}; confira o tempo entre os voos."))
        detalhes.append(("info", _regra_24h(data_ida)))
        if tem_volta:
            detalhes.append(("info", "O preço é o total de ida e volta na mesma reserva; a volta você escolhe na tela seguinte do Google Flights."))
        passos = [
            f"Abra a busca no Google Flights pelo link desta opção.",
            f"Escolha o voo de ida: {_desc_voo(v)}.",
        ]
        if tem_volta:
            passos.append("Na tela seguinte, escolha a volta mais barata.")
        passos += [
            "Em \"Opções de reserva\", prefira comprar direto no site da companhia (remarcação e reembolso mais fáceis).",
            "Guarde o comprovante: as 24 horas de desistência contam a partir dele.",
        ]
        opcoes.append({
            "tipo": "normal", "jogada": "Compra normal",
            "preco": v["preco"], "paradas": _paradas(v), "risco": "baixo",
            "pernas": [_perna("Ida", v)], "detalhes": detalhes, "passos": passos, "link": url,
        })
    return opcoes


def _trechos_separados(idas, voltas, url_ida, url_volta, data_ida):
    opcoes = []
    combos = sorted(((i["preco"] + v["preco"], i, v) for i in idas[:4] for v in voltas[:4]),
                    key=lambda c: c[0])
    vistos = set()
    for total, i, v in combos:
        chave = (i["preco"], v["preco"])
        if chave in vistos:
            continue
        vistos.add(chave)
        cias = set(i["companhias"]) | set(v["companhias"])
        detalhes = [
            ("info", "São duas passagens só de ida, em reservas separadas. Nenhuma regra é violada."),
            ("aviso", "Mala despachada é cobrada em cada reserva."),
            ("info", "Se a ida for cancelada, a volta continua valendo (e vice-versa); cada reserva tem seu próprio reembolso."),
            ("info", _regra_24h(data_ida)),
        ]
        if len(cias) > 1:
            detalhes.insert(1, ("info", f"Companhias diferentes na ida e na volta ({' e '.join(sorted(cias))})."))
        passos = [
            f"Compre a ida só de ida: {_desc_voo(i)} ({_br(i['preco'])}).",
            f"Compre a volta só de ida: {_desc_voo(v)} ({_br(v['preco'])}).",
            "Use o mesmo nome e documento nas duas; ponha o seu número de fidelidade nas duas, pode.",
            "Faça o check-in de cada reserva separadamente.",
        ]
        opcoes.append({
            "tipo": "separados", "jogada": "Trechos separados",
            "preco": total, "paradas": f"{_paradas(i)} / {_paradas(v)}", "risco": "baixo",
            "pernas": [_perna("Ida", i), _perna("Volta", v)], "detalhes": detalhes, "passos": passos,
            "link": url_ida, "link_volta": url_volta,
        })
        if len(opcoes) >= 4:
            break
    return opcoes


def _escalas_ocultas(origem, destino, data, rotulo, buscas):
    """buscas: {destino_alem: (voos, url)} para origem -> destino_alem."""
    achados = []
    for alem, (voos, url) in buscas.items():
        for v in voos:
            if not any(aeroportos.mesma_cidade(e, destino) for e in v["escalas"]):
                continue
            desce = next(e for e in v["escalas"] if aeroportos.mesma_cidade(e, destino))
            # trechos usados de verdade, até a escala
            usados = []
            for t in v["trechos"]:
                usados.append(t)
                if t["para"] == desce:
                    break
            achados.append((v["preco"], v, desce, url, usados))
    achados.sort(key=lambda a: a[0])
    return achados


def _opcao_oculta(rotulo, v, desce, url, usados, data_ida):
    jogados = [t for t in v["trechos"][len(usados):]]
    detalhes = [
        ("risco", "Só bagagem de mão. Mala despachada segue para o destino final do bilhete, não para onde você desce."),
        ("risco", "Mala pequena: se o voo lotar, a companhia pode mandar sua mala de mão para o porão, e aí ela segue para o destino final."),
        ("risco", "Não informe número de fidelidade (milhas). Violar o contrato pode custar a conta e as milhas."),
        ("risco", "Só funciona em passagem só de ida: depois do trecho que você não usa, tudo o que vier na mesma reserva é cancelado."),
        ("risco", "Viola o contrato da companhia. A American baniu um passageiro por isso em 2023. Não repita na mesma companhia com frequência."),
        ("aviso", "Se a companhia mudar o voo e tirar a escala em " + desce + ", você pode acabar voando até o destino final."),
        ("info", _regra_24h(data_ida)),
    ]
    passos = [
        f"Compre só de ida {v['origem']} → {v['destino']} ({aeroportos.cidade(v['destino'])}): {_desc_voo(v)}.",
        "Na compra, não informe número de fidelidade e não compre mala despachada.",
        "Faça o check-in normalmente; o cartão de embarque vai mostrar os dois trechos.",
        f"Embarque no voo até {desce} ({aeroportos.cidade(desce)}).",
        f"Em {desce}, saia pelo desembarque. Não embarque em {', '.join(t['voo'] for t in jogados)} para {v['destino']}.",
    ]
    return {
        "tipo": "oculta", "jogada": "Escala oculta",
        "preco": v["preco"], "paradas": f"desce em {desce}", "risco": "alto",
        "pernas": [_perna(rotulo, v, desce)], "detalhes": detalhes, "passos": passos, "link": url,
    }


def _jogar_fora_volta(rt, url, data_ida, data_volta_falsa):
    opcoes = []
    for v in rt[:3]:
        detalhes = [
            ("aviso", "Você compra ida e volta e não usa a volta. Como é o último trecho, nada mais é cancelado."),
            ("aviso", "Algumas companhias proíbem isso no contrato; em voo doméstico no Brasil a cobrança da diferença é rara, mas não use número de fidelidade."),
            ("info", f"A volta fica marcada para {data_volta_falsa}; não precisa fazer nada nesse dia."),
            ("info", _regra_24h(data_ida)),
        ]
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
            "pernas": [_perna("Ida", v)], "detalhes": detalhes, "passos": passos, "link": url,
        })
    return opcoes


# ---------- caçada ----------

def cacar(origem, destino, ida, volta=None, ao_progresso=None):
    origem, destino = origem.upper().strip(), destino.upper().strip()
    tarefas = {}
    tarefas["ida"] = ([(ida, origem, destino)], False)
    if volta:
        tarefas["volta"] = ([(volta, destino, origem)], False)
        tarefas["rt"] = ([(ida, origem, destino), (volta, destino, origem)], True)
    else:
        falsa = (dt.date.fromisoformat(ida) + dt.timedelta(days=7)).isoformat()
        tarefas["rt_falsa"] = ([(ida, origem, destino), (falsa, destino, origem)], True)
    for x in aeroportos.alem_de(origem, destino):
        tarefas[("oculta_ida", x)] = ([(ida, origem, x)], False)
    if volta:
        for x in aeroportos.alem_de(destino, origem):
            tarefas[("oculta_volta", x)] = ([(volta, destino, x)], False)

    resultados, falhas, bloqueio = {}, [], None
    total, feitos = len(tarefas), 0
    with ThreadPoolExecutor(max_workers=4) as ex:
        futuros = {ex.submit(_buscar, tuple(t), rt): k for k, (t, rt) in tarefas.items()}
        for f, k in futuros.items():
            try:
                resultados[k] = f.result()
            except gflights.Bloqueado as e:
                bloqueio = str(e)
            except Exception as e:  # rota sem voo, rede, formato mudou
                falhas.append(f"{k}: {e}")
            feitos += 1
            if ao_progresso:
                ao_progresso(feitos, total)
    if bloqueio and not resultados:
        raise gflights.Bloqueado(bloqueio)

    opcoes = []
    idas, url_ida = resultados.get("ida", ([], None))
    if volta:
        voltas, url_volta = resultados.get("volta", ([], None))
        rt, url_rt = resultados.get("rt", ([], None))
        opcoes += _compra_normal(rt, url_rt, ida, True)
        if idas and voltas:
            opcoes += _trechos_separados(idas, voltas, url_ida, url_volta, ida)
    else:
        opcoes += _compra_normal(idas, url_ida, ida, False)
        rt, url_rt = resultados.get("rt_falsa", ([], None))
        mais_barata_ida = idas[0]["preco"] if idas else None
        falsa = (dt.date.fromisoformat(ida) + dt.timedelta(days=7)).isoformat()
        if rt and (mais_barata_ida is None or rt[0]["preco"] < mais_barata_ida):
            opcoes += _jogar_fora_volta(rt, url_rt, ida, falsa)

    ocultas_ida = _escalas_ocultas(origem, destino, ida, "Ida",
                                   {k[1]: v for k, v in resultados.items() if isinstance(k, tuple) and k[0] == "oculta_ida"})
    teto_ida = idas[0]["preco"] if idas else None
    ocultas_ida = [a for a in ocultas_ida if teto_ida is None or a[0] < teto_ida][:3]

    if not volta:
        for preco, v, desce, url, usados in ocultas_ida:
            opcoes.append(_opcao_oculta("Ida", v, desce, url, usados, ida))
    else:
        voltas, url_volta = resultados.get("volta", ([], None))
        ocultas_volta = _escalas_ocultas(destino, origem, volta, "Volta",
                                         {k[1]: v for k, v in resultados.items() if isinstance(k, tuple) and k[0] == "oculta_volta"})
        teto_volta = voltas[0]["preco"] if voltas else None
        ocultas_volta = [a for a in ocultas_volta if teto_volta is None or a[0] < teto_volta][:3]
        # combina cada lado oculto com o melhor do outro lado (oculto ou normal)
        lados_ida = [("oculta", a) for a in ocultas_ida] + ([("normal", idas[0])] if idas else [])
        lados_volta = [("oculta", a) for a in ocultas_volta] + ([("normal", voltas[0])] if voltas else [])
        for ti, a in lados_ida:
            for tv, b in lados_volta:
                if ti == "normal" and tv == "normal":
                    continue  # já está em "Trechos separados"
                opcoes.append(_combo_oculta(ti, a, tv, b, url_ida, url_volta, ida))
    opcoes.sort(key=lambda o: o["preco"])

    # referência: a compra normal mais barata
    normais = [o["preco"] for o in opcoes if o["tipo"] in ("normal", "separados")]
    ref = min(normais) if normais else None
    for o in opcoes:
        o["economia"] = (ref - o["preco"]) if ref and o["preco"] < ref else 0
        if o["risco"] != "baixo" and ref and o["economia"] < ref * 0.05:
            o["detalhes"].insert(0, ("aviso", f"Economia de só {_br(o['economia'])} sobre a compra normal: pouco para o risco."))
    return {
        "origem": origem, "destino": destino, "ida": ida, "volta": volta,
        "cidade_origem": aeroportos.cidade(origem), "cidade_destino": aeroportos.cidade(destino),
        "referencia": ref, "opcoes": opcoes, "buscas": total,
        "falhas": len(falhas), "aviso_bloqueio": bloqueio,
        "quando": dt.datetime.now().isoformat(timespec="minutes"),
    }


def _combo_oculta(ti, a, tv, b, url_ida, url_volta, data_ida):
    partes, pernas, detalhes, passos, links = [], [], [], [], {}
    preco = 0
    for rotulo, tipo, x, url_normal in (("Ida", ti, a, url_ida), ("Volta", tv, b, url_volta)):
        if tipo == "oculta":
            p, v, desce, url, usados = x
            o = _opcao_oculta(rotulo, v, desce, url, usados, data_ida)
            preco += p
            pernas += o["pernas"]
            passos += [f"{rotulo}: {s}" for s in o["passos"]]
            detalhes += [d for d in o["detalhes"] if d not in detalhes and "24 horas" not in d[1]]
            links["link" if rotulo == "Ida" else "link_volta"] = url
            partes.append(f"{rotulo.lower()} com escala oculta")
        else:
            v = x
            preco += v["preco"]
            pernas.append(_perna(rotulo, v))
            passos.append(f"{rotulo}: compre só de ida {_desc_voo(v)} ({_br(v['preco'])}).")
            links["link" if rotulo == "Ida" else "link_volta"] = url_normal
            partes.append(f"{rotulo.lower()} normal")
    detalhes.append(("info", "São duas reservas separadas; a escala oculta em uma não afeta a outra."))
    detalhes.append(("info", _regra_24h(data_ida)))
    return {
        "tipo": "oculta", "jogada": "Escala oculta",
        "preco": preco, "paradas": " + ".join(partes), "risco": "alto",
        "pernas": pernas, "detalhes": detalhes, "passos": passos, **links,
    }


if __name__ == "__main__":
    import json
    import sys
    args = sys.argv[1:] + [None] * 4
    r = cacar(args[0], args[1], args[2], args[3], lambda f, t: print(f"{f}/{t}", end="\r"))
    print()
    print("referência", r["referencia"], "buscas", r["buscas"], "falhas", r["falhas"])
    for o in r["opcoes"]:
        print(o["preco"], o["jogada"], "|", o["paradas"], "| economia", o["economia"])
    open("ultima_cacada.json", "w", encoding="utf-8").write(json.dumps(r, ensure_ascii=False, indent=1))
