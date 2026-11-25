---
title: "Créer son bot crypto de A à Z"
subtitle: "Python · Coinbase · Claude — de zéro jusqu'au bot qui tourne"
---

# Avant de commencer

## Ce que tu vas construire

À la fin de ce guide, tu auras un bot de trading qui :

- télécharge l'historique des prix de Coinbase (les « bougies ») ;
- calcule des indicateurs (EMA, RSI, ATR, Donchian, MACD, Bollinger) ;
- applique des règles d'achat et de vente que tu as écrites ;
- se teste lui-même sur deux ans d'historique, frais compris ;
- se juge sur des données qu'il n'a jamais vues et se compare à « acheter et garder » ;
- tourne en direct, d'abord avec de l'argent fictif, puis, si tu le décides, avec de l'argent réel ;
- protège ton capital avec un stop, une taille de position calculée et un coupe-circuit à −20 %.

Tout le code est fourni dans le dossier `bot-crypto`. Tu peux le lire, le lancer et le modifier.

## Ce que ce guide ne te promettra pas

Tu as peut-être vu des vidéos du type « J'ai laissé une IA trader seule : 100 € → 200 € en deux jours ».
Deux jours, c'est du bruit. Sur deux jours, une pièce de monnaie peut aussi « doubler ».
Ce qui compte, c'est le comportement sur des mois, frais compris, comparé à ne rien faire.

La plupart des bots amateurs **perdent de l'argent**, surtout à cause des frais. Ce guide t'apprend
à construire un bot honnête, qui te dit la vérité, même quand elle est décevante. Un bot qui te dit
« cette stratégie ne marche pas » t'a fait économiser de l'argent.

> **Avertissement.** Ce guide est éducatif. Ce n'est pas un conseil en investissement.
> Les cryptoactifs sont très volatils et tu peux perdre la totalité de ton capital.
> N'engage que des sommes que tu peux te permettre de perdre. Les performances passées
> ne préjugent pas des performances futures.

## Le plan

1. Partir de zéro : installer Python et VS Code, et le Python indispensable
2. Les bases : comment marchent un bot et un échange de cryptos
3. Avec Claude : construire le bot sans tout coder toi-même
4. Les données : bougies et indicateurs
5. Les stratégies : écrire des règles, backtester, valider honnêtement
6. Les méthodes reconnues : Donchian, MACD, Bollinger, filtres, Sharpe, Calmar, Monte-Carlo
7. Le direct : gestion du risque, simulation, suivi, dépannage
8. Le bilan : résultats, erreurs à éviter, checklist complète

# Chapitre 1 — Partir de zéro

## 1.1 Installer Python

**Windows**

1. Va sur python.org, rubrique *Downloads*, et télécharge la dernière version 3 (3.12 ou plus récente).
2. Lance l'installateur et **coche « Add python.exe to PATH »** avant de cliquer sur *Install Now*.
   C'est l'oubli numéro un.
3. Ouvre l'*Invite de commandes* et tape `python --version`. Tu dois voir `Python 3.x.x`.

**macOS**

1. Télécharge l'installateur sur python.org et lance-le.
2. Dans le *Terminal*, tape `python3 --version`.

Sur Mac et Linux, la commande s'appelle souvent `python3` au lieu de `python`. Dans ce guide,
remplace `python` par `python3` si besoin.

## 1.2 Installer VS Code

1. Télécharge Visual Studio Code sur code.visualstudio.com et installe-le.
2. Ouvre-le, clique sur l'icône *Extensions* (les quatre carrés à gauche) et installe l'extension **Python** de Microsoft.
3. *Fichier → Ouvrir le dossier…* et choisis le dossier `bot-crypto`.
4. Ouvre un terminal intégré : *Terminal → Nouveau terminal*. Tout se passera là.

## 1.3 Créer un environnement virtuel

Un environnement virtuel est une boîte isolée qui contient les bibliothèques de ton projet.
Comme ça, tu ne mélanges pas les projets entre eux.

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

