"""
/tutorial and /index: the Old Master's lessons (paged with buttons) and the Jianghu Compendium,
an index of every beast, technique manual, weapon, armor piece, artifact, chest, pill and herb in the game.

Everything in the index is read from the game data modules (beasts.py, technique.py,
equipments.py, explore.py, training.py, alchemy.py, bot/loot.py), so it stays in step when they change.
The /index pages are built in bot/compendium.py and drawn as image cards by cards/compendium.py.
"""
import alchemy
import battle
import discord

import economy
import explore
import forge
import quests
import realms
import technique
import training
import talent as talent_rules

from cards.compendium import render_compendium

from . import compendium, crafting
from . import player as rules
from . import render as card_render
from .views import COLOR, OwnedView, png

GUIDE_TIMEOUT = 600   # seconds the page buttons keep working

# ── /tutorial ─────────────────────────────────────────────────────────

def _recipe(kind, grade):
    """'2 Spirit Grass and 1 Dew Leaf' for a pill recipe."""
    parts = [f"{n} {alchemy.HERBS[grade][t][0]}" for t, n in crafting.KINDS[kind][3]]
    return " and ".join(parts)


def _forge_recipe():
    lines = []
    for i, tier in enumerate(forge.TIERS):
        r = forge.RECIPE[tier]
        lines.append(f"• {tier.title()}: {r['base']} {forge.BASE_MATERIALS['weapon'][i]} / "
                     f"{forge.BASE_MATERIALS['armor'][i]} / {forge.BASE_MATERIALS['artifact'][i]} "
                     f"+ {r['binding']} {forge.BINDINGS[i]}")
    return "\n".join(lines)


def _forge_rarities():
    return " · ".join(f"{need}+ {forge.RARITY_EMOJI[r]} {r}" for need, r in reversed(forge.SCORE_TO_RARITY))


def _batch_ranks():
    """'2 at 2nd Grade, 3 at 4th, 4 at 6th, 5 at 8th' from alchemy.BATCH_BY_RANK."""
    first, out = {}, []
    for rank, n in sorted(alchemy.BATCH_BY_RANK.items()):
        first.setdefault(n, rank)
    for n, rank in sorted(first.items()):
        if n > 1:
            out.append(f"{n} at {_ordinal(rank)} Grade")
    return ", ".join(out)


def _ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


TRY = "👉 Try it now"

