"""Tabela de aeroportos usada para escolher onde testar a escala oculta.

Coordenadas aproximadas (graus). Serve para achar destinos que ficam "depois"
do destino pedido, na mesma direção, onde a escala pode cair no destino.
"""
import math

AEROPORTOS = {
    # código: (cidade, lat, lon, país)
    "BEL": ("Belém", -1.38, -48.48, "BR"), "MAO": ("Manaus", -3.04, -60.05, "BR"),
    "STM": ("Santarém", -2.42, -54.79, "BR"), "MCP": ("Macapá", 0.05, -51.07, "BR"),
    "SLZ": ("São Luís", -2.59, -44.24, "BR"), "THE": ("Teresina", -5.06, -42.82, "BR"),
    "FOR": ("Fortaleza", -3.78, -38.53, "BR"), "NAT": ("Natal", -5.77, -35.37, "BR"),
    "JPA": ("João Pessoa", -7.15, -34.95, "BR"), "REC": ("Recife", -8.13, -34.92, "BR"),
    "MCZ": ("Maceió", -9.51, -35.79, "BR"), "AJU": ("Aracaju", -10.98, -37.07, "BR"),
    "SSA": ("Salvador", -12.91, -38.33, "BR"), "IOS": ("Ilhéus", -14.82, -39.03, "BR"),
    "BPS": ("Porto Seguro", -16.44, -39.08, "BR"), "IMP": ("Imperatriz", -5.53, -47.46, "BR"),
    "MAB": ("Marabá", -5.37, -49.14, "BR"), "PMW": ("Palmas", -10.29, -48.36, "BR"),
    "BSB": ("Brasília", -15.87, -47.92, "BR"), "GYN": ("Goiânia", -16.63, -49.22, "BR"),
    "CGB": ("Cuiabá", -15.65, -56.12, "BR"), "CGR": ("Campo Grande", -20.47, -54.67, "BR"),
    "UDI": ("Uberlândia", -18.88, -48.23, "BR"), "CNF": ("Belo Horizonte", -19.63, -43.97, "BR"),
    "VIX": ("Vitória", -20.26, -40.29, "BR"), "GIG": ("Rio de Janeiro", -22.81, -43.25, "BR"),
    "SDU": ("Rio de Janeiro", -22.91, -43.16, "BR"), "GRU": ("São Paulo", -23.43, -46.47, "BR"),
    "CGH": ("São Paulo", -23.63, -46.66, "BR"), "VCP": ("Campinas", -23.01, -47.13, "BR"),
    "RAO": ("Ribeirão Preto", -21.13, -47.78, "BR"), "LDB": ("Londrina", -23.33, -51.13, "BR"),
    "MGF": ("Maringá", -23.48, -52.01, "BR"), "CWB": ("Curitiba", -25.53, -49.18, "BR"),
    "IGU": ("Foz do Iguaçu", -25.60, -54.49, "BR"), "JOI": ("Joinville", -26.22, -48.80, "BR"),
    "NVT": ("Navegantes", -26.88, -48.65, "BR"), "FLN": ("Florianópolis", -27.67, -48.55, "BR"),
    "POA": ("Porto Alegre", -29.99, -51.17, "BR"), "PVH": ("Porto Velho", -8.71, -63.90, "BR"),
    "RBR": ("Rio Branco", -9.87, -67.89, "BR"), "BVB": ("Boa Vista", 2.85, -60.69, "BR"),
    "CAC": ("Cascavel", -24.99, -53.50, "BR"), "XAP": ("Chapecó", -27.13, -52.66, "BR"),
    "CXJ": ("Caxias do Sul", -29.20, -51.19, "BR"), "PFB": ("Passo Fundo", -28.24, -52.33, "BR"),
    "JDO": ("Juazeiro do Norte", -7.22, -39.27, "BR"), "PNZ": ("Petrolina", -9.36, -40.57, "BR"),
    "MOC": ("Montes Claros", -16.71, -43.82, "BR"), "IPN": ("Ipatinga", -19.47, -42.49, "BR"),
    "SJP": ("São José do Rio Preto", -20.82, -49.41, "BR"), "PPB": ("Presidente Prudente", -22.18, -51.42, "BR"),
    "UBA": ("Uberaba", -19.76, -47.97, "BR"), "CPV": ("Campina Grande", -7.27, -35.90, "BR"),
    "JJD": ("Jericoacoara", -2.91, -40.36, "BR"), "FEN": ("Fernando de Noronha", -3.85, -32.42, "BR"),
    "ATM": ("Altamira", -3.25, -52.25, "BR"), "CKS": ("Parauapebas", -6.12, -50.00, "BR"),
    "ROO": ("Rondonópolis", -16.59, -54.72, "BR"), "TBT": ("Tabatinga", -4.25, -69.94, "BR"),
    "EZE": ("Buenos Aires", -34.82, -58.54, "AR"), "AEP": ("Buenos Aires", -34.56, -58.42, "AR"),
    "MVD": ("Montevidéu", -34.84, -56.03, "UY"), "ASU": ("Assunção", -25.24, -57.52, "PY"),
    "SCL": ("Santiago", -33.39, -70.79, "CL"), "LIM": ("Lima", -12.02, -77.11, "PE"),
    "BOG": ("Bogotá", 4.70, -74.15, "CO"), "PTY": ("Cidade do Panamá", 9.07, -79.38, "PA"),
    "CAY": ("Caiena", 4.82, -52.36, "GF"), "PBM": ("Paramaribo", 5.45, -55.19, "SR"),
    "MIA": ("Miami", 25.79, -80.29, "US"), "MCO": ("Orlando", 28.43, -81.31, "US"),
    "JFK": ("Nova York", 40.64, -73.78, "US"), "CUN": ("Cancún", 21.04, -86.87, "MX"),
    "LIS": ("Lisboa", 38.77, -9.13, "PT"), "OPO": ("Porto", 41.24, -8.68, "PT"),
    "MAD": ("Madri", 40.47, -3.56, "ES"), "CDG": ("Paris", 49.01, 2.55, "FR"),
}