Quand l'environnement est actif, tu vois `(.venv)` au début de la ligne du terminal.
Dans VS Code, choisis-le aussi en bas à droite (*Sélectionner l'interpréteur*).

## 1.4 Le Python indispensable

Tu n'as pas besoin d'être développeur. Tu as besoin de **lire** du code et d'en modifier un peu.
Voici les 10 notions qui suffisent pour ce projet.

**Variables et types**

```python
capital = 100.0          # un nombre à virgule (float)
paire = "BTC-EUR"        # du texte (str)
en_position = False      # vrai ou faux (bool)
```

**Listes et dictionnaires**

```python
prix = [58000, 58200, 57900]                       # une liste
config = {"paire": "BTC-EUR", "frais": 0.006}      # un dictionnaire : clé -> valeur
print(prix[0], config["frais"])                    # 58000 0.006
```

**Conditions**

```python
if rsi < 30:
    print("survendu")
elif rsi > 70:
    print("suracheté")
else:
    print("neutre")
```

L'indentation (les 4 espaces) n'est pas décorative : c'est elle qui dit à Python ce qui est « dans » le `if`.

**Boucles**

```python
for p in prix:
    print(p)
```

**Fonctions**

```python
def variation(ancien, nouveau):
    return nouveau / ancien - 1

print(variation(100, 110))   # 0.1, soit +10 %
```

**Modules et import**

```python
import pandas as pd                     # une bibliothèque externe
from botcrypto import indicators        # un fichier du projet
```

**pandas en trois lignes.** pandas manipule des tableaux (des *DataFrame*). Chaque colonne est une *Series*.

```python
df["close"]                 # la colonne des prix de clôture
df["close"].iloc[-1]        # la dernière valeur
df["close"].rolling(20).mean()   # la moyenne mobile sur 20 bougies
```

**Les erreurs.** Une erreur Python se lit **de bas en haut** : la dernière ligne dit ce qui ne va pas,
les lignes au-dessus disent où. Copie-la telle quelle à Claude : c'est souvent la façon la plus rapide de la corriger.

**try / except**

```python
try:
    prix = recuperer_prix()
except Exception as e:
    print("Problème réseau :", e)
```

Un bot qui tourne 24 h/24 *va* rencontrer des coupures réseau. Il doit les encaisser sans planter.

**Lancer un script**

```bash
python bot.py compare
```

# Chapitre 2 — Les bases

## 2.1 Un bot, c'est quoi ?

Un bot de trading est une boucle très simple :

1. **Observer** : récupérer les derniers prix.
2. **Décider** : appliquer des règles écrites à l'avance (« si le prix casse le plus haut des 20 dernières heures, j'achète »).
3. **Agir** : passer un ordre, ou ne rien faire.
4. **Noter** : écrire ce qu'il a fait dans un journal.
5. **Attendre** la prochaine bougie, et recommencer.

Le bot n'est pas plus intelligent que ses règles. Son seul avantage sur toi : il applique les règles
sans peur, sans avidité et sans fatigue, à 3 h du matin comme à midi.

## 2.2 Comment marche un échange

Un échange comme Coinbase met en relation des acheteurs et des vendeurs.

- **La paire** : `BTC-EUR` veut dire « acheter ou vendre du bitcoin contre des euros ».
  BTC est la devise *de base*, EUR la devise *de cotation*.
- **Le carnet d'ordres** : la liste des offres d'achat (*bids*) et de vente (*asks*). L'écart entre
  le meilleur acheteur et le meilleur vendeur s'appelle le **spread**.
- **Ordre au marché** : « achète tout de suite au meilleur prix disponible ». Exécuté immédiatement,
  mais tu paies le spread et les frais *taker*.
- **Ordre à cours limité** : « achète seulement à 58 000 € ou moins ». Moins cher (frais *maker*),
  mais il peut ne jamais être exécuté.
- **Le glissement (slippage)** : la différence entre le prix que tu voyais et le prix obtenu.

## 2.3 Les frais, le vrai adversaire

Sur Coinbase Advanced, pour un petit volume, les frais *taker* tournent autour de **0,6 % par ordre**,
et les frais *maker* autour de 0,4 %. Les barèmes changent : vérifie les tiens dans ton compte.

Un aller-retour (acheter puis revendre) coûte donc environ **1,2 %**, plus le glissement.
Un bot qui fait 100 allers-retours par an paie environ 120 % de frais cumulés sur l'argent engagé.
Il doit gagner *énormément* juste pour revenir à zéro.

**Conséquence : un bon bot amateur trade peu.** Des bougies d'une heure ou plus, des signaux rares.

## 2.4 L'API et les clés

L'**API** est la porte d'entrée des programmes sur Coinbase. Il y en a deux sortes :

