# Rasante

Caçador pessoal de passagens aéreas. Você digita origem, destino, ida e volta;
ele busca no Google Flights todas as formas de comprar a mesma viagem e lista
da mais barata para a mais cara, com os detalhes ocultos (riscos) e o
procedimento de cada jogada. Também vigia rotas salvas e avisa no Telegram
quando o preço chega na meta.

## Como usar

1. Duplo clique em `TESTAR - index.html.bat`. Abre em http://127.0.0.1:8740/.
2. Códigos de 3 letras do aeroporto (BEL, GRU, CGH, GIG...). Sem data de volta,
   ele caça só a ida.
3. Telegram: engrenagem no canto, siga os três passos (BotFather, colar o
   código, mandar /start e Conectar).

A vigia só roda com o Rasante aberto neste computador.

## Jogadas testadas

| Jogada | Quando aparece | Risco |
|---|---|---|
| Compra normal | sempre | baixo |
| Trechos separados | com volta: duas passagens só de ida | baixo |
| Conexão montada | dois bilhetes só de ida por um hub no caminho (até 2 hubs), com 3 h a 10 h de espera | médio |
| Escala oculta | voo para uma cidade além do destino, com escala no destino, mais barato que o direto | alto |
| Ida e volta jogando fora a volta | sem volta: quando ida e volta sai mais barato que só ida | médio |

Jogada arriscada que não sai mais barata que a compra normal não aparece.

## Pessoas

Adultos, crianças (2 a 11 anos) e bebês de colo, até 9. Os preços são o total
do grupo, com o valor por pessoa embaixo. Em alguns trechos o Google não cota
criança e devolve vazio (Cascavel, nov/2026); aí a criança é cotada como
adulto e a opção sai marcada como "estimado".

## Quando vem vazio

O Google Flights às vezes não monta o voo (Cascavel → Belém em jun/2027 veio
vazio, com Cascavel → Campinas e Campinas → Belém à venda). Por isso existe a
conexão montada. Se nem ela achar, a tela explica as causas prováveis (data
além de ~330 dias, código errado, rota sem voo no dia).

Todas trazem a regra da ANAC de desistência em 24 h (Res. 400, art. 11: compra
7 dias ou mais antes do voo).

## Como funciona por dentro

- `gflights.py`: raspador próprio. Monta o parâmetro `tfs` (protobuf em base64)
  que a página do Google Flights usa, baixa o HTML e lê o bloco `ds:1`. Se o
  Google mudar o formato, o ajuste é aqui. Se o Google pedir verificação
  (captcha), o Rasante para e avisa; não contorna.
- `aeroportos.py`: tabela de aeroportos e a escolha dos destinos "além" do
  destino para testar escala oculta (mesma direção, mais longe).
- `jogadas.py`: monta as opções, os detalhes ocultos e o procedimento.
- `servidor.py`: servidor local (só 127.0.0.1), caçada em segundo plano com
  progresso, vigia a cada N horas e Telegram. Dados em `dados/` (fora do git):
  `vigias.json` e `config.json` (código do bot).
- `web/`: a tela, HTML/CSS/JS puros, fiel a `imagens/tela-principal-v1.jpg`.

## Limites conhecidos

- Uma caçada com volta faz cerca de 23 buscas no Google Flights (só ida, 12).
  Cache de 30 min por busca. Uso pesado pode levar o Google a pedir captcha.
- Só a primeira tela de resultados do Google Flights é lida.
- Preço em milhas não entra (Smiles, LATAM Pass, Azul não aparecem no Google).
- Escala oculta só é testada em voos domésticos quando origem e destino são do
  mesmo país (no internacional a imigração na escala atrapalha).
