# -*- coding: utf-8 -*-
"""
Discord Bot for HardwareFlare and others
@author: Tisboyo
"""

import logging

from discord.ext import commands

from util.database import Database
from util.permissions import Permissions
from util.utils import Utils

logger = logging.getLogger(__name__)


class lol(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.name = "lol"

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
            del Database.Cogs[self.name][guild.id]

    @commands.command(hidden=True)
    @Permissions.check()
    async def loltoggle(self, ctx):
        """
        Toggles on and off the bot responding to lol
        """

        settings = Database.Cogs[self.name][ctx.guild.id]["settings"]

        if settings["enabled"]:
            settings["enabled"] = False
        else:
            settings["enabled"] = True

        await Utils.send_confirmation(self, ctx.message)

        Database.writeSettings(self, ctx.guild.id)

    @commands.Cog.listener()
    async def on_message(self, message):
        # Guard Clause
        if (
            message.guild == None  # Not in a guild means DM or Group chat.
            or message.author.bot  # Ignore bots
            or not Database.Cogs[self.name][message.guild.id]["settings"]["enabled"]  # Not enabled
            or Database.Bot["sleeping"]  # If the bot is sleeping, don't do anything.
        ):
            return

        if "lol" in message.content:
            # Create the dictionary key if it doesn't exist.
            if not Database.Cogs[self.name][message.guild.id].get(message.channel.id, False):
                Database.Cogs[self.name][message.guild.id][message.channel.id] = set()

            # Add the message author to the set
            Database.Cogs[self.name][message.guild.id][message.channel.id].add(message.author.id)

            # Check if the last x people have used lol
            threshold = 3  # Number of different users to trigger the event.
            if len(Database.Cogs[self.name][message.guild.id][message.channel.id]) >= threshold:
                await message.channel.send(":rofl: :rofl: :rofl: :rofl: :rofl: :rofl: :rofl: :rofl: :rofl: ")
                # Dump the memory so it doesn't fire if a x+1 person triggers
                del Database.Cogs[self.name][message.guild.id][message.channel.id]

        else:
            # If the key exists, delete it because the messages aren't sequential
            if Database.Cogs[self.name][message.guild.id].get(message.channel.id, False):
                del Database.Cogs[self.name][message.guild.id][message.channel.id]

    def cog_unload(self):
        logger.info(f"{__name__} unloaded...")


def setup(client):
    """
    lol setup
    """
    logger.info(f"Loading {__name__}...")
    client.add_cog(lol(client))
    logger.info(f"Loaded {__name__}")