- **publique**, sans clé : les prix et les bougies. Le backtest et la simulation n'utilisent que celle-là ;
- **privée**, avec une clé : ton solde et tes ordres. Seul le mode réel en a besoin.

Règles d'or des clés API :

1. Droits **View** et **Trade** seulement. **Jamais Transfer** (retraits). Si ta clé fuit, personne ne pourra vider ton compte vers l'extérieur.
2. La clé va dans un fichier `.env` qui n'est **jamais** partagé, envoyé ou publié (il est dans `.gitignore`).
3. Ne colle jamais ta clé dans une conversation, même avec une IA.
4. Si tu as un doute, supprime la clé et recrée-en une.

# Chapitre 3 — Construire le bot avec Claude

## 3.1 La bonne méthode

Claude peut écrire l'essentiel du code. Ton rôle est de **décider**, de **vérifier** et de **tester**.
La méthode qui marche :

1. Une petite étape à la fois. Jamais « fais-moi un bot qui gagne de l'argent ».
2. Pour chaque étape : tu décris ce que tu veux, Claude écrit le code, tu le lances, tu colles le résultat ou l'erreur.
3. Tu demandes des **tests** pour chaque morceau important.
4. Tu demandes à Claude de **chercher les failles** de ton propre backtest.

## 3.2 Les prompts, étape par étape

Voici l'ordre dans lequel le bot du dossier `bot-crypto` a été construit. Tu peux refaire le chemin.

**Étape 1 — Les données**

> Écris une fonction Python qui télécharge les bougies d'une heure de BTC-EUR depuis l'API publique
> Coinbase Exchange (`/products/{id}/candles`), sur 2 ans, par paquets de 300 bougies, avec une pause
> entre les appels et une gestion de l'erreur 429. Renvoie un DataFrame pandas indexé par la date UTC,
> avec les colonnes open, high, low, close, volume, triées et sans doublons.

**Étape 2 — Les indicateurs**

> Écris les fonctions EMA, RSI (méthode de Wilder), ATR, canal de Donchian, MACD et bandes de Bollinger.
> Contrainte : la valeur à l'instant t ne doit utiliser que les bougies jusqu'à t. Le Donchian doit
> exclure la bougie en cours. Ajoute un test qui le vérifie.

**Étape 3 — Une stratégie**

> Écris une stratégie de cassure de Donchian : acheter quand la clôture dépasse le plus haut des 20
> bougies précédentes, et seulement si le prix est au-dessus de l'EMA 200 ; revendre quand la clôture
> passe sous le plus bas des 10 bougies précédentes. Renvoie une série de 0 et de 1.

**Étape 4 — Le backtest**

> Écris un backtest bougie par bougie. Le signal calculé à la clôture de t est exécuté à l'ouverture
> de t+1. Compte 0,6 % de frais et 0,05 % de glissement par ordre. Ajoute un stop à 3 × ATR, une taille
> de position qui risque 2 % du capital, et un coupe-circuit qui vend tout à −20 % depuis le plus haut.
> Calcule rendement, drawdown max, Sharpe, Calmar, nombre de trades, et le rendement d'acheter-et-garder.

**Étape 5 — L'avocat du diable**

> Voici mon backtest. Cherche toutes les façons dont il pourrait me mentir : biais d'anticipation,
> frais oubliés, surapprentissage, exécution irréaliste. Écris un test pour chaque faille trouvée.

**Étape 6 — La validation**

> Ajoute une validation hors échantillon : optimise les paramètres sur les 70 % premiers des données,
> puis évalue uniquement sur les 30 % restants. Ajoute un test de Monte-Carlo qui rééchantillonne les trades.

**Étape 7 — Le direct**

> Écris une boucle qui, une fois par bougie clôturée, récupère les données, calcule le signal et passe
> l'ordre via un objet « broker ». Fais deux brokers avec la même interface : un PaperBroker (argent fictif,
> sauvegardé dans un JSON) et un CoinbaseBroker (SDK coinbase-advanced-py). La boucle ne doit jamais
> acheter deux fois sur la même bougie et ne doit pas planter sur une erreur réseau.

## 3.3 Vérifier ce que Claude écrit

Une IA peut se tromper avec beaucoup d'assurance. Trois réflexes :

- **Lance les tests** : `python -m pytest`. S'ils ne passent pas, colle la sortie à Claude.
- **Teste un cas que tu peux calculer à la main.** Exemple du projet : marché parfaitement plat, un
  achat puis une vente avec 1 % de frais. Il doit rester exactement 100 × 0,99 × 0,99 = 98,01 €.
