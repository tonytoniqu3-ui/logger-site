"""Génère slides.html (41 diapos 16:9) ; puis `node build.js` produit slides.pdf."""
import html

S = [
 ("cover", "Créer son bot crypto de\u00a0A\u00a0à\u00a0Z", ["Python · Coinbase · Claude", "La version résumée en 41 diapos"]),
 ("Ce que tu vas construire", ["Un bot qui lit les prix de Coinbase", "Qui applique tes règles", "Qui se teste honnêtement, frais compris", "Qui tourne en simulation, puis en réel"]),
 ("Ce qu'on ne te promet pas", ["100 € → 200 € en 2 jours = du bruit", "La plupart des bots amateurs perdent", "Un bot honnête t'évite de perdre"]),
 ("Avertissement", ["Contenu éducatif, pas un conseil", "Risque de perte totale", "N'engage que ce que tu peux perdre"]),
 ("section", "1 · Partir de zéro", []),
 ("Installer Python", ["python.org → Downloads", "Windows : coche « Add to PATH »", "Vérifie : python --version"]),
 ("Installer VS Code", ["code.visualstudio.com", "Extension « Python » de Microsoft", "Ouvre le dossier bot-crypto"]),
 ("L'environnement virtuel", ["python -m venv .venv", "Active-le : (.venv) apparaît", "pip install -r requirements.txt"]),
 ("Le Python indispensable", ["Variables, listes, dictionnaires", "if / for / def", "import pandas as pd", "Erreurs : se lisent de bas en haut"]),
 ("section", "2 · Les bases", []),
 ("Un bot, c'est une boucle", ["Observer → Décider → Agir", "Noter → Attendre la bougie suivante", "Pas plus intelligent que ses règles"]),
 ("Un échange de cryptos", ["Paire BTC-EUR", "Carnet d'ordres, spread", "Ordre au marché (taker) / limite (maker)", "Glissement"]),
 ("Les frais : le vrai adversaire", ["≈ 0,6 % par ordre (taker, petit volume)", "≈ 1,2 % par aller-retour", "Un bon bot amateur trade peu"]),
 ("Les clés API", ["Droits View + Trade, JAMAIS Transfer", "Dans .env, jamais partagé", "Jamais collée dans une conversation"]),
 ("section", "3 · Avec Claude", []),
 ("La méthode", ["Une petite étape à la fois", "Tu décris, Claude code, tu lances", "Tu colles le résultat ou l'erreur", "Tu demandes des tests"]),
 ("Les 7 prompts", ["Données → Indicateurs → Stratégie", "Backtest → Avocat du diable", "Validation → Direct"]),
 ("Vérifier ce que Claude écrit", ["python -m pytest", "Un cas calculable à la main", "Résultat trop beau = bug"]),
 ("section", "4 · Les données", []),
 ("Les bougies", ["open · high · low · close · volume", "Ignore la bougie en cours", "Débute en journalier : le seul qui a tenu face aux frais"]),
 ("EMA : la tendance", ["Moyenne qui privilégie le récent", "Prix > EMA 200 : tendance haussière", "EMA 20 × EMA 50 : accélération"]),
 ("RSI : l'élan", ["De 0 à 100, sur 14 bougies", "< 30 survendu, > 70 suracheté", "« Survendu » ≠ « va remonter »"]),
 ("ATR : la nervosité", ["Amplitude moyenne d'une bougie", "Place le stop (3 × ATR)", "Calcule la taille de position"]),
 ("section", "5 · Les stratégies", []),
 ("Une règle précise", ["Applicable sans hésiter", "Signal 1 = acheté, 0 = à plat", "Décision à la clôture, exécution à t+1"]),
 ("Un backtest réaliste", ["Aucun regard vers le futur", "Tous les frais + glissement", "Stops réalistes, pas de levier"]),
 ("Lire les résultats", ["Rendement vs acheter-et-garder", "Drawdown max, Sharpe, Calmar", "Nombre de trades, profit factor"]),
 ("Valider honnêtement", ["70 % pour régler", "30 % jamais vus pour juger", "Validée seulement si : gagne, bat le marché, PF > 1"]),
 ("section", "6 · Les méthodes reconnues", []),
 ("Cassure de Donchian", ["Entrée : plus haut des 20 bougies", "Sortie : plus bas des 10 bougies", "Peu de gains, mais gros"]),
 ("MACD et Bollinger", ["MACD > signal et > 0", "Rebond sous la bande basse", "Retour à la moyenne"]),
 ("Les filtres", ["Tendance : au-dessus de l'EMA 200", "Volume : > 1,2 × la moyenne", "Ils suppriment les mauvais signaux"]),
 ("Sharpe, Calmar, Monte-Carlo", ["Sharpe : payé pour les secousses ?", "Calmar : gain annuel ÷ pire chute", "Monte-Carlo : et si la chance tournait ?"]),
 ("section", "7 · Le direct", []),
 ("4 protections", ["Stop à 3 × ATR", "Position qui risque 2 % du capital", "Coupe-circuit à −20 %", "Montant maximum par ordre"]),
 ("Simulation d'abord", ["python bot.py paper", "100 € fictifs, mêmes frais", "Au moins 4 semaines"]),
 ("Puis le réel, petit", ["Clé API sans retrait", "Petite somme, max_order bas", "python bot.py live --yes-real-money"]),
 ("Suivi et dépannage", ["Chaque jour : bot.log + journal", "Chaque mois : vs acheter-et-garder", "Erreur ? colle-la à Claude"]),
 ("section", "8 · Le bilan", []),
 ("Les 5 erreurs qui coûtent", ["Oublier les frais", "Regarder le futur sans le savoir", "Surapprendre le passé", "Juger sur 3 jours", "Désactiver le coupe-circuit"]),
 ("Le mot de la fin", ["Un bon bot est honnête avec lui-même", "Il compte tous les frais", "Il se teste sur des données jamais vues", "Il se compare à « acheter et garder »"]),
]
assert len(S) == 41, len(S)
e = html.escape
out = []
for i, s in enumerate(S, 1):
    if s[0] == "cover":
        out.append(f'<section class="s cover"><h1>{e(s[1])}</h1>' + "".join(f"<p>{e(x)}</p>" for x in s[2]) + "</section>")
    elif s[0] == "section":
        out.append(f'<section class="s sec"><h1>{e(s[1])}</h1><span class="n">{i}/41</span></section>')
    else:
        out.append(f'<section class="s"><h2>{e(s[0])}</h2><ul>' + "".join(f"<li>{e(x)}</li>" for x in s[1]) + f'</ul><span class="n">{i}/41</span></section>')
