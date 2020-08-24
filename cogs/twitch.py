# -*- coding: utf-8 -*-
"""
Discord Bot for HardwareFlare and others
@author: Tisboyo
"""

import logging
from datetime import datetime, timezone, timedelta
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

# TODO Add ability for individuals to be marked as owner of a channel, so they can set other parameters
# such as image, notification text (stripping out mentions if guild owner disables)
# needs to be done once a global database is established instead of individual databases for each guild
# so the settings can be global.


class Twitch(commands.Cog):
    client_id = twitch_settings["client_id"]
    oauth = twitch_settings["key"]
    headers = {"Client-ID": client_id, "Authorization": f"Bearer {oauth}"}
    streamers = dict()
    profile_picture = dict()
    view_count = dict()
    profile_update = datetime.max
    ready = False

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

                for streamer, channel_id in streamers.items():
                    if not Twitch.streamers.get(streamer, False):
                        Twitch.streamers[streamer] = dict()
                        Twitch.streamers[streamer]["started_at"] = None
                        Twitch.streamers[streamer]["channels"] = set()

                    # Get a discord.TextChannel object
                    # Considered adding a delay, but this isn't an API call so it shouldn't matter
                    channel = self.client.get_channel(channel_id)

                    # Add to the global streamers notification
                    # Stores discord.TextChannel objects
                    Twitch.streamers[streamer]["channels"].add(channel)

                    # Add to the guild list of streamers
                    # Stores an integer of the TextChannel ID
                    Database.Cogs[self.name][guild_id]["streamers"][
                        streamer
                    ] = channel_id

        # Let the rest of the bot know we're ready.
        Twitch.ready = True

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

    @commands.group()
    @Permissions.check()
    async def twitch(self, ctx):
        # Guard Clause
        if ctx.invoked_subcommand is not None:  # if subcommand was used.
            return

        await ctx.send_help(ctx.command)

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

        # Wait until the on_ready has fired before proceeding.
        while not Twitch.ready:
            await asyncio.sleep(1)

        # Set the name to all lowercase for easier matching
        streamer = streamer.lower()

        if not Twitch.streamers.get(streamer, False):
            Twitch.streamers[streamer] = dict()
            Twitch.streamers[streamer]["started_at"] = None
            Twitch.streamers[streamer]["channels"] = set()

        # Add to the global streamers notification
        Twitch.streamers[streamer]["channels"].add(discord_channel)

        # Add to server specific settings
        streamers = Database.Cogs[self.name][ctx.guild.id]["streamers"]
        streamers[streamer] = discord_channel.id

        await self.save_to_database(streamers, ctx.guild)

        await ctx.message.add_reaction(Dictionary.check_box)

    @twitch.command(aliases=["del"])
    @Permissions.check()
    async def remove(self, ctx, streamer: str, discord_channel: discord.TextChannel):
        """
        Remove twitch channel being watched

		Default Permissions: Guild Administrator only
		"""
        # Guard Clause
        if ctx.guild == None:  # Not in a guild means DM or Group chat.
            return

        # Wait until the on_ready has fired before proceeding.
        while not Twitch.ready:
            await asyncio.sleep(1)

        # Set the name to all lowercase for easier matching
        streamer = streamer.lower()

        streamers = Database.Cogs[self.name][ctx.guild.id]["streamers"]

        # Make sure we are even watching this streamer
        if streamer in streamers.keys():
            # Delete channel from global list
            Twitch.streamers[streamer]["channels"].remove(discord_channel)

            # If we aren't monitoring for any channels, delete the streamer completely
            if len(Twitch.streamers[streamer]["channels"]) == 0:
                del Twitch.streamers[streamer]

            # Delete from guild list
            del streamers[streamer]

            await self.save_to_database(streamers, ctx.guild)

            await ctx.message.add_reaction(Dictionary.check_box)

        else:
            await ctx.message.add_reaction(Dictionary.red_no_circle)

    @twitch.command(aliases=["list"])
    @Permissions.check()
    async def twitch_list(self, ctx, streamer: str = None):
        # Guard Clause
        if ctx.guild == None:  # Not in a guild means DM or Group chat.
            return

        # Wait until the on_ready has fired before proceeding.
        while not Twitch.ready:
            await asyncio.sleep(1)

        db = Database.Cogs[self.name][ctx.guild.id]["streamers"]

        embed = discord.Embed(
            title="Streams the bot is Watching for and the Channel they post in."
        )
        for streamer, channel in db.items():
            embed.add_field(name=f"{streamer}", value=f"<#{channel}>")

        await ctx.send(embed=embed)

    @twitch.command()
    @Permissions.check()
    async def owner(self, ctx, streamer: str, owner: discord.Member):
        """
        Associates a discord member as owner of a twitch channel
        """
        pass

    @twitch.error
    @add.error
    @remove.error
    @twitch_list.error
    @owner.error
    async def _error(self, ctx, error):
        await Utils.errors(self, ctx, error)

    async def save_to_database(self, streamers: dict, guild: discord.Guild):

        # Quick handle for settings
        settings = Database.Cogs[self.name][guild.id]["settings"]

        for streamer, channel in streamers.items():
            if isinstance(channel, discord.TextChannel):
                # Set the value to a text channel ID instead of a textchannel object
                streamers[streamer] = channel.id

        # Save to database
        settings["streamers"] = json.dumps(streamers)
        Database.writeSettings(self, guild.id)

    @classmethod
    async def get_twitch_profiles(self):
        """
        Retrieves the streams profile information
        Primarily profile picture
        """

        users_url = "https://api.twitch.tv/helix/users"
        users_params = {"login": list(Twitch.streamers.keys())}

        async with aiohttp.ClientSession() as cs:
            async with cs.get(
                users_url, params=users_params, headers=Twitch.headers
            ) as r:
                users_data = await r.json()
                users_data = users_data["data"]

        streamer_profile_picture = dict()
        streamer_view_count = dict()

        # Save streamer profile pictures
        for streamer in users_data:
            name = streamer["login"].lower()
            streamer_profile_picture[name] = streamer["profile_image_url"]
            streamer_view_count[name] = streamer["view_count"]

        Twitch.profile_picture = streamer_profile_picture
        Twitch.view_count = streamer_view_count
        Twitch.profile_update = datetime.now()


