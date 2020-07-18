# -*- coding: utf-8 -*-
"""
Discord Bot for HardwareFlare and others
@author: Tisboyo
"""

import datetime
import logging

import discord
from discord.ext import commands

from util.database import Database
from util.utils import Utils
from util.permissions import Permissions

logger = logging.getLogger(__name__)


class Moderation(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.name = "moderation"

        Database.readSettings(self)

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        # Have to reload Database.Cogs when joining a new guild to prevent errors.
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
            message.guild == None
            or Database.Bot[  # Not in a guild means DM or Group chat.
                "sleeping"
            ]  # If the bot is sleeping, don't do anything.
        ):
            return

    @commands.group(hidden=True)
    @Permissions.check()
    async def mod(self, ctx):
        """
		Moderation

		Default Permissions: Guild Administrator only
		"""
        # Guard Clause
        if (
            ctx.guild == None
            or ctx.invoked_subcommand  # Not in a guild means DM or Group chat.
            is not None  # A subcommand was used.
        ):
            return

        # Send the help embed for the current command
        await ctx.send_help(ctx.command)

    @mod.command()
    @Permissions.check()
    async def edit_channel(self, ctx, channel: discord.TextChannel):
        """
		Sets a channel for edit notifications

		Usage:
			To set: mod edit_channel #Channel_Name
			To display: mod edit_channel

		Default Permissions: Guild Administrator only
		"""
        # Guard Clause
        if ctx.guild == None:  # Not in a guild means DM or Group chat.
            return

        Database.Cogs[self.name][ctx.guild.id]["settings"]["edit_channel"] = channel

        Database.writeSettings(self, ctx.guild.id)

        await Utils.send_confirmation(self, ctx.message)

    @edit_channel.error
    async def edit_channel_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):

            # Get the channel object
            channel = Utils.get_channel(self, ctx.guild, "edit_channel")

            if channel:
                message = f"Current channel is {channel.mention}"
            else:
                # The setting was not set.
                message = "Channel is not set."

            await ctx.send(message)

            return

        if isinstance(error, commands.BadArgument):
            await ctx.send("Invalid channel name.")
            return

        # Sends the error to the console since it's unanticipated
        Utils.error_to_console(ctx, error)

    @mod.command()
    @Permissions.check()
    async def delete_channel(self, ctx, channel: discord.TextChannel):
        """
		Sets a channel for message delete notifications

		Usage:
			To set: mod delete_channel #Channel_Name
			To display: mod delete_channel

		Default Permissions: Guild Administrator only
		"""
        # Guard Clause
        if ctx.guild == None:  # Not in a guild means DM or Group chat.
            return

        Database.Cogs[self.name][ctx.guild.id]["settings"]["delete_channel"] = channel

        Database.writeSettings(self, ctx.guild.id)

        await Utils.send_confirmation(self, ctx.message)

    @delete_channel.error
    async def delete_channel_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):

            # Get the channel object
            channel = Utils.get_channel(self, ctx.guild, "delete_channel")

            if channel:
                message = f"Current channel is {channel.mention}"
            else:
                # The setting was not set.
                message = "Channel is not set."

            await ctx.send(message)

            return

        if isinstance(error, commands.BadArgument):
            await ctx.send("Invalid channel name.")
            return

        # Sends the error to the console since it's unanticipated
        Utils.error_to_console(ctx, error)

    @mod.group()
    @Permissions.check()
    async def disable(self, ctx):
        """
		Used to disable features of moderation plugin.

		Default Permissions: Guild Administrator only
		"""

        # Guard Clause
        if (
            ctx.guild == None
            or ctx.invoked_subcommand  # Not in a guild means DM or Group chat.
            is not None  # A subcommand was used.
        ):
            return

        # Send the help embed for the current command
        await ctx.send_help(ctx.command)

    @disable.command(name="edit_channel")
    @Permissions.check()
    async def edit_channel_disable(self, ctx):
        """
		Used to disable announcing edits.

		Usage: mod disable edit_channel

		Default Permissions: Guild Administrator only
		"""

        # Guard Clause
        if ctx.guild == None:  # Not in a guild means DM or Group chat.
            return

        Database.Cogs[self.name][ctx.guild.id]["settings"]["edit_channel"] = None

        Database.writeSettings(self, ctx.guild.id)

        await Utils.send_confirmation(self, ctx.message)

    @disable.command(name="delete_channel")
    @Permissions.check()
    async def delete_channel_disable(self, ctx):
        """
		Used to disable announce message deletions.

		Usage: mod disable delete_channel

		Default Permissions: Guild Administrator only
		"""

        # Guard Clause
        if ctx.guild == None:  # Not in a guild means DM or Group chat.
            return

        Database.Cogs[self.name][ctx.guild.id]["settings"]["delete_channel"] = None

        Database.writeSettings(self, ctx.guild.id)

        await Utils.send_confirmation(self, ctx.message)

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload):

        # Need an integer for guard clause so grabbing this early
        guild_id = int(payload.data["guild_id"])

        # Guard Clause
        if (  # edit_channel has been set
            not Database.Cogs[self.name][guild_id]["settings"].get(
                "edit_channel", False
            )
            or not payload.data.get("author", False)
            or Database.Bot[  # Occurs when an embed only edit is made
                "sleeping"
            ]  # If the bot is sleeping, don't do anything.
        ):
            return

        # Save a message just in case we dont' have the old message in the bot cache
        old_message = "Old message is not in the bot's cache."

        channel = self.client.get_channel(int(payload.data["channel_id"]))
        guild = self.client.get_guild(guild_id)
        member = guild.get_member(int(payload.data["author"]["id"]))
        output_channel = Utils.get_channel(self, guild, "edit_channel")

        if hasattr(payload.cached_message, "content"):
            old_message = payload.cached_message.clean_content

        new_message = await channel.fetch_message(int(payload.data["id"]))
        new_message = new_message.clean_content

        embed = discord.Embed(title="Message Edited")
        embed.add_field(name="Author", value=f"{member}")
        embed.add_field(name="Channel", value=f"{channel.mention}")

        # Value is limited to 1024 characters, so split it and add a second one
        embed.add_field(name="Old Message", value=f"{old_message[:1024]}", inline=False)
        if len(old_message) > 1024:
            embed.add_field(
                name="Old Message Continued",
                value=f"{old_message[1025:]}",
                inline=False,
            )

        embed.add_field(name="New Message", value=f"{new_message[:1024]}", inline=False)
        if len(new_message) > 1024:
            embed.add_field(
                name="New Message Continued",
                value=f"{new_message[1025:]}",
                inline=False,
            )

        await output_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload):

        # Guard Clause
        if (  # delete_channel has been set
            not Database.Cogs[self.name][payload.guild_id]["settings"].get(
                "delete_channel", False
            )
            or Database.Bot["sleeping"]  # If the bot is sleeping, don't do anything.
        ):
            return

        guild = self.client.get_guild(payload.guild_id)
        channel = Utils.get_channel(self, guild, "delete_channel")
        message_channel = self.client.get_channel(payload.channel_id)

        # Ignore #hydra_songrequests in HWF
        if message_channel.id == 665746396040790039:
            return

        # Ignore our own messages.
        elif payload.cached_message is not None:  # Check if message is cached
            if payload.cached_message.author.id == self.client.user.id:  # bot.id
                return

        if payload.cached_message == None:  # Message was not in cache
            await channel.send(
                f"An uncached message has been deleted in {message_channel.mention}"
            )
        else:  # Message was in cache
            embed = discord.Embed(title="Message Deleted")
            embed.add_field(
                name="Author", value=f"{payload.cached_message.author.mention} "
            )
            embed.add_field(name="Channel", value=f"{message_channel.mention} ")

            # Figure out how old the message is, so we can say that.
            original_time = payload.cached_message.created_at.strftime(
                "%H:%M:%S %Y/%m/%d"
            )
            how_long_ago = (
                datetime.datetime.utcnow() - payload.cached_message.created_at
            )

            embed.add_field(
                name="Original Time", value=f"{original_time} ({how_long_ago} ago.)"
            )

            if len(payload.cached_message.content) > 0:
                embed.add_field(
                    name="Message Contents",
                    value=f"{payload.cached_message.content} ",
                    inline=False,
                )
            else:
                embed.add_field(
                    name="Message Contents", value="Bot embed or image.", inline=False
                )

            await channel.send("", embed=embed)

    @mod.command(hidden=True)
    @Permissions.check()
    async def delete_message(self, ctx, message_id: int):
        """
        Deletes a message by id.
        """

        message = await ctx.fetch_message(message_id)
        await message.delete()

    @delete_message.error
    async def _error(self, ctx, error):
        await Utils.errors(self, ctx, error)


def setup(client):
    """
	Moderation setup
	"""
    logger.info(f"Loading {__name__}...")
    client.add_cog(Moderation(client))
    logger.info(f"Loaded {__name__}")
