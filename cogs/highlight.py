# -*- coding: utf-8 -*-
"""
Discord Bot for HardwareFlare and others
@author: Tisboyo
"""

import logging
import asyncio
import time

import discord
from discord.ext import commands

from util.database import Database
from util.utils import Utils, Dictionary
from util.permissions import Permissions

logger = logging.getLogger(__name__)


class Highlight(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.name = "highlight"
        Database.Cogs[self.name] = dict()

        Database.readSettings(self)

        for guild_id in Database.Main:
            # Create a dictionary for tracking cooldowns
            Database.Cogs[self.name][guild_id]["cooldown"] = dict()

            if "highlight_channel" not in Database.Cogs[self.name][guild_id]["settings"].keys():
                Database.Cogs[self.name][guild_id]["settings"]["highlight_channel"] = None

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        # Have to reload Database.Cogs when joining a new guild to prevent errors.
        Database.readSettings(self)

        if "highlight_channel" not in Database.Main[guild.id]["settings"].keys():
            Database.Main[guild.id]["settings"]["highlight_channel"] = None

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        # No point in holding stuff in memory for a guild we aren't in.
        if Database.Cogs[self.name].get(guild.id, False):
            Database.writeSettings(self, guild.id)
            del Database.Cogs[self.name][guild.id]

    @commands.group()
    @commands.guild_only()
    @Permissions.check(role="everyone")
    async def highlight(self, ctx):
        """
        Use to highlight content to a specific channel.

        Default Permissions: Everyone role
        """

        # Guard Clause
        if ctx.invoked_subcommand is not None:  # if subcommand was used.
            return

        # Check if channel is set
        if not Database.Cogs[self.name][ctx.guild.id]["settings"].get("highlight_channel", False):
            await ctx.send("Channel is not set for highlight, please ask an administrator to set one.")
            return

        # Assign the text channel to a variable for use
        channel = Utils.get_channel(self, ctx.guild, "highlight_channel")

        # Check when the user last sent something to the highlight channel
        user_cooldown = Database.Cogs[self.name][ctx.guild.id]["cooldown"].get(ctx.message.author.id, 0)
        if int(user_cooldown + channel.slowmode_delay - 1) > int(time.time()):
            # Calculate the time left of the users cooldown, and inform the user
            cooldown_left = int((user_cooldown + channel.slowmode_delay) - time.time())
            await ctx.author.send(
                f"{ctx.author.mention} you currently have {cooldown_left} "
                f"seconds left on cooldown for {channel.mention}. Your message "
                f"will be sent then, at which point another "
                f"{channel.slowmode_delay} second cooldown will begin."
            )
            # Add a waiting reaction
            await ctx.message.add_reaction(Dictionary.hourglass)
            # Then sleep until the cooldown is up
            await asyncio.sleep(cooldown_left)
            # Wait is over, remove the waiting reaction
            await ctx.message.remove_reaction(Dictionary.hourglass, ctx.me)
            # Sleep for just a tad bit longer to prevent rate limiting when adding the check
            await asyncio.sleep(0.25)

        # Update the users cooldown
        Database.Cogs[self.name][ctx.guild.id]["cooldown"][ctx.message.author.id] = int(time.time())

        # Find the length of the command prefix, plus command name and a space to strip out later
        drop_len = len(ctx.prefix) + 9 + 1

        message = f"{ctx.author.mention} has shared {ctx.message.clean_content[drop_len:]}"
        await channel.send(message)
        await ctx.message.add_reaction(Dictionary.check_box)

    @highlight.command()
    @commands.guild_only()
    @Permissions.check(permission=["manage_channels"])
    async def channel(self, ctx, channel: discord.TextChannel):
        """
        Sets a channel for the higlight command.

        Default Permissions: manage_channels permission
        """

        # Save the channel to memory
        Database.Cogs[self.name][ctx.guild.id]["settings"]["highlight_channel"] = channel

        # Write the settings to the database
        Database.writeSettings(self, ctx.guild.id)

        await ctx.message.add_reaction(Dictionary.check_box)

    @highlight.command()
    @commands.guild_only()
    @Permissions.check(permission=["manage_channels"])
    async def disable(self, ctx):
        """
        Removes the set channel for the highlight command.

        Running this will disable use of the highlight command.

        Default Permissions: manage_channels permission
        """

        # Remove the channel from memory
        Database.Cogs[self.name][ctx.guild.id]["settings"]["highlight_channel"] = None

        # Write the settings to the database
        Database.writeSettings(self, ctx.guild.id)

        await ctx.message.add_reaction(Dictionary.check_box)

    @commands.Cog.listener()
    async def on_message(self, message):
        """
        Used to keep track of the last time a user posted a message in the highlights channel
        to honor the cooldown
        """

        # Get the highlight channel to use in the Guard Clause
        channel = Utils.get_channel(self, message.guild, "highlight_channel")

        # Guard clause
        if (
            message.author.bot
            or len(message.content) == 0  # Ignore bots
            or message.guild == None  # No message contents, users join/leave/reactions
            or message.content[0]  # Not in a guild means DM or Group chat.
            == Database.Main[message.guild.id].get("prefix", ".")
            or  # Ignore commands
            # Ignore messages not in our highlights channel
            message.channel != channel
        ):
            return  # Abort abort!

        # Update the users cooldown if they posted directly to the highlights channel
        Database.Cogs[self.name][message.guild.id]["cooldown"][message.author.id] = int(time.time())

    @highlight.error
    @channel.error
    @disable.error
    async def _error(self, ctx, error):
        await Utils.errors(self, ctx, error)

    def cog_unload(self):
        logger.info(f"{__name__} unloaded...")


def setup(client):
    """
    Highlight setup
    """
    logger.info(f"Loading {__name__}...")
    client.add_cog(Highlight(client))
    logger.info(f"Loaded {__name__}")
