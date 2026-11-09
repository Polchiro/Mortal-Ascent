"""
/tutorial and /index: the Old Master's lessons (paged with buttons) and the Jianghu Compendium,
an index of every beast, technique manual, weapon, armor piece, artifact, chest, pill and herb in the game.

Everything in the index is read from the game data modules (beasts.py, technique.py,
equipments.py, explore.py, training.py, alchemy.py, bot/loot.py), so it stays in step when they change.
The /index pages are built in bot/compendium.py and drawn as image cards by cards/compendium.py.
"""
import alchemy
import discord

import explore
import forge
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
      ("/internal qi", "Your dantian: the Qi bar, Qi waiting behind a bottleneck, your Qi Rate, how long until the "
                       "bar fills, and every bonus that feeds it."),
      ("/balance", "Your purse: 🪷 Lotus Coins (earned by playing) and 🌙 Moon Pearls (the rare currency).")]),

    ("Gathering Qi",
     "\"Qi is the root of everything. Fill your dantian and the layers open on their own.\"",
     [("/train", "A timed challenge with the master. Your score becomes Internal Qi. Every 60 minutes."),
      ("Passive Qi", "Qi also gathers by itself at your full Qi Rate, for as long as you are away. There is "
                     "nothing to collect: it is added to your bar every minute. **/internal qi** shows how fast it flows."),
      ("/seclusion", f"Shut yourself away for {training.SECLUSION_MIN_HOURS}–{training.SECLUSION_MAX_HOURS} hours at "
                     f"×{training.SECLUSION_QI_MULTIPLIER:g} Qi Rate. No exploring or sparring meanwhile, and leaving "
                     "early loses the bonus.")]),

    ("The Gates Within",
     "\"Layers inside a phase open by themselves. Between phases and realms stands a wall.\"",
     [("Bottlenecks", "When your Qi bar is full at the end of a phase (3rd, 6th, 9th layer) or at the 10th "
                      "layer, the bar stops, but no Qi is lost: the extra waits behind the gate and flows into "
                      "your next layers when you break through. Use **/breakthrough** and the bot shows the chance "
                      "first. I mention you once when your bar fills; **/settings** turns that off."),
      ("The odds", f"Phase bottleneck: {training.PHASE_BOTTLENECK_SUCCESS:.0%}. New realm: "
                   f"{training.REALM_BREAKTHROUGH_SUCCESS:.0%} (Mortal → Martial Apprentice always succeeds). "
                   f"A failure costs {training.BREAKTHROUGH_FAIL_QI_LOSS:.0%} of your bar; the Qi waiting behind the gate refills it, so you can try again."),
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
      ("What waits", "Wild beasts, treasure chests, herb patches (1–3 herbs of any grade), merchants, stone tablets, hermits, "
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
      ("Why hunt Kings", "Legendary and Mythic Chests, and a Beast King kill is needed to reach Martial King and Martial Saint."),
      ("/duel @player", "A friendly duel on the fight screen. Both fight at the lower player's realm and layer and "
                        "pick moves in secret each turn. Nothing to win or lose; wins and losses show on your Profile.")]),

    ("Spoils of the Road",
     "\"Treasure means nothing if it rots in your bag.\"",
     [("/inventory", "Your bag in tabs: chests, manuals, weapons, armor, artifacts, pills, herbs and materials. "
                     "Pick an item to **open** a chest, **learn** a manual, **equip** gear or **take** a pill."),
      ("/daily", "Four daily quests, new every day at midnight UTC. Each pays Lotus Coins and Moon Pearls; "
                 "finish all four for a bonus and a chance of a Common to Legendary Chest."),
      ("/trade @player", "Swap items, Lotus Coins and Moon Pearls with another player. Add items by category and "
                         "grade, review the Trade Preview, and it happens once both confirm. No tax."),
      ("/equipment", "Your four gear slots (weapon, armor, two artifacts), your stats before and after them, and "
                     "what your artifacts do. Swap or remove gear here. Two artifacts of one family can't be worn together."),
      ("Manuals", "Learning one is instant and equips it. A copy of a manual you already know becomes mastery EXP.")]),

    ("Herbs and the Cauldron",
     "*The Old Master lifts the lid of a blackened cauldron.*\n"
     "\"A pill is only as good as the herbs in it, and the herbs are only as good as the eyes that picked them.\"",
     [("/gather", "Gather herbs as long as you like. I name a herb and describe it; pick the plant that matches "
                  "before time runs out. **Read carefully:** poisonous look-alikes differ in one detail and cost you "
                  f"{alchemy.DECOY_HP_LOSS:.0%} HP."),
      ("Tiers and types", "Any grade can grow anywhere: most herbs are Mortal, rarer ones Yellow, Mystic, Earth "
                          "and (very rarely) Heaven. Higher realms are luckier. 🌀 Qi herbs make Qi pills, "
                          "❤️ Healing herbs make Mending pills, 💧 Purity herbs go into every recipe, and 🏔️ "
                          "Breakthrough herbs make Breakthrough pills."),
      ("Old herbs", "Every herb has an age, from 🌱 10-year to 🏵️ 1000-year. Older herbs make better pills, but "
                    "100-year and older ones try to escape: more choices, less time. Pick right many times in a row "
                    "and your 🔥 **Herbal Insight** finds old herbs more often."),
      ("Your herb bag", "Herbs stack by kind and age in the **Herbs** tab of **/inventory**. Herb Patches in /explore "
                        "and merchants give herbs too. The merchant never buys them back. Beasts sometimes drop a "
                        "🔮 **Beast Core** (Materials tab), needed for Breakthrough pills."),
      ("Pills", "Qi pills speed up your Qi, Qi Burst pills give Qi at once, Mending pills shorten injuries, "
                "Cleansing pills clear toxicity and Breakthrough pills help at a realm gate. **/index** → Pills "
                "lists every recipe.")]),

    ("The Cauldron I · Your First Pill",
     "*The Old Master pushes a small cauldron toward you.*\n"
     "\"Do not be afraid of it. Follow these steps, one at a time, and your first pill will be born.\"",
     [("Step 1 · Get the herbs", f"Use **/gather** to pick herbs. Your first pill, the **{alchemy.QI_PILLS['Mortal']['name']}**, "
                                 f"needs {_recipe('qi', 'Mortal')}. Check them in **/inventory** → Herbs."),
      ("Step 2 · Open the cauldron", "Type **/craft**. Open the menu **Choose a pill to craft**. Pills marked "
                                     "*Ready* are the ones you have every herb for. New pills appear as your "
                                     "alchemist rank grows."),
      ("Step 3 · Read the recipe", "The screen shows the **Recipe**, the **Difficulty** (stages and seconds per "
                                   "decision) and either ✅ **Will use** or ❌ **Missing**. The button **Use oldest "
                                   "herbs / Use youngest herbs** picks which herbs go in: older herbs make better "
                                   "pills, younger ones save your rare herbs."),
      ("Step 4 · Press 🔥 Begin", "The herbs are used up now, so be ready. From here every decision has a timer "
                                 "(shown at the bottom). If time runs out it counts as a wrong move."),
      ("Step 5 · Play the stages", "Read the text above the buttons and press the right one. The next lesson "
                                   "explains every stage and which button to press."),
      ("Step 6 · Your pill", "The result shows your **patterns** (1 to 9, more is better). The pill goes to "
                             "**/inventory** → Pills; pick it there to **take** it. Press **Craft Again** for another "
                             "or **Close**.")]),

    ("The Cauldron II · What to Press",
     "*The Old Master taps the cauldron and it rings like a bell.*\n"
     "\"Fire, order, balance, timing. Read what the cauldron tells you, then act.\"",
     [("🔥 Ignite the Cauldron", f"Keep the heat inside a hidden safe zone for every round.\n"
                                f"• *The herbs lie dull and cold* → **Stoke** (+{crafting.HEAT_STEP}°)\n"
                                f"• *The cauldron hisses and smokes* → **Fan** (−{crafting.HEAT_STEP}°)\n"
                                "• *A soft golden glow* → **Hold**\n"
                                "Watch the last line: *flames lick hungrily* means the heat is about to jump up "
                                "(Fan or Hold), *a cold draught* means it will drop (Stoke)."),
      ("🌿 Add the Herbs", "The clues say where each herb goes, e.g. *The Spirit Grass wants to go in first and "
                          "third*. The question asks which herb goes in next: press that herb's button. A wrong "
                          "herb causes a backlash."),
      ("☯️ Fuse the Essences", "Bring **Yin** and **Yang** both to 50 (within 5 is perfect).\n"
                             "• **Cool**: Yin +12 · **Ignite**: Yang +12\n"
                             "• **Compress**: both −10 · **Circulate**: pulls them toward each other\n"
                             "Both too high? Compress. One too low? Raise it. Far apart? Circulate."),
      ("💊 Condense the Pill", f"Press **Wait** while the light grows. When it says *{crafting.PULSES[4]}*, press "
                              "**Condense**. Earlier gives a weaker pill; waiting past it cracks the pill. This "
                              "stage counts double."),
      ("🔒 Seal the Core", "Breakthrough pills only. The same Yin and Yang balance, but in just "
                          f"**{alchemy.SEAL_CORE_MOVES} moves**. Miss and the Beast Core shatters and the craft fails."),
      ("⚡ Pill Tribulation", "Only for a nearly perfect craft. Lightning gathers from the left, above or the right: "
                             "press the matching **Shield** button each time. Block all "
                             f"{crafting.TRIBULATION_STRIKES} for a 9-pattern pill."),
      ("Which stages you get", "Mortal pills: Ignite and Condense. Yellow adds the Herbs. Mystic and higher add "
                               "Fuse. Breakthrough pills are one level harder and add Seal the Core.")]),

    ("The Cauldron III · Patterns and Rank",
     "\"Every pill teaches the hand. Even the ones that explode.\"",
     [("Pill patterns 丹纹", f"Your score becomes **1 to 9 patterns**. More patterns make a stronger pill with less "
                            f"toxicity. Below {alchemy.EXPLODE_BELOW:.0%} the cauldron explodes. Herb age sets the "
                            "highest you can reach: 10-year herbs up to 5 patterns, 1000-year herbs up to 9."),
      ("Alchemist rank", "Every craft gives alchemy EXP (an explosion gives a little). Each new rank unlocks "
                         "harder pills. Being above a pill's rank gives more time, a wider safe zone, herb hints "
                         "and, at 2 ranks above, one forgiven mistake."),
      ("Batch crafting", "From 2nd Grade you can refine several pills at once (up to "
                         f"{max(alchemy.BATCH_BY_RANK.values())} at 8th Grade): pick the batch size under the "
                         "recipe. One minigame for all of them, but each extra pill means less time and narrower "
                         "safe zones, and an explosion loses every herb."),
      ("Hints that lie", "From Mystic pills on, some hints can be false. If the heat number and the text disagree, "
                         "trust the number you know you just moved."),
      ("Tips for beginners", "• Craft many cheap Mortal pills first to raise your rank.\n"
                             "• Keep your 100-year and older herbs for pills that matter.\n"
                             "• Every craft leaves 丹 **Cauldron Ash**, an essence used at the forge.\n"
                             "• **/index** → Pills lists every recipe and what it does.")]),

    ("The Forge I · Materials",
     "*Sparks leap from the anvil. The Old Master does not flinch.*\n"
     "\"A blade remembers every blow. But first you need metal to strike.\"",
     [("What forging does", "Forging puts a **passive** (a hidden power, like *Lifesteal* or *+3% Attack*) into a "
                            "free slot of your weapon, armor or artifact. Ordinary, Refined and Spirit gear have 1 "
                            "slot; Treasure and Divine gear have 2."),
      ("What every forge needs", "Base material (weapon / armor / artifact) and a binding, **the same tier as the gear**:\n" + _forge_recipe()),
      ("Where materials drop", "⛏️ **Ore Veins** in /explore: weapon metal and fuel · 🐾 **Beasts**: bindings and "
                               "armor materials · 📦 **Chests**: artifact jade and Seal Stones · 🌿 **/gather**: "
                               "quench liquids · ⚗️ **/craft**, 📜 **/practice**, 🏋️ **/train**: essences. The "
                               "tier follows your realm."),
      ("Optional extras", "• **Essence**: chooses the passive's family. Shard reaches Uncommon, Crystal Epic, "
                          "Heart Mythical.\n• **Fuel**: widens the Ignite safe zone.\n• **Quench liquid**: widens "
                          "the Quench window."),
      ("Check your pouch", "**/inventory** → Materials shows everything you have. Materials don't use bag slots.")]),

    ("The Forge II · At the Anvil",
     "\"Choose your gear, choose your aim, then strike. In that order.\"",
     [("Step 1 · Open the forge", "Type **/forge**. Open the menu **Choose gear to forge**: it lists your weapons, "
                                  "armor and artifacts and the passives they already have."),
      ("Step 2 · Choose what to do", "• ✨ **Enchant**: fill an empty slot (materials only).\n"
                                    "• 🎲 **Reroll**: forge every slot again. The old passives are replaced "
                                    "(materials + Lotus Coins).\n"
                                    "• 🔒 **Replace**: Treasure and Divine gear only. Lock one slot with a 🔏 Seal "
                                    "Stone and forge the other."),
      ("Step 3 · Add extras (optional)", "Use the menus **Essence**, **Fuel** and **Quench liquid** if you have them. "
                                         "Leave them on *None* to forge without."),
      ("Step 4 · Read the plan", "✅ **Will use** lists what the forge takes. ❌ **Missing** tells you what you still "
                                 "need (materials, coins or blacksmith rank). **Best possible** is the highest "
                                 "rarity this forge can give."),
      ("Step 5 · Press 🔥 Begin", "The materials and coins are taken now. Then five stages follow, each with a "
                                 "timer per decision. The next lesson explains each one.")]),

    ("The Forge III · The Five Stages",
     "*The Old Master hands you the hammer.*\n"
     "\"Each stage is worth 20 points. Read, then strike.\"",
     [("🔥 Ignite the Forge", f"Keep the heat in the hidden safe zone.\n"
                             f"• *The coals glow dull and sleepy* → **Pump** (+{forge.IGNITE['pump']}°)\n"
                             f"• *Sparks roar out of the forge mouth* → **Vent** ({forge.IGNITE['vent']}°)\n"
                             "• *A clean orange fire hums* → **Hold**\n"
                             "*The wind gusts* means a jump up is coming, *a cold draught* a drop."),
      ("🌡️ Heat the Metal", "The text names the colour the gear needs (Ordinary: cherry red). Press **Keep heating** "
                           "until the metal glows that colour, then **Pull it out**. One colour off gives half; "
                           "heating past white burns it."),
      ("🔨 Hammer", "Read each strike's hint:\n• *rings true* → **Strike Hard**\n• *a dull thud* → "
                   "**Strike Light**\n• *cooling, the glow is fading* → **Reheat**"),
      ("💧 Quench", "First choose **Water** (narrow window, up to 20 points) or **Oil** (wide window, up to 15). "
                   "The text shows the target temperature. **Wait** cools the blade a lot, **Wait a breath** a "
                   "little. Press **Plunge** when the blade is close to the target. Too cold and you miss."),
      ("✨ Inscribe", "The rune's strokes are listed in order, e.g. *Hook → Dot → Sweep*. Press them one by one, "
                     "in that order."),
      ("Harder gear", "Higher tiers give less time and more strikes and strokes. From Spirit gear on, some "
                      "hints can lie. In Ignite, the heat number never lies: trust it over the text.")]),

    ("The Forge IV · Results and Rank",
     "\"A poor forge costs you metal. It never costs you the blade.\"",
     [("Score → passive", f"Your five stages add up to 100. Below **{forge.FAIL_BELOW}** the forge fails. Above "
                          "it, a higher score gives a rarer passive:\n" + _forge_rarities()),
      ("The caps", "The rarity can't go above the gear's cap (Ordinary: Rare · Refined and Spirit: Epic · "
                   "Treasure: Legendary · Divine: Mythical) or the essence's grade. Epic and above also need a "
                   "good **Inscribe**."),
      ("If it fails", "All the materials used are lost, extras included. Your gear and its passives are safe."),
      ("Blacksmith rank", "Every forge gives blacksmith EXP, even a failed one. Higher gear tiers need a higher "
                          "rank. Being above the needed rank gives more time and wider zones."),
      ("See your passive", "**/equipment** shows each slot's passive. Passives work in fights, duels (at half "
                           "strength) and everyday actions."),
      ("Tips for beginners", "• Start with Ordinary gear: 6 seconds per decision and honest hints.\n"
                             "• Pick **Oil** when unsure: fewer points, but much safer.\n"
                             "• **/index** → Passives lists every passive and its family.")]),

    ("Coin and Pearl",
     "\"Even immortals pay for their tea.\"",
     [("🪷 Lotus Coins", "Earned from chests, beasts and bandits. Spent at merchants, on **/physician**, "
                        "and on **/reroll** to reroll your talent (it can go lower!)."),
      ("🌙 Moon Pearls", "Spent in **/shop** (Qi pills, a Heavenly Fate Reroll that never goes lower, bag space, "
                        "a new name) and on **/blessing**, 30-day boosts to Qi, coins and more. "
                        "**/recharge** lists the pearl packages."),
      ("Rare finds", "Divine weapons, armor and artifacts, Heaven manuals and the Heaven-Defying Pill are announced "
                     "to the whole server.")]),

    ("Walk Alone",
     "*The Old Master stands and brushes off his robe.*\n"
     "\"You have taken your first step on the martial path. The rest, you must walk alone.\"",
     [("A good day's path", "**/train** → **/explore** → open chests in **/inventory** → **/practice** "
                            "→ **/spar** → **/gather** herbs and **/craft** pills, **/forge** your gear between cooldowns → "
                            "**/breakthrough** when the bar is full. Check **/internal qi** to see how far you are."),
      ("Lost?", "**/index** lists every beast, technique, weapon, armor, artifact, chest, pill and herb in the world. "
                "**/tutorial** brings back these lessons any time.")]),
]

SCROLL_NUMBERS = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "十一", "十二", "十三", "十四", "十五",
                  "十六", "十七", "十八", "十九", "二十"]


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