# The lessons, grouped in chapters. Each lesson is (title, the Old Master's words, [(field, text)]).
# Every lesson ends with a "Try it now" field naming the command to use next.
CHAPTERS = [
    ("🌱", "First Steps", [
        ("Welcome, Disciple",
         "*The Old Master sets down his tea.* \"Another one who wishes to climb. Good. I will keep it short.\"",
         [("What is this game?", "You are a cultivator. Gather **Qi** to climb the realms, learn **techniques**, fight "
                                 "beasts, brew **pills** and forge **gear**. Every command starts with `/`, or with "
                                 "`m` in chat (`m explore`). **m help** lists them all."),
          ("Begin", "Use **/start**. The Aptitude Stone reveals your **talent**, from " +
                    " → ".join(talent_rules.TALENTS) + ". A higher talent gathers Qi faster."),
          ("You start with", "Mortal realm, 1st layer · the **Iron Fist** and **Horse Stance Guard** techniques · "
                             f"🪷 {rules.STARTING_LOTUS_COINS} Lotus Coins."),
          ("The road ahead", "Mortal → " + " → ".join(rules.REALM_ORDER[1:]) + ".\n"
                             f"Mortal has {rules.max_layer('Mortal')} layers. Every realm after it has "
                             f"{realms.LAYERS_PER_REALM}: Early (1–3), Middle (4–6), Late (7–9) and Peak (10)."),
          (TRY, "**/start**, then press **Next** below.")]),

        ("Know Yourself",
         "\"A cultivator who does not know their own body walks blind.\"",
         [("/profile", "Your **Character Sheet**, with tabs: Profile, Techniques, Equipment, Inventory and Purse. "
                       "Add a member to look at someone else."),
          ("/internal qi", "Your Qi bar, your Qi Rate, how long until the bar is full, and every bonus feeding it."),
          ("/cooldown", "Every timer in one place: when you can explore, train, practice and spar again, your "
                        "daily counts, injuries and boosts."),
          (TRY, "**/profile** and **/internal qi**.")]),
    ]),

    ("☯️", "Qi and Realms", [
        ("Gathering Qi",
         "\"Qi is the root of everything. Fill the bar and the layers open on their own.\"",
         [("Passive Qi", "Qi flows in **by itself**, every minute, even while you are offline. There is nothing to "
                         "collect. A higher talent, blessings, Qi pills and some artifacts make it flow faster."),
          ("/train", f"A short timed challenge with the master. A better score gives more Qi. Every "
                     f"{training.TRAIN_COOLDOWN_MINUTES} minutes."),
          ("Layers", "When the bar is full you move up a layer by yourself. Only the gates below need a "
                     "breakthrough."),
          (TRY, "**/train**.")]),

        ("Breaking Through",
         "\"Between phases and realms stands a wall. Gather your Qi, then strike it.\"",
         [("The gates", "At the 3rd, 6th and 9th layer (end of a phase) and at the 10th layer (end of a realm) "
                        "your bar stops at full. Use **/breakthrough**: it shows your chance first."),
          ("No Qi is lost", "Qi you gather while stuck at a gate is **saved** behind it. After you break through, "
                            "it flows on into your next layers. I mention you once when the bar fills "
                            "(**/settings** turns that off)."),
          ("The odds", f"Phase gate: **{training.PHASE_BOTTLENECK_SUCCESS:.0%}**. New realm: "
                       f"**{training.REALM_BREAKTHROUGH_SUCCESS:.0%}** (Mortal → Martial Apprentice always works). "
                       f"A failure costs {training.BREAKTHROUGH_FAIL_QI_LOSS:.0%} of your bar, and your saved Qi "
                       "tops it back up, so you can try again."),
          ("Higher gates", "Martial Master, Martial King and Martial Saint also need technique mastery, and the "
                           "last two need a slain **Beast King**."),
          (TRY, "**/breakthrough** when your bar is full.")]),
    ]),

    ("⚔️", "Techniques and Fights", [
        ("Techniques",
         "\"Qi without technique is a river without a channel.\"",
         [("/techniques", "Everything you have learned. Equip one **attack** and one **defense** technique (a third, "
                          "free slot opens at Martial Warrior)."),
          ("/practice", f"A challenge that gives one technique mastery EXP. Every "
                        f"{technique.PRACTICE_COOLDOWN_MINUTES} minutes; the first "
                        f"{technique.PRACTICE_DAILY_RATES[0][0]} each day give full EXP."),
          ("/spar", f"A real fight with a master for mastery EXP. Every "
                    f"{technique.SPAR_COOLDOWN_MINUTES // 60} hours. When a technique's bar is full, sparring "
                    "with it is its **mastery trial**."),
          ("Mastery stages", " → ".join(s["name"] for s in technique.MASTERY_STAGES) + ". Each stage makes the "
                             "technique stronger. New manuals drop from chests and beasts."),
          (TRY, "**/techniques**, then **/practice Iron Fist**.")]),

        ("How Fights Work",
         "\"Read your enemy. Then do the one thing it does not expect.\"",
         [("One turn", f"Explore fights, spars and duels are turn-based. Each turn you have "
                       f"{battle.TURN_SECONDS} seconds to pick a move, then both moves happen at once."),
          ("The three moves", "🗡️ **Strike** beats **Break** · 🛡️ **Guard** beats **Strike** · 💥 **Break** "
                              "beats **Guard**."),
          ("Read the warning", "Beasts often show what they plan, like *\"The wolf bares its fangs...\"* (a "
                               "Strike). Pick the move that beats it."),
          ("Techniques and pills", "Your equipped techniques are stronger moves, but rest for a few turns after use. "
                                   f"**Mending pills** heal you mid-fight (up to {battle.PILLS_PER_FIGHT}). "
                                   "**Flee** ends the fight."),
          ("Too slow?", "No pick in time counts as **Guard**. Three in a row and you flee."),
          (TRY, "**/spar** to learn the screen safely.")]),
    ]),

    ("🏔️", "Adventure", [
        ("Into the Wild",
         "\"The mountains hold beasts, bandits, herbs and treasure. Mostly beasts.\"",
         [("/explore", f"A trip of up to {explore.MAX_STEPS} steps. At each step read the clue and pick a path. "
                       "Go deeper for better finds, or turn back with what you have. Every "
                       f"{explore.EXPLORE_COOLDOWN_MINUTES} minutes."),
          ("What you find", "Beasts and bandits, treasure chests, herb patches, ore veins, merchants, hermits, "
                            "Blessed Lands that boost your Qi, and rare beast lairs."),
          ("If you lose", f"You are injured for {explore.DEFEAT_INJURY_HOURS} hour and drop half of what you found. "
                          "**/physician** heals you now for Lotus Coins."),
          (TRY, "**/explore**.")]),

        ("Beasts, Hunts and Duels",
         "\"Know the beast before you meet it. Know your friend before you hit them.\"",
         [("/bestiary", "A realm's beasts and how strong they are against you."),
          ("Lairs and Kings", "An **Elite Lair** or **Beast King Den** found in /explore calls the whole channel to a "
                              "team hunt. Join, and the finder starts the fight. Every winner gets their own chest. "
                              "Beast Kings drop the best chests and are needed for the top realms."),
          ("/duel @player", "A friendly fight against another player. Both fight with the lower player's realm stats, "
                            "so it is fair. Nothing to win or lose; your record shows on your Profile."),
          (TRY, "**/bestiary**.")]),
    ]),

    ("🎒", "Gear and Bag", [
        ("Your Bag and Gear",
         "\"Treasure means nothing if it rots in your bag.\"",
         [("/inventory", "Your bag in tabs: chests, manuals, weapons, armor, artifacts, pills, herbs and materials. "
                         "Pick an item to **open** a chest, **learn** a manual, **equip** gear or **take** a pill."),
          ("/equipment", "Your four gear slots: a **weapon**, **armor** and **two artifacts**, with your stats before "
                         "and after. Artifacts give special effects (more Qi, dodging, healing...). Two artifacts "
                         "of the same family can't be worn together."),
          ("Gear tiers", "Ordinary → Refined → Spirit → Treasure → Divine. Higher tiers are stronger and can hold "
                         "more forged passives (chapter ⚒️)."),
          ("Manuals", "Learning one is instant. A copy of a manual you already know becomes mastery EXP."),
          (TRY, "**/inventory**, then open a chest if you have one.")]),
    ]),

    ("⚗️", "Alchemy", [
        ("Gathering Herbs",
         "*The Old Master lifts the lid of a blackened cauldron.* \"A pill is only as good as its herbs.\"",
         [("/gather", "I name a herb and describe it; pick the matching plant before time runs out. Gather as long "
                      "as you like. **Read carefully:** poisonous look-alikes differ in one detail and cost "
                      f"{alchemy.DECOY_HP_LOSS:.0%} HP."),
          ("Rarity", "Most herbs are Mortal grade. Yellow, Mystic, Earth and Heaven herbs are rarer and rarer; "
                     "higher realms find them more often. Earth and Heaven finds are announced to the channel."),
          ("Herb types", "🌀 Qi herbs → Qi pills · ❤️ Healing → Mending pills · 💧 Purity → every recipe · 🏔️ "
                         "Breakthrough → Breakthrough pills (they also need a 🔮 **Beast Core** from beasts)."),
          ("Age", "Herbs are 🌱 10-year up to 🏵️ 1000-year. Older herbs make better pills, but they try to escape: "
                  "more choices, less time. Pick right many times in a row and your 🔥 **Herbal Insight** finds old "
                  "herbs more often."),
          (TRY, "**/gather** a few herbs.")]),

        ("The Cauldron I · Your First Pill",
         "*He pushes a small cauldron toward you.* \"Follow these steps, one at a time.\"",
         [("Step 1 · Get the herbs", f"Your first pill, the **{alchemy.QI_PILLS['Mortal']['name']}**, needs "
                                     f"{_recipe('qi', 'Mortal')}. Check them in **/inventory** → Herbs."),
          ("Step 2 · Open the cauldron", "Type **/craft** and open the menu **Choose a pill to craft**. Pills marked "
                                         "*Ready* are the ones you have every herb for."),
          ("Step 3 · Read the screen", "It shows the **Recipe**, the **Difficulty**, and ✅ **Will use** or ❌ "
                                       "**Missing**. **Use oldest herbs / Use youngest herbs** picks which herbs go "
                                       "in: old ones make better pills, young ones save your rare herbs."),
          ("Step 4 · Press 🔥 Begin", "The herbs are used now. Every decision has a timer; running out counts as a "
                                     "wrong move."),
          ("Step 5 · Play the stages", "Read the text above the buttons and press the right one (next lesson)."),
          ("Step 6 · Your pill", "You get **1 to 9 patterns** (more is better). The pill goes to **/inventory** → "
                                 "Pills; pick it there to take it. **Craft Again** brews another."),
          (TRY, "**/craft**.")]),

        ("The Cauldron II · What to Press",
         "*He taps the cauldron and it rings like a bell.* \"Read what it tells you, then act.\"",
         [("🔥 Ignite", "Keep the heat in a hidden safe zone.\n"
                       f"• *dull and cold* → **Stoke** (+{crafting.HEAT_STEP}°)\n"
                       f"• *hisses and smokes* → **Fan** (−{crafting.HEAT_STEP}°)\n"
                       "• *soft golden glow* → **Hold**\n"
                       "*Flames lick hungrily* = heat jumps up next. *A cold draught* = it drops."),
          ("🌿 Add the Herbs", "Clues say the order, e.g. *Spirit Grass goes in first and third*. Press the herb that "
                              "goes in next. A wrong herb causes a backlash."),
          ("☯️ Fuse", "Bring **Yin** and **Yang** both to 50 (within 5 is perfect).\n"
                     "• **Cool** Yin +12 · **Ignite** Yang +12\n"
                     "• **Compress** both −10 · **Circulate** pulls them together"),
          ("💊 Condense", f"Press **Wait** while the light grows. At *{crafting.PULSES[4]}* press **Condense**. Too "
                         "early = weaker pill, too late = cracked. Counts double."),
          ("🔒 Seal the Core", f"Breakthrough pills only: the same balance in **{alchemy.SEAL_CORE_MOVES} moves**. "
                              "Miss and the craft fails."),
          ("⚡ Tribulation", "Only for a near-perfect craft. Press the **Shield** that matches where lightning "
                            f"gathers (left, above, right). Block all {crafting.TRIBULATION_STRIKES} for 9 patterns."),
          ("Which stages?", "Mortal pills: Ignite + Condense. Yellow adds Herbs. Mystic and up add Fuse."),
          (TRY, f"Brew a few {alchemy.QI_PILLS['Mortal']['name']}s.")]),

        ("The Cauldron III · Rank and Batches",
         "\"Every pill teaches the hand. Even the ones that explode.\"",
         [("Patterns 丹纹", f"More patterns = a stronger pill with less toxicity. Below {alchemy.EXPLODE_BELOW:.0%} "
                          "the cauldron explodes. Herb age caps it: 10-year herbs reach 5 patterns, 1000-year 9."),
          ("Alchemist rank", "Every craft gives alchemy EXP. New ranks unlock harder pills. Being above a pill's rank "
                             "gives more time, wider zones and hints."),
          ("Batch crafting", f"Craft several pills in one go: {_batch_ranks()}. Pick the batch size under the recipe. "
                             "Each extra pill makes the game a little harder, and an explosion loses every herb."),
          ("Watch out", "From Mystic pills on, some hints lie. Trust the heat number you just moved."),
          ("Tips", "• Brew cheap Mortal pills first to raise your rank.\n"
                   "• Save 100-year and older herbs for pills that matter.\n"
                   "• **/index** → Pills lists every recipe."),
          (TRY, "**/index pills**.")]),
    ]),

    ("⚒️", "Forging", [
        ("The Forge I · Materials",
         "*Sparks leap from the anvil.* \"A blade remembers every blow. First, find metal.\"",
         [("What forging does", "It puts a **passive** (a hidden power like *Lifesteal* or *+3% Attack*) into a free "
                                "slot of a weapon, armor or artifact. Ordinary, Refined and Spirit gear have 1 slot; "
                                "Treasure and Divine have 2."),
          ("Every forge needs", "A base material and a binding of **the same tier as the gear** "
                                "(weapon / armor / artifact base + binding):\n" + _forge_recipe()),
          ("Where to find them", "⛏️ Ore Veins in /explore · 🐾 beasts · 📦 chests · 🌿 /gather · and essences "
                                 "from /craft, /practice and /train. The tier follows your realm."),
          ("Optional extras", "**Essence** picks the passive's family · **Fuel** widens the Ignite zone · "
                              "**Quench liquid** widens the Quench window."),
          (TRY, "**/inventory** → Materials.")]),

        ("The Forge II · At the Anvil",
         "\"Choose your gear, choose your aim, then strike.\"",
         [("Step 1 · Open the forge", "Type **/forge** and open **Choose gear to forge**."),
          ("Step 2 · Choose what to do", "• ✨ **Enchant**: fill an empty slot (materials only).\n"
                                        "• 🎲 **Reroll**: forge every slot again (materials + Lotus Coins).\n"
                                        "• 🔒 **Replace**: Treasure and Divine only. Lock one slot with a 🔏 Seal "
                                        "Stone and forge the other."),
          ("Step 3 · Extras (optional)", "Pick an **Essence**, **Fuel** or **Quench liquid**, or leave them on *None*."),
          ("Step 4 · Read the plan", "✅ **Will use**, ❌ **Missing** and **Best possible** (the rarest passive "
                                     "this forge can give)."),
          ("Step 5 · Press 🔥 Begin", "Materials are taken now. Five timed stages follow (next lesson)."),
          (TRY, "**/forge** on your weapon.")]),

        ("The Forge III · The Five Stages",
         "*He hands you the hammer.* \"Each stage is worth 20 points.\"",
         [("🔥 Ignite", "Keep the heat in the safe zone.\n"
                       f"• *dull and sleepy* → **Pump** (+{forge.IGNITE['pump']}°)\n"
                       f"• *sparks roar out* → **Vent** ({forge.IGNITE['vent']}°)\n"
                       "• *clean orange fire* → **Hold**"),
          ("🌡️ Heat", "Press **Keep heating** until the metal glows the colour the text names, then **Pull it "
                     "out**. Past white, it burns."),
          ("🔨 Hammer", "*rings true* → **Strike Hard** · *dull thud* → **Strike Light** · *glow is fading* → "
                       "**Reheat**"),
          ("💧 Quench", "Choose **Water** (narrow window, up to 20) or **Oil** (wide window, up to 15). **Wait** cools "
                       "a lot, **Wait a breath** a little. **Plunge** near the target temperature."),
          ("✨ Inscribe", "Press the rune's strokes in the order shown, e.g. *Hook → Dot → Sweep*."),
          ("Harder gear", "Higher tiers give less time and more steps. From Spirit gear on, some hints lie; the heat "
                          "number never does."),
          (TRY, "Forge an Ordinary piece first.")]),

        ("The Forge IV · Results and Rank",
         "\"A poor forge costs you metal. It never costs you the blade.\"",
         [("Score → passive", f"The five stages add up to 100. Below **{forge.FAIL_BELOW}** the forge fails. Higher "
                              "scores give rarer passives:\n" + _forge_rarities()),
          ("The caps", "Gear caps the rarity (Ordinary: Rare · Refined and Spirit: Epic · Treasure: Legendary · "
                       "Divine: Mythical), and so does the essence. Epic and up need a good **Inscribe**."),
          ("If it fails", "The materials are lost. Your gear and its passives are safe."),
          ("Blacksmith rank", "Every forge gives EXP, even a failed one. Higher tiers need a higher rank."),
          ("Tips", "• Pick **Oil** when unsure.\n• **/equipment** shows each passive.\n"
                   "• **/index** → Passives lists them all."),
          (TRY, "**/equipment** to see your new passive.")]),
    ]),

    ("🪷", "Wealth and Friends", [
        ("Coin and Pearl",
         "\"Even immortals pay for their tea.\"",
         [("🪷 Lotus Coins", "Earned from beasts, chests, bandits and quests. Spent at merchants, on **/physician**, "
                            f"on forging, and on **/reroll**: a new talent for a flat 🪷 "
                            f"{talent_rules.FATE_REROLL['cost']:,} (it can go lower!)."),
          ("🌙 Moon Pearls", "Earned from daily quests. Spent in **/shop** (a Heavenly Fate Reroll that never goes "
                            f"lower for 🌙 {economy.PEARL_SHOP['heavenly_fate_reroll']}, Qi pills, bag space, Seal "
                            "Stones, a new name) and on **/blessing**, 30-day boosts. **/balance** shows your purse."),
          ("/daily", f"{quests.QUESTS_PER_DAY} quests, new every day at midnight UTC. Each pays coins and pearls; "
                     "finish them all for a bonus and a chance of a chest."),
          (TRY, "**/daily**.")]),

        ("Other Cultivators",
         "\"The Jianghu is never empty.\"",
         [("/trade @player", "Swap items, Lotus Coins and Moon Pearls. Review the Trade Preview; it happens once "
                             "both confirm. No tax."),
          ("/leaderboard", "The top ten by Realm, Lotus Coins or Moon Pearls, and your own rank."),
          ("Rare finds", "Divine gear, Heaven manuals, rare herbs and the Heaven-Defying Pill are announced to the "
                         "whole server."),
          (TRY, "**/leaderboard**.")]),

        ("Walk Alone",
         "*The Old Master stands and brushes off his robe.* \"The rest, you must walk alone.\"",
         [("A good day", "1. **/daily** to see today's quests\n2. **/train** and **/explore**\n"
                         "3. Open chests in **/inventory**\n4. **/practice** and **/spar**\n"
                         "5. **/gather** and **/craft** between cooldowns\n6. **/forge** better gear\n"
                         "7. **/breakthrough** when the bar is full"),
          ("Lost?", "**/index** lists every beast, technique, item, pill, herb and passive. **/cooldown** shows "
                    "what you can do now. **/tutorial** brings these lessons back."),
          (TRY, "**/index**.")]),
    ]),
]