- **Méfie-toi des résultats trop beaux.** Un backtest à +900 % par an contient presque toujours un bug.

# Chapitre 4 — Les données

## 4.1 Les bougies

Une **bougie** résume les échanges sur une période (une minute, une heure, un jour) avec cinq nombres :

| Champ | Sens |
|---|---|
| open | le prix au début de la période |
| high | le plus haut atteint |
| low | le plus bas atteint |
| close | le prix à la fin de la période |
| volume | la quantité échangée |

**Le piège de la bougie en cours.** La dernière bougie renvoyée par l'API n'est souvent pas terminée :
son `close` change encore. Si ton bot décide sur elle, un signal peut apparaître puis disparaître.
Le projet retire donc toute bougie non clôturée (`drop_unclosed`).

**Quelle taille de bougie ?** Plus elles sont petites, plus il y a de signaux, donc de frais et de bruit.
Pour débuter, prends **1 h** ou plus.

## 4.2 L'EMA : la tendance

La **moyenne mobile exponentielle** (EMA) lisse les prix en donnant plus de poids aux plus récents.

- Prix au-dessus de l'EMA 200 : tendance de fond plutôt haussière.
- EMA 20 qui croise l'EMA 50 vers le haut : la tendance courte accélère.

```python
def ema(s, period):
    return s.ewm(span=period, adjust=False, min_periods=period).mean()
```

## 4.3 Le RSI : l'élan

Le **RSI** (Relative Strength Index) va de 0 à 100. Il compare la taille des hausses à celle des baisses
sur 14 bougies.

- RSI < 30 : le prix a beaucoup baissé récemment (« survendu »).
- RSI > 70 : il a beaucoup monté (« suracheté »).

« Survendu » ne veut pas dire « va remonter ». En pleine chute, le RSI peut rester sous 30 longtemps.
C'est pour ça qu'on l'associe à un filtre de tendance.

## 4.4 L'ATR : la nervosité

L'**ATR** (Average True Range) mesure l'amplitude moyenne d'une bougie. Ce n'est pas une direction,
c'est une **volatilité**. C'est l'indicateur le plus utile du bot, car il sert à :

- placer le stop assez loin pour ne pas être sorti par le bruit (3 × ATR) ;
- calculer la taille de la position (plus le marché est nerveux, plus on achète petit).

# Chapitre 5 — Les stratégies

## 5.1 Écrire une règle

Une règle de trading doit être **assez précise pour qu'un ordinateur l'applique sans hésiter**.

- Mauvais : « acheter quand ça a l'air de repartir ».
- Bon : « acheter à l'ouverture de la bougie suivante si la clôture est au-dessus du plus haut des
  20 bougies précédentes et au-dessus de l'EMA 200 ; revendre si la clôture passe sous le plus bas des
  10 bougies précédentes ».

Dans le projet, chaque stratégie renvoie une série de 0 (à plat) et de 1 (acheté). C'est tout.

## 5.2 Backtester

Un **backtest** rejoue le passé comme si le bot avait tourné. Il est utile seulement s'il est réaliste :

1. **Pas de regard vers le futur.** Une décision prise avec la clôture de t est exécutée à l'ouverture de t+1.
2. **Tous les frais** et un peu de glissement à chaque ordre.
3. **Les stops** sont déclenchés dès que le plus bas de la bougie les touche, au prix du stop, ou pire si le marché ouvre en dessous.
4. **Pas de levier**, pas d'argent qui n'existe pas.

```bash
python bot.py backtest --strategy donchian
python bot.py compare
```

## 5.3 Lire les résultats

| Mesure | Question à laquelle elle répond |
|---|---|
| rendement | combien j'ai gagné ou perdu au total ? |
| acheter_garder | combien j'aurais fait sans bot ? |
| max_drawdown | quelle a été la pire chute depuis un sommet ? |
| sharpe | le rendement vaut-il le stress ? |
| calmar | rendement annuel ÷ pire chute |
| trades | assez de trades pour que ce ne soit pas de la chance ? |
| profit_factor | gains totaux ÷ pertes totales (> 1 = gagnant) |
| frais_payes | combien est parti chez l'échange |

**La règle de base :** si ton bot ne bat pas « acheter et garder » après frais, sur des données qu'il n'a
jamais vues, il ne sert à rien. Achète et garde, c'est plus simple et c'est gratuit.

