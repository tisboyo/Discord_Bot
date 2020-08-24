# -*- coding: utf-8 -*-
"""
Discord Bot for HardwareFlare and others
@author: Tisboyo
"""

import random
import datetime
import sqlite3
import logging
import json

import discord
from discord.ext import commands

from util.database import Database
from util.permissions import Permissions
from util.utils import Utils, dotdict

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


class ReactToMessages(commands.Cog):
    """
	This module will add a reaction to users messages at random.

	Data format
	Database.Cogs[self.name][guild_id]['users'][member_id]['emojis'] = list()
														  ['frequency'] = int()
														  ['lastquery'] = datetime.datetime object


	"""

    # Set this to check how often the database will be queried for a users data
    user_query_frequency = datetime.timedelta(minutes=15)

    def __init__(self, client):
        self.client = client
        self.name = "react_to_message"

        Database.readSettings(self)

        for guild_id in Database.Main:
            # Storage for user data
            Database.Cogs[self.name][guild_id]["users"] = dict()

            self.setup_database(guild_id)

    def setup_database(self, guild_id):

        cursor = Database.cursor[guild_id]

        # Check if users table exists, if not create it.
        try:
            query = f"SELECT * FROM {self.name}_users LIMIT 1"
            Database.dbExecute(self, cursor, guild_id, query)
        except sqlite3.OperationalError as e:
            # The table doesn't exist, so we're going to create it and re-run the query.
            if "no such table" in e.args[0]:
                insert_query = f"""CREATE TABLE IF NOT EXISTS {self.name}_users(
									user_id INTEGER, emojis TEXT, frequency INTEGER,
									PRIMARY KEY("user_id") )"""
                Database.dbExecute(self, cursor, guild_id, insert_query)
                logger.info(f"{self.name}_users table created for {guild_id}.")

                Database.dbExecute(self, cursor, guild_id, query)

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        # Have to reload Database.Cogs when joining a new guild to prevent errors.
        Database.readSettingsGuild(self, guild.id)
        self.setup_database(guild.id)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        # No point in holding stuff in memory for a guild we aren't in.
        Database.writeSettings(self, guild.id)
        if Database.Cogs[self.name].get(guild.id, False):
            del Database.Cogs[self.name][guild.id]

    @commands.Cog.listener()
    async def on_message(self, message):
        # Guard clause
        if (
            Database.Bot["sleeping"]
            or message.author.bot
            or len(message.content) == 0  # Bot
            or message.guild == None  # No message contents, users join/leave
            or message.content[0]  # Not in a guild means DM or Group chat.
            == Database.Main[message.guild.id].get("prefix", ".")  # Bot commands
        ):
            return  # Abort abort!

        # Handle to access guild
        handle = Database.Cogs[self.name][message.guild.id]["users"]

        # Convert message.author.id to string for use in dictionary lookups
        author = message.author

        self.get_user_data(author)

        # Check the users frequency, and get a random number within that.

        max_rand = int(handle[author.id]["frequency"])

        # If we are set below zero, just use the generic value
        if max_rand <= 0:
            max_rand = 10

        # Pick a number to see if we should proceed
        rand = random.randint(1, max_rand)

        if rand != 1:
            return

        # Check if your user has any emojis set
        if len(handle[author.id]["emojis"]):  # If len is not 0 returns true

            # Pick a random emoji
            emoji = random.choice(handle[author.id]["emojis"])

            try:
                await message.add_reaction(emoji)

            except discord.HTTPException as e:
                if e.code == 50013:
                    # Not allowed to add reactions, so just fail quietly.
                    return

    @commands.group(aliases=["rtm"])
    @commands.guild_only()
    @Permissions.check(permission=["add_reactions"])
    async def react_to_messages(self, ctx):
        """
		Adds reactions to user messages automatically.

		Default Permissions: add_reactions permission
		"""
        # Guard Clause
        if ctx.invoked_subcommand is not None:  # A subcommand was used.
            return

        await ctx.send_help(ctx.command)

    def get_user_data(self, member):
        """
		Reads the users data from the database and stores it in memory
		"""
        if not Database.Cogs[self.name][member.guild.id]["users"].get(member.id, False):
            # User doesn't exist in memory yet, need to create them
            Database.Cogs[self.name][member.guild.id]["users"][member.id] = dict()

        # Check if enough time has elapsed to query the database again. Time is set at top of class, above __init__
        now = datetime.datetime.utcnow()
        last_query = Database.Cogs[self.name][member.guild.id]["users"][member.id].get(
            "lastquery", datetime.datetime.utcfromtimestamp(0)
        )

        if now - last_query > ReactToMessages.user_query_frequency:

            # Query the database for the users settings
            cursor = Database.cursor[member.guild.id]

            query = f"SELECT user_id, emojis, frequency FROM {self.name}_users WHERE user_id = ?"
            values = (member.id,)
            result = Database.dbExecute(self, cursor, member.guild.id, query, values)

            if result is not None:
                # Store the results
                Database.Cogs[self.name][member.guild.id]["users"][member.id][
                    "emojis"
                ] = json.loads(result[1])
                Database.Cogs[self.name][member.guild.id]["users"][member.id][
                    "frequency"
                ] = int(result[2])
                Database.Cogs[self.name][member.guild.id]["users"][member.id][
                    "lastquery"
                ] = datetime.datetime.utcnow()
                logger.debug(
                    f"Member {member.id}-{member} retrieved from {self.name}_users"
                )

            else:
                # No results, create empty ones
                Database.Cogs[self.name][member.guild.id]["users"][member.id][
                    "emojis"
                ] = list()
                Database.Cogs[self.name][member.guild.id]["users"][member.id][
                    "frequency"
                ] = 10  # 1 in 10 is the default value
                Database.Cogs[self.name][member.guild.id]["users"][member.id][
                    "lastquery"
                ] = datetime.datetime.utcnow()
                logger.debug(
                    f"Member {member.id}-{member} did not exist in {self.name}_users"
                )

    def write_user_data(self, member):
        """
		Writes the users data back to the database.
		"""

        # Check to make sure the user is actually in memory, thereby get_user_data was called for this member
        if not Database.Cogs[self.name][member.guild.id]["users"].get(member.id, False):
            # User doesn't exist in memory, throw an error and bail
            logger.error(
                "ReactToMessages.write_user_data called before a user was read."
            )
            return

        # Shorter names to use in queries
        emojis = json.dumps(
            Database.Cogs[self.name][member.guild.id]["users"][member.id]["emojis"],
            ensure_ascii=False,
        )
        frequency = Database.Cogs[self.name][member.guild.id]["users"][member.id].get(
            "frequency", 10
        )

        cursor = Database.cursor[member.guild.id]

        query = (
            f"UPDATE {self.name}_users SET emojis = ?, frequency = ? WHERE user_id = ?"
        )
        values = (emojis, frequency, member.id)
        _, rows = Database.dbExecute(
            self, cursor, member.guild.id, query, values, False, True
        )
        logger.debug(f"Member {member.id}-{member} updated in {self.name}_users")

        if rows == 0:
            # User wasn't in the database, we need to insert them.
            query = f"INSERT INTO {self.name}_users (emojis, frequency, user_id) VALUES (?, ?, ?) "
            Database.dbExecute(self, cursor, member.guild.id, query, values)
            logger.debug(f"Member {member.id}-{member} inserted into {self.name}_users")

    @react_to_messages.command()
    @commands.guild_only()
    @Permissions.check(permission=["add_reactions"])
    async def add(self, ctx, member, emoji):
        """
		Add a reaction to a users messages

		Usage: add (User) (An Emoji)

		You can either mention a user, use their name or
		name#discriminator without mentioning the user.
		If name#discriminator has a space, wrap it in quotes.

		For the Emoji, send any guild or regular emoji.
		If it doesn't appear when you send it, you will
		get an Invalid Argument error.

		Default Permissions: add_reactions permission
		"""

        mentions = ctx.message.mentions

        # If the member wasn't mentioned, run it through the converter to get a member object
        if len(mentions) == 0:  # No users mentioned directly
            mentions.append(await commands.MemberConverter().convert(ctx, member))

        # Handle to access guild
        handle = Database.Cogs[self.name][ctx.author.guild.id]["users"]

        words = ctx.message.content.split()
        emojiRaw = words[len(words) - 1]

        mentionedUser = mentions[0]

        try:  # Check if it is a custom emoji.
            emoji = await commands.EmojiConverter().convert(ctx, emojiRaw)
            emoji = str(emoji)

        except:  # Not a custom on this server, must be a regular emoji
            emoji = emojiRaw

        # Read the users data
        self.get_user_data(mentionedUser)

        # Check if the emoji is already in the list so we don't add it a second time.
        if emoji not in handle[mentionedUser.id].get("emojis", []):

            try:
                # We are responding with the emoji the user requested, primarily as a test
                # to see if the emoji is valid. If it's not, it throws a HTTPException code 10014
                await ctx.message.add_reaction(
                    emoji
                )  # Add the emoji the user requested.

            except discord.HTTPException as e:
                if e.code == 10014:
                    await ctx.send(
                        f"Sorry, but discord doesn't have that emoji in it's reaction library."
                    )

                    # Send failure to the user
                    await Utils.send_failure(self, ctx.message)

                    # We don't want to try adding the bad emoji to the database, so returning.
                    return

                elif e.code == 50013:
                    await ctx.send(
                        f"I'm sorry, but I'm not allowed to add reactions to messages."
                    )
                    return

                else:  # A different error code
                    # Send failure to the user
                    await Utils.send_failure(self, ctx.message)

                    # Send the error to the console so we can figure out the cause of it.
                    Utils.error_to_console(ctx, e)
                    return

            # Add the reaction to the existing list
            handle[mentionedUser.id]["emojis"].append(emoji)

            # Save the changes
            self.write_user_data(mentionedUser)

            # Send confirmation to the user
            await Utils.send_confirmation(self, ctx.message)

        else:
            await ctx.send(
                f"{emoji} is already in the list for {mentions[0].display_name}."
            )

    @react_to_messages.command(name="del", aliases=["remove"])
    @commands.guild_only()
    @Permissions.check(permission=["add_reactions"])
    async def _del(self, ctx, member, emojiRaw):
        """
		Remove a reaction from the list of reactions

		Usage: del (User) (An Emoji)

		You can either mention a user, use their name or
		name#discriminator without mentioning the user.
		If name#discriminator has a space, wrap it in quotes.

		For the Emoji, send any guild or regular emoji.
		If it doesn't appear when you send it, you will
		get an Invalid Argument error.

		Default Permissions: add_reactions permission
		"""

        mentions = ctx.message.mentions

        # If the member wasn't mentioned, run it through the converter to get a member object
        if len(mentions) == 0:  # No users mentioned directly
            mentions.append(await commands.MemberConverter().convert(ctx, member))

        # Handle to access guild
        handle = Database.Cogs[self.name][ctx.author.guild.id]["users"]

        # words = ctx.message.content.split()
        # emojiRaw = words[len(words)-1]

        mentionedUser = mentions[0]

        # Read the users data
        self.get_user_data(mentionedUser)

        if len(handle[mentionedUser.id]) == 0:
            # The user doesn't have any reactions set, so we're done here.
            await Utils.send_confirmation(self, ctx.message)
            return

        try:  # Check if it is a custom emoji.
            emoji = await commands.EmojiConverter().convert(ctx, emojiRaw)
            emoji = str(emoji)

        except:  # Not a custom on this server, must be a regular emoji
            emoji = emojiRaw

        if emoji in handle[mentionedUser.id]["emojis"]:
            # Remove the reaction from the list.
            handle[mentionedUser.id]["emojis"].remove(emoji)

            # Save the changes
            self.write_user_data(mentionedUser)

            # Send confirmation to the user
            await Utils.send_confirmation(self, ctx.message)

        else:
            # Send failure to the user
            await Utils.send_failure(self, ctx.message)

    @react_to_messages.command(name="list")
    @commands.guild_only()
    @Permissions.check(permission=["add_reactions"])
    async def _list(self, ctx, member):
        """
		Lists the reactions for a user.

		Usage: listreactions (User)

		You can either mention a user, use their name or
		name#discriminator without mentioning the user.
		If name#discriminator has a space, wrap it in quotes.

		Default Permissions: add_reactions permission
		"""

        mentions = ctx.message.mentions

        # If the member wasn't mentioned, run it through the converter to get a member object
        if len(mentions) == 0:  # No users mentioned directly
            mentions.append(await commands.MemberConverter().convert(ctx, member))

        # Handle to access guild
        handle = Database.Cogs[self.name][ctx.author.guild.id]["users"]

        mentionedUser = mentions[0]

        # Read the users data
        self.get_user_data(mentionedUser)

        if len(handle[mentionedUser.id]["emojis"]) == 0:
            # The user doesn't have any reactions set, so we're done here.
            await ctx.send(f"{mentionedUser.display_name} has no reactions set.")

        else:

            output = f"{mentionedUser.display_name} has the following reactions randomly added to their messages: "
            for each in handle[mentionedUser.id]["emojis"]:
                output += each

            await ctx.send(output)

    @add.error
    @_del.error
    @_list.error
    async def _errors(self, ctx, error):
        await Utils.errors(self, ctx, error)


def setup(client):
    """
	setup
	"""
    logger.info(f"Loading {__name__}...")
    client.add_cog(ReactToMessages(client))
    logger.info(f"Loaded {__name__}")
