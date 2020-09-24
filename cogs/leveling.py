# -*- coding: utf-8 -*-
"""
Discord Bot for HardwareFlare and others
@author: Tisboyo
"""
import datetime
import json
import logging
import sqlite3

import discord
from discord.ext import commands

from util.database import Database
from util.permissions import Permissions
from util.utils import dotdict
from util.utils import Utils

logger = logging.getLogger(__name__)


class Levels(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.name = "levels"
        self.db_users_ver = 2
        Database.Cogs[self.name] = dict()

        Database.readSettings(self)

        for guild_id in Database.Main:
            if Database.Cogs[self.name][guild_id]["settings"].get("dbVer", 0) < self.db_users_ver:
                self.db_setup(guild_id)

    def db_setup(self, guild_id):

        current_ver = Database.Cogs[self.name][guild_id]["settings"].get("dbVer", 0)
        query = list()

        # Add queries to a list that need to be run
        if current_ver < 1:
            # Create the initial table
            query.append(
                """
                   CREATE TABLE IF NOT EXISTS levels(
                   user_id TEXT,
                   exp TEXT DEFAULT '0',
                   level TEXT DEFAULT '0',
                   messages TEXT DEFAULT '0',
                   words TEXT DEFAULT '0',
                   lastseen TEXT DEFAULT '0',
                   lastseenurl TEXT DEFAULT NULL,
                   lastexp TEXT DEFAULT NULL,
                   nickname_history TEXT DEFAULT NULL,
                   upvotes TEXT DEFAULT '0',
                   downvotes TEXT DEFAULT '0',
                   PRIMARY KEY("user_id")
                   )
                   """
            )
            current_ver = 1

        if current_ver < 2:
            # Change the name of the table to more accurately reflect it's use
            query.append("ALTER TABLE levels RENAME TO users")
            current_ver = 2

        # If there are any queries, execute them.
        if len(query) > 0:
            cursor = Database.cursor[guild_id]
            for each in query:
                try:
                    Database.dbExecute(self, cursor, guild_id, each, list(), True)
                    logger.info(f"Executed: {query}")

                except sqlite3.OperationalError as e:
                    logger.critical(e)

        # Store the new dbVer and write that back to the cog settings
        Database.Cogs[self.name][guild_id]["settings"]["dbVer"] = current_ver
        Database.writeSettings(self, guild_id)

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.client.guilds:
            if not Database.Cogs[self.name][guild.id]["settings"].get("firstRunSetup", 0):
                await self.first_run_setup(guild)

    def first_run_setup(self, guild):
        logger.info(f"[levels] Loading existing guild members into database for {guild.id}")

        cursor = Database.cursor[guild.id]

        # Load the members currently in the database
        query = "SELECT user_id FROM users"
        db_members = Database.dbExecute(self, cursor, guild.id, query, list(), True)

        # Create a list of members currently in the database
        db_member_list = list()
        for member in db_members:
            db_member_list.append(int(member[0]))

        # Loop through the existing members
        for member in guild.members:
            # Check if the guild member is already in the database
            if member.id not in db_member_list:
                # Insert the member into the database
                query = """INSERT OR IGNORE INTO
                users(user_id, exp, level, words, messages, lastseen, lastseenurl)
                VALUES(?,?,?,?,?,?,?)"""
                values = (member.id, 0, 0, 0, 0, 0, None)
                # We don't need to save the result of this
                Database.dbExecute(self, cursor, member.guild.id, query, values)

        Database.Cogs[self.name][guild.id]["settings"]["firstRunSetup"] = 1
        Database.writeSettings(self, guild.id)

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        """Create all of the users after joining the guild"""
        Database.readSettingsGuild(self, guild.id)
        self.db_setup(guild.id)
        self.first_run_setup(guild)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """
        Insert the newly joined member into the levels table
        """

        cursor = Database.cursor[member.guild.id]

        # Insert the member into the database
        query = """INSERT OR IGNORE INTO
        users(user_id, exp, level, words, messages, lastseen, lastseenurl)
        VALUES(?,?,?,?,?,?,?)"""
        values = (member.id, 0, 0, 0, 0, 0, None)
        # We don't need to save the result of this
        Database.dbExecute(self, cursor, member.guild.id, query, values)

    def buildUserTable(self, guild_id):
        pass

    @commands.command()
    @commands.guild_only()
    @Permissions.check()
    async def setlevel(self, ctx, member, level: int):
        """
        Sets the users level.

        Use this command to manually set a user level.

        You can either mention a user, use their name or
        name#discriminator without mentioning the user.
        If name#discriminator has a space, wrap it in quotes.

        This is useful when migrating from another bot such as MEE6.

        Default Permissions: Guild Administrator only
        """

        # If the bot is sleeping, don't do anything.
        if Database.Bot["sleeping"]:
            return

        # Read in any mentions
        mentions = ctx.message.mentions

        # If the member wasn't mentioned, run it through the converter to get a member object
        if len(mentions) == 0:  # No users mentioned directly
            mentions.append(await commands.MemberConverter().convert(ctx, member))

        if len(mentions) > 0:
            # Database handle
            cursor = Database.cursor[ctx.guild.id]

            for each in mentions:
                # Get the users current level
                query = "SELECT exp, level FROM users where user_id = ?"
                vals = (each.id,)
                result = Database.dbExecute(self, cursor, ctx.guild.id, query, vals)

                exp = int(result[0])
                previousLevel = int(result[1])

                # Set the new level in the Database
                query = "UPDATE users SET exp = ?, level = ? WHERE user_id = ?"
                values = (exp, level, each.id)
                result = Database.dbExecute(self, cursor, ctx.guild.id, query, values)

                # Output to the calling user
                if previousLevel <= level:
                    output = f"{each.mention}'s level has been updated from {previousLevel} to {level}"

                else:
                    output = (
                        f"{each.mention} must have been naughty for you reduce their level from {previousLevel} to {level}"
                    )

                await ctx.send(output)

    @commands.command()
    @commands.guild_only()
    @Permissions.check(role="everyone")
    async def level(self, ctx, member):
        """
        Display the users level.

        Use this command to see the mentioned users level.

        You can either mention a user, use their name or
        name#discriminator without mentioning the user or
        the users snowflake UID.
        If name#discriminator has a space, wrap it in quotes.

        Default Permissions: Everyone role
        """

        # Read in any mentions
        mentions = ctx.message.mentions

        # If the member wasn't mentioned, run it through the converter to get a member object
        if len(mentions) == 0:  # No users mentioned directly

            # User ID sent as the query
            if member.isnumeric() and len(member) == 18:
                # Manually build mentions from uid passed
                new_member = dict()
                new_member["id"] = int(member)
                new_member["display_name"] = f"UID: {member}"
                new_member["avatar_url"] = "https://cdn.discordapp.com/embed/avatars/1.png"
                member = dotdict(new_member)
                mentions.append(member)

            # Run what was mentioned through the converter to get a member object
            else:
                mentions.append(await commands.MemberConverter().convert(ctx, member))

        if len(mentions) > 0:
            # Database handle
            cursor = Database.cursor[ctx.author.guild.id]

            for each in mentions:

                query = (
                    "SELECT exp, level, words, messages, lastseen, lastseenurl, upvotes, downvotes "
                    "FROM users where user_id = ?"
                )
                vals = (each.id,)
                result = Database.dbExecute(self, cursor, ctx.guild.id, query, vals)

                # Set the display name if they have one set, otherwise use the account name.
                displayName = each.display_name

                embed = discord.Embed(title=f"Statistics for {displayName}")
                embed.set_thumbnail(url=each.avatar_url)
                if result is None:
                    # User isn't in the database
                    embed.add_field(name="Lurker?", value=f"{displayName} hasn't been seen.")

                else:
                    embed.add_field(name="Level", value=f"{result[1]}")
                    embed.add_field(name="Experience", value=f"{result[0]}")
                    embed.add_field(name="Words spoken", value=f"{result[2]}")
                    embed.add_field(name="Messages sent", value=f"{result[3]}")
                    embed.add_field(name="Last seen", value=f"[{result[4]}]({result[5]})")
                    if Database.Cogs["karma"][ctx.guild.id]["settings"]["enabled"]:
                        embed.add_field(
                            name="Karma",
                            value=f"Upvotes: {result[6]} \r\nDownvotes: {result[7]}",
                        )

            await ctx.send(content=None, embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message):
        # Guard Clause
        if (
            message.author.bot
            or len(message.content) == 0  # No points for bots
            or message.guild is None  # No message contents, users join/leave/reactions
            or message.content[0]  # Not in a guild means DM or Group chat.
            == Database.Main[message.guild.id].get("prefix", ".")  # No points for commands
        ):
            return  # Abort abort!

        # How many words are in the message
        wordCount = self.countWords(message)

        # Database handle
        cursor = Database.cursor[message.author.guild.id]

        # What is the current experience.
        query = "SELECT exp, level, words, messages, lastexp FROM users WHERE user_id = ?"
        values = (message.author.id,)
        result = Database.dbExecute(self, cursor, message.guild.id, query, values)

        # If they aren't in the database result = None, Insert the user
        if result is None:

            query = "INSERT INTO users(user_id, exp, level, words, messages, lastseen, lastseenurl) VALUES(?,?,?,?,?,?,?)"
            values = (message.author.id, 0, 0, 0, 0, 0, None)
            # We don't need to save the result of this
            Database.dbExecute(self, cursor, message.guild.id, query, values)
            # Lets set some default values
            # using str(datetime.datetime.now()) because that is how it's read from the database
            result = [0, 0, wordCount, 1, str(datetime.datetime.now())]

        # The if statements take care of blank fields in the database by giving a default value
        # Blank responses shouldn't happen unless they are a new user
        exp = int(result[0]) if result[0] is not None else 0
        level = int(result[1]) if result[1] is not None else 0
        words = int(result[2]) + wordCount if result[2] is not None else wordCount
        messages = int(result[3]) + 1 if result[3] is not None else 1
        lastexp = result[4] if result[4] is not None else str(datetime.datetime.now())

        # Convert time from database to a datetime object
        t_format = "%Y-%m-%d %H:%M:%S.%f"
        lastexp = datetime.datetime.strptime(lastexp, t_format)

        # Check if it has been at least 60 seconds since last message
        timeSince = datetime.datetime.now() - lastexp
        if timeSince.seconds > 60:
            # Add experience and increase level if needed
            exp, level = self.gainExperience(exp, level, wordCount)
            lastexp = datetime.datetime.now()

        # Update to their new values
        query = (
            "UPDATE users SET exp = ?, level = ?, words = ?, messages = ?, "
            "lastseen = ?, lastseenurl = ?, lastexp = ? WHERE user_id = ?"
        )
        values = (
            exp,
            level,
            words,
            messages,
            message.created_at,
            message.jump_url,
            lastexp,
            message.author.id,
        )
        result = Database.dbExecute(self, cursor, message.guild.id, query, values)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        """
        When a member changes their nickname, store the old one in the database.
        """

        # Guard Clause
        if before.nick == after.nick:  # nickname wasn't changed
            return

        # database query
        cursor = Database.cursor[before.guild.id]
        query = "SELECT nickname_history FROM users WHERE user_id = ?"
        values = (before.id,)
        query_result = Database.dbExecute(self, cursor, before.guild.id, query, values)

        # Create our nickname_history list, either from the query or blank if no results
        if query_result[0] is not None:
            # Extract just the first row, as there is only one
            nickname_history = json.loads(query_result[0])
        else:
            # Create an empty list
            nickname_history = list()

        # Save for comparison later
        nickname_original = nickname_history.copy()

        if before.nick is not None:  # Save the old nickname
            # No need to check if it's in the database, because we always
            # prune dupes before writing.
            nickname_history.append(before.nick)

        # If the new nickname is in the history, remove it.
        if after.nick in nickname_history:
            nickname_history.remove(after.nick)

        # In the event a duplicate makes it to the list, remove it. Also sorts the list
        nickname_history = list(set(nickname_history))
        nickname_history.sort()

        if nickname_original != nickname_history:
            # Write back to the database if any changes were made
            new_history = json.dumps(nickname_history)
            query = "UPDATE users SET nickname_history = ? WHERE user_id = ?"
            values = (new_history, before.id)
            Database.dbExecute(self, cursor, before.guild.id, query, values)

    def countWords(self, message):
        """
        countWords(message)

        returns number of words that count as an int.
        """
        text = message.content
        splitText = sorted(text.split(), key=len)

        if "```" in splitText:
            return 1  # 1 point for quotes

        count = 0

        # Count the number of words that are equal to or over a specified length
        minLength = 3
        for each in range(len(splitText)):
            if len(splitText[each]) >= minLength:  # Minimum 3 characters to count as a word
                count += 1
        return count

    def gainExperience(self, exp, level, wordCount):
        """
        gainExperience(self, exp, level, wordCount)

        returns exp as int, level as int

        Figures out and returns the new values for exp and level
        Uses the mee6 formula for levels of 5 * (lvl ^ 2) + 50 * lvl + 100
        Plus some secret sauce for exp
        """
        # figure out experience for this messages
        wordExp = wordCount
        # 1 point per word, minimum 5 points, max 25.
        if wordExp < 5:
            wordExp = 5
        if wordExp > 25:
            wordExp = 25

        # Add our new exp to the old
        exp += wordExp

        # Figure out if experience exceeds the limit for the next level
        expNeeded = 5 * (level ** 2) + 50 * level + 100

        # increase level if so.
        if exp >= expNeeded:
            level += 1
            exp = 0

        return (exp, level)

    @setlevel.error
    @level.error
    async def _error(self, ctx, error):
        await Utils.errors(self, ctx, error)

    def cog_unload(self):
        logger.info(f"{__name__} unloaded...")


def setup(client):
    """
    Leveling setup
    """
    logger.info(f"Loading {__name__}...")
    client.add_cog(Levels(client))
    logger.info(f"Loaded {__name__}")
