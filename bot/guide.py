"""
/tutorial and /index: the Old Master's lessons (paged with buttons) and the Jianghu Compendium,
an index of every beast, technique manual, weapon, chest, pill and herb in the game.

Everything in the index is read from the game data modules (beasts.py, technique.py,
equipments.py, explore.py, training.py, bot/loot.py), so it stays in step when they change.
"""
import discord

import beasts as beast_rules
import equipments
import explore
import technique
import training
import talent as talent_rules

from . import loot
from . import player as rules
from .expedition import MERCHANT_HERB_PRICE, MERCHANT_PILL_PRICE
from .sheet.items import technique_effect
from .views import COLOR, SHOP_PILLS, OwnedView

GUIDE_TIMEOUT = 600   # seconds the page buttons keep working

# ── /tutorial ─────────────────────────────────────────────────────────

# (scroll title, Old Master's words, [(field name, field text)])
LESSONS = [
    ("The Gates of the Jianghu",
     "*The Old Master sets down his tea.*\n"
     "\"So, another one who wishes to climb. Listen well, and I will only say it once... or as many times "
     "as you press these buttons.\"",
     [("Begin", "Use **/start**. You place your hand on the Aptitude Stone and it reveals your **talent**, "
                "from " + " → ".join(talent_rules.TALENTS) + ". A higher talent gathers Qi faster."),
      ("What you start with", "Mortal, 1st Layer · **Iron Fist** and **Horse Stance Guard** · 🪷 "
                              f"{rules.STARTING_LOTUS_COINS} Lotus Coins."),
      ("The long road", "Mortal → " + " → ".join(rules.REALM_ORDER[1:]) + ".\n"
                        "Each realm has 10 layers in four phases: Early (1–3), Middle (4–6), Late (7–9) and Peak (10).")]),

    ("Know Yourself",
     "\"A cultivator who does not know their own body walks blind.\"",
     [("/profile", "Your scroll: realm, layer, Qi, HP / Attack / Defense, equipped techniques and weapon. "
                   "Add a member to look at someone else's."),
      ("/internal qi", "Your dantian: the Qi bar, Qi waiting to be collected, your Qi Rate, how long until the "
                       "bar fills, and every bonus that feeds it."),
      ("/balance", "Your purse: 🪷 Lotus Coins (earned by playing) and 🌙 Moon Pearls (the rare currency).")]),

    ("Gathering Qi",
     "\"Qi is the root of everything. Fill your dantian and the layers open on their own.\"",
     [("/train", "A timed challenge with the master. Your score becomes Internal Qi. Every 60 minutes."),
      ("/meditate", "Qi also gathers by itself at your Qi Rate, even while you are away (up to 12 hours is kept). "
                    "It is collected for you before every command; /meditate shows how fast it flows."),
      ("/seclusion", f"Shut yourself away for {training.SECLUSION_MIN_HOURS}–{training.SECLUSION_MAX_HOURS} hours at "
                     f"×{training.SECLUSION_QI_MULTIPLIER:g} Qi Rate. No exploring or sparring meanwhile, and leaving "
                     "early loses the bonus.")]),

    ("The Gates Within",
     "\"Layers inside a phase open by themselves. Between phases and realms stands a wall.\"",
     [("Bottlenecks", "When your Qi bar is full at the end of a phase (3rd, 6th, 9th layer) or at the 10th "
                      "layer, the Qi stops. Use **/breakthrough** and the bot shows the chance first."),
      ("The odds", f"Phase bottleneck: {training.PHASE_BOTTLENECK_SUCCESS:.0%}. New realm: "
                   f"{training.REALM_BREAKTHROUGH_SUCCESS:.0%} (Mortal → Martial Apprentice always succeeds). "
                   f"A failure costs {training.BREAKTHROUGH_FAIL_QI_LOSS:.0%} of your Qi."),
      ("Higher gates", "Martial Master, Martial King and Martial Saint also ask for technique mastery, "
                       "and the last two for a slain Beast King.")]),

    ("The Way of the Fist",
     "\"Qi without technique is a river without a channel.\"",
     [("/techniques", "Everything you have learned, with effects and mastery. Equip one **attack** and one "
                      "**defense** technique (a third, flexible slot opens at Martial Warrior)."),
      ("/practice", "A challenge that trains one technique's mastery EXP. Every 30 minutes; the first 5 "
                    "sessions each day give full EXP."),
      ("/spar", "A turn-by-turn bout with a master: Strike, Guard or Break, and use techniques at the right "
                "moment. When a technique's bar is full, sparring with it is its **mastery trial**. Every 2 hours."),
      ("Mastery stages", " → ".join(s["name"] for s in technique.MASTERY_STAGES) +
                         ". Each stage makes the technique stronger.")]),

    ("Into the Wild",
     "\"The mountains hold beasts, bandits, herbs and treasure. Mostly beasts.\"",
     [("/explore", f"A {explore.MAX_STEPS}-step expedition. At each step, read the clue and pick a path. "
                   f"Go deeper for better finds, or turn back with what you have. Every {explore.EXPLORE_COOLDOWN_MINUTES} minutes."),
      ("What waits", "Wild beasts, treasure chests, herb patches, merchants, stone tablets, hermits, "
                     "Blessed Lands that multiply your Qi... and rare lairs of Elite beasts and Beast Kings."),
      ("Defeat", f"Lose a fight and you are injured for {explore.DEFEAT_INJURY_HOURS} hour and drop half the coins "
                 "and herbs you found. **/physician** heals you for Lotus Coins."),
      ("/cooldown", "Every timer at once: when you can explore, train, practice and spar again, your daily "
                    "counts, seclusion, injury and active boons, in your own time zone.")]),

    ("Beasts and Hunts",
     "\"Know the beast before you meet it.\"",
     [("/bestiary", "A realm's six beasts with their strength measured against you."),
      ("Elite Lairs and Beast King Dens", "Finding one in /explore calls the whole channel to a hunt. "
                                          "Join, then the finder starts the fight. Every winner rolls their own chest."),
      ("Why hunt Kings", "Jade Chests, and a Beast King kill is needed to reach Martial King and Martial Saint.")]),

    ("Spoils of the Road",
     "\"Treasure means nothing if it rots in your bag.\"",
     [("/inventory", "Your bag in tabs: manuals, weapons, pills, materials and chests. Pick an item "
                     "to **open** a chest, **learn** a manual, **equip** a weapon or **take** a pill."),
      ("/equipment", "Your weapon and your stats before and after it. Swap or remove it here."),
      ("Manuals", "Learning one is instant and equips it. A copy of a manual you already know becomes mastery EXP.")]),

    ("Coin and Pearl",
     "\"Even immortals pay for their tea.\"",
     [("🪷 Lotus Coins", "Earned from chests, beasts and bandits. Spent at merchants, on **/physician**, "
                        "and on **/reroll** to reroll your talent (it can go lower!)."),
      ("🌙 Moon Pearls", "Spent in **/shop** (Qi pills, a Heavenly Fate Reroll that never goes lower, bag space, "
                        "a new name) and on **/blessing**, 30-day boosts to Qi, coins and more. "
                        "**/recharge** lists the pearl packages."),
      ("Rare finds", "Divine weapons, Heaven manuals and the Heaven-Defying Pill are announced to the whole server.")]),

    ("Walk Alone",
     "*The Old Master stands and brushes off his robe.*\n"
     "\"You have taken your first step on the martial path. The rest, you must walk alone.\"",
     [("A good day's path", "**/train** → **/explore** → open chests in **/inventory** → **/practice** "
                            "→ **/spar** → **/breakthrough** when the bar is full. Check **/internal qi** "
                            "to see how far you are."),
      ("Lost?", "**/index** lists every beast, technique, weapon, chest, pill and herb in the world. "
                "**/tutorial** brings back these lessons any time.")]),
]