## 5.4 Valider honnêtement

Le plus grand danger est le **surapprentissage** : à force d'essayer des réglages, tu finis par trouver
celui qui colle parfaitement au passé. Par pur hasard.

La parade : **séparer les données.**

- 70 % du début : on a le droit d'essayer des réglages (« entraînement »).
- 30 % de la fin : on ne les regarde **qu'une fois**, avec le réglage choisi (« hors échantillon »).

```bash
python bot.py validate --strategy donchian
```

Le verdict du programme est strict. Une stratégie est validée seulement si, sur les 30 % jamais vus :
elle gagne de l'argent, elle bat acheter-et-garder, son profit factor dépasse 1, et elle a fait au moins 5 trades.

Si tu relances la validation vingt fois en changeant tout jusqu'à ce que ça passe, tu as triché :
les 30 % ne sont plus « jamais vus ».

# Chapitre 6 — Les méthodes reconnues

## 6.1 La cassure de Donchian

Inventée par Richard Donchian et rendue célèbre par les « Turtle Traders » dans les années 1980.
Idée : quand le prix dépasse son plus haut des N dernières périodes, une tendance commence peut-être.

- Entrée : clôture > plus haut des 20 bougies précédentes.
- Sortie : clôture < plus bas des 10 bougies précédentes.

Elle perd souvent un peu (fausses cassures) et gagne parfois beaucoup (grandes tendances).
Le taux de réussite est bas (30 à 40 %), c'est normal.

## 6.2 Le MACD

Le MACD est la différence entre une EMA 12 et une EMA 26. On le compare à sa propre moyenne (ligne de signal, EMA 9).

- Achat : MACD au-dessus de sa ligne de signal *et* au-dessus de zéro.
- Sortie : MACD repasse sous sa ligne de signal.

## 6.3 Les bandes de Bollinger

Une moyenne sur 20 bougies, plus et moins 2 écarts-types. Les bandes s'écartent quand le marché s'agite.

- Version « rebond » (dans le projet) : acheter sous la bande basse, revendre au retour à la moyenne.
- Version « cassure » : acheter au-dessus de la bande haute. À toi de l'écrire avec Claude, c'est un bon exercice.

## 6.4 Les filtres

Un filtre ne crée pas de signal, il en **supprime**. C'est souvent ce qui améliore le plus une stratégie.

- **Filtre de tendance** : n'acheter que si le prix est au-dessus de l'EMA 200 (`trend_filter`).
  En crypto, la plupart des grosses pertes arrivent quand on achète dans un marché baissier.
- **Filtre de volume** : n'acheter que si le volume dépasse 1,2 fois sa moyenne (`volume_filter`).
  Une cassure sans volume est souvent une fausse cassure.

## 6.5 Le ratio de Sharpe

Rendement moyen ÷ volatilité, ramené à l'année. Il répond à : « est-ce que je suis payé pour les secousses ? »

- < 0 : tu perds de l'argent.
- 0 à 1 : médiocre.
- 1 à 2 : bon.
- > 3 en backtest : méfiance, cherche le bug.

## 6.6 Le ratio de Calmar

Rendement annuel ÷ pire chute (drawdown max). Un Calmar de 1 veut dire : « en un an, je gagne autant que
ce que j'ai perdu dans ma pire période ». C'est la mesure que le projet utilise pour choisir les réglages,
parce qu'elle pénalise les stratégies qui te font vivre des chutes insupportables.

## 6.7 Le test de Monte-Carlo

Ton backtest a produit une suite de trades dans un certain ordre. Mais cet ordre est en partie dû à la chance.
Le test de Monte-Carlo **mélange** les trades des milliers de fois (avec remise) et regarde ce qui aurait pu arriver :

- le rendement médian ;
- le rendement des 5 % de scénarios les plus mauvais ;
- la probabilité de finir en perte ;
- le drawdown des 5 % de scénarios les plus mauvais.

Si 5 % des scénarios font −40 %, prépare-toi à vivre −40 % un jour. Si ça t'est insupportable, réduis la taille des positions.

# Chapitre 7 — Le direct

## 7.1 La gestion du risque

C'est le chapitre le plus important. Une stratégie moyenne avec une bonne gestion du risque survit.
Une bonne stratégie avec une mauvaise gestion du risque finit par tout perdre.

Les quatre protections du bot :

