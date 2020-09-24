# -*- coding: utf-8 -*-
"""
Discord Bot for HardwareFlare and others
@author: Tisboyo
"""
import datetime
import logging
import traceback

import discord
from discord.ext import commands

from util.database import Database

logger = logging.getLogger(__name__)


class Utils(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.name = "utils"

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

    def get_channel(self, guild, channel_name):
        """
        Returns a channel object
        """

        if isinstance(guild, discord.Guild):
            guild_id = guild.id
        elif isinstance(guild, (str, int)):
            guild_id = guild
        elif guild is None:
            return None
        else:
            logger.critical(f"Babint says its broke. {type(guild)}")
            return None

        channel = Database.Cogs[self.name][guild_id]["settings"][channel_name]

        if isinstance(channel, discord.TextChannel):
            logger.debug(f"Returning existing channel object {channel_name}")
            return channel

        elif isinstance(channel, (int, str)):  # Database values are stored as strings
            channel_instance = self.client.get_channel(int(channel))

            # Save the handle for later
            Database.Cogs[self.name][guild_id]["settings"][channel_name] = channel_instance

            logger.info(f"Returning new channel object {channel_name}")
            return channel_instance

        else:
            return None  # Return None then handle error in calling function.

    async def errors(self, ctx, error):

        logger.info(
            "\r\n"
            f"----- Guild: {ctx.guild.name}-{ctx.guild.id}\r\n"
            f"----- Channel: #{ctx.channel.name}-{ctx.channel.id}\r\n"
            f"----- Author: {ctx.author.display_name}-{ctx.author.id}\r\n"
            f"----- Message: {ctx.message.content}\r\n"
            f"{error}"
        )

        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Missing required arguments")
            await ctx.send_help(ctx.command)
            await ctx.message.add_reaction("🚫")

        elif isinstance(error, commands.BadArgument):
            await ctx.send("Invalid argument given.")
            await ctx.send_help(ctx.command)
            await ctx.message.add_reaction("🚫")

        elif isinstance(error, commands.MissingPermissions):
            await ctx.send(f"You do not have permissions to use that command.")
            await ctx.message.add_reaction("🚫")
            return

        elif isinstance(error, discord.errors.Forbidden):
            await ctx.message.add_reaction("🚫")
            return

        elif isinstance(error, commands.CommandError):
            # This must be the last error checked because all other errors are sub errors of CommandError
            messages = {
                "MissingPermissions": f"You do not have permissions to use that command.",
                "NotAvailableInThisGuild": "This command is guild specific in the bot, and is unavailable here.",
                "BotIsSleeping": "Bot is currently unavailable for commands.",
            }

            if str(error) in messages:
                await ctx.send(messages[str(error)])

            await ctx.message.add_reaction("🚫")
            return

        else:
            Utils.error_to_console(ctx, error)

    @staticmethod
    def error_to_console(ctx, error):
        # Disable all the no-member violations in this function
        # pylint: disable=no-member

        # Output to console
        author = ctx.message.author
        user = f"{author.display_name} ({author.name}#{author.discriminator})"

        server = ctx.message.guild.name
        print("*************************************************************")
        print(f"{datetime.datetime.now()}")
        print(f"{user} @ {server} > {error}")
        print(f"message.content> {ctx.message.content}")
        print(f"error type> {type(error)}")
        print(f"")
        print(f"")
        print(f"****************************TRACEBACK***********************")
        traceback.print_tb(error.__traceback__)
        # traceback.print_stack()
        # traceback.print_exc()
        print(f"************************END TRACEBACK***********************")

    async def send_confirmation(self, message):
        # Try to add a reaction to the message, if permissions don't allow, send it as a message.
        try:
            await message.add_reaction(Dictionary.check_box)
        except:
            await message.channel.send(Dictionary.check_box)

    async def send_failure(self, message: discord.Message):
        # Try to add a reaction to the message, if permissions don't allow, send it as a message.
        try:
            await message.add_reaction(Dictionary.red_no_circle)
        except:
            await message.channel.send(Dictionary.red_no_circle)

    @staticmethod
    def starprint(message: str):
        print(message.center(80, "*"))


class dotdict(dict):
    """
    dot.notation access to dictionary attributes
    https://stackoverflow.com/a/23689767
    """

    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


class Dictionary:
    check_box = "☑️"  # ballot_box_with_check
    red_no_circle = "🚫"
    hourglass = "\U000023F3"


def setup(client):
    """
    Test setup
    """
    logger.info(f"Loading {__name__}...")
    client.add_cog(Utils(client))
    logger.info(f"Loaded {__name__}")