SCROLL_NUMBERS = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二"]


def lesson_embed(i):
    title, words, fields = LESSONS[i]
    e = discord.Embed(title=f"卷{SCROLL_NUMBERS[i]} · {title}", description=words, color=COLOR)
    for name, value in fields:
        e.add_field(name=name, value=value, inline=False)
    e.set_author(name="The Old Master's Lessons")
    e.set_footer(text=f"Lesson {i + 1} of {len(LESSONS)}")
    return e


class TutorialView(OwnedView):
    def __init__(self, owner_id, page=0):
        super().__init__(owner_id, timeout=GUIDE_TIMEOUT)
        self.page = page
        self.prev = self.button("Back", self.go_prev, emoji="◀️")
        self.next = self.button("Next", self.go_next, emoji="▶️", style=discord.ButtonStyle.primary)
        select = discord.ui.Select(placeholder="Jump to a lesson", row=1, options=[
            discord.SelectOption(label=f"{n + 1}. {t[0]}", value=str(n)) for n, t in enumerate(LESSONS)])
        select.callback = self.jump
        self.select = select
        self.add_item(select)
        self.refresh()

    def refresh(self):
        self.prev.disabled = self.page == 0
        self.next.disabled = self.page == len(LESSONS) - 1

    async def show(self, interaction):
        self.refresh()
        await interaction.response.edit_message(embed=lesson_embed(self.page), view=self)

    async def go_prev(self, interaction):
        self.page = max(0, self.page - 1)
        await self.show(interaction)

    async def go_next(self, interaction):
        self.page = min(len(LESSONS) - 1, self.page + 1)
        await self.show(interaction)

    async def jump(self, interaction):
        self.page = int(self.select.values[0])
        await self.show(interaction)

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(view=None)
            except discord.HTTPException:
                pass