1. **Le stop ATR.** À l'achat, le bot note un prix de stop à 3 × ATR sous le prix d'entrée.
   Si le prix le touche, il vend. Après un stop, il attend que le signal s'éteigne puis se rallume avant de racheter.
2. **La taille de position.** Le bot achète une quantité telle que, si le stop est touché, la perte soit
   d'environ 2 % du capital. Marché calme : position plus grosse. Marché nerveux : position plus petite.
3. **Le coupe-circuit.** Si le capital baisse de 20 % depuis son plus haut, le bot vend tout et
   **s'arrête**. Il ne redémarre pas tant que tu n'as pas supprimé son fichier d'état. C'est voulu :
   un humain doit comprendre ce qui s'est passé.
4. **Le montant maximum par ordre** (`max_order`), au cas où un bug calculerait une taille absurde.

## 7.2 La simulation (paper trading)

```bash
python bot.py paper
```

Le bot tourne en direct sur les vrais prix, avec 100 € **fictifs** et les mêmes frais que le réel.
Il écrit chaque décision dans `state/journal_paper.csv`.

Laisse-le tourner **au moins quatre semaines**. Tu vérifies trois choses :

- il fait ce que le backtest prévoyait (même genre de signaux, même fréquence) ;
- il survit aux coupures réseau, aux redémarrages, aux mises en veille de l'ordinateur ;
- tu supportes émotionnellement ses pertes.

## 7.3 Passer en réel

Seulement si la validation est passée **et** que la simulation s'est bien déroulée :

1. Crée une clé API Coinbase (droits View + Trade, jamais Transfer).
2. Copie `.env.example` en `.env` et remplis-le.
3. Commence avec une petite somme et un `max_order` bas.
4. `python bot.py live --yes-real-money`

Pour qu'il tourne 24 h/24, il faut une machine allumée en permanence : un vieux PC, un Raspberry Pi,
ou un petit serveur loué. Sur Linux, `tmux` ou un service `systemd` permet de le garder actif après déconnexion.

## 7.4 Le suivi

Chaque jour, deux minutes :

- regarde la fin de `bot.log` : le bot tourne-t-il ? y a-t-il des erreurs ?
- regarde `state/journal_live.csv` : les achats et ventes ont-ils un sens ?
- compare le solde réel sur Coinbase avec ce que le bot croit avoir.

Chaque mois : compare la performance du bot à « acheter et garder » sur la même période.

## 7.5 Le dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| `ModuleNotFoundError` | environnement virtuel non activé | `source .venv/bin/activate` puis `pip install -r requirements.txt` |
| `python` introuvable (Windows) | PATH non coché | réinstaller Python en cochant « Add to PATH » |
| erreur 429 | trop de requêtes | le code patiente déjà ; augmente `poll_seconds` |
| erreur 401 en réel | clé mal copiée | vérifie les `\n` du secret dans `.env`, ou recrée la clé |
| « INSUFFICIENT_FUND » | solde trop faible ou frais non prévus | baisse `max_order` |
| « arrêté (coupe-circuit) » | −20 % atteint | analyse le journal, puis supprime `state/state_live.json` |
| le bot ne trade jamais | filtres trop stricts, ou marché baissier | normal sous l'EMA 200 ; vérifie avec `backtest` |
| résultats paper ≠ backtest | bougie en cours utilisée, frais différents | vérifie `drop_unclosed` et tes frais réels |

# Chapitre 8 — Le bilan

## 8.1 Les vrais résultats

Voici ce qu'affiche la commande `python bot.py compare --demo`, sur un **marché synthétique**
(une marche aléatoire générée par ordinateur, en baisse de 43 % sur la période). Ce n'est pas le vrai
bitcoin, et ces chiffres ne disent rien du vrai marché. Ils montrent ce que le bot sait mesurer :

| Stratégie | Rendement | Acheter et garder | Drawdown max | Trades |
|---|---|---|---|---|
| ema_cross | −20,4 % | −43,2 % | −20,4 % | 19 |
| rsi_dip | −3,6 % | −43,2 % | −5,7 % | 4 |
| donchian | −20,3 % | −43,2 % | −20,3 % | 21 |
| macd | −20,8 % | −43,2 % | −20,8 % | 30 |
| bollinger | −19,6 % | −43,2 % | −20,3 % | 21 |

Ce que ce tableau enseigne :

