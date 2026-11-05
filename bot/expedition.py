"""
/explore — game logic for one expedition (docs/explore.md).

Expedition holds all state and has no Discord code, so it can be tested
directly. bot/views.py drives it with buttons.
"""
import random
import time

import alchemy
import beasts
import challenges
import explore
import technique
import training

from . import combat, db, hunt, loot, mastery
from . import player as rules

CLUES = {
    "wild_beast":         ["You hear low growling...", "Fresh claw marks scar the trees.", "Something heavy breathes in the brush."],
    "treasure_chest":     ["Something glints between the roots.", "A faint golden glow...", "An old cart lies overturned."],
    "herb_patch":         ["A sweet, earthy smell drifts by.", "Dew sparkles on thick green leaves.", "Bees hum over wild flowers."],
    "peaceful_clearing":  ["Complete silence.", "Soft sunlight through the leaves.", "Birds sing calmly."],
    "hazard":             ["The air smells sour.", "Loose stones trickle down the slope.", "A thin mist clings to the ground."],
    "bandits":            ["Muffled voices and laughter.", "A campfire's smoke rises ahead.", "Boot prints, many of them."],
    "wandering_merchant": ["A bell jingles in the distance.", "The creak of a heavy pack.", "Someone hums a trader's tune."],
    "injured_stranger":   ["A weak voice calls for help.", "Drops of blood on the path.", "A torn sleeve hangs on a branch."],
    "stone_tablet":       ["Moss-covered stones in a ring.", "Carved characters peek through vines.", "An old shrine, long forgotten."],
    "elite_lair":         ["Bones are piled by a cave mouth.", "The ground trembles with heavy steps.", "Every bird has fled."],
    "blessed_land":       ["The air feels light and pure.", "Qi ripples like warm water.", "Flowers bloom out of season."],
    "wandering_hermit":   ["A flute plays a lonely melody.", "An old voice recites scripture.", "Incense smoke curls through the trees."],
    "beast_king_den":     ["A roar shakes the whole forest.", "The trees are torn from their roots.", "A crushing pressure fills the air."],
}
PATH_EMOJI = {"left": "⬅️", "middle": "⬆️", "right": "➡️"}
BLESSED_LAND_NAMES = {"spirit_spring": "💧 Spirit Spring", "lotus_grove": "🌸 Lotus Grove", "dragon_vein": "🐉 Dragon Vein"}

# DEFAULTS where explore.md leaves numbers open
BEAST_COINS = (3, 8)                      # Lotus Coins per Normal beast (× realm scale)
BANDIT_WIN_COINS = (10, 20)
STRANGER_REWARD_COINS = (20, 40)
STRANGER_COIN_COST = (5, 10)
STRANGER_HP_COST = 0.15
MERCHANT_PILL_PRICE = {"Mortal": 40, "Yellow": 120, "Mystic": 400}
MERCHANT_HERB_PRICE = 10
HERMIT_MASTERY_EXP = 300
HERMIT_MANUAL_CHANCE = 0.10
HAZARD_SECONDS = 3.0
TIMER_GRACE_SECONDS = 1.0                 # Discord round-trip allowance on timed buttons


def encounter_odds(step):
    """Base chances with rare ones multiplied by the step bonus; commons scaled so the sum stays 1."""
    mult = explore.RARE_CHANCE_BY_STEP[step]
    rare = {k: v["chance"] * mult for k, v in explore.ENCOUNTERS.items() if v["rare"]}
    common = {k: v["chance"] for k, v in explore.ENCOUNTERS.items() if not v["rare"]}
    scale = (1 - sum(rare.values())) / sum(common.values())
    return {**{k: v * scale for k, v in common.items()}, **rare}