# ── /index: the Jianghu Compendium ────────────────────────────────────

TIER_LABEL = {"normal": "Normal", "elite": "Elite", "beast_king": "Beast King"}
ROLE_TRAIT = {"brute": "tough but slower", "hunter": "fragile but deadly", "swift": "15% dodge",
              "armored": "double defense"}
GRADE_SEAL = {"Mortal": "凡", "Yellow": "黄", "Mystic": "玄", "Earth": "地", "Heaven": "天"}
TIER_SEAL = {"ordinary": "凡", "refined": "精", "spirit": "灵", "treasure": "宝", "divine": "神"}
CHEST_SEAL = {"wooden": "木", "bronze": "铜", "silver": "银", "jade": "玉"}


def pct(x):
    """0.25 → '25%', 0.005 → '0.5%', 0.0005 → '0.05%'."""
    v = x * 100
    return f"{v:.0f}%" if v >= 1 and v == int(v) else f"{v:g}%"


def beast_multipliers(tier, role):
    """(hp, attack, defense) as multiples of a player at the same realm and layer (beast.md)."""
    t, r = beast_rules.BEAST_TIERS[tier], beast_rules.ROLES[role]
    hp = t["hp"] * r.get("hp", 1.0)
    atk = t["attack"] * r.get("attack", 1.0)
    dfn = atk * beast_rules.BEAST_DEFENSE_RATIO * r.get("defense", 1.0)
    return hp, atk, dfn


def chest_sources(tier):
    src = []
    if tier in explore.TREASURE_CHEST_TIER:
        src.append(f"treasure finds in /explore ({pct(explore.TREASURE_CHEST_TIER[tier])})")
    for beast_tier, spec in explore.BEAST_CHEST.items():
        if tier in spec["tiers"]:
            src.append("Beast Kings" if beast_tier == "beast_king" else f"{TIER_LABEL[beast_tier]} beasts")
    return ", ".join(src)


def odds_text(odds, label=str):
    return " · ".join(f"{label(k)} {pct(v)}" for k, v in odds.items())


def beast_pages():
    pages = []
    for realm in rules.REALM_ORDER:
        fields = []
        for name, tier, role in beast_rules.BEASTS[realm]:
            hp, atk, dfn = beast_multipliers(tier, role)
            team = beast_rules.BEAST_TIERS[tier]["team_size"]
            chest = explore.BEAST_CHEST[tier]
            fields.append((name, (
                f"**{TIER_LABEL[tier]}** · {role.title()} ({ROLE_TRAIT[role]})\n"
                f"HP ×{hp:.2g} · ATK ×{atk:.2g} · DEF ×{dfn:.2g}\n"
                + ("Solo" if team == 1 else f"Hunt with {team}+") + f" · chest {pct(chest['chance'])}")))
        pages.append((f"Beasts · {realm}",
                      "Strength is shown as a multiple of a cultivator at the same realm and layer. "
                      "Elites and Beast Kings are hunted as a team from lairs found in /explore. "
                      "**/bestiary** shows the exact numbers against you.", fields))
    return pages


