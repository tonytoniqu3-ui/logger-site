# Bot crypto — le code de l'ebook « Créer son bot crypto de A à Z »

Bot de trading en Python pour Coinbase. Configuration livrée : bitcoin + ether, bougies journalières. Il est fait pour rester honnête avec lui-même :
tous les frais sont comptés, il est testé sur des données jamais vues et toujours comparé à « acheter et garder ».

> ⚠️ Ce code est pédagogique. Ce n'est pas un conseil en investissement. Le trading de cryptos peut
> te faire perdre tout ce que tu y mets. N'utilise que de l'argent que tu peux perdre.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install -r requirements.txt
```

## Les commandes

| Commande | Ce qu'elle fait |
|---|---|
| `python bot.py portfolio` | Teste la configuration complète (BTC + ETH, capital partagé) sur tout l'historique |
| `python bot.py compare` | Teste toutes les stratégies sur une paire (avec les frais) |
| `python bot.py backtest --strategy donchian` | Teste une seule stratégie |
| `python bot.py validate` | Optimise sur 70 % du passé, juge sur les 30 % jamais vus, puis Monte-Carlo |
| `python bot.py paper` | Fait tourner le bot en direct avec 100 € **fictifs** |
| `python research.py` | Refait la recherche : toutes les stratégies × 6 paires × 1 h / 6 h / 1 jour |
| `python bot.py live --yes-real-money` | Argent réel (seulement après des semaines de `paper`) |

Ajoute `--demo` pour tester sans internet sur un marché synthétique.

## Les réglages (`config.json`)

- `products`, `timeframe` : les paires (le capital est partagé à parts égales) et la taille des bougies (`1h`, `6h`, `1d`…)
- `strategy` : `ema_cross`, `rsi_dip`, `donchian`, `macd`, `bollinger`, `trend`, `buy_hold`
- `costs.fee` : 0,006 = 0,6 % par ordre (frais taker Coinbase pour un petit volume, à vérifier sur ton compte)
- `risk.atr_stop` : stop placé à 3 × ATR sous le prix d'achat
- `risk.risk_per_trade` : 0,03 = on perd au plus environ 3 % de la part de capital de la paire si le stop est touché
- `risk.kill_drawdown` : 0,20 = si le capital baisse de 20 % depuis son plus haut, le bot vend tout et s'arrête
- `max_order` : montant maximum d'un ordre, comme garde-fou

## Résultats sur les vraies données (Coinbase, 25 novembre 2026)

Configuration livrée : BTC-EUR + ETH-EUR, bougies 1 jour, Donchian 20/10 + filtre EMA 200, stop 3 × ATR, 3 % de risque, frais 0,6 %.
Réglages choisis sur les 70 % les plus anciens, verdict sur les 30 % récents jamais vus.

| Période | Bot | Acheter et garder | Pire chute du bot | Trades |
|---|---|---|---|---|
| Entraînement (2017-08 → 2024-02) | +129,0 % | +1 214,3 % | −15,6 % | 40 |
| Jamais vue (2024-02 → 2026-11) | +9,8 % | −6,6 % | −9,6 % | 20 |

Le bot gagne beaucoup moins qu'acheter et garder pendant les grandes hausses, et il protège pendant les baisses.
Avec 20 trades seulement sur la période jamais vue, la chance pèse encore lourd. Aucun gain futur n'est garanti.
En bougies de 1 h, toutes les stratégies testées perdent après frais (voir `research.py`).

## Mode réel

1. Crée une clé API sur Coinbase Developer Platform avec les droits **View** et **Trade** seulement, jamais **Transfer**.
2. Copie `.env.example` en `.env` et colle la clé. Le fichier `.env` n'est jamais commité.
3. Lance `python bot.py live --yes-real-money`.

Le bot écrit son journal dans `state/journal_<mode>.csv` et ses messages dans `bot.log`.
Si le coupe-circuit s'est déclenché, le bot refuse de repartir tant que tu n'as pas supprimé
`state/state_<mode>.json`. C'est voulu : il faut d'abord comprendre ce qui s'est passé.

## Organisation du code

```
botcrypto/indicators.py   EMA, RSI, ATR, Donchian, MACD, Bollinger
botcrypto/data.py         bougies Coinbase (API publique) + cache CSV + marché synthétique
botcrypto/strategies.py   les règles : signal 1 = être acheté, 0 = être à plat
botcrypto/backtest.py     simulation avec frais, stop ATR, coupe-circuit, Sharpe, Calmar, Monte-Carlo
botcrypto/broker.py       PaperBroker (simulation) et CoinbaseBroker (réel)
botcrypto/live.py         la boucle du bot en direct
tests/                    python -m pytest
```

## Le desk à 6 agents (`desk.html`)

Ouvre `desk.html` dans ton navigateur (double-clic). Il récupère les vraies bougies Coinbase et montre le bot
au travail, avec 6 agents : Scout (données), Filtre (tendance), Analyste (signal), Risque (protection),
Exécution (ordres) et Journal (suivi).

- **Rejouer 1 000 jours** : rejoue les 1 000 derniers jours en accéléré, sur BTC et ETH en bougies journalières, et compare le résultat à « acheter et garder » le même panier.
- **Direct** : une décision par jour sur les vraies bougies, tant que la page reste ouverte.

C'est toujours une **simulation** : aucun ordre réel n'est passé, et le badge le dit à l'écran.
Si Coinbase est injoignable, la page bascule sur des données synthétiques, et le badge l'indique en rouge.
Les règles sont les mêmes que celles du bot Python (frais, stop ATR, 2 % de risque, coupe-circuit).
