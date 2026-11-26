"""Robot MT5 pour l'or (XAUUSD). COMPTE DE DÉMONSTRATION UNIQUEMENT.

Il tourne en boucle (toutes les quelques secondes), lit les bougies M5 clôturées, applique la stratégie
(robot/strategie.py, la même que le simulateur) et gère des ordres stop en attente avec stop et objectif.

Garde-fous :
  - vérifie à CHAQUE tour que le compte est un compte DÉMO, sinon il s'arrête ;
  - fichier PAUSE.flag à côté du robot : plus aucune nouvelle entrée ;
  - perte maximale par jour et par semaine, objectif hebdomadaire optionnel ;
  - tout est fermé à 21:00 (heure serveur), jamais de position la nuit ni le week-end ;
  - ne rejoue jamais automatiquement un ordre dont la réponse est incertaine.
"""
from __future__ import annotations

import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from .strategie import Bar, Config, Strategie, taille_position

MAGIC = 26112026
VERSION = "2026-11-25"


class Stop(Exception):
    """Arrêt volontaire et propre du robot."""


class Robot:
    def __init__(self, cfg: dict, mt5, dossier: str = ".", notifier=None, log=print):
        self.cfg, self.mt5, self.log = cfg, mt5, log
        self.strat = Strategie(Config.from_dict(cfg.get("strategie", {})))
        self.dir = Path(dossier)
        (self.dir / "journal").mkdir(parents=True, exist_ok=True)
        self.etat_path = self.dir / "journal" / "etat.json"
        self.journal_path = self.dir / "journal" / "journal.csv"
        self.notifier = notifier
        self.etat = json.loads(self.etat_path.read_text()) if self.etat_path.exists() else {}
        self.etat.setdefault("attente", {})      # session -> ordre armé (pas forcément posé chez le courtier)
        self.etat.setdefault("positions", {})    # ticket -> infos à l'ouverture (risque en €, session)
        self.derniere_bougie = None
        self.symbole = None
        self.dernier_incertain = False

    # ---------- outils ----------
    def sauver(self):
        self.etat_path.write_text(json.dumps(self.etat, indent=2, default=str))

    def noter(self, evenement: str, **infos):
        nouveau = not self.journal_path.exists()
        with self.journal_path.open("a", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter=";")
            if nouveau:
                w.writerow(["heure_serveur", "evenement", "details"])
            w.writerow([self.heure().strftime("%Y-%m-%d %H:%M:%S"), evenement, json.dumps(infos, default=str, ensure_ascii=False)])
        self.log(f"[{self.heure():%d/%m %H:%M}] {evenement} {infos if infos else ''}")
        if self.notifier and evenement in ("ORDRE ARMÉ", "POSITION OUVERTE", "POSITION FERMÉE", "PAUSE", "ARRÊT", "BILAN DU JOUR"):
            self.notifier(f"[DÉMO or] {evenement} {json.dumps(infos, default=str, ensure_ascii=False)}")

    def heure(self) -> datetime:
        """Heure du serveur (l'heure de la dernière cotation)."""
        tick = self.mt5.symbol_info_tick(self.symbole) if self.symbole else None
        if tick is None or not getattr(tick, "time", 0):
            return datetime.now(timezone.utc).replace(tzinfo=None)
        return datetime.fromtimestamp(tick.time, tz=timezone.utc).replace(tzinfo=None)

    # ---------- démarrage ----------
    def connecter(self):
        if not self.mt5.initialize():
            # passager (MT5 pas encore ouvert) : le lanceur réessaie dans une minute
            raise RuntimeError(f"MetaTrader 5 ne répond pas ({self.mt5.last_error()}). Ouvre MT5 et connecte-toi à ton compte démo.")
        self.verifier_demo()
        voulu = self.cfg.get("symbole", "XAUUSD")
        candidats = [voulu] + [s.name for s in (self.mt5.symbols_get("*XAU*") or []) if "USD" in s.name]
        for nom in candidats:
            if self.mt5.symbol_select(nom, True) and self.mt5.symbol_info(nom) is not None:
                self.symbole = nom
                break
        if not self.symbole:
            raise Stop("Symbole de l'or introuvable chez ce courtier (XAUUSD).")
        info = self.mt5.symbol_info(self.symbole)
        ai = self.mt5.account_info()
        self.log(f"Robot or {VERSION} · compte démo ...{str(ai.login)[-3:]} · solde {ai.balance:.2f} {ai.currency} · "
                 f"symbole {self.symbole} (lot min {info.volume_min}, pas {info.volume_step})")

    def verifier_demo(self):
        ai = self.mt5.account_info()
        if ai is None:
            raise Stop("Compte MT5 introuvable : connecte-toi à ton compte démo dans MT5.")
        if ai.trade_mode != self.mt5.ACCOUNT_TRADE_MODE_DEMO:
            raise Stop("CE N'EST PAS UN COMPTE DÉMO. Le robot refuse de trader de l'argent réel et s'arrête.")

    # ---------- données ----------
    def bougies_cloturees(self, n: int) -> list[Bar]:
        rates = self.mt5.copy_rates_from_pos(self.symbole, self.mt5.TIMEFRAME_M5, 0, n)
        if rates is None or len(rates) < 2:
            return []
        point = self.mt5.symbol_info(self.symbole).point
        out = []
        for r in rates[:-1]:  # la dernière bougie est encore en cours
            t = datetime.fromtimestamp(int(r["time"]), tz=timezone.utc).replace(tzinfo=None)
            out.append(Bar(t, float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]), float(r["spread"]) * point))
        return out

    def rechauffer(self):
        """Au démarrage : la stratégie relit l'historique récent pour connaître la tendance et les ranges du jour."""
        bougies = self.bougies_cloturees(self.cfg.get("historique_bougies", 5000))
        if not bougies:
            raise Stop("Pas d'historique M5 pour l'or : ouvre un graphique XAUUSD M5 dans MT5 et relance.")
        aujourd_hui = bougies[-1].t.date()
        self.etat["attente"] = {}
        for b in bougies:
            if b.t.date() == aujourd_hui:
                self.verifier_contre(b, silencieux=True)
            for cmd in self.strat.on_bar(b):
                if b.t.date() == aujourd_hui:
                    self.commande(cmd, rechauffage=True, arme_a=b.t)
                elif cmd["type"] == "fermer":
                    self.etat["attente"] = {}
        self.derniere_bougie = bougies[-1].t
        self.log(f"Historique chargé : {len(bougies)} bougies, dernière {self.derniere_bougie:%d/%m %H:%M}")

    # ---------- les commandes de la stratégie ----------
    def commande(self, cmd: dict, rechauffage: bool = False, arme_a=None):
        jour = self.heure().date().isoformat()
        if cmd["type"] == "fermer":
            if not rechauffage:
                self.tout_fermer("fermeture 21h")
            self.etat["attente"] = {}
            return
        if cmd["type"] == "armer":
            deja = self.etat.get("sessions_jouees", {}).get(cmd["session"])
            if deja == jour:
                return
            self.etat["attente"][cmd["session"]] = {k: cmd[k] for k in ("haut", "bas", "w")} | {
                "cotes": list(cmd["cotes"]), "ticket": None, "arme_a": str(arme_a), "essais": 0}
            if not rechauffage:
                self.noter("ORDRE ARMÉ", session=cmd["session"], haut=round(cmd["haut"], 2), bas=round(cmd["bas"], 2),
                           sens="achat" if cmd["cotes"] == (1,) else "vente" if cmd["cotes"] == (-1,) else "les deux")

    # ---------- les ordres chez le courtier ----------
    def mes_positions(self):
        return [p for p in (self.mt5.positions_get(symbol=self.symbole) or []) if p.magic == MAGIC]

    def mes_ordres(self):
        return [o for o in (self.mt5.orders_get(symbol=self.symbole) or []) if o.magic == MAGIC]

    def _remplissage(self):
        fm = self.mt5.symbol_info(self.symbole).filling_mode
        if fm & 1:
            return self.mt5.ORDER_FILLING_FOK
        if fm & 2:
            return self.mt5.ORDER_FILLING_IOC
        return self.mt5.ORDER_FILLING_RETURN

    def envoyer(self, req: dict, quoi: str):
        self.dernier_incertain = False
        res = self.mt5.order_send(req)
        if res is not None and res.retcode == 10030 and "type_filling" in req:  # mode d'exécution refusé : on essaie les autres
            for mode in (self.mt5.ORDER_FILLING_FOK, self.mt5.ORDER_FILLING_IOC, self.mt5.ORDER_FILLING_RETURN):
                if mode != req["type_filling"]:
                    res = self.mt5.order_send(req | {"type_filling": mode})
                    if res is None or res.retcode != 10030:
                        break
        if res is None:
            self.dernier_incertain = True
            self.noter("RÉPONSE INCERTAINE", quoi=quoi, erreur=str(self.mt5.last_error()))
            return None  # jamais rejoué automatiquement
        if res.retcode not in (self.mt5.TRADE_RETCODE_DONE, self.mt5.TRADE_RETCODE_PLACED):
            self.noter("ORDRE REFUSÉ", quoi=quoi, code=res.retcode, message=getattr(res, "comment", ""))
            return None
        return res

    def lots_pour(self, w: float, cote: int, prix: float) -> tuple[float, str]:
        info = self.mt5.symbol_info(self.symbole)
        typ = self.mt5.ORDER_TYPE_BUY if cote == 1 else self.mt5.ORDER_TYPE_SELL
        perte_1lot = abs(self.mt5.order_calc_profit(typ, self.symbole, 1.0, prix, prix - cote * w) or 0)
        solde = self.mt5.account_info().balance
        lots, why = taille_position(solde, perte_1lot, self.cfg["risque"], self.cfg["risque_max"],
                                    lot_min=info.volume_min, pas=info.volume_step)
        return min(lots, info.volume_max), why

    def poser(self, session: str, od: dict):
        """Pose l'ordre stop de la session (ou entre au marché si le niveau est déjà dépassé de peu)."""
        tick = self.mt5.symbol_info_tick(self.symbole)
        rr = self.strat.cfg.rr
        for cote in od["cotes"]:
            niveau = od["haut"] if cote == 1 else od["bas"]
            prix_actuel = tick.ask if cote == 1 else tick.bid
            deja_passe = prix_actuel >= niveau if cote == 1 else prix_actuel <= niveau
            prix = prix_actuel if deja_passe else niveau
            if deja_passe and not self.strat.prix_entree_ok(cote, niveau, prix, od["w"]):
                self.noter("SÉANCE ABANDONNÉE", session=session, raison="prix déjà trop loin du niveau")
                return "abandon"
            lots, why = self.lots_pour(od["w"], cote, prix)
            if lots <= 0:
                self.noter("SÉANCE ABANDONNÉE", session=session, raison=why)
                return "abandon"
            sl, tp = prix - cote * od["w"], prix + cote * rr * od["w"]
            digits = self.mt5.symbol_info(self.symbole).digits
            req = {"symbol": self.symbole, "volume": lots, "sl": round(sl, digits), "tp": round(tp, digits),
                   "magic": MAGIC, "comment": f"or {session}"[:31], "deviation": 30, "type_time": self.mt5.ORDER_TIME_GTC}
            if deja_passe:
                req |= {"action": self.mt5.TRADE_ACTION_DEAL, "price": prix, "type_filling": self._remplissage(),
                        "type": self.mt5.ORDER_TYPE_BUY if cote == 1 else self.mt5.ORDER_TYPE_SELL}
            else:
                req |= {"action": self.mt5.TRADE_ACTION_PENDING, "price": round(niveau, digits),
                        "type_filling": self.mt5.ORDER_FILLING_RETURN,
                        "type": self.mt5.ORDER_TYPE_BUY_STOP if cote == 1 else self.mt5.ORDER_TYPE_SELL_STOP}
            res = self.envoyer(req, f"{session} {'achat' if cote == 1 else 'vente'}")
            if res is None:
                od["essais"] = od.get("essais", 0) + 1
                if self.dernier_incertain or od["essais"] >= 3:
                    self.noter("SÉANCE ABANDONNÉE", session=session,
                               raison="réponse incertaine du courtier" if self.dernier_incertain else "3 refus du courtier")
                    return "abandon"
                return "erreur"
            if deja_passe:
                self.noter("ENTRÉE AU MARCHÉ", session=session, prix=prix, lots=lots, note=why)
                od["ticket"] = "marché"
            else:
                od.setdefault("tickets", []).append(res.order)
                od["ticket"] = res.order
        return "ok"

    def annuler(self, ticket):
        self.envoyer({"action": self.mt5.TRADE_ACTION_REMOVE, "order": ticket}, f"annulation {ticket}")

    def fermer_position(self, p, raison: str):
        tick = self.mt5.symbol_info_tick(self.symbole)
        achat = p.type == self.mt5.POSITION_TYPE_BUY
        self.envoyer({"action": self.mt5.TRADE_ACTION_DEAL, "symbol": self.symbole, "volume": p.volume, "position": p.ticket,
                      "type": self.mt5.ORDER_TYPE_SELL if achat else self.mt5.ORDER_TYPE_BUY,
                      "price": tick.bid if achat else tick.ask, "deviation": 30, "magic": MAGIC,
                      "type_filling": self._remplissage(), "comment": raison[:31]}, f"fermeture {p.ticket}")

    def tout_fermer(self, raison: str):
        for o in self.mes_ordres():
            self.annuler(o.ticket)
        for p in self.mes_positions():
            self.fermer_position(p, raison)
        self.etat["attente"] = {}

    # ---------- suivi des positions ----------
    def suivre_positions(self):
        actuelles = {str(p.ticket): p for p in self.mes_positions()}
        # nouvelles positions
        for tk, p in actuelles.items():
            if tk not in self.etat["positions"]:
                session = (p.comment or "").replace("or ", "") or "?"
                od = self.etat["attente"].pop(session, None)
                w = od["w"] if od else abs(p.price_open - p.sl)
                risque_eur = abs(self.mt5.order_calc_profit(self.mt5.ORDER_TYPE_BUY, self.symbole, p.volume, p.price_open,
                                                            p.price_open - w) or 0)
                self.etat["positions"][tk] = {"session": session, "risque_eur": risque_eur, "ouverte": self.heure()}
                self.etat.setdefault("sessions_jouees", {})[session] = self.heure().date().isoformat()
                # stop et objectif recalés sur le vrai prix d'exécution
                cote = 1 if p.type == self.mt5.POSITION_TYPE_BUY else -1
                sl, tp = p.price_open - cote * w, p.price_open + cote * self.strat.cfg.rr * w
                if abs(sl - p.sl) > 0.05 or abs(tp - p.tp) > 0.05:
                    d = self.mt5.symbol_info(self.symbole).digits
                    self.envoyer({"action": self.mt5.TRADE_ACTION_SLTP, "symbol": self.symbole, "position": p.ticket,
                                  "sl": round(sl, d), "tp": round(tp, d), "magic": MAGIC}, "recalage stop/objectif")
                self.noter("POSITION OUVERTE", session=session, sens="achat" if cote == 1 else "vente",
                           prix=p.price_open, lots=p.volume, risque_eur=round(risque_eur, 2))
                # une seule position à la fois : on retire les autres ordres (ils seront reposés après)
                for o in self.mes_ordres():
                    self.annuler(o.ticket)
                for od2 in self.etat["attente"].values():
                    od2["ticket"] = None
        if len(actuelles) > 1:  # deux ordres déclenchés en même temps : on garde la plus ancienne
            for p in sorted(actuelles.values(), key=lambda x: x.time)[1:]:
                self.fermer_position(p, "une seule position")
        # positions fermées
        for tk in [t for t in self.etat["positions"] if t not in actuelles]:
            infos = self.etat["positions"].pop(tk)
            gain = self.gain_position(int(tk))
            r = gain / infos["risque_eur"] if infos["risque_eur"] else 0
            self.noter("POSITION FERMÉE", session=infos["session"], gain_eur=round(gain, 2), r=round(r, 2),
                       solde=round(self.mt5.account_info().balance, 2))

    def gain_position(self, ticket: int) -> float:
        deals = self.mt5.history_deals_get(position=ticket) or []
        return sum(d.profit + d.commission + d.swap + getattr(d, "fee", 0.0) for d in deals)

    # ---------- limites ----------
    def limites(self) -> str | None:
        ai = self.mt5.account_info()
        now = self.heure()
        jour, semaine = now.date().isoformat(), "%d-S%02d" % now.isocalendar()[:2]
        if self.etat.get("jour") != jour:
            if self.etat.get("jour"):
                self.noter("BILAN DU JOUR", jour=self.etat["jour"], solde=round(ai.balance, 2),
                           resultat=round(ai.balance - self.etat.get("solde_jour", ai.balance), 2))
            self.etat["jour"], self.etat["solde_jour"] = jour, ai.balance
        if self.etat.get("semaine") != semaine:
            self.etat["semaine"], self.etat["solde_semaine"] = semaine, ai.balance
        if (self.dir / "PAUSE.flag").exists():
            return "fichier PAUSE.flag présent"
        if ai.equity <= self.etat["solde_jour"] * (1 - self.cfg["perte_max_jour"]):
            return f"perte du jour ≥ {self.cfg['perte_max_jour']:.0%}"
        if ai.equity <= self.etat["solde_semaine"] * (1 - self.cfg["perte_max_semaine"]):
            return f"perte de la semaine ≥ {self.cfg['perte_max_semaine']:.0%}"
        obj = self.cfg.get("objectif_semaine")
        if obj and ai.balance >= self.etat["solde_semaine"] * (1 + obj) and not self.mes_positions():
            return f"objectif de la semaine atteint (+{obj:.0%})"
        return None

    def verifier_contre(self, b: Bar, silencieux: bool = False):
        """Séance annulée si le prix casse du mauvais côté (filtre de tendance), sur les bougies APRÈS l'armement."""
        for nom, od in list(self.etat["attente"].items()):
            if str(b.t) <= od.get("arme_a", ""):
                continue
            contre_bas = od["cotes"] == [1] and b.low <= od["bas"]
            contre_haut = od["cotes"] == [-1] and b.high + b.spread >= od["haut"]
            if contre_bas or contre_haut:
                if not silencieux:
                    ouverts = [o.ticket for o in self.mes_ordres()]
                    for tk in od.get("tickets", []):
                        if tk in ouverts:
                            self.annuler(tk)
                del self.etat["attente"][nom]
                if not silencieux:
                    self.noter("SÉANCE ANNULÉE", session=nom, raison="cassure dans le sens contraire à la tendance")

    # ---------- un tour de boucle ----------
    def tour(self):
        self.verifier_demo()
        # 1) nouvelles bougies clôturées -> stratégie
        for b in self.bougies_cloturees(50):
            if self.derniere_bougie is None or b.t > self.derniere_bougie:
                self.derniere_bougie = b.t
                self.verifier_contre(b)
                for cmd in self.strat.on_bar(b):
                    self.commande(cmd, arme_a=b.t)
        # 2) positions : nouvelles, fermées ; après 21:00 rien ne doit rester ouvert
        self.suivre_positions()
        m_now = self.heure().hour * 60 + self.heure().minute
        if m_now >= self.strat.flat and (self.mes_positions() or self.mes_ordres()):
            self.tout_fermer("fermeture 21h")
        # 3) limites et pause
        stop = self.limites()
        if stop:
            if self.etat.get("pause") != stop:
                self.etat["pause"] = stop
                for o in self.mes_ordres():
                    self.annuler(o.ticket)
                for od in self.etat["attente"].values():
                    od["ticket"] = None
                self.noter("PAUSE", raison=stop)
        else:
            if self.etat.get("pause"):
                self.noter("REPRISE")
            self.etat["pause"] = None
            # 4) poser les ordres armés s'il n'y a pas de position
            if not self.mes_positions():
                m = self.heure().hour * 60 + self.heure().minute
                if m < self.strat.flat:
                    for nom, od in list(self.etat["attente"].items()):
                        if od.get("ticket") is None:
                            if self.poser(nom, od) == "abandon":
                                del self.etat["attente"][nom]
        self.sauver()

    def tourner(self, pause_s: float = 5.0):
        self.connecter()
        self.rechauffer()
        self.noter("DÉMARRAGE", version=VERSION, symbole=self.symbole)
        erreurs = 0
        while True:
            try:
                self.tour()
                erreurs = 0
            except Stop:
                raise
            except Exception as e:  # coupure, MT5 fermé... on réessaie sans planter
                erreurs += 1
                self.log(f"Erreur ({erreurs}) : {e}")
                if erreurs >= 30:
                    self.noter("ARRÊT", raison=f"trop d'erreurs : {e}")
                    raise
                time.sleep(10)
                if not self.mt5.initialize():
                    continue
            time.sleep(pause_s)