def technique_pages():
    pages = []
    for grade, min_realm in technique.GRADES.items():
        skill, atk_passive = technique.ATTACK_TECHNIQUE[grade]
        block, def_passive = technique.DEFENSE_TECHNIQUE[grade]
        chests = [CHEST_SEAL[c] + " " + loot.CHEST_NAMES[c] for c, odds in explore.CHEST_MANUAL_GRADE_ODDS.items()
                  if grade in odds]
        fields = []
        for t in technique.TECHNIQUES.values():
            if t["grade"] != grade:
                continue
            kind = "⚔️ Attack" if t["type"] == "attack" else "🛡️ Defense"
            fields.append((t["name"], f"{kind} · {t['school']}\n{technique_effect(t['effect']) if t.get('effect') else 'No special effect'}"))
        start = [s["name"] for s in rules.starting_techniques()] if grade == "Mortal" else []
        pages.append((f"{GRADE_SEAL[grade]} {grade} Manuals", (
            f"Learn from **{min_realm}**. Attack: ×{skill:g} skill damage, +{pct(atk_passive)} ATK passive. "
            f"Defense: blocks {pct(block)} of a hit, +{pct(def_passive)} DEF passive. "
            f"Mastery EXP needed ×{technique.GRADE_EXP_MULTIPLIER[grade]:g}.\n"
            f"Found in: {', '.join(chests) or 'not yet in the world'}."
            + (f"\nEvery cultivator starts with {' and '.join(start)}." if start else "")), fields))
    return pages


def weapon_pages():
    pages = []
    for tier in equipments.TIERS:
        chests = [f"{CHEST_SEAL[c]} {loot.CHEST_NAMES[c]} ({pct(equipments.CHEST_WEAPON_CHANCE[c] * odds[tier])})"
                  for c, odds in equipments.CHEST_TIER_ODDS.items() if tier in odds]
        fields = []
        for wtype in equipments.WEAPON_TYPES:
            buffs = equipments.WEAPON_BUFFS[wtype][tier]
            text = " · ".join(f"+{round(lo * 100)}–{round(hi * 100)}% {rules.STAT_LABELS[s]}"
                              if lo != hi else f"+{round(lo * 100)}% {rules.STAT_LABELS[s]}"
                              for s, (lo, hi) in buffs.items())
            fields.append((equipments.WEAPON_NAMES[tier][wtype], f"{wtype.title()}\n{text}"))
        label = equipments.TIER_DISPLAY[tier].split(" ", 1)[1]
        pages.append((f"{TIER_SEAL[tier]} {label} Weapons", (
            f"Equip from **{equipments.TIER_REALM_REQUIREMENT[tier]}**. One weapon at a time.\n"
            f"Found in: {', '.join(chests)}.\n"
            "Each drop rolls its buffs inside the range: the best rolls are *Flawless* or *Fine*, "
            "the worst are *Cracked*."), fields))
    return pages


def chest_pages():
    fields = []
    for tier, name in loot.CHEST_NAMES.items():
        lo, hi = loot.CHEST_COINS[tier]
        lines = [f"🪷 {lo}–{hi} Lotus Coins",
                 f"Manual {pct(explore.CHEST_MANUAL_CHANCE[tier])}: "
                 + odds_text(explore.CHEST_MANUAL_GRADE_ODDS[tier]),
                 f"Weapon {pct(equipments.CHEST_WEAPON_CHANCE[tier])}: "
                 + odds_text(equipments.CHEST_TIER_ODDS[tier], str.title)]
        if tier == "jade":
            lines.append(f"Heaven-Defying Pill {pct(talent_rules.HEAVEN_DEFYING_PILL['jade_chest_chance'])}")
        lines.append(f"From: {chest_sources(tier)}")
        fields.append((f"{CHEST_SEAL[tier]} {name}", "\n".join(lines)))
    return [("Chests", "Open chests from **/inventory**. Coins shown are for Mortal and double with each realm.",
             fields)]


def item_pages():
    shop = {grade for grade, _ in SHOP_PILLS.values()}
    fields = []
    for grade, mult in training.QI_PILLS.items():
        src = []
        if grade in shop:
            src.append("/shop")
        if grade in MERCHANT_PILL_PRICE:
            src.append(f"merchants (🪷 {MERCHANT_PILL_PRICE[grade]})")
        fields.append((f"{GRADE_SEAL[grade]} {grade} Qi Pill", (
            f"×{mult:g} Qi Rate for {training.QI_PILL_DURATION_HOURS}h\n"
            f"From: {', '.join(src) or 'not yet in the world'}")))
    fields.append(("天 Heaven-Defying Pill", (
        f"Raises your talent one rank (up to {talent_rules.HEAVEN_DEFYING_PILL['max_talent']}). Cannot be traded.\n"
        f"From: Jade Chests ({pct(talent_rules.HEAVEN_DEFYING_PILL['jade_chest_chance'])})")))
    herbs = "\n".join(f"· {h}" for h in loot.HERBS)
    fields.append(("🌿 Herbs", f"{herbs}\nFrom herb patches and merchants (🪷 {MERCHANT_HERB_PRICE}). Kept for alchemy, which "
                              "is not open yet."))
    return [("Pills and Herbs", "Take pills from **/inventory**. Too many pills in a short time build "
                                "toxicity and weaken the next ones.", fields)]