css = """@page{size:1280px 720px;margin:0}*{box-sizing:border-box}body{margin:0;font-family:Inter,'Segoe UI',system-ui,sans-serif}
.s{width:1280px;height:720px;page-break-after:always;background:#0b0d14;color:#f4f6fb;padding:90px 110px;position:relative;overflow:hidden}
.s::before{content:"";position:absolute;inset:auto -200px -260px auto;width:620px;height:620px;border-radius:50%;background:radial-gradient(#12a16055,transparent 70%)}
h2{font-size:54px;margin:0 0 50px;color:#3ddc97}ul{margin:0;padding:0;list-style:none}li{font-size:36px;margin:0 0 26px;padding-left:44px;position:relative}
li::before{content:"";position:absolute;left:0;top:16px;width:16px;height:16px;border-radius:4px;background:#f5a524}
.cover,.sec{display:flex;flex-direction:column;justify-content:center}.cover h1{font-size:84px;line-height:1.05;margin:0 0 30px}
.cover p{font-size:34px;color:#9be7c0;margin:6px 0}.sec h1{font-size:76px;color:#3ddc97}.n{position:absolute;right:50px;bottom:36px;color:#6b7186;font-size:20px}"""
open("slides.html", "w").write(f'<!doctype html><html lang="fr"><meta charset="utf-8"><title>Bot crypto — 41 diapos</title><style>{css}</style><body>{"".join(out)}</body></html>')
print("41 diapos")