- **Sur un marché sans vraie tendance, aucune stratégie ne gagne.** Ici, le hasard plus 1,2 % de frais par aller-retour suffit à tout faire perdre.
- **Le coupe-circuit fait son travail.** Les pertes s'arrêtent vers −20 % au lieu de −43 %.
- **« Perdre moins que le marché » n'est pas « gagner ».** La validation stricte rejette ces stratégies, et elle a raison.

**Tes résultats.** Lance maintenant `python bot.py compare` puis `python bot.py validate` sur les vraies données
de Coinbase. Note les chiffres dans ton carnet, **datés**. Ils dépendent de la période : une stratégie de tendance
brille pendant une grande hausse et souffre dans un marché qui tourne en rond. C'est pour ça qu'on teste sur
deux ans, et qu'on revalide tous les trois mois.

## 8.2 Les erreurs à éviter

1. **Oublier les frais.** C'est l'erreur qui transforme un bot « gagnant » en bot perdant.
2. **Le biais d'anticipation.** Utiliser une information du futur, même d'une seule bougie. Exemple classique : un Donchian qui inclut la bougie en cours.
3. **Le surapprentissage.** Trouver le réglage parfait pour le passé. Il ne marchera pas demain.
4. **Juger sur trois jours.** Il faut des dizaines de trades et plusieurs mois.
5. **Ne pas se comparer à « acheter et garder ».**
6. **Trader trop souvent.** Bougies de 1 minute, 50 trades par jour : les frais gagnent.
7. **Augmenter la mise après des gains**, ou pire, après des pertes « pour se refaire ».
8. **Donner le droit de retrait à la clé API.**
9. **Désactiver le coupe-circuit** « juste cette fois ».
10. **Croire une vidéo** qui montre un bot doubler en deux jours.

## 8.3 La checklist complète

**Installation**

- [ ] Python 3.12+ installé, `python --version` fonctionne
- [ ] VS Code + extension Python
- [ ] Environnement virtuel créé et activé
- [ ] `pip install -r requirements.txt` sans erreur
- [ ] `python -m pytest` : tous les tests passent

**Backtest**

- [ ] Au moins 2 ans de données
- [ ] Frais réels de ton compte saisis dans `config.json`
- [ ] Décision à la clôture, exécution à la bougie suivante
- [ ] Comparaison avec acheter-et-garder
- [ ] Au moins 30 trades sur la période complète

**Validation**

- [ ] Réglages choisis sur 70 % des données uniquement
- [ ] Hors échantillon : rendement > 0, bat acheter-et-garder, profit factor > 1
- [ ] Monte-Carlo : le pire scénario à 5 % est supportable pour toi
- [ ] Tu n'as pas relancé la validation jusqu'à ce qu'elle passe

**Simulation**

- [ ] Au moins 4 semaines de `paper`
- [ ] Les signaux ressemblent à ceux du backtest
- [ ] Le bot a survécu à au moins une coupure réseau et un redémarrage

**Réel**

- [ ] Clé API sans droit de retrait
- [ ] `.env` jamais partagé ni publié
- [ ] Petite somme de départ, `max_order` bas
- [ ] Coupe-circuit actif (`kill_drawdown`)
- [ ] Suivi quotidien du journal, bilan mensuel contre acheter-et-garder

## 8.4 Le mot de la fin

Un bon bot, c'est surtout un bot honnête avec lui-même : il compte tous les frais, il se teste sur des
données jamais vues et il se compare à « acheter et garder ». S'il ne passe pas ces trois épreuves,
le meilleur trade est de ne pas le lancer. Et tu auras quand même appris à coder, à lire un marché
et à te méfier des promesses trop belles.

# Annexe — Fiscalité et cadre légal (France)

- Les plus-values sur cryptoactifs réalisées par un particulier sont en principe imposables lors d'une
  conversion en euros (ou d'un achat de bien), via le formulaire 2086. Un échange crypto contre crypto
  n'est en général pas imposable pour un particulier.
- Les comptes ouverts sur des plateformes étrangères doivent être déclarés (formulaire 3916-bis).
- Une activité de trading très fréquente peut être requalifiée en activité professionnelle.
- Ces règles évoluent. Vérifie sur impots.gouv.fr ou auprès d'un professionnel avant ta déclaration.
- Vérifie aussi que la plateforme utilisée est bien autorisée à fournir ses services en France (liste
  des prestataires sur le site de l'AMF).
