# Bot crypto — le code de l'ebook « Créer son bot crypto de A à Z »

Bot de trading en Python pour Coinbase (BTC-EUR, ETH-EUR…). Il est fait pour rester honnête avec lui-même :
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
| `python bot.py compare` | Teste les 6 stratégies sur 2 ans de BTC-EUR (avec les frais) |
| `python bot.py backtest --strategy donchian` | Teste une seule stratégie |
| `python bot.py validate` | Optimise sur 70 % du passé, juge sur les 30 % jamais vus, puis Monte-Carlo |
| `python bot.py paper` | Fait tourner le bot en direct avec 100 € **fictifs** |
| `python bot.py live --yes-real-money` | Argent réel (seulement après des semaines de `paper`) |

Ajoute `--demo` pour tester sans internet sur un marché synthétique.

## Les réglages (`config.json`)

- `product`, `timeframe` : la paire et la taille des bougies (`1h`, `6h`, `1d`…)
- `strategy` : `ema_cross`, `rsi_dip`, `donchian`, `macd`, `bollinger`, `buy_hold`
- `costs.fee` : 0,006 = 0,6 % par ordre (frais taker Coinbase pour un petit volume, à vérifier sur ton compte)
- `risk.atr_stop` : stop placé à 3 × ATR sous le prix d'achat
- `risk.risk_per_trade` : 0,02 = on perd au plus environ 2 % du capital si le stop est touché
- `risk.kill_drawdown` : 0,20 = si le capital baisse de 20 % depuis son plus haut, le bot vend tout et s'arrête
- `max_order` : montant maximum d'un ordre, comme garde-fou

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
