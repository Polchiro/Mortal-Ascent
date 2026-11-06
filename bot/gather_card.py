"""
Plain data for the live /gather cards (cards/herbfield.py), built from a running Gathering.

Only reads the gathering: it never changes a rule or a number.
"""
import alchemy

SIGN_WORD = {"moon": "the moon", "sun": "the sun", "star": "the star", "flame": "the flame", "leaf": "the leaf",
             "wave": "the wave"}


def outcome(text):
    """The kind of result from the text Gathering.answer returned."""
    if text.startswith(("✅ You find", "✅ You gather", "✨")):
        return "full" if "bag is full" in text else "gathered"
    if text.startswith("☠"):
        return "poison"
    if text.startswith("⏳"):
        return "slow"
    if text.startswith("👻"):
        return "passed" if "not a puppet" in text else "failed"
    return "wrong"


def streak_bonus(streak):
    mult = next(m for min_streak, m in alchemy.STREAK_BONUS if streak >= min_streak)
    nxt = next(((s, m) for s, m in reversed(alchemy.STREAK_BONUS) if s > streak), None)
    return mult, nxt


def session_rows(gathered):
    """Herbs gathered this session, counted by name and age, oldest first."""
    rows = {}
    for h in gathered:
        d = h.get("data") or {}
        key = (h["name"], d.get("age", 10))
        row = rows.setdefault(key, {"name": h["name"], "type": d.get("type", "qi"), "age": d.get("age", 10), "qty": 0})
        row["qty"] += 1
    return sorted(rows.values(), key=lambda r: (-r["age"], -r["qty"]))


def _common(g, player):
    rows = session_rows(g.gathered)
    best = f"{rows[0]['age']}-year {rows[0]['name']}" if rows else None
    mult, nxt = streak_bonus(player["herb_streak"])
    return {"session": rows, "gathered": len(g.gathered), "best": best, "hp": g.hp, "max_hp": g.max_hp,
            "streak": player["herb_streak"], "streak_mult": mult, "streak_next": nxt,
            "decoy_note": f"−{alchemy.DECOY_HP_LOSS:.0%} HP, streak resets"}


def field_data(g, player, r, result_text=None, picked=None):
    """The herb field for round r; with result_text, the same round after the pick."""
    herb = r.herb
    d = herb.get("data") or {}
    tier, type_ = d.get("tier", herb.get("grade")), d.get("type")
    choices = [{"key": k, "name": r.names[k], "look": label} for k, label, _ in r.options]
    data = dict(_common(g, player), place=r.place, tier=tier, name=herb["name"], type=type_, age=d.get("age", 10),
                old=r.old, desc=alchemy.HERBS[tier][type_][1], seconds=r.seconds, choices=choices, result=None)
    if result_text is not None:
        data["result"] = {"answer": r.answer, "picked": picked, "outcome": outcome(result_text), "text": result_text}
    return data


def spirit_data(g, player, r, result_text=None):
    left = alchemy.SPIRIT_CHECK_FAILS_TO_PAUSE - player["spirit_check_fails"]
    data = {"place": r.place or "the misty slope", "sign": SIGN_WORD.get(r.answer, r.shown or r.answer),
            "seconds": r.seconds, "fails_left": max(1, left), "result": None}
    if result_text is not None:
        from cards.activity import clean
        data["result"] = {"outcome": outcome(result_text), "text": clean(result_text)[0]}
    return data