LESSONS = [lesson for _, _, lessons in CHAPTERS for lesson in lessons]
CHAPTER_OF = [(emoji, name) for emoji, name, lessons in CHAPTERS for _ in lessons]

SCROLL_NUMBERS = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二", "十三", "十四", "十五",
                  "十六", "十七", "十八", "十九", "二十", "二十一", "二十二", "二十三", "二十四", "二十五"]


def lesson_embed(i):
    title, words, fields = LESSONS[i]
    emoji, chapter = CHAPTER_OF[i]
    e = discord.Embed(title=f"{emoji} {title}", description=words, color=COLOR)
    for name, value in fields:
        e.add_field(name=name, value=value, inline=False)
    e.set_author(name=f"The Old Master's Lessons · 卷{SCROLL_NUMBERS[i]}")
    e.set_footer(text=f"Lesson {i + 1} of {len(LESSONS)} · {chapter} · use the menu to jump to any lesson")
    return e


class TutorialView(OwnedView):
    def __init__(self, owner_id, page=0):
        super().__init__(owner_id, timeout=GUIDE_TIMEOUT)
        self.page = page
        self.prev = self.button("Back", self.go_prev, emoji="◀️")
        self.next = self.button("Next", self.go_next, emoji="▶️", style=discord.ButtonStyle.primary)
        select = discord.ui.Select(placeholder="Jump to a lesson", row=1, options=[
            discord.SelectOption(label=f"{n + 1}. {t[0]}", value=str(n), emoji=CHAPTER_OF[n][0],
                                 description=CHAPTER_OF[n][1]) for n, t in enumerate(LESSONS)])
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
# The pages are built in bot/compendium.py and drawn by cards/compendium.py: one image card per
# section + tier, with the same page as text under it.