# section key → (menu label, emoji, page builder, short description)
SECTIONS = {
    "beasts":     ("Beasts", "🐾", beast_pages, "Every beast, realm by realm"),
    "techniques": ("Techniques", "📜", technique_pages, "Manuals by grade, with effects"),
    "weapons":    ("Weapons", "⚔️", weapon_pages, "Weapons by tier, with buffs"),
    "chests":     ("Chests", "📦", chest_pages, "What each chest holds"),
    "items":      ("Pills and Herbs", "💊", item_pages, "Qi pills, rare pills, herbs"),
}


def index_embed(section, page):
    label, emoji, build, _ = SECTIONS[section]
    pages = build()
    page = min(max(0, page), len(pages) - 1)
    title, desc, fields = pages[page]
    e = discord.Embed(title=f"{emoji} {title}", description=desc, color=COLOR)
    e.set_author(name="The Jianghu Compendium · 万物录")
    for name, value in fields:
        e.add_field(name=name, value=value, inline=True)
    e.set_footer(text=f"{label} · page {page + 1} of {len(pages)}" if len(pages) > 1 else label)
    return e, len(pages)


class IndexView(OwnedView):
    def __init__(self, owner_id, section="beasts", page=0):
        super().__init__(owner_id, timeout=GUIDE_TIMEOUT)
        self.section, self.page, self.pages = section, page, 1
        select = discord.ui.Select(placeholder="Choose a section", row=0, options=[
            discord.SelectOption(label=label, value=key, emoji=emoji, description=desc, default=key == section)
            for key, (label, emoji, _, desc) in SECTIONS.items()])
        select.callback = self.pick
        self.select = select
        self.add_item(select)
        self.prev = self.button("Back", self.go_prev, emoji="◀️", row=1)
        self.next = self.button("Next", self.go_next, emoji="▶️", style=discord.ButtonStyle.primary, row=1)

    def render(self):
        e, self.pages = index_embed(self.section, self.page)
        self.page = min(self.page, self.pages - 1)
        self.prev.disabled = self.page == 0
        self.next.disabled = self.page >= self.pages - 1
        for opt in self.select.options:
            opt.default = opt.value == self.section
        return e

    async def show(self, interaction):
        await interaction.response.edit_message(embed=self.render(), view=self)

    async def pick(self, interaction):
        self.section, self.page = self.select.values[0], 0
        await self.show(interaction)

    async def go_prev(self, interaction):
        self.page = max(0, self.page - 1)
        await self.show(interaction)

    async def go_next(self, interaction):
        self.page = min(self.pages - 1, self.page + 1)
        await self.show(interaction)

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(view=None)
            except discord.HTTPException:
                pass


def register(bot):
    from discord import app_commands

    @bot.tree.command(name="tutorial", description="The Old Master's lessons: how to play Mortal Ascent")
    async def tutorial(interaction: discord.Interaction):
        view = TutorialView(interaction.user.id)
        await interaction.response.send_message(embed=lesson_embed(0), view=view)
        view.message = await interaction.original_response()

    @bot.tree.command(name="index", description="The Jianghu Compendium: every beast, technique, weapon, chest and pill")
    @app_commands.describe(section="Which section to open first", realm="For beasts: which realm")
    @app_commands.choices(
        section=[app_commands.Choice(name=v[0], value=k) for k, v in SECTIONS.items()],
        realm=[app_commands.Choice(name=r, value=r) for r in rules.REALM_ORDER])
    async def index(interaction: discord.Interaction, section: app_commands.Choice[str] | None = None,
                    realm: app_commands.Choice[str] | None = None):
        key = section.value if section else "beasts"
        page = rules.REALM_ORDER.index(realm.value) if realm and key == "beasts" else 0
        view = IndexView(interaction.user.id, key, page)
        await interaction.response.send_message(embed=view.render(), view=view)
        view.message = await interaction.original_response()