# Aeroportos da mesma cidade: descer em qualquer um deles serve.
MESMA_CIDADE = [{"GRU", "CGH"}, {"GIG", "SDU"}, {"EZE", "AEP"}]

# Usados quando a rota tem aeroporto fora da tabela.
HUBS_PADRAO = ["GRU", "BSB", "GIG", "CNF", "REC", "SSA", "FOR", "VCP", "POA", "CWB"]


def mesma_cidade(a, b):
    if a == b:
        return True
    return any(a in g and b in g for g in MESMA_CIDADE)


def cidade(codigo):
    a = AEROPORTOS.get(codigo)
    return a[0] if a else codigo


def _dist(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[1], a[2], b[1], b[2]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def _rumo(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[1], a[2], b[1], b[2]))
    y = math.sin(lo2 - lo1) * math.cos(la2)
    x = math.cos(la1) * math.sin(la2) - math.sin(la1) * math.cos(la2) * math.cos(lo2 - lo1)
    return math.degrees(math.atan2(y, x)) % 360


HUBS_CONEXAO = ["GRU", "CGH", "VCP", "BSB", "GIG", "SDU", "CNF", "REC", "FOR", "SSA", "POA", "CWB"]


def hubs_entre(origem, destino, quantos=2):
    """Hubs no caminho, para montar a conexão com dois bilhetes separados.

    Critério: o desvio (origem-hub + hub-destino) fica até 35% maior que o
    voo direto.
    """
    a, b = AEROPORTOS.get(origem), AEROPORTOS.get(destino)
    if not a or not b:
        return [h for h in ("GRU", "BSB") if h not in (origem, destino)][:quantos]
    d_ab = _dist(a, b)
    cand = []
    for h in HUBS_CONEXAO:
        if mesma_cidade(h, origem) or mesma_cidade(h, destino):
            continue
        x = AEROPORTOS[h]
        razao = (_dist(a, x) + _dist(x, b)) / d_ab
        if razao < 1.35:
            cand.append((razao, h))
    cand.sort()
    escolhidos, cidades = [], []
    for _, h in cand:
        if any(mesma_cidade(h, c) for c in cidades):
            continue  # GRU e CGH contam como um hub só
        escolhidos.append(h)
        cidades.append(h)
        if len(escolhidos) == quantos:
            break
    return escolhidos


def alem_de(origem, destino, quantos=6):
    """Destinos que ficam depois de `destino`, vindo de `origem`.

    Um voo origem -> X muitas vezes faz escala em `destino`; é ali que a
    escala oculta acontece.
    """
    a, b = AEROPORTOS.get(origem), AEROPORTOS.get(destino)
    if not a or not b:
        return [h for h in HUBS_PADRAO if h not in (origem, destino)][:quantos]
    d_ab, rumo_ab = _dist(a, b), _rumo(a, b)
    mesmo_pais = a[3] == b[3]
    candidatos = []
    for cod, x in AEROPORTOS.items():
        if cod in (origem, destino) or mesma_cidade(cod, destino) or mesma_cidade(cod, origem):
            continue
        if mesmo_pais and x[3] != b[3]:
            continue  # escala oculta em voo internacional cai na imigração; fica de fora
        d_ax = _dist(a, x)
        diff = abs((_rumo(a, x) - rumo_ab + 180) % 360 - 180)
        if d_ax > d_ab * 0.85 and diff < 70:
            candidatos.append((_dist(b, x), cod))
    candidatos.sort()
    return [c for _, c in candidatos[:quantos]]
