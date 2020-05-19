# -*- coding: utf-8 -*-
"""
First created on Sun Jun 23 21:46:28 2019

Discord Bot for HardwareFlare and others
@author: Tisboyo

"""

import logging
import os
import datetime
from sys import version as python_version

import discord
from discord.ext import commands

import keys

# Load these after loading the cog so they are populated.
# from util.database import Database
# from util.utils import Utils

# Set logging level and format
logging.basicConfig(
    format="%(asctime)s %(levelname)s: %(name)s: %(message)s", level=keys.logging_level
)
logger = logging.getLogger(__name__)

# Get the bot Token
Token = keys.discord["token"]


def get_prefix(client, message):
    """Function used to return the server prefix"""
    # Check if we are in a DM. If so, use default prefix.
    if isinstance(message.channel, discord.DMChannel) or isinstance(
        message.channel, discord.GroupChannel
    ):
        prefix = "."
    else:
        # Check when the last time the database was queried for the prefix
        last_prefix_check = Database.Main[message.guild.id].get(
            "last_prefix_check", datetime.datetime.utcfromtimestamp(0)
        )
        now = datetime.datetime.utcnow()
        update_difference = datetime.timedelta(seconds=15)
        if now - last_prefix_check > update_difference:

            # Query for the prefix of the guild
            cursor = Database.cursor[message.guild.id]
            query = "SELECT setting_data FROM main WHERE setting_id = 'prefix' LIMIT 1"
            result = Database.dbExecute(None, cursor, message.guild.id, query)

            # If the database had a result, use it. Otherwise use the default
            if result is not None:
                prefix = Database.Main[message.guild.id]["prefix"] = result[0]
            else:
                prefix = "."

            # Update the last time we queried the prefix
            Database.Main[message.guild.id]["last_prefix_check"] = now
        else:
            # In between time checks, use get to return the default in case something doesn't update.
            prefix = Database.Main[message.guild.id].get("prefix", ".")

    return commands.when_mentioned_or(prefix)(client, message)


client = commands.Bot(command_prefix=get_prefix, case_insensitive=True)


@client.event
async def on_ready():

    logger.warning(f"Bot started in {len(client.guilds)} servers.")

    for each in client.guilds:
        logger.warning(f"Guild: {each} - {each.id}")

    logger.warning(f"Discord.py version: {discord.__version__}")
    logger.warning(f"Python version: {python_version}")

    logger.info(f"I can see {len(set(client.get_all_members()))} unique users.")


@client.command()
@commands.is_owner()
@commands.dm_only()
async def loadcog(ctx, extension):
    """Load a cog. (Bot owner and DM only.)"""

    logger.info(f"Loading {extension}...")  # Send a notice to the console
    client.load_extension(f"cogs.{extension}")
    await ctx.send(f"Loading {extension}.")
    Database.Bot["loaded_cogs"].append(extension)


@client.command()
@commands.is_owner()
@commands.dm_only()
async def unloadcog(ctx, extension):
    """Unload a cog. (Bot owner and DM only.)"""

    logger.info(f"Unloading {extension}")  # Send a notice to the console
    client.unload_extension(f"cogs.{extension}")
    await ctx.send(f"Unloading {extension}.")
    Database.Bot["loaded_cogs"].remove(extension)


@client.command()
@commands.is_owner()
@commands.dm_only()
async def listcog(ctx):
    """List loaded cogs to console (Bot owner and DM only)."""

    print(f"Printing loaded cogs".center(80, "*"))

    if len(Database.Bot["loaded_cogs"]) == 0:
        print(f"No cogs are loaded.")
        return

    # Loop through the cogs that are currently loaded.
    for each in Database.Bot["loaded_cogs"]:
        print(f"--> {each}")


# Always load these cogs
client.load_extension("util.database")
client.load_extension("util.permissions")
client.load_extension("util.utils")

# Load these after loading the cog so they are populated.
# Something changed in discord.py==1.3.0 that would recreate these objects
# instead of updating them to the same object. Loading them here makes
# them accessible throughout.
from util.database import Database
from util.utils import Utils

# Create our list of loaded cogs
Database.Bot["loaded_cogs"] = list()

# Add always loaded cogs to list
Database.Bot["loaded_cogs"].extend(["database", "permissions", "utils"])

for filename in os.listdir("./cogs"):
    if filename.endswith(".py") and not filename.startswith("__"):
        client.load_extension(f"cogs.{filename[:-3]}")
        Database.Bot["loaded_cogs"].append(filename[:-3])


@client.event
async def on_command_error(ctx, error):
    # Catch errors here if they aren't caught in the cog

    if hasattr(ctx.command, "on_error"):
        # If the command has it's own error return
        return

    elif isinstance(error, commands.CommandNotFound):
        # The console doesn't really need to know about unknown commands
        return

    else:
        # Call the util error handler
        Utils.error_to_console(ctx, error)
        return


if __name__ == "__main__":
    client.run(Token)
