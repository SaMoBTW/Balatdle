"""Feedback rules: how a guessed joker compares to the answer, one attribute at a time.

Every attribute comes back as "exact", "partial" or "none". The partial rules are:
  rarity       one tier apart, in the order Common, Uncommon, Rare, Legendary
  cost         within COST_RANGE dollars; cost also points toward the answer's cost
  effect_type  same family: Mult with XMult, or Chips and Mult with either Chips or Mult
  unlock       both jokers need unlocking, but by different requirements
Activation and scales have no partial match.
"""
RARITIES = ["Common", "Uncommon", "Rare", "Legendary"]
EFFECT_FAMILIES = {frozenset(pair) for pair in [("Mult", "XMult"), ("Chips and Mult", "Chips"), ("Chips and Mult", "Mult")]}
STARTER = "Available from start"
COST_RANGE = 2


def level(exact, partial=False):
    return "exact" if exact else "partial" if partial else "none"


def compare(guessed, answer):
    """Feedback for each attribute. Only the guessed joker's own values are included,
    so the result never states anything about the answer directly."""
    g, a = guessed, answer
    rarity_gap = abs(RARITIES.index(g["rarity"]) - RARITIES.index(a["rarity"]))
    cost_gap = a["cost"] - g["cost"]
    return [
        {"attribute": "rarity", "value": g["rarity"], "match": level(rarity_gap == 0, rarity_gap == 1)},
        {"attribute": "cost", "value": g["cost"], "match": level(cost_gap == 0, abs(cost_gap) <= COST_RANGE),
         "direction": "higher" if cost_gap > 0 else "lower" if cost_gap < 0 else None},
        {"attribute": "effect_type", "value": g["effect_type"],
         "match": level(g["effect_type"] == a["effect_type"], frozenset((g["effect_type"], a["effect_type"])) in EFFECT_FAMILIES)},
        {"attribute": "activation", "value": g["activation"], "match": level(g["activation"] == a["activation"])},
        {"attribute": "scales", "value": g["scales"], "match": level(g["scales"] == a["scales"])},
        {"attribute": "unlock_method", "value": g["unlock_method"],
         "match": level(g["unlock_method"] == a["unlock_method"], STARTER not in (g["unlock_method"], a["unlock_method"]))},
    ]