async def get_twitch_status():
    """
    This is the actual loop that will post to the channels
    """

    # Check to make sure a client_id is set, otherwise return
    if not Twitch.client_id:
        return

    # Build URL parameters
    streams_url = "https://api.twitch.tv/helix/streams"

    while not Twitch.ready:
        # Sleep until on_ready fires
        logger.info("Waiting for on_ready")
        await asyncio.sleep(1)

    while True:
        streams_params = {"user_login": list(Twitch.streamers.keys())}

        # If there aren't any streamers in the list, don't do any queries
        if len(Twitch.streamers) > 0:
            # Get the status
            async with aiohttp.ClientSession() as cs:
                async with cs.get(
                    streams_url, params=streams_params, headers=Twitch.headers
                ) as r:
                    streams_data = await r.json()
                    streams_data = streams_data["data"]

            # If we haven't gotten the profile pictures in the last hour, grab them
            if Twitch.profile_update > (datetime.now() + timedelta(hours=1)):
                await Twitch.get_twitch_profiles()

            for streamers in streams_data:  # Walk through the returned json object
                user_name = streamers["user_name"].lower()
                started_at = streamers["started_at"]

                # Make sure we actually care about the streamer returned
                if Twitch.streamers.get(user_name, False) and (
                    Twitch.streamers[user_name].get("started_at", None) != started_at
                ):
                    for channel in Twitch.streamers[user_name]["channels"]:
                        logger.info(f"Announcing Twitch stream for {user_name}")
                        embed = discord.Embed(
                            title=f"{streamers['user_name']} is live!",
                            url=f"https://twitch.tv/{user_name}",
                            timestamp=datetime.now(tz=timezone.utc),
                            color=discord.Color.green(),
                            type="rich",
                        )
                        embed.set_image(
                            url=streamers["thumbnail_url"].format(width=640, height=480)
                        )
                        embed.set_thumbnail(url=Twitch.profile_picture[user_name])
                        embed.add_field(
                            name=f"{streamers['user_name']}",
                            value=f"{streamers['title']}",
                            inline=True,
                        )
                        await channel.send(
                            f"{streamers['user_name']} is live on Twitch at https://twitch.tv/{user_name}",
                            embed=embed,
                        )
                        Twitch.streamers[user_name]["started_at"] = started_at
                elif Twitch.streamers[user_name].get("started_at", None) == started_at:
                    logger.debug(
                        f"{streamers[user_name]} is live but already announced."
                    )

        for x in range(60):
            logger.info(f"get_twitch_status sleeping {x} of 60")
            await asyncio.sleep(5)  # 300 = 5 Minutes
        logger.warning("get_twitch_status I'M AWAKE!!")


def setup(client):
    """
	Twitch setup
	"""
    logger.info(f"Loading {__name__}...")
    client.add_cog(Twitch(client))
    client.loop.create_task(get_twitch_status())
    logger.info(f"Loaded {__name__}")
