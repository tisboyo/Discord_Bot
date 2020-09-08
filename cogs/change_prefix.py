# -*- coding: utf-8 -*-
"""
Discord Bot for HardwareFlare and others
@author: Tisboyo
"""

import logging

# import discord
from discord.ext import commands

from util.database import Database
from util.permissions import Permissions
from util.utils import Dictionary, Utils

logger = logging.getLogger(__name__)


class Prefix(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.name = "changeprefix"

        # No cog settings, nothing to read
        # Database.Cogs[self.name] = dict()

        # Database.readSettings(self)

    @commands.command()
    @commands.guild_only()
    @Permissions.check()
    async def changeprefix(
        self, ctx, prefix: commands.clean_content(escape_markdown=True)
    ):
        """
		Used to change the prefix for this guild.

		Usage: changeprefix (new prefix)

		Default Permissions: Guild Administrator only
		"""

        # Set it to memory
        Database.Main[ctx.guild.id]["prefix"] = prefix

        # database query
        cursor = Database.cursor[ctx.guild.id]
        query = "UPDATE main SET setting_data = ? WHERE setting_id = ? "
        values = (prefix, "prefix")
        Database.dbExecute(self, cursor, ctx.guild.id, query, values)

        await ctx.send(f"Command prefix has been updated to `{prefix}`")
        await ctx.message.add_reaction(Dictionary.check_box)

    @commands.command()
    @commands.guild_only()
    @Permissions.check(role="everyone")
    async def prefix(self, ctx):
        """
		Responds with the bot's prefix.

		Default Permissions: Everyone role
		"""

        prefix = Database.Main[ctx.guild.id]["prefix"]
        await ctx.send(f"The current prefix is `{prefix}`")

    @prefix.error
    @changeprefix.error
    async def _error(self, ctx, error):
        await Utils.errors(self, ctx, error)

    def cog_unload(self):
        logger.info(f"{__name__} unloaded...")


def setup(client):
    """
	Change prefix setup
	"""
    logger.info(f"Loading {__name__}...")
    client.add_cog(Prefix(client))
    logger.info(f"Loaded {__name__}")
