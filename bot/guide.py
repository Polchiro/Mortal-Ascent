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
import technique
import training
import talent as talent_rules

from cards.compendium import render_compendium

from . import compendium
from . import player as rules
from . import render as card_render
from .views import COLOR, OwnedView, png

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
      ("What waits", "Wild beasts, treasure chests, herb patches (1–3 herbs of your tier), merchants, stone tablets, hermits, "
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
      ("Why hunt Kings", "Jade Chests, and a Beast King kill is needed to reach Martial King and Martial Saint."),
      ("/duel @player", "A friendly duel on the fight screen. Both fight at the lower player's realm and layer and "
                        "pick moves in secret each turn. Nothing to win or lose; wins and losses show on your Profile.")]),

    ("Spoils of the Road",
     "\"Treasure means nothing if it rots in your bag.\"",
     [("/inventory", "Your bag in tabs: chests, manuals, weapons, armor, artifacts, pills, herbs and materials. "
                     "Pick an item to **open** a chest, **learn** a manual, **equip** gear or **take** a pill."),
      ("/equipment", "Your four gear slots (weapon, armor, two artifacts), your stats before and after them, and "
                     "what your artifacts do. Swap or remove gear here. Two artifacts of one family can't be worn together."),
      ("Manuals", "Learning one is instant and equips it. A copy of a manual you already know becomes mastery EXP.")]),

    ("Herbs and the Cauldron",
     "*The Old Master lifts the lid of a blackened cauldron.*\n"
     "\"A pill is only as good as the herbs in it, and the herbs are only as good as the eyes that picked them.\"",
     [("/gather", "Gather herbs as long as you like. I name a herb and describe it; pick the plant that matches "
                  "before time runs out. **Read carefully:** poisonous look-alikes differ in one detail and cost you "
                  f"{alchemy.DECOY_HP_LOSS:.0%} HP."),
      ("Tiers and types", "You find herbs of your own realm's tier (凡 黄 玄 地 天). 🌀 Qi herbs make Qi pills, "
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

    ("The Cauldron",
     "*The Old Master taps the cauldron and it rings like a bell.*\n"
     "\"Fire, order, balance, timing. Fail any of them and the cauldron will tell the whole mountain.\"",
     [("/craft", "Pick a pill whose herbs you have, then refine it. Every decision has a timer. No cooldown: "
                 "your herbs are the limit, and they are used up when you begin."),
      ("The stages", "🔥 **Ignite**: Stoke, Fan or Hold to keep the heat in a hidden safe zone; the hints say if it "
                     "is cold or hot and warn of spikes.\n🌿 **Add the Herbs**: follow the clues for the order. A "
                     "wrong herb causes a backlash.\n☯️ **Fuse**: bring Yin and Yang to 50.\n💊 **Condense**: press "
                     "at *the light trembles*. Too early is weak, too late it cracks.\n🔒 **Seal the Core**: "
                     "Breakthrough pills only. Fail and the Beast Core shatters."),
      ("Pill patterns 丹纹", "Your score becomes **1 to 9 patterns**. More patterns make a stronger pill with "
                            "less toxicity. Below 40% the cauldron explodes. Older herbs raise the cap (10-year "
                            "herbs reach 5 patterns, 1000-year herbs 9), and a 9-pattern pill must survive the "
                            "⚡ **Pill Tribulation**."),
      ("Harder pills", "Mortal pills are 🟢 Normal (2 stages); Heaven pills are 💀 Super Hard (4 stages, 3 "
                       "seconds a decision, misleading hints, wild herbs). Breakthrough pills are one level harder."),
      ("Alchemist rank", "You start as a 1st Grade Alchemist. Every craft gives alchemy EXP (an explosion gives a "
                         "little). New ranks unlock higher grades; being above a recipe's rank makes it easier, "
                         "but easy pills give less EXP.")]),

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
                            "→ **/spar** → **/gather** herbs and **/craft** pills between cooldowns → **/breakthrough** when the bar is "
                            "full. Check **/internal qi** to see how far you are."),
      ("Lost?", "**/index** lists every beast, technique, weapon, armor, artifact, chest, pill and herb in the world. "
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
                label=f"{seal} {data.get('tier_label', label)}"[:100], value=key,
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
                           search="Jump straight to an item by name, e.g. Qilin or Jade Chest")
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
