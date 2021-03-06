# -*- coding: utf-8 -*-
"""
Discord Bot for HardwareFlare and others
@author: Tisboyo
"""
import logging

from discord.ext import commands

from util.permissions import Permissions
from util.utils import Utils

# import discord
# from util.database import Database

logger = logging.getLogger(__name__)


class Ping(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.command()
    @Permissions.check(role="everyone")
    async def ping(self, ctx):
        """
        The bot will respond with it's latency.

        Default Permissions: Everyone role
        """

        await ctx.send(f"Pong! {round(self.client.latency * 1000)}ms")

        logger.info(f"Pong! {round(self.client.latency * 1000)}ms")

    @ping.error
    async def _error(self, ctx, error):
        await Utils.errors(self, ctx, error)

    def cog_unload(self):
        logger.info(f"{__name__} unloaded...")


def setup(client):
    """
    Ping setup
    """
    logger.info(f"Loading {__name__}...")
    client.add_cog(Ping(client))
    logger.info(f"Loaded {__name__}")
