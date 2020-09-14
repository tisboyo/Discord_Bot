# -*- coding: utf-8 -*-
"""
Discord Bot for HardwareFlare and others
@author: Tisboyo
"""

import logging
import random
import string
import re
import datetime
import asyncio

# import sqlite3

import discord
from discord.ext import commands

from util.database import Database
from util.permissions import Permissions
from util.utils import Utils

logger = logging.getLogger(__name__)


class FunStuff(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.name = "funstuff"

        # Used for cooldown tracking
        self.last_run = dict()

        Database.Cogs[self.name] = dict()

        Database.readSettings(self)

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        # Have to reload Database.Cogs when joining a new guild to prevent errors.
        Database.readSettings(self)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        # No point in holding stuff in memory for a guild we aren't in.
        if Database.Cogs[self.name].get(guild.id, False):
            Database.writeSettings(self, guild.id)
            del Database.Cogs[self.name][guild.id]

    @commands.Cog.listener()
    async def on_message(self, message):
        # Guard Clause
        if message.guild == None:  # Not in a guild means DM or Group chat.
            return

        # Strip punctuation, and force to lower case
        msg_no_lower: str = re.sub("[" + string.punctuation + "]", "", message.content)
        msg: str = msg_no_lower.lower()

        # Establish a wait time between sending the same message
        wait_time = datetime.timedelta(minutes=5)

        if ("snow" in msg) and (message.guild.id == 425699298957852672 or message.guild.id == 378302095633154050):
            # 425699298957852672 - HardwareFlare
            # 378302095633154050 - MyServer
            # 220348421259657218 - Runeadair

            if self.last_run.get("snow", datetime.datetime.min) + wait_time <= datetime.datetime.now():
                phrases = [
                    "<@220348421259657218> https://tenor.com/37es.gif ",
                    f"<@220348421259657218>, {message.author.mention} is using evil 4 letter words!!!",
                ]
                rand_phrase = random.choice(phrases)
                await message.channel.send(rand_phrase)

                self.last_run["snow"] = datetime.datetime.now()

            else:
                cooldown = (self.last_run["snow"] + wait_time) - datetime.datetime.now()
                logger.info(f"Snow is on cooldown for another {cooldown}.")
                await message.add_reaction("⏳")

        elif "good bot" in msg:
            await message.channel.send(f"Well thank you {message.author.mention}.")

        elif "dats right bot" in msg:
            await message.channel.send(f"You know it is.")

        elif ("bad bot" in msg) or ("fu bot" in msg):
            await message.add_reaction("👎")

        elif "thank you bot" in msg:
            await message.channel.send(f"You're welcome {message.author}")

        elif "(╯°□°）╯︵ ┻━┻" == message.content:  # Doesn't use the processed msg variable because of needed punctuation.
            await message.channel.send(f"┬─┬ ノ( ゜-゜ノ) - Here let me put that back for you.")

        elif "thats what she said" in msg:
            phrases = [
                "https://tenor.com/rRGv.gif",
                "https://tenor.com/sHBT.gif",
                "Not to you they don't.",
            ]
            rand_phrase = random.choice(phrases)
            await message.channel.send(rand_phrase)

        elif ("has the box shipped" in msg or "wheres the box" in msg) and message.channel.id == 426451859440664576:
            if self.last_run.get("box_shipped", datetime.datetime.min) + wait_time <= datetime.datetime.now():

                await message.channel.send(f"http://www.hasthejunkerboxmoved.com")
                self.last_run["box_shipped"] = datetime.datetime.now()
            else:
                cooldown = (self.last_run["box_shipped"] + wait_time) - datetime.datetime.now()
                logger.info(f"Has the box shipped is on cooldown for another {cooldown}.")
                await message.add_reaction("⏳")

        elif ("moving on") in msg:
            if self.last_run.get("moving_on", datetime.datetime.min) + wait_time <= datetime.datetime.now():
                await message.channel.send("https://clips.twitch.tv/PoliteLaconicCrabKappaPride")
                self.last_run["moving_on"] = datetime.datetime.now()
            else:
                cooldown = (self.last_run["moving_on"] + wait_time) - datetime.datetime.now()
                logger.info(f"Moving on is on cooldown for another {cooldown}.")
                await message.add_reaction("⏳")

        elif msg in ["🤦", "🤦‍♂️", "🤦‍♀️"] and message.channel.id in [
            466048561994268682,
            504084460954845194,
            600768675645227037,
        ]:
            await message.channel.send(file=discord.File("images/baldengineer_facepalm.png"))

        elif msg in ["🙀", "😱"]:  # :scream_cat: or :scream:
            await message.channel.send(file=discord.File("images/peachcatboo.gif"))

        elif msg in [
            "😎",
        ]:  # :sunglasses
            await message.channel.send(file=discord.File("images/safety_squints.jpg"))

        elif msg == "427578603207917580 no":
            await message.channel.send(
                "NO <@!427578603207917580>! https://tenor.com/view/jermichael-no-urn-spray-bottle-spray-gif-13258723"
            )

        elif ":facedesk:" in message.content.lower():
            await message.channel.send("https://tenor.com/yWTN.gif")

        elif (msg.upper() == msg_no_lower) and (not message.author.bot) and (len(msg) > 4) and (not msg.isnumeric()):
            if self.last_run.get("yelling", datetime.datetime.min) + wait_time <= datetime.datetime.now():
                msg = await message.channel.send(f"WHY ARE WE YELLING {message.author.mention}?")
                self.last_run["yelling"] = datetime.datetime.now()
                await asyncio.sleep(8)
                await msg.delete()

            else:
                await message.add_reaction("👎")
                await message.add_reaction("⏳")
                await asyncio.sleep(5)
                await message.remove_reaction("⏳", self.client.user)

    @commands.group(hidden=True)
    @Permissions.check()
    async def fight(self, ctx, member: discord.Member):
        try:
            await ctx.message.delete()
        except:
            pass

        await ctx.message.channel.send(f"I'm watching you {member.mention}. 🗡️⚔️")

    @commands.group(hidden=True)
    @Permissions.check(role="everyone")
    async def shrug(self, ctx):
        r"""
        ¯\_(ツ)_/¯
        """
        await ctx.send(r" ¯\_(ツ)_/¯ ")

    @commands.command(hidden=True)
    @Permissions.check(role="everyone")
    async def babintdrinkstoomuch(self, ctx):
        """ sorry babs"""
        await ctx.send("I agree.")

    @commands.command(hidden=True)
    @Permissions.check(role="everyone")
    async def mathishard(self, ctx):
        await ctx.send("I agree. https://www.twitch.tv/baldengineer/clip/PatientDeliciousCockroachNononoCat")

    @commands.command(hidden=True)
    @Permissions.check(role="everyone")
    async def doh(self, ctx):
        await ctx.send("https://clips.twitch.tv/PatientHumbleSproutKreygasm")

    @commands.command(hidden=True)
    @Permissions.check(role="everyone")
    async def ahole(self, ctx):
        await ctx.send("https://clips.twitch.tv/PoorUninterestedSnailGOWSkull")

    @commands.command(hidden=True)
    @commands.is_owner()
    async def permissionscheck(self, ctx):
        await ctx.send(f"https://discordapi.com/permissions.html#{ctx.guild.me.guild_permissions.value}")

    @commands.command(hidden=True)
    @Permissions.check()
    async def annoy(self, ctx, count: int, *, message):

        count = abs(count)
        if count > 5:
            count = 5

        for _ in range(count):
            await ctx.send(message)
            await asyncio.sleep(1)

    @commands.command(hidden=True)
    @Permissions.check()
    async def superannoy(self, ctx, count: int, *, message):
        count = abs(count)
        if count > 15:
            count = 15

        for _ in range(count):
            m = await ctx.send(message)
            await asyncio.sleep(1)
            await m.delete()

    @commands.command(hidden=True)
    @Permissions.check(role="everyone")
    async def honk(self, ctx):
        await ctx.channel.send(file=discord.File("images/honque.jpg"))

    @commands.command()
    @Permissions.check(role="everyone")
    async def bubblewrap(self, ctx):
        pop = "||*pop*||" * 100
        embed = discord.Embed(title="")
        embed.add_field(name="pop....", value=pop)
        await ctx.channel.send(embed=embed)

    @commands.command()
    @Permissions.check(role="everyone")
    async def popcorn(self, ctx):
        pop = "||🍿||" * 100
        embed = discord.Embed(title="")
        embed.add_field(name=":popcorn:", value=pop)
        await ctx.channel.send(embed=embed)

    @permissionscheck.error
    @mathishard.error
    @babintdrinkstoomuch.error
    @shrug.error
    @annoy.error
    @superannoy.error
    @fight.error
    @honk.error
    async def _error(self, ctx, error):
        await Utils.errors(self, ctx, error)

    def cog_unload(self):
        logger.info(f"{__name__} unloaded...")


def setup(client):
    """
    Funstuff setup
    """
    logger.info(f"Loading {__name__}...")
    client.add_cog(FunStuff(client))
    logger.info(f"Loaded {__name__}")
