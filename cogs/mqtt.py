# -*- coding: utf-8 -*-
"""
Discord Bot for HardwareFlare and others
@author: Tisboyo
"""

import logging

import discord
from discord.ext import commands

# import paho.mqtt.publish as mqtt_publish
from asyncio_mqtt import Client as mqttClient

# from datetime import datetime

from util.database import Database
from util.permissions import Permissions
from util.utils import Utils

from os import getenv

logger = logging.getLogger(__name__)


class MQTT(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.name = "mqtt"
        self.mqtt_server = getenv("mqtt_server")

    @commands.Cog.listener()
    async def on_ready(self):
        # Send an update for all of the guilds on startup
        for guild in self.client.guilds:
            await self.publish_member_count(guild.id, guild.member_count)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        # Publish member count when someone joins
        await self.publish_member_count(member.guild.id, member.guild.member_count)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        # Publish member count when someone leaves
        await self.publish_member_count(member.guild.id, member.guild.member_count)

    async def publish_member_count(self, guild_id, count):
        # If a mqtt server is set, push the message to the mqtt server
        if self.mqtt_server:
            async with mqttClient(
                self.mqtt_server, port=1883, client_id="Boyo_Bot"
            ) as client:
                await client.publish(f"discord/{guild_id}/member_count", f"{count}")

    @commands.Cog.listener()
    async def on_message(self, message):
        # Guard Clause
        if (
            message.guild == None  # Not in a guild means DM or Group chat.
            or Database.Bot["sleeping"]  # If the bot is sleeping, don't do anything.
        ):
            return

    def cog_unload(self):
        logger.info(f"{__name__} unloaded...")


def setup(client):
    """
	MQTT setup
	"""
    logger.info(f"Loading {__name__}...")
    client.add_cog(MQTT(client))
    logger.info(f"Loaded {__name__}")
