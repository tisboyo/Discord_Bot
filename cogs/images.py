# -*- coding: utf-8 -*-
"""
Discord Bot for HardwareFlare and others
@author: Tisboyo
"""

import logging

import discord
from discord.ext import commands
import aiohttp
import asyncio

from util.database import Database
from util.permissions import Permissions
from util.utils import Utils

logger = logging.getLogger(__name__)


class Images(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.name = "images"

        Database.readSettings(self)

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
            message.guild == None
            or Database.Bot[  # Not in a guild means DM or Group chat.
                "sleeping"
            ]  # If the bot is sleeping, don't do anything.
        ):
            return

    @commands.command(aliases=["kitten"])
    @Permissions.check(role="everyone")
    async def cat(self, ctx):
        """
        Returns a Random Cat from http://random.cat

                Default Permissions: role="everyone"
        """

        async with ctx.channel.typing():
            async with aiohttp.ClientSession() as cs:
                async with cs.get("http://aws.random.cat/meow") as r:
                    data = await r.json()

                    embed = discord.Embed(title="Meow")
                    embed.set_image(url=data["file"])
                    embed.set_footer(text="http://random.cat")

                    await ctx.send(embed=embed)

    @commands.command(aliases=["puppy"])
    @Permissions.check(role="everyone")
    async def dog(self, ctx):
        """
        Returns a Random Dog from http://random.dog

                Default Permissions: role="everyone"
        """
        async with ctx.channel.typing():
            async with aiohttp.ClientSession() as cs:
                # Sometimes random.dog returns an mp4, which
                # embeds don't support, so looping will let us
                # get a different image
                try_count = 0
                while True:
                    try_count += 1
                    async with cs.get("http://random.dog/woof.json") as r:
                        data = await r.json()

                        # Check if an mp4 was returned and try again if so
                        if data["url"][-3:] == "mp4":
                            logger.warning(f"MP4 recieved: {data['url']}")

                            # If we get too many mp4's just give up.
                            # this is to prevent hitting the server too much
                            if try_count >= 3:
                                await ctx.send("Unable to get a valid image from random.dog. 😢")
                                return

                            asyncio.sleep(1)  # Lets not hammer the server
                            continue

                        embed = discord.Embed(title="Woof!")
                        embed.set_image(url=data["url"])
                        embed.set_footer(text="http://random.dog")

                        await ctx.send(embed=embed)
                        # Break out of the while True loop
                        return

    @commands.command()
    @Permissions.check(role="everyone")
    async def fox(self, ctx):
        """
        Returns a Random Fox from https://randomfox.ca/
        """
        async with ctx.channel.typing():
            async with aiohttp.ClientSession() as cs:
                async with cs.get("https://randomfox.ca/floof/") as r:
                    data = await r.json()

                    embed = discord.Embed(title="Floof")
                    embed.set_image(url=data["image"])
                    embed.set_footer(text="https://randomfox.ca/")

                    await ctx.send(embed=embed)

    @cat.error
    @dog.error
    async def _error(self, ctx, error):
        await Utils.errors(self, ctx, error)

    def cog_unload(self):
        logger.info(f"{__name__} unloaded...")


def setup(client):
    """
    Images setup
    """
    logger.info(f"Loading {__name__}...")
    client.add_cog(Images(client))
    logger.info(f"Loaded {__name__}")