pct = compendium.pct                            # kept here for older imports
beast_multipliers = compendium.beast_multipliers


def page_embed(data):
    """The text version under the card (Discord shows text at full size, the card at about half)."""
    e = discord.Embed(description=compendium.text_version(data)[:4000], color=COLOR)
    e.set_author(name="The Jianghu Compendium · 万物录")
    return e


class IndexView(OwnedView):
    """Row 1: section menu · row 2: tier menu (Overview first) · row 3: Back / Next when a tier has
    more items than fit on one card."""

    def __init__(self, owner_id, section="beasts", tier=compendium.OVERVIEW, page=0, found=None):
        super().__init__(owner_id, timeout=GUIDE_TIMEOUT)
        self.section, self.tier, self.page, self.found = section, tier, page, found
        self.pages = 1

    def page_data(self):
        data = compendium.tier_page(self.section, self.tier, self.page, self.found)
        self.page, self.pages = data["page"] - 1, data["pages"]
        return data

    async def render(self):
        """(file, embed) for the current page; rebuilds the menus to match."""
        data = self.page_data()
        self.build()
        image = await card_render.render(render_compendium, data)
        return png(image, "compendium.png"), page_embed(data)

    def build(self):
        self.clear_items()
        sections = discord.ui.Select(placeholder="Choose a section", row=0, options=[
            discord.SelectOption(label=label, value=key, emoji=emoji, description=desc, default=key == self.section)
            for key, (label, emoji, desc, *_) in compendium.SECTIONS.items()])
        sections.callback = self.pick_section
        self.add_item(sections)
        overview = compendium.SECTIONS[self.section][5]()
        options = [discord.SelectOption(label="Overview", value=compendium.OVERVIEW, emoji="📖",
                                        description=overview["subtitle"][:100],
                                        default=self.tier == compendium.OVERVIEW)]
        for key, seal, label, _ in compendium.tiers(self.section):
            data = compendium.build(self.section, key)
            options.append(discord.SelectOption(
                label=data.get("tier_label", label)[:100], value=key,
                description=data["subtitle"][:100], default=key == self.tier))
        tiers = discord.ui.Select(placeholder="Choose a tier", row=1, options=options[:25])
        tiers.callback = self.pick_tier
        self.add_item(tiers)
        if self.pages > 1:
            self.button("Back", self.go_prev, emoji="◀️", row=2, disabled=self.page == 0)
            self.button(f"Page {self.page + 1} of {self.pages}", self.go_prev, row=2, disabled=True)
            self.button("Next", self.go_next, emoji="▶️", style=discord.ButtonStyle.primary, row=2,
                        disabled=self.page >= self.pages - 1)

    async def show(self, interaction):
        await interaction.response.defer()
        file, embed = await self.render()
        await interaction.edit_original_response(embed=embed, attachments=[file], view=self)

    async def pick_section(self, interaction):
        self.section, self.tier, self.page, self.found = interaction.data["values"][0], compendium.OVERVIEW, 0, None
        await self.show(interaction)

    async def pick_tier(self, interaction):
        self.tier, self.page, self.found = interaction.data["values"][0], 0, None
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

    async def search_autocomplete(interaction: discord.Interaction, current: str):
        return [app_commands.Choice(name=n[:100], value=n[:100]) for n in compendium.search_names(current)]

    @bot.tree.command(name="index", description="The Jianghu Compendium: every beast, technique, weapon, armor, artifact, chest, pill and herb")
    @app_commands.describe(section="Which section to open first", realm="For beasts: which realm",
                           search="Jump straight to an item by name, e.g. Qilin or Mythic Chest")
    @app_commands.choices(
        section=[app_commands.Choice(name=v[0], value=k) for k, v in compendium.SECTIONS.items()],
        realm=[app_commands.Choice(name=r, value=r) for r in rules.REALM_ORDER])
    @app_commands.autocomplete(search=search_autocomplete)
    async def index(interaction: discord.Interaction, section: app_commands.Choice[str] | None = None,
                    realm: app_commands.Choice[str] | None = None, search: str | None = None):
        key = section.value if section else "beasts"
        tier, page, found = compendium.OVERVIEW, 0, None
        if realm and key == "beasts":
            tier = realm.value
        if search:
            hit = compendium.search(search)
            if hit is None:
                await interaction.response.send_message(
                    f"Nothing in the Compendium is called **{search[:80]}**. Try part of the name.", ephemeral=True)
                return
            key, tier, page, found = hit
        await interaction.response.defer()
        view = IndexView(interaction.user.id, key, tier, page, found)
        file, embed = await view.render()
        view.message = await interaction.followup.send(embed=embed, file=file, view=view, wait=True)
