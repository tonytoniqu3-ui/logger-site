"""La stratégie, sans aucune dépendance à MT5 : elle est partagée par le simulateur et le robot.

Règles (heure du serveur MT5) :
  - Pour chaque séance (Asie 01:00-03:00, New York 10:00-15:00), on mesure le plus haut et le plus bas.
  - À la fin de la séance, on arme un ordre stop au plus haut (achat) et/ou au plus bas (vente).
    Avec le filtre de tendance, seulement dans le sens de la tendance (prix vs EMA ~200 heures).
  - Stop = largeur du range, objectif = 2 x le risque. Une seule position à la fois.
  - Tout est fermé à 21:00. Jamais de position la nuit ni le week-end.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


def hm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


@dataclass
class Bar:
    t: datetime          # heure d'OUVERTURE de la bougie M5, heure serveur
    open: float
    high: float
    low: float
    close: float
    spread: float = 0.0  # en prix (dollars), pas en points


@dataclass
class Config:
    sessions: list = field(default_factory=lambda: [("Asie", "01:00", "03:00"), ("New York", "10:00", "15:00")])
    fermeture: str = "21:00"
    rr: float = 2.0
    tendance: bool = True
    ema_bougies: int = 2400          # EMA sur 2400 bougies M5 = environ 200 heures
    retard_max: float = 0.35         # on n'entre pas si le prix est déjà à plus de 35 % du range au-delà du niveau
    min_bougies_range: float = 0.6   # range valide si au moins 60 % des bougies attendues sont là

    @classmethod
    def from_dict(cls, d: dict) -> "Config":
        c = cls()
        for k, v in d.items():
            if hasattr(c, k):
                setattr(c, k, [tuple(x) for x in v] if k == "sessions" else v)
        return c


class Strategie:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.sessions = [(n, hm(a), hm(b)) for n, a, b in cfg.sessions]
        self.flat = hm(cfg.fermeture)
        self.alpha = 2 / (cfg.ema_bougies + 1)
        self.ema = None
        self.jour = None
        self.acc = {}
        self.fait = set()
        self.ferme = False

    def on_bar(self, b: Bar) -> list[dict]:
        """Appelée à la CLÔTURE de chaque bougie M5. Renvoie des commandes :
        {"type": "armer", "session", "haut", "bas", "w", "cotes": (1, -1) ou (1,) ou (-1,)}
        {"type": "fermer"}  (21:00 : tout fermer et annuler)"""
        cmds = []
        jour = b.t.date()
        if jour != self.jour:
            self.jour, self.acc, self.fait, self.ferme = jour, {}, set(), False
        ema_avant = self.ema
        self.ema = b.close if self.ema is None else self.alpha * b.close + (1 - self.alpha) * self.ema
        m = b.t.hour * 60 + b.t.minute
        fin_bougie = m + 5
        for nom, a, z in self.sessions:
            if a <= m < z:
                hi, lo, n = self.acc.get(nom, (b.high, b.low, 0))
                self.acc[nom] = (max(hi, b.high), min(lo, b.low), n + 1)
            if nom not in self.fait and fin_bougie >= z and m < self.flat and nom in self.acc:
                self.fait.add(nom)
                hi, lo, n = self.acc[nom]
                if n < max(3, (z - a) // 5 * self.cfg.min_bougies_range) or hi <= lo:
                    continue
                cotes = (1, -1)
                if self.cfg.tendance:
                    if ema_avant is None or b.close == ema_avant:
                        continue
                    cotes = (1,) if b.close > ema_avant else (-1,)
                cmds.append({"type": "armer", "session": nom, "haut": hi, "bas": lo, "w": hi - lo, "cotes": cotes})
        if not self.ferme and fin_bougie >= self.flat:
            self.ferme = True
            cmds.append({"type": "fermer"})
        return cmds

    def prix_entree_ok(self, cote: int, niveau: float, prix: float, w: float) -> bool:
        """Règle d'entrée tardive : pas plus de `retard_max` x range au-delà du niveau."""
        return abs(prix - niveau) <= self.cfg.retard_max * w


def taille_position(solde: float, perte_par_lot: float, risque: float, risque_max: float,
                    lot_min: float = 0.01, pas: float = 0.01) -> tuple[float, str]:
    """Nombre de lots pour risquer `risque` x solde. Si c'est sous le lot minimum, on accepte le lot minimum
    tant que le risque réel reste sous `risque_max` (sinon on passe le trade)."""
    if perte_par_lot <= 0:
        return 0.0, "perte par lot invalide"
    lots = int(solde * risque / perte_par_lot / pas + 1e-9) * pas
    if lots >= lot_min:
        return round(lots, 2), "ok"
    if perte_par_lot * lot_min <= solde * risque_max:
        return lot_min, "lot minimum (risque %.1f %%)" % (100 * perte_par_lot * lot_min / solde)
    return 0.0, "range trop large pour ce solde (risque au lot minimum %.1f %%)" % (100 * perte_par_lot * lot_min / solde)
