# -*- coding: utf-8 -*-
"""
Discord Bot for HardwareFlare and others
@author: Tisboyo
"""

import logging

import discord
from discord.ext import commands

from util.database import Database
from util.permissions import Permissions
from util.utils import Utils

logger = logging.getLogger(__name__)


class Karma(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.name = "karma"

        self.Karma = dict()

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

    @commands.Cog.listener()
    async def on_message(self, message):
        # Guard Clause
        if message.guild == None:  # Not in a guild means DM or Group chat.
            return

    @commands.Cog.listener()
    @commands.guild_only()
    async def on_raw_reaction_add(self, payload):
        """
		Check for Upvote and Downvote reaction
		"""

        # Who did the vote
        voter = self.client.get_user(payload.user_id)

        # Guard Clause
        if (
            voter.bot  # Check if a bot did the reaction
            or Database.Bot["sleeping"]  # If the bot is sleeping, don't do anything.
        ):
            return

        # A handle for settings to appease babint. Thank you babint for all the help.
        settings = Database.Cogs[self.name][payload.guild_id]["settings"]

        # Get a message object to identify the original message author
        channel = self.client.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)

        # Check to make sure the user isn't voting for themselves
        if message.author.id == payload.user_id:
            return

        if str(payload.emoji) == settings.get("upvote", False):
            logger.info(
                f"{channel.guild}-#{channel.name} - {voter.name} upvoted {message.author.name}"
            )
            current_karma = self.get_current_karma(payload.guild_id, message.author.id)
            new_karma = [current_karma[0] + 1, current_karma[1]]
            self.set_new_karma(payload.guild_id, message.author.id, new_karma)

        elif str(payload.emoji) == settings.get("downvote", False):
            logger.info(
                f"{channel.guild}-#{channel.name} - {voter.name} downvoted {message.author.name}"
            )
            current_karma = self.get_current_karma(payload.guild_id, message.author.id)
            new_karma = [current_karma[0], current_karma[1] + 1]
            self.set_new_karma(payload.guild_id, message.author.id, new_karma)

        else:
            # Any other emoji was added, so we don't really care.
            pass

    @commands.Cog.listener()
    @commands.guild_only()
    async def on_raw_reaction_remove(self, payload):
        """
		Check for removal of Upvote and Downvote reaction
		"""

        # Who did the vote
        voter = self.client.get_user(payload.user_id)

        # Guard Clause
        if (
            voter.bot  # Check if a bot did the reaction
            or Database.Bot["sleeping"]  # If the bot is sleeping, don't do anything.
        ):
            return

        # A handle for settings
        settings = Database.Cogs[self.name][payload.guild_id]["settings"]

        # Get a message object to identify the original message author
        channel = self.client.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)

        # Check to make sure the user isn't voting for themselves
        if message.author.id == payload.user_id:
            return

        if str(payload.emoji) == settings.get("upvote", False):
            logger.info(
                f"{channel.guild}-#{channel.name} - {voter.name} removed their upvote for {message.author.name}"
            )
            current_karma = self.get_current_karma(payload.guild_id, message.author.id)
            new_karma = [current_karma[0] - 1, current_karma[1]]
            self.set_new_karma(payload.guild_id, message.author.id, new_karma)

        elif str(payload.emoji) == settings.get("downvote", False):
            logger.info(
                f"{channel.guild}-#{channel.name} - {voter.name} removed their downvote for {message.author.name}"
            )
            current_karma = self.get_current_karma(payload.guild_id, message.author.id)
            new_karma = [current_karma[0], current_karma[1] - 1]
            self.set_new_karma(payload.guild_id, message.author.id, new_karma)

        else:
            pass

    def get_current_karma(self, guild_id: int, user_id: int):
        """
		Returns the message owners current upvotes and downvotes
		"""

        # Setup variables if they are new
        # We are storing the karma this way so in the future a global karma is accessible
        try:
            self.Karma[user_id]
        except:
            self.Karma[user_id] = dict()

        if not self.Karma[user_id].get(guild_id, False):
            # Karma for user is not currently in memory, do a db query

            # database query
            cursor = Database.cursor[guild_id]
            query = "SELECT upvotes, downvotes FROM users WHERE user_id = ?"
            values = (user_id,)
            result = Database.dbExecute(self, cursor, guild_id, query, values)

            self.Karma[user_id][guild_id] = [int(result[0]), int(result[1])]

        return self.Karma[user_id][guild_id]

    def set_new_karma(self, guild_id: int, user_id: int, karma: list):
        """
		Sets the new Karma for a user

		karma is a list of [ int(upvote_value), int(downvote_value) ]
		"""

        # Setup variables if they are new
        # We are storing the karma this way so in the future a global karma is accessible
        try:
            self.Karma[user_id]
        except:
            self.Karma[user_id] = dict()

        self.Karma[user_id][guild_id] = karma
        logger.debug(f"New karma set for {guild_id}-{user_id} of {karma}")

        # Database handle
        cursor = Database.cursor[guild_id]

        query = "UPDATE users SET upvotes = ?, downvotes = ? WHERE user_id = ?"
        values = (karma[0], karma[1], user_id)
        _, rows = Database.dbExecute(self, cursor, guild_id, query, values, False, True)

        # User was not in Database yet, insert them.
        # This should theoretically never happen since they are normally inserted on Levels.on_message, but just in case.
        if rows == 0:
            query = "INSERT INTO users(user_id, exp, level, words, messages, lastseen, lastseenurl, upvotes, downvotes) VALUES(?,?,?,?,?,?,?,?,?)"
            values = (user_id, 0, 0, 0, 0, 0, None, karma[0], karma[1])
            # We don't need to save the result of this
            Database.dbExecute(self, cursor, guild_id, query, values)
            logger.warning("User was inserted into database from Karma.set_new_karma.")
            logger.warning(f"Guild: {guild_id} User: {user_id}, Karma: {karma}")

    @commands.group()
    @commands.guild_only()
    @Permissions.check(role="everyone")
    async def karma(self, ctx):
        """
		Commands to set or show Karma upvote and downvote emojis

		Default Permissions: Manage Guild permission
		"""
        # Guard Clause
        if ctx.invoked_subcommand is not None:  # A subcommand was used.
            return

        # Build and send a message of current settings
        upvote = Database.Cogs[self.name][ctx.guild.id]["settings"].get(
            "upvote", "None"
        )
        downvote = Database.Cogs[self.name][ctx.guild.id]["settings"].get(
            "downvote", "None"
        )

        message = f"Current Upvote: {upvote} \nCurrent Downvote: {downvote}"
        await ctx.send(message)

    @karma.command()
    @commands.guild_only()
    @Permissions.check(permission=["manage_guild"])
    async def upvote(self, ctx, emoji):
        """
		Set the emoji to use as an Upvote

		Default Permissions: Manage Guild permission
		"""

        # Guard Clause
        if False:  # Future use
            return

        emoji_object = await self.check_emoji(ctx, emoji)

        Database.Cogs[self.name][ctx.guild.id]["settings"]["upvote"] = emoji_object

        # Write the settings to the database
        Database.writeSettings(self, ctx.guild.id)

        await Utils.send_confirmation(self, ctx.message)

    @karma.command()
    @commands.guild_only()
    @Permissions.check(permission=["manage_guild"])
    async def downvote(self, ctx, emoji):
        """
		Set the emoji to use as a Downvote

		Default Permissions: Manage Guild permission
		"""

        # Guard Clause
        if False:  # Future use
            return

        emoji_object = await self.check_emoji(ctx, emoji)

        Database.Cogs[self.name][ctx.guild.id]["settings"]["downvote"] = emoji_object

        # Write the settings to the database
        Database.writeSettings(self, ctx.guild.id)

        await Utils.send_confirmation(self, ctx.message)

    @karma.group()
    @commands.guild_only()
    @Permissions.check(permission=["manage_guild"])
    async def disable(self, ctx):
        """
		Disables Upvote and Downvote emojis

		Usage: karma disable both (Disables both up and down votes.)
			   karma disable upvote (Disables just the upvote emoji.)
			   karma disable downvote (Disables just the downvote.)

		Default Permissions: Manage Guild permission
		"""

        # Guard Clause
        if ctx.invoked_subcommand is not None:  # A subcommand was used.
            return

        # Send the help embed for the current command
        await ctx.send_help(ctx.command)

    @disable.command(name="upvote")
    @commands.guild_only()
    @Permissions.check(permission=["manage_guild"])
    async def karma_disable_upvote(self, ctx):
        """
		Disable the upvote emoji

		Default Permissions: Manage Guild permission
		"""

        # Disable
        Database.Cogs[self.name][ctx.guild.id]["settings"]["upvote"] = None

        # Save the database
        Database.writeSettings(self, ctx.guild.id)

        # Provide user feedback
        await Utils.send_confirmation(self, ctx.message)

    @disable.command(name="downvote")
    @commands.guild_only()
    @Permissions.check(permission=["manage_guild"])
    async def karma_disable_downvote(self, ctx):
        """
		Disable the downvote emoji

		Default Permissions: Manage Guild permission
		"""

        # Disable
        Database.Cogs[self.name][ctx.guild.id]["settings"]["downvote"] = None

        # Save the database
        Database.writeSettings(self, ctx.guild.id)

        # Provide user feedback
        await Utils.send_confirmation(self, ctx.message)

    @disable.command(name="both")
    @commands.guild_only()
    @Permissions.check(permission=["manage_guild"])
    async def karma_disable_both(self, ctx):
        """
		Disable both up and down vote emoji

		Default Permissions: Manage Guild permission
		"""

        # Disable
        Database.Cogs[self.name][ctx.guild.id]["settings"]["upvote"] = None
        Database.Cogs[self.name][ctx.guild.id]["settings"]["downvote"] = None

        # Save the database
        Database.writeSettings(self, ctx.guild.id)

        # Provide user feedback
        await Utils.send_confirmation(self, ctx.message)

    async def check_emoji(self, ctx, emojiRaw):
        """
		Checks if an emoji is valid or not
		"""
        try:  # Check if it is a custom emoji.
            emoji = await commands.EmojiConverter().convert(ctx, emojiRaw)
            emoji = str(emoji)

        except:  # Not a custom on this server, must be a regular emoji
            emoji = emojiRaw

        try:
            # We are responding with the emoji the user requested, primarily as a test
            # to see if the emoji is valid. If it's not, it throws a HTTPException code 10014
            await ctx.message.add_reaction(emoji)  # Add the emoji the user requested.

        except discord.HTTPException as e:
            if e.code == 10014:
                await ctx.send(
                    f"Sorry, but discord doesn't have that emoji in it's reaction library."
                )
                await Utils.send_failure(self, ctx.message)
                # We don't want to try adding the bad emoji to the database, so returning.
                return

            else:  # A different error code
                # Send the error to the console so we can figure out the cause of it.
                await Utils.send_failure(self, ctx.message)
                Utils.error_to_console(ctx, e)
                return

        except:
            await Utils.send_failure(self, ctx.message)

        return emoji

    @upvote.error
    @downvote.error
    @disable.error
    @karma_disable_upvote.error
    @karma_disable_downvote.error
    @karma_disable_both.error
    async def _error(self, ctx, error):
        await Utils.errors(self, ctx, error)


def setup(client):
    """
	Karma setup
	"""
    logger.info(f"Loading {__name__}...")
    client.add_cog(Karma(client))
    logger.info(f"Loaded {__name__}")
