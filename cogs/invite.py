# -*- coding: utf-8 -*-
"""
Discord Bot for HardwareFlare and others
@author: Tisboyo
"""

import logging

import discord
from discord.ext import commands

from util.database import Database
from util.utils import Utils

logger = logging.getLogger(__name__)


class Invite(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.name = "invite"
        Database.Cogs[self.name] = dict()

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        # Have to reload Database.Cogs when joining a new guild to prevent errors.
        Database.readSettingsGuild(self, guild.id)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        # No point in holding stuff in memory for a guild we aren't in.
        if Database.Cogs[self.name].get(guild.id, False):
            Database.writeSettings(self, guild.id)
            del Database.Cogs[self.name][guild.id]

    @commands.Cog.listener()
    async def on_message(self, message):
        # Guard Clause
        if message.guild == None:  # Not in a guild means DM or Group chat.
            return

    @commands.command()
    async def invite(self, ctx):
        """
		Responds with a current invite link to share with friends.
		"""

        if ctx.guild.id == 425699298957852672:
            await ctx.send(
                "Feel free to share this invite link: https://discord.io/HardwareFlare"
            )
        elif ctx.guild.id == 378302095633154050:
            new_permission = discord.Permissions(ctx.guild.me.guild_permissions.value)
            inviteLink = discord.utils.oauth_url(
                ctx.guild.me.id, permissions=new_permission, guild=ctx.guild
            )
            await ctx.send(inviteLink)
        elif ctx.guild.id == 369243434080272385:
            await ctx.send("http://addohms.com/discord")

    @invite.error
    async def _error(self, ctx, error):
        await Utils.errors(self, ctx, error)


def setup(client):
    """
	Invite setup
	"""
    logger.info(f"Loading {__name__}...")
    client.add_cog(Invite(client))
    logger.info(f"Loaded {__name__}")