class Expedition:
    def __init__(self, conn, user_id, rng=None):
        self.conn, self.user_id = conn, user_id
        self.rng = rng or random.Random()
        self.player = db.get_player(conn, user_id)
        self.techniques = db.get_techniques(conn, user_id)
        weapon = db.equipped_weapon(conn, user_id)
        hp, self.attack, self.defense = rules.final_stats(self.player, self.techniques, weapon)
        self.hp = self.max_hp = hp
        self.tier = challenges.REALM_TIER[self.player["realm"]]
        self.step = 0
        self.paths = {}
        self.coins = 0
        self.items = []           # found this expedition
        self.beasts_slain = 0
        self.story = []           # lines describing the latest step
        self.pending = None       # "merchant", "stranger", "hazard"
        self.merchant = None
        self.hazard = None
        self.over = False
        self.defeated = False
        self.summary = []
        self.notes = []           # mastery trial reminders, shown at the end
        self.lair = None          # set when an Elite Lair or Beast King Den is found
        self.announce = []        # server-wide announcements for rare finds
        self.banked = None        # what finish() put in the purse and bag

    # ── steps ────────────────────────────────────────────────────────

    def next_step(self):
        self.step += 1
        self.story, self.pending = [], None
        odds = encounter_odds(self.step)
        mislead = explore.MISLEADING_CLUE_CHANCE[self.tier]
        self.paths = {}
        for path in explore.PATHS:
            enc = loot.pick(odds, self.rng)
            shown = enc
            if self.rng.random() < mislead:
                shown = self.rng.choice([k for k in CLUES if k != enc])
            self.paths[path] = (enc, self.rng.choice(CLUES[shown]))

    def choose(self, path):
        enc, _ = self.paths[path]
        self.story = []
        getattr(self, f"_{enc}")()
        if self.hp <= 0:
            self._defeat()

    @property
    def can_go_deeper(self):
        return not self.over and self.pending is None and self.step < explore.MAX_STEPS

    # ── encounters ───────────────────────────────────────────────────

    def _hero(self):
        return {"hp": self.hp, "max_hp": self.max_hp, "attack": self.attack, "defense": self.defense}

    def _fight(self, enemy):
        hero = self._hero()
        res = combat.fight(hero, enemy, self.techniques, self.rng)
        self.hp = hero["hp"]
        self._mastery_from_fight(res)
        self.story += res["log"]
        return res

    def _mastery_from_fight(self, res):
        for t in self.techniques:
            uses = res["attack_uses"] if t["type"] == "attack" else res["guard_uses"]
            if uses:
                self._give_mastery(t, uses * technique.COMBAT_EXP_PER_USE, quiet=True)

    def _give_mastery(self, tech, exp, quiet=False):
        gained, note = mastery.gain(self.conn, self.player, tech, exp)
        if not quiet and gained:
            self.story.append(f"📈 **{tech['name']}** gains **{gained} mastery EXP**.")
        if note and note not in self.notes:
            self.notes.append(note)
        return gained

    def _wild_beast(self):
        normals = [b for b in beasts.BEASTS[self.player["realm"]] if b[1] == "normal"]
        enemy = combat.beast_stats(self.player, self.rng.choice(normals), self.step)
        bonus = f" (+{(self.step - 1) * 10}% stronger this deep)" if self.step > 1 else ""
        self.story.append(f"🐾 A **{enemy['name']}** ({enemy['role'].title()}) leaps out{bonus}!")
        res = self._fight(enemy)
        if not res["won"]:
            self.story.append(f"The {enemy['name']} overwhelms you...")
            return
        self.beasts_slain += 1
        coins = loot.roll_coins(self.player, BEAST_COINS, self.rng)
        self.coins += coins
        self.story.append(f"⚔️ The **{enemy['name']}** falls! +🪷 {coins}")
        c = loot.beast_chest(self.player, "normal", self.rng)
        if c:
            self.items.append(c)
            self.story.append(f"{loot.CHEST_EMOJI[c['key']]} It dropped a **{c['name']}**!")

    def _treasure_chest(self):
        c = loot.chest(loot.pick(explore.TREASURE_CHEST_TIER, self.rng))
        self.items.append(c)
        self.story.append(f"📦 Hidden under the roots: a **{c['name']}**! (Open it from /inventory.)")

    def _herb_patch(self):
        found = [loot.roll_herb(self.player["realm"], self.rng)
                 for _ in range(self.rng.randint(*alchemy.HERB_PATCH_HERBS))]
        self.items += found
        self.story.append("🌿 A patch of wild herbs! You gather " + ", ".join(f"**{loot.describe(h)}**" for h in found)
                          + ". (**/gather** finds more.)")

    def _peaceful_clearing(self):
        heal = round(self.max_hp * explore.PEACEFUL_CLEARING_HEAL)
        before = self.hp
        self.hp = min(self.max_hp, self.hp + heal)
        self.story.append(f"🏕️ A peaceful clearing. You rest and recover **{self.hp - before} HP**.")

    def _hazard(self):
        kind = self.rng.choice(["poison mist", "landslide"])
        danger = self.rng.choice(explore.PATHS)
        self.hazard = {"kind": kind, "danger": danger, "shown_at": None,
                       "seconds": HAZARD_SECONDS}
        self.pending = "hazard"
        where = {"left": "from the LEFT", "middle": "straight AHEAD", "right": "from the RIGHT"}[danger]
        verb = "rolls in" if kind == "poison mist" else "comes crashing down"
        self.story.append(f"⚠️ A **{kind}** {verb} {where}! Leap to safety, quickly!")

    def dodge(self, path, now=None):
        now = time.time() if now is None else now
        h = self.hazard
        slow = h["shown_at"] is not None and now - h["shown_at"] > h["seconds"] + TIMER_GRACE_SECONDS
        self.pending = None
        self.story = []
        if path == h["danger"] or slow:
            lost = round(self.max_hp * explore.HAZARD_FAIL_HP_LOSS)
            self.hp = max(0, self.hp - lost)
            why = "too slow" if slow else "straight into it"
            self.story.append(f"💥 You leapt {why}! The {h['kind']} costs you **{lost} HP**.")
            if self.hp <= 0:
                self._defeat()
        else:
            self.story.append(f"💨 You leap clear of the {h['kind']}!")

    def _bandits(self, ambush=False):
        enemy = combat.bandit_stats(self.player, self.rng)
        self.story.append(f"🗡️ {'Ambush! ' if ambush else ''}**{enemy['name']}** block the path!")
        res = self._fight(enemy)
        if res["won"]:
            coins = loot.roll_coins(self.player, BANDIT_WIN_COINS, self.rng)
            self.coins += coins
            self.story.append(f"You drive them off and take their purse: +🪷 {coins}")
        else:
            wallet = db.get_player(self.conn, self.user_id)["lotus_coins"]
            stolen = int(wallet * explore.BANDIT_COIN_LOSS)
            db.add_coins(self.conn, self.user_id, -stolen, "Robbed by bandits")
            self.story.append(f"They beat you and rob **🪷 {stolen}** from your purse.")

    def _wandering_merchant(self):
        grade = {1: "Mortal", 2: "Yellow"}.get(self.tier, "Mystic")
        scale = rules.realm_scale(self.player["realm"])
        herb = loot.herb(alchemy.HERB_TIER_BY_REALM[self.player["realm"]], rng=self.rng)    # a 10-year herb
        self.merchant = {"pill": grade, "pill_price": MERCHANT_PILL_PRICE[grade] * scale,
                         "herb_item": herb, "herb": herb["name"], "herb_price": MERCHANT_HERB_PRICE * scale,
                         "bought": set()}
        self.story.append("🧳 A wandering merchant waves you over: *\"Fine wares for a fine warrior!\"*")

    def buy(self, what):
        m = self.merchant
        price = m[f"{what}_price"]
        wallet = db.get_player(self.conn, self.user_id)["lotus_coins"]
        if what in m["bought"]:
            return "You already bought that."
        if wallet < price:
            return f"You need 🪷 {price} but only have 🪷 {wallet}."
        item = loot.pill(m["pill"]) if what == "pill" else dict(m["herb_item"])
        if db.spend(self.conn, self.user_id, "lotus_coins", price, f"Merchant: {item['name']}") is None:
            return f"You need 🪷 {price} but only have 🪷 {wallet}."
        stored, _ = loot.store(self.conn, self.user_id, [item])
        if not stored:
            db.change_currency(self.conn, self.user_id, "lotus_coins", price, "Refund: bag full")
            return "Your bag is full."
        m["bought"].add(what)
        self.story.append(f"🛒 You bought **{item['name']}** for 🪷 {price}.")
        return None

    def _injured_stranger(self):
        scale = rules.realm_scale(self.player["realm"])
        self.stranger_cost = self.rng.randint(*STRANGER_COIN_COST) * scale
        self.pending = "stranger"
        self.story.append("🩸 A wounded traveller lies by the path, clutching their side. *\"Please... help me...\"*")

    def help_stranger(self, how):
        """how: 'coins', 'hp' or 'leave'."""
        self.pending = None
        self.story = []
        if how == "leave":
            self.story.append("You walk past. Their groans fade behind you.")
            return
        if how == "coins":
            wallet = db.get_player(self.conn, self.user_id)["lotus_coins"]
            paid = min(wallet, self.stranger_cost)
            db.add_coins(self.conn, self.user_id, -paid, "Helped a wounded traveller")
            self.story.append(f"You give them 🪷 {paid} for medicine.")
        else:
            lost = round(self.max_hp * STRANGER_HP_COST)
            self.hp = max(1, self.hp - lost)
            self.story.append(f"You channel Qi into their wounds (−{lost} HP).")
        if self.rng.random() < explore.INJURED_STRANGER_GRATEFUL:
            coins = loot.roll_coins(self.player, STRANGER_REWARD_COINS, self.rng)
            self.coins += coins
            h = loot.roll_herb(self.player["realm"], self.rng)
            self.items.append(h)
            self.story.append(f"🙏 *\"I won't forget this!\"* They press a reward into your hands: "
                              f"🪷 {coins} and **{loot.describe(h)}**.")
        else:
            self.story.append("😈 The stranger leaps up, laughing. It was a trap!")
            self._bandits(ambush=True)
            if self.hp <= 0:
                self._defeat()

    def _stone_tablet(self):
        self.story.append("🪨 An ancient stone tablet. Its carvings speak of the martial path...")
        if self.techniques:
            t = self.rng.choice(self.techniques)
            if not self._give_mastery(t, technique.PRACTICE_BASE_EXP * explore.STONE_TABLET_PRACTICE_SESSIONS):
                self.story.append(f"**{t['name']}** can learn nothing more until it passes its trial.")

    def _elite_lair(self):
        self.lair = hunt.roll_lair(self.player, "elite", self.rng)
        self.story.append(f"⚔️ You find the lair of a **{self.lair['beast'][0]}** (Elite)! It is far too strong to face "
                          f"alone. You mark the spot and call for a team: the lair stays open "
                          f"{hunt.open_minutes('elite')} minutes.")

    def _beast_king_den(self):
        self.lair = hunt.roll_lair(self.player, "beast_king", self.rng)
        self.story.append(f"👑 The den of **{self.lair['beast'][0]}**, a Beast King! Its aura alone makes your knees "
                          f"shake. You send up a signal flare: the den stays open {hunt.open_minutes('beast_king')} minutes.")

    def _blessed_land(self):
        kind = loot.pick(explore.BLESSED_LAND_TYPE, self.rng)
        minutes = self.rng.randint(*training.BLESSED_LAND_DURATION_MINUTES)
        expires = time.time() + minutes * 60
        db.update_player(self.conn, self.user_id, blessed_land=kind, blessed_land_expires=expires)
        self.player["blessed_land"], self.player["blessed_land_expires"] = kind, expires
        land = training.BLESSED_LANDS[kind]
        extra = f", mastery EXP ×{land['mastery_multiplier']:g}" if land["mastery_multiplier"] > 1 else ""
        self.story.append(f"✨ You discover a **{BLESSED_LAND_NAMES[kind]}**! For {minutes} minutes: "
                          f"Qi Rate ×{land['qi_multiplier']:g}{extra}, and /train cooldown halved.")

    def _wandering_hermit(self):
        self.story.append("🧙 A wandering hermit studies you. *\"Show me your stance...\"* He corrects every flaw.")
        if self.techniques:
            self._give_mastery(self.rng.choice(self.techniques), HERMIT_MASTERY_EXP)
        if self.rng.random() < HERMIT_MANUAL_CHANCE:
            m = loot.roll_manual(loot.pick(explore.CHEST_MANUAL_GRADE_ODDS["silver"], self.rng), self.rng)
            self.items.append(m)
            self.story.append(f"📜 As he leaves, he hands you a **{m['name']}**!")

    # ── ending ───────────────────────────────────────────────────────

    def _defeat(self):
        self.defeated = True
        self.finish()

    def finish(self, now=None):
        """Bank the loot, set the cooldown (and injury on defeat). Safe to call twice."""
        if self.over:
            return
        now = time.time() if now is None else now
        self.over, self.pending = True, None
        coins, items = self.coins, list(self.items)
        lines = []
        if self.defeated:
            coins = round(coins * (1 - explore.DEFEAT_LOOT_LOSS))
            kept = []
            for it in items:
                if it["category"] == "herbs":
                    q = it.get("qty", 1) - round(it.get("qty", 1) * explore.DEFEAT_LOOT_LOSS)
                    if q > 0:
                        kept.append(dict(it, qty=q))
                else:
                    kept.append(it)
            items = kept
            lines.append(f"☠️ **You were defeated.** Half of the coins and herbs you found are lost, and you are "
                         f"injured for {explore.DEFEAT_INJURY_HOURS} hour(s).")
        stored, lost = loot.store(self.conn, self.user_id, items)
        self.banked = {"coins": coins, "stored": stored, "lost": lost}     # for the result card
        self.announce += [a for a in (loot.announcement(self.player["name"], i) for i in stored) if a]
        db.add_coins(self.conn, self.user_id, coins, "Expedition loot")
        fields = {"beasts_slain": self.player["beasts_slain"] + self.beasts_slain}
        if self.defeated:
            fields["injured_until"] = now + explore.DEFEAT_INJURY_HOURS * 3600
        db.update_player(self.conn, self.user_id, **fields)
        db.set_cooldown(self.conn, self.user_id, "explore", explore.EXPLORE_COOLDOWN_MINUTES * 60, now)

        if coins:
            lines.append(f"🪷 **{coins:,}** Lotus Coins")
        lines += [f"• {loot.describe(i)}" for i in stored]
        lines += [f"⚠️ Bag full, left behind: {loot.describe(i)}" for i in lost]
        if self.beasts_slain:
            lines.append(f"🐾 Beasts slain: {self.beasts_slain}")
        if len(lines) == (1 if self.defeated else 0):
            lines.append("You return empty-handed.")
        lines += self.notes
        self.summary = lines
