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


class BanHammer(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.name = "BanHammer"

    @commands.Cog.listener()
    async def on_member_join(self, member):
        naughty_list = [486042866901188628, 581888665244925952]
        if member.id in naughty_list:
            # Ban
            await member.guild.ban(member, reason="Auto-Ban for being on Naughty-List")

    @commands.Cog.listener()
    async def on_member_ban(self, guild, member):
        channels = dict()
        channels[369243434080272385] = 466048561994268682  # Addohms/mods
        channels[378302095633154050] = 378302095633154052  # Myserver/general
        if guild.id in channels.keys():
            channel: discord.TextChannel = self.client.get_channel(channels[guild.id])
            await channel.send(f"{member.name} banned.")


def setup(client):
    """
	BanHammer setup
	"""
    logger.info(f"Loading {__name__}...")
    client.add_cog(BanHammer(client))
    logger.info(f"Loaded {__name__}")
