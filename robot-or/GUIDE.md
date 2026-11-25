# Robot or (XAUUSD) sur MetaTrader 5 — COMPTE DÉMO

Le robot tourne 24 h/24 sur ton PC Windows, à côté de MetaTrader 5. Il ne trade que l'or,
et **il refuse de fonctionner sur un compte réel** : il le vérifie à chaque tour, toutes les 5 secondes.

## Ce qu'il fait

Chaque jour (heure du serveur MT5) :

1. **Séance d'Asie** : il note le plus haut et le plus bas de l'or entre 01:00 et 03:00.
2. **Séance de New York** : il note le plus haut et le plus bas entre 10:00 et 15:00.
3. À la fin de chaque séance, il place **un ordre en attente** au-dessus du plus haut (achat) ou au-dessous
   du plus bas (vente), **seulement dans le sens de la tendance** (prix au-dessus ou au-dessous de sa moyenne sur environ 200 heures).
4. Stop = largeur de la séance. Objectif = 2 fois le stop. Une seule position à la fois.
5. **Tout est fermé à 21:00.** Jamais de position la nuit ni le week-end.

Protections : perte maximale de 10 % par jour et par semaine, pause dès que la semaine atteint **+5 %**,
fichier pause, et jamais d'ordre rejoué si la réponse du courtier est incertaine.

## Ce qu'on peut en attendre (chiffres mesurés, pas des promesses)

Sur 17 mois de données M5 de ton courtier (juin 2025 → novembre 2026), avec 500 € de départ :

| | Toute la période | Période récente (mars → novembre 2026) |
|---|---|---|
| Gain moyen par trade | +0,17 R | **+0,08 R** |
| Semaines gagnantes | environ 60 % | **environ 50 %** |
| Semaine moyenne | +1,9 % | **+0,5 à +1 %** |
| Pire semaine | −10,7 % | −10 % |

(1 R = la somme risquée sur un trade, environ 15 à 25 € ici.)

**Attends-toi à une semaine sur deux en perte.** L'avantage est petit, et il a été plus faible sur la période récente.
Le vrai test, c'est la démo : **il faut environ 100 trades (4 à 5 mois) pour savoir s'il tient.**

Pourquoi le risque est de 3 à 5 % par trade : avec 500 €, la plus petite position possible (0,01 lot = 1 once d'or)
risque déjà 15 à 25 € selon la largeur de la séance. Si une séance est trop large (plus de 5 % de risque), le robot la saute.

## Installation (une seule fois)

1. **MetaTrader 5** : ouvre-le et connecte-toi à ton **compte démo**. Mets le solde de la démo à 500 € si ton courtier le permet.
   Utilise le même courtier que celui qui a fourni les données : les heures des séances sont celles de son serveur.
2. Dans MT5 : *Outils* → *Options* → *Expert Advisors* → coche **« Autoriser le trading algorithmique »**.
   Vérifie aussi que le bouton **« Algo Trading »** de la barre d'outils est vert.
3. Ouvre un graphique **XAUUSD en M5** dans MT5, et laisse-le ouvert.
4. Installe Python depuis python.org en cochant **« Add python.exe to PATH »** (déjà fait si le bot crypto tourne).
5. Copie le dossier `robot-or` dans **`C:\robot-or`**, sans espace dans le chemin.
6. Double-clique sur **`windows\1-installer.bat`**. À la fin, tu dois voir `9 passed`.

## Utilisation

| Fichier | Quand |
|---|---|
| `2-simulation.bat` | Voir ce que la stratégie a donné, semaine par semaine, sur l'historique |
| `3-lancer-robot.bat` | **Démarrer le robot.** Laisse la fenêtre ouverte (tu peux la réduire) |
| `4-demarrage-automatique.bat` | Le robot redémarre seul à chaque ouverture de session (tape `O`) |
| `5-releve-semaine.bat` | **Chaque week-end** : le résultat de la semaine et depuis le début. Envoie-le-moi |
| `6-pause-marche.bat` | Mettre le robot en pause, ou le relancer |

Mets aussi MetaTrader 5 dans le démarrage automatique de Windows : touche Windows + R, tape `shell:startup`,
puis glisse un raccourci de MT5 dans le dossier qui s'ouvre.

**Alertes Telegram (facultatif)** : ouvre `.env` avec le Bloc-notes et colle le même `TELEGRAM_BOT_TOKEN` et le même
`TELEGRAM_CHAT_ID` que pour le bot crypto. Tu recevras chaque ordre armé, chaque position ouverte ou fermée, les pauses et le bilan du jour.

## Ce que tu verras dans la fenêtre

```
Robot or 2026-11-25 · compte démo ...678 · solde 500.00 EUR · symbole XAUUSD (lot min 0.01, pas 0.01)
[26/11 03:00] ORDRE ARMÉ {'session': 'Asie', 'haut': 3905.2, 'bas': 3881.4, 'sens': 'achat'}
[26/11 04:35] POSITION OUVERTE {'session': 'Asie', 'sens': 'achat', 'prix': 3905.45, 'lots': 0.01, 'risque_eur': 20.7}
[26/11 21:00] POSITION FERMÉE {'session': 'Asie', 'gain_eur': 12.3, 'r': 0.59, 'solde': 512.3}
```

« SÉANCE ANNULÉE » est normal : la cassure est partie dans le sens contraire à la tendance, le robot s'abstient.

## Que faire si…

| Problème | Solution |
|---|---|
| « CE N'EST PAS UN COMPTE DÉMO » | Normal : le robot refuse le réel. Connecte MT5 à ton compte démo |
| « MetaTrader 5 ne répond pas » | Ouvre MT5 et connecte-toi. Le robot réessaie tout seul toutes les minutes |
| « ORDRE REFUSÉ » avec le code 10027 | Le trading algorithmique est désactivé dans MT5 (voir l'installation, étape 2) |
| Rien ne se passe pendant des heures | Normal : 2 séances par jour au maximum, et seulement dans le sens de la tendance |
| Le robot est « EN PAUSE » | Limite de perte atteinte, objectif de la semaine atteint (+5 %), ou fichier pause. Il reprend tout seul la semaine ou le jour suivant |

## Pour les curieux

- `robot/strategie.py` : la stratégie, partagée par le robot et le simulateur
- `robot/mt5_robot.py` : le robot MT5 (ordres, garde-fous, journal)
- `robot/simulateur.py` : le simulateur (même stratégie, même exécution)
- `recherche/` : la recherche (32 configurations, conception puis contrôle)
- `tests/` : les tests, dont un **faux MT5** qui fait tourner le vrai robot sur l'historique.
  Le robot et le simulateur y prennent les mêmes trades (316 entrées communes sur 321).
