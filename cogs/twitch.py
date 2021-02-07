# -*- coding: utf-8 -*-
"""
Discord Bot for HardwareFlare and others
@author: Tisboyo
"""
import asyncio
import json
import logging
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from io import BytesIO

import aiohttp
import discord
from discord.ext import commands

from keys import error_channel_webhook
from keys import twitch as twitch_settings
from util.database import Database
from util.permissions import Permissions
from util.utils import Dictionary
from util.utils import Utils

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
    next_live_query = datetime.min
    seconds_between_checks = 300  # Caching doesn't allow checking more frequently

    def __init__(self, client):
        self.client = client
        self.name = "twitch"

        Database.readSettings(self)

    @commands.Cog.listener()
    async def on_ready(self):
        for guild_id in Database.Main:
            settings = Database.Cogs[self.name][guild_id]["settings"].get("streamers", None)

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
                    Database.Cogs[self.name][guild_id]["streamers"][streamer] = channel_id

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
            message.guild is None  # Not in a guild means DM or Group chat.
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
        if ctx.guild is None:  # Not in a guild means DM or Group chat.
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

        # Reset the time check for downloading profiles pictures to force query with new channels
        Twitch.profile_update = datetime.max

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
        if ctx.guild is None:  # Not in a guild means DM or Group chat.
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

    @twitch.command(name="list")
    @Permissions.check()
    async def twitch_list(self, ctx, streamer: str = None):
        """
        Lists the Twitch channels and Discord channels they post in.
        """
        # Guard Clause
        if ctx.guild is None:  # Not in a guild means DM or Group chat.
            return

        # Wait until the on_ready has fired before proceeding.
        while not Twitch.ready:
            await asyncio.sleep(1)

        db = Database.Cogs[self.name][ctx.guild.id]["streamers"]

        embed = discord.Embed(title="Streams the bot is Watching for and the Channel they post in.")
        for streamer, channel in db.items():
            embed.add_field(name=f"{streamer}", value=f"<#{channel}>")

        embed.set_footer(text=f"Next Twitch query at: {Twitch.next_live_query}")
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
    async def get_twitch_profiles(cls):
        """
        Retrieves the streams profile information
        Primarily profile picture
        """

        users_url = "https://api.twitch.tv/helix/users"
        users_params = {"login": list(Twitch.streamers.keys())}

        async with aiohttp.ClientSession() as cs:
            async with cs.get(users_url, params=users_params, headers=Twitch.headers) as r:
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

    def cog_unload(self):
        logger.info(f"{__name__} unloaded...")


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

    first_loop = True

    while True:
        try:
            # Skips the sleep cycle for the first loop when the bot runs.
            if first_loop:
                first_loop = False
            else:
                sleep = Twitch.next_live_query - datetime.now(tz=timezone.utc)
                logger.debug(f"Sleeping for {sleep.seconds} seconds.")
                await asyncio.sleep(sleep.seconds)

            logger.debug("Starting Twitch status retrieval")
            streams_params = {"user_login": list(Twitch.streamers.keys())}

            # If there aren't any streamers in the list, don't do any queries
            if len(Twitch.streamers) > 0:
                # Get the status
                async with aiohttp.ClientSession() as cs:
                    async with cs.get(streams_url, params=streams_params, headers=Twitch.headers) as r:
                        streams_data = await r.json()

                        try:
                            streams_data = streams_data["data"]
                        except KeyError:
                            if streams_data.get("error", False):
                                if streams_data["message"] == "Invalid OAuth token":
                                    error_message = (
                                        "<@219518082266300417> Invalid Twitch Oauth token!! "
                                        f"https://id.twitch.tv/oauth2/authorize?response_type=token&client_id={Twitch.client_id}&redirect_uri=https://twitchapps.com/tokengen/ "  # noqa E501
                                    )
                                else:
                                    error_message = f"<@219518082266300417> Twitch: {streams_data['message']}"

                                logger.warning(f"{streams_data['status']} : {streams_data['message']}")
                            else:
                                logger.warning("Unknown KeyError")
                                error_message = "<@219518082266300417> Unknown KeyError in cogs.twitch.get_twitch_status"

                            # Send error to discord channel
                            if error_channel_webhook is not None:
                                async with aiohttp.ClientSession() as session:
                                    # Not catching the response, because if it errors it doesn't matter
                                    await session.post(
                                        error_channel_webhook,
                                        json={"content": error_message},
                                    )
                            else:
                                logger.warning("error_channel_webhook is not set")

                            continue
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
                        file = discord.File("images/twitch.jpg", filename="twitch-image.jpg")
                        # Set url to pass to discord
                        image_url = "attachment://twitch-image.jpg"

                        logger.info(f"Announcing Twitch stream for {user_name}")
                        embed = discord.Embed(
                            title=f"{streamers['user_name']} is live!",
                            url=f"https://twitch.tv/{user_name}",
                            timestamp=datetime.strptime(started_at, "%Y-%m-%dT%H:%M:%S%z"),  # 2020-09-08T19:30:09Z
                            color=discord.Color.green(),
                            type="rich",
                        )

                        # If user is baldengineer send a special image
                        if user_name == "baldengineer":  # TODO #27
                            date = datetime.now().strftime("%Y-%m-%d")
                            remote_image_url = f"https://baldengineer.com/thumbs/twitch-{date}.jpg"

                        else:
                            remote_image_url = streamers["thumbnail_url"].format(width=640, height=480)

                        # Download the embed image
                        async with aiohttp.ClientSession() as session:
                            async with session.get(remote_image_url) as resp:
                                if resp.status == 200:

                                    buffer = BytesIO(await resp.read())
                                    # Use response object as file object
                                    file = discord.File(buffer, filename="twitch-image.jpg")

                        embed.set_image(url=image_url)

                        embed.set_thumbnail(url=Twitch.profile_picture[user_name])
                        embed.add_field(
                            name=streamers["user_name"],
                            value=streamers["title"] if streamers["title"] else f"{streamers['user_name']} stream.",
                            inline=True,
                        )
                        embed.set_footer(text="Stream started")

                        live_message = f"{streamers['user_name']} is live on Twitch at https://twitch.tv/{user_name}"

                        # Log that we've already announced this stream
                        Twitch.streamers[user_name]["started_at"] = started_at

                        # Send the message
                        for channel in Twitch.streamers[user_name]["channels"]:
                            if file:  # If the file exists, send it
                                await channel.send(
                                    live_message,
                                    embed=embed,
                                    file=file,
                                )
                            else:  # Otherwise don't try to send file
                                await channel.send(
                                    live_message,
                                    embed=embed,
                                )

                    elif Twitch.streamers[user_name].get("started_at", None) == started_at:
                        logger.debug(f"{streamers['user_name']} is live but already announced.")

                logger.debug("Twitch statuses retrieved")

            # Save what time the next run will be, used in the list command
            Twitch.next_live_query = datetime.now(tz=timezone.utc) + timedelta(seconds=Twitch.seconds_between_checks)

        except aiohttp.client_exceptions.ClientConnectionError:
            logger.warning("Twitch connection error.")
            await asyncio.sleep(Twitch.seconds_between_checks)

        except Exception as e:
            logger.warning("Twitch loop exception!")
            logger.warning(e)
            logger.warning(type(e))
            await asyncio.sleep(Twitch.seconds_between_checks)


def setup(client):
    """
    Twitch setup
    """
    logger.info(f"Loading {__name__}...")
    client.add_cog(Twitch(client))
    client.loop.create_task(get_twitch_status())
    logger.info(f"Loaded {__name__}")
