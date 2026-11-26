# Installer le bot sur ton PC Windows qui tourne 24 h/24

Compte environ 30 minutes. Tu n'as rien à programmer : tu double-cliques sur des fichiers dans l'ordre.

> Rappel : le bot est éducatif. Sur les vraies données, il a gagné environ 3 % par an sur la période test
> et il gagne beaucoup moins qu'acheter et garder pendant les grandes hausses. Aucun profit n'est garanti.
> N'y mets que de l'argent que tu peux perdre.

## Étape 1 — Récupérer le code

1. Va sur https://github.com/tonytoniqu3-ui/logger-site
2. En haut à gauche, choisis la branche `claude/crypto-trading-bot-j01gff` (ou `main` une fois la pull request fusionnée).
3. Bouton vert **Code** → **Download ZIP**.
4. Décompresse le ZIP, puis copie le dossier `bot-crypto` vers **`C:\bot-crypto`**.
   Évite les dossiers avec des espaces dans le nom (le démarrage automatique les gère mal).

## Étape 2 — Installer Python

1. Va sur https://www.python.org/downloads/ et télécharge la dernière version 3.
2. Lance l'installateur et **coche « Add python.exe to PATH »** avant de cliquer sur *Install Now*.

## Étape 3 — Installer le bot

Dans `C:\bot-crypto\windows`, double-clique sur **`1-installer.bat`**.

Il installe les bibliothèques, lance les tests, puis teste la stratégie sur les vraies données de Coinbase.
À la fin, tu dois voir `21 passed`, puis trois blocs de résultats, dont « Données jamais vues (30 %) ».

Si Windows affiche « Windows a protégé votre ordinateur », clique sur **Informations complémentaires** → **Exécuter quand même**.

## Étape 4 — Empêcher le PC de se mettre en veille

*Paramètres* → *Système* → *Alimentation* → *Écran et veille* : mets **Jamais** pour « Mettre en veille l'appareil ».
L'écran peut s'éteindre, ce n'est pas un problème. La veille, si : elle arrête le bot.

## Étape 5 — Les alertes Telegram

1. Dans Telegram, cherche **@BotFather** (avec le badge bleu), puis envoie `/newbot`.
2. Donne un nom (par exemple « Mon bot crypto ») puis un identifiant qui finit par `bot` (par exemple `tonpseudo_crypto_bot`).
3. BotFather te répond avec un **token** du genre `123456789:AAH...`. Garde-le secret.
4. Ouvre `C:\bot-crypto\.env` avec le Bloc-notes et colle le token :
   `TELEGRAM_BOT_TOKEN=123456789:AAH...`
   Enregistre.
5. Dans Telegram, ouvre ton nouveau bot et envoie-lui « bonjour ».
6. Double-clique sur **`2-tester-telegram.bat`**. Il affiche une ligne `TELEGRAM_CHAT_ID=...`.
   Copie-la dans `.env`, enregistre, puis relance `2-tester-telegram.bat`.
7. Tu dois recevoir « ✅ Le bot crypto est bien relié à Telegram. »

Ce que tu recevras ensuite :
- 🟢 à chaque achat, 🟡 à chaque vente sur signal, 🔴 à chaque stop ;
- 📊 un bilan chaque jour (capital, tendance du BTC et de l'ETH, positions) ;
- ⚠️ ou ⛔ si le bot rencontre des erreurs ou si le coupe-circuit se déclenche.

## Étape 6 — Lancer la simulation

Double-clique sur **`3-lancer-simulation.bat`**. Une fenêtre noire s'ouvre et doit **rester ouverte** (tu peux la réduire).
Le bot joue avec 100 € fictifs, vérifie le marché toutes les 15 minutes et ne décide qu'une fois par jour, après la clôture
de la bougie journalière (minuit UTC, soit 1 h du matin en hiver en France). S'il plante, il redémarre tout seul au bout d'une minute.

**Il est normal qu'il ne fasse rien pendant des semaines** : tant que le bitcoin et l'ether sont sous leur
moyenne de 200 jours, il reste en euros. C'est sa protection.

Pour voir ce qu'il fait : **`6-voir-le-journal.bat`**.

## Étape 7 — Démarrage automatique

Double-clique sur **`4-demarrage-automatique.bat`** et tape `S`. Le bot redémarrera tout seul à chaque ouverture de session,
par exemple après une mise à jour de Windows.

Pour que la session s'ouvre toute seule après un redémarrage, il faut activer la connexion automatique de Windows
(touche Windows, tape `netplwiz`). Fais-le seulement si personne d'autre n'a accès à ce PC.

## Étape 8 — Passer en argent réel (après 4 à 8 semaines de simulation)

Ne passe en réel que si la simulation a tourné plusieurs semaines sans souci et que les alertes arrivent bien.

1. **Coinbase** : ouvre un compte, vérifie ton identité et dépose une petite somme en euros (par exemple 100 à 200 €).
2. **Clé API** : sur https://portal.cdp.coinbase.com, crée une clé API (*API keys* → *Create API key*).
   - Droits : **View** et **Trade** seulement. **Jamais Transfer.**
   - Si on te demande l'algorithme de signature, choisis **ECDSA**.
   - Télécharge le fichier de la clé, renomme-le **`cdp_api_key.json`** et place-le dans `C:\bot-crypto`.
   - Ne l'envoie à personne, ne le mets jamais sur GitHub (il est exclu automatiquement), ne le colle dans aucune conversation.
3. **Budget** : ouvre `config.json` avec le Bloc-notes. `"capital"` est le budget du bot en euros, par exemple `"capital": 100`.
   **Le bot ne touche jamais au reste de ton compte** : il ne dépense que ce budget et ne revend que ce qu'il a lui-même acheté.
   Mets aussi `"max_order"` au même montant.
4. Ferme la fenêtre de simulation, puis double-clique sur **`5-lancer-reel.bat`** et tape `OUI`.
5. Pour le démarrage automatique en réel, relance `4-demarrage-automatique.bat` et tape `R`.

Les alertes Telegram indiquent alors `[ARGENT RÉEL]` au lieu de `[SIMULATION]`.

## Que faire si…

| Problème | Solution |
|---|---|
| « Python est introuvable » | Réinstalle Python en cochant « Add python.exe to PATH » |
| La fenêtre noire se ferme aussitôt | Lance d'abord `1-installer.bat` |
| Pas de message Telegram | Relance `2-tester-telegram.bat` et vérifie le token et le chat id dans `.env` |
| « Coupe-circuit » sur Telegram | Le bot a perdu 20 % depuis son plus haut et s'est arrêté. Regarde le journal, puis supprime `state\state_paper.json` (ou `state_live.json`) pour le relancer |
| Erreur 401 en réel | La clé Coinbase est refusée : recrée-la (View + Trade, ECDSA) et remplace `cdp_api_key.json` |
| Le bot ne fait rien | Normal si le BTC et l'ETH sont sous leur moyenne de 200 jours. Le bilan Telegram du jour l'indique |
| Je veux tout arrêter | Ferme la fenêtre noire, puis `4-demarrage-automatique.bat` et tape `A` |

## Tous les 3 mois

Relance `1-installer.bat` (ou `python bot.py portfolio`) pour revoir les résultats à jour, et compare ton capital réel
à ce qu'aurait donné « acheter et garder ». Si le bot fait nettement moins bien pendant plusieurs mois, arrête-le.
