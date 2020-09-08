# -*- coding: utf-8 -*-
"""
Discord Bot for HardwareFlare and others
@author: Tisboyo
"""

import logging

import discord
from discord.ext import commands

from util.database import Database

# from util.permissions import Permissions

logger = logging.getLogger(__name__)


class Sleepybot(commands.Cog):
    """
    Sleepybot puts the bot to sleep, and sets it to offline.

    Add to each function that will sleep
    #If the bot is sleeping, don't do anything.
    if Database.Bot['sleeping']: return

    """

    def __init__(self, client):
        self.client = client
        Database.Bot["sleeping"] = False

    @commands.command()
    @commands.is_owner()
    @commands.dm_only()
    async def sleep(self, ctx):
        """Puts the bot to sleep. (Bot owner only.)"""

        await self.client.change_presence(status=discord.Status.invisible)

        Database.Bot["sleeping"] = True

        await ctx.send(
            f'Bot going to sleep.. will not respond again until `{Database.Main[ctx.guild.id].get("prefix", ".")}wake` is sent'
        )

    @commands.command()
    @commands.is_owner()
    @commands.dm_only()
    async def wake(self, ctx):
        """Wakes the bot up from sleep. (Bot owner only.)"""
        await self.client.change_presence(status=discord.Status.online)

        Database.Bot["sleeping"] = False

        await ctx.send("Huh? What? Oh... I'm awake.")

    def cog_unload(self):
        logger.info(f"{__name__} unloaded...")


def setup(client):
    """
    Sleepybot setup
    """
    logger.info(f"Loading {__name__}...")
    client.add_cog(Sleepybot(client))
    logger.info(f"Loaded {__name__}")
