# -*- coding: utf-8 -*-
"""
Discord Bot for HardwareFlare and others
@author: Tisboyo
"""

import logging
from datetime import datetime
import json

import discord
from discord.ext import commands
import aiohttp
import asyncio

from util.database import Database
from util.permissions import Permissions
from util.utils import Utils, Dictionary

from keys import twitch as twitch_settings

logger = logging.getLogger(__name__)


class Twitch(commands.Cog):
    client_id = twitch_settings["client_id"]
    oauth = twitch_settings["key"]
    streamers = dict()

    def __init__(self, client):
        self.client = client
        self.name = "twitch"

        Database.readSettings(self)

    @commands.Cog.listener()
    async def on_ready(self):
        for guild_id in Database.Main:
            settings = Database.Cogs[self.name][guild_id]["settings"].get(
                "streamers", None
            )

            Database.Cogs[self.name][guild_id]["streamers"] = dict()
            streamers = Database.Cogs[self.name][guild_id]["streamers"]

            if settings:
                streamers = json.loads(settings)

                for streamer, channel in streamers.items():
                    if not Twitch.streamers.get(streamer, False):
                        Twitch.streamers[streamer] = dict()
                        Twitch.streamers[streamer]["started_at"] = None
                        Twitch.streamers[streamer]["channels"] = set()

                    # Get a discord.TextChannel object
                    # Considered adding a delay, but this isn't an API call so it shouldn't matter
                    channel = self.client.get_channel(channel)

                    # Add to the global streamers notification
                    Twitch.streamers[streamer]["channels"].add(channel)

                    # Add to the guild list of streamers
                    Database.Cogs[self.name][guild_id]["streamers"][streamer] = channel

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        # Have to reload Database.Cogs when joining a new guild to prevent errors.
        Database.readSettingsGuild(self, guild.id)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        # No point in holding stuff in memory for a guild we aren't in.
        Database.writeSettings(self, guild.id)
        if Database.Cogs[self.name].get(guild.id, False):
            del Database.Cogs[self.name][guild.id]

    @commands.Cog.listener()
    async def on_message(self, message):
        # Guard Clause
        if (
            message.guild == None  # Not in a guild means DM or Group chat.
            or Database.Bot["sleeping"]  # If the bot is sleeping, don't do anything.
        ):
            return

    @commands.group(hidden=True)
    @Permissions.check()
    async def twitch(self, ctx):
        pass

    @twitch.command()
    @Permissions.check()
    async def add(self, ctx, streamer: str, discord_channel: discord.TextChannel):
        """
        Add a twitch channel to watch

		Default Permissions: Guild Administrator only
		"""
        # Guard Clause
        if ctx.guild == None:  # Not in a guild means DM or Group chat.
            return

        # Set the name to all lowercase for easier matching
        streamer = streamer.lower()

        if not Twitch.streamers.get(streamer, False):
            Twitch.streamers[streamer] = dict()
            Twitch.streamers[streamer]["started_at"] = None
            Twitch.streamers[streamer]["channels"] = set()

        # Add to the global streamers notification
        Twitch.streamers[streamer]["channels"].add(discord_channel)

        # Add to server specific settings
        q = Database.Cogs[self.name][ctx.guild.id]["streamers"]
        q[streamer] = discord_channel.id

        # Save to database
        Database.Cogs[self.name][ctx.guild.id]["settings"]["streamers"] = json.dumps(q)
        Database.writeSettings(self, ctx.guild.id)

        await ctx.message.add_reaction(Dictionary.check_box)

    @twitch.command(aliases=["del"])
    @Permissions.check()
    async def remove(self, ctx, streamer: str):
        """
        Remove twitch channel being watched

		Default Permissions: Guild Administrator only
		"""
        # Guard Clause
        if ctx.guild == None:  # Not in a guild means DM or Group chat.
            return

        # Set the name to all lowercase for easier matching
        streamer = streamer.lower()

        streamers = Database.Cogs[self.name][ctx.guild.id]["streamers"]
        if streamer in streamers.keys():
            # Delete from global list

            Twitch.streamers[streamer]["channels"].remove(streamers[streamer])

            if len(Twitch.streamers[streamer]["channels"]) == 0:
                del Twitch.streamers[streamer]

            # Delete from guild list
            del streamers[streamer]

            # Save to database
            Database.Cogs[self.name][ctx.guild.id]["settings"][
                "streamers"
            ] = json.dumps(streamers)
            Database.writeSettings(self, ctx.guild.id)

        await ctx.message.add_reaction(Dictionary.check_box)

    @twitch.command()
    @Permissions.check()
    async def owner(self, ctx, streamer: str, owner: discord.Member):
        """
        Associates a discord member as owner of a twitch channel
        """
        pass

    @add.error
    @remove.error
    async def _error(self, ctx, error):
        await Utils.errors(self, ctx, error)


async def get_twitch_status():
    """
    This is the actual loop that will post to the channels
    """

    # Check to make sure a client_id is set, otherwise return
    if not Twitch.client_id:
        return

    # Build URL parameters
    url = "https://api.twitch.tv/helix/streams"
    headers = {"Client-ID": Twitch.client_id, "Authorization": f"Bearer {Twitch.oauth}"}

    while True:
        params = {"user_login": list(Twitch.streamers.keys())}

        # If there aren't any streamers in the list, don't do any queries
        if len(Twitch.streamers) > 0:
            # Get the status
            async with aiohttp.ClientSession() as cs:
                async with cs.get(url, params=params, headers=headers) as r:
                    data = await r.json()

            for streamers in data["data"]:  # Walk through the returned json object
                user_name = streamers["user_name"].lower()
                started_at = streamers["started_at"]

                # Make sure we actually care about the streamer returned
                if Twitch.streamers.get(user_name, False) and (
                    Twitch.streamers[user_name].get("started_at", None) != started_at
                ):
                    for channel in Twitch.streamers[user_name]["channels"]:
                        logger.info(f"Announcing Twitch stream for {user_name}")
                        await channel.send(f"{user_name} streaming on twitch.")
                        Twitch.streamers[user_name]["started_at"] = started_at

        await asyncio.sleep(10)


def setup(client):
    """
	Twitch setup
	"""
    logger.info(f"Loading {__name__}...")
    # client.add_cog(Twitch(client))
    # client.loop.create_task(get_twitch_status())
    logger.info(f"Loaded {__name__}")
