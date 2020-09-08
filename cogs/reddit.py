# -*- coding: utf-8 -*-
"""
Discord Bot for HardwareFlare and others
@author: Tisboyo
"""

import logging
import random

# import discord
from discord.ext import commands

from util.database import Database
from util.permissions import Permissions
from util.utils import Utils

logger = logging.getLogger(__name__)


class Reddit(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.name = "reddit"

        Database.readSettings(self)

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        # Read the database when joining a new guild
        Database.readSettingsGuild(self, guild.id)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        # No point in holding stuff in memory for a guild we aren't in.
        Database.writeSettings(self, guild.id)
        if Database.Cogs[self.name].get(guild.id, False):
            del Database.Cogs[self.name][guild.id]

    @commands.Cog.listener()
    async def on_message(self, message):
        # Guard Clause
        if (
            message.guild == None  # Not in a guild means DM or Group chat.
            or Database.Bot["sleeping"]  # If the bot is sleeping, don't do anything.
            or
            # Check if autolink is disabled
            not Database.Cogs[self.name][message.guild.id]["settings"]["autolink"]
        ):
            return

        message_split = message.content.split()

        for word in message_split:
            if word.startswith("/r/"):
                # Random phrases have to be defined inside the for loop so that word is available to them.
                random_phrases = [
                    f"Did you mean https://reddit.com{word} ?",
                    f"Oh, I've heard of https://reddit.com{word} before!",
                ]

                # Pick a random phrase
                rand = random.randint(0, len(random_phrases) - 1)

                # and send it to the channel
                await message.channel.send(random_phrases[rand])

    @commands.group()
    @Permissions.check()
    async def reddit(self, ctx):
        """
		Used for interacting with reddit. See help reddit
		"""
        # Guard Clause
        if False:  # Future use
            return

    @reddit.command()
    @commands.has_permissions(administrator=True)
    async def autolink(self, ctx):
        """
		Toggles on and off autolinking of mentioned subreddits.
		"""
        # Guard Clause
        if False:  # Future use
            return

        settings = Database.Cogs[self.name][ctx.guild.id]["settings"]

        if settings["autolink"] == 1:
            settings["autolink"] = 0
            await ctx.send("Autolinking of subreddits has been disabled.")
        else:
            settings["autolink"] = 1
            await ctx.send("Autolinking of subreddits has been enabled.")
        Database.writeSettings(self, ctx.guild.id)

    def cog_unload(self):
        logger.info(f"{__name__} unloaded...")


def setup(client):
    """
	Reddit setup
	"""
    logger.info(f"Loading {__name__}...")
    client.add_cog(Reddit(client))
    logger.info(f"Loaded {__name__}")
