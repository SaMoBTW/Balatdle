"""Checks every feedback rule in evaluate.py. No database needed.

Usage:  python test_evaluate.py
"""
from evaluate import compare


def joker(**overrides):
    base = dict(rarity="Common", cost=5, effect_type="Mult", activation="Independent",
                scales=False, unlock_method="Available from start")
    return {**base, **overrides}


def matches(guessed, answer):
    return {f["attribute"]: f["match"] for f in compare(guessed, answer)}


def cost(guessed, answer):
    return next(f for f in compare(joker(cost=guessed), joker(cost=answer)) if f["attribute"] == "cost")


# the answer itself is exact on every attribute, with no cost arrow
assert set(matches(joker(), joker()).values()) == {"exact"}
assert cost(5, 5)["direction"] is None

# rarity: one tier apart is partial, two or more is none
assert matches(joker(rarity="Uncommon"), joker(rarity="Common"))["rarity"] == "partial"
assert matches(joker(rarity="Legendary"), joker(rarity="Rare"))["rarity"] == "partial"
assert matches(joker(rarity="Common"), joker(rarity="Rare"))["rarity"] == "none"

# cost: within $2 is partial, and the arrow points toward the answer's cost
assert cost(5, 7) == {"attribute": "cost", "value": 5, "match": "partial", "direction": "higher"}
assert cost(5, 3)["match"] == "partial" and cost(5, 3)["direction"] == "lower"
assert cost(5, 8)["match"] == "none" and cost(5, 8)["direction"] == "higher"
assert cost(20, 10)["match"] == "none" and cost(20, 10)["direction"] == "lower"

# effect type: only the listed families are partial
fam = lambda g, a: matches(joker(effect_type=g), joker(effect_type=a))["effect_type"]
assert fam("XMult", "Mult") == fam("Mult", "XMult") == "partial"
assert fam("Chips", "Chips and Mult") == fam("Chips and Mult", "Mult") == "partial"
assert fam("XMult", "Chips and Mult") == "none"
assert fam("Economy", "Effect") == "none"

# activation and scales are exact or nothing
assert matches(joker(activation="On Scored"), joker(activation="On Held"))["activation"] == "none"
assert matches(joker(scales=True), joker())["scales"] == "none"

# unlock: both locked behind different requirements is partial; starter against locked is none
unl = lambda g, a: matches(joker(unlock_method=g), joker(unlock_method=a))["unlock_method"]
assert unl("Win a run", "Have at least $400") == "partial"
assert unl("Available from start", "Win a run") == "none"
assert unl("Win a run", "Win a run") == "exact"

# a wrong guess only ever reports the guessed joker's own values
feedback = compare(joker(rarity="Rare", cost=8), joker(rarity="Common", cost=2))
assert [f["value"] for f in feedback if f["attribute"] in ("rarity", "cost")] == ["Rare", 8]

print("US-4 feedback rules passed.")
