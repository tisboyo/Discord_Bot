# -*- coding: utf-8 -*-
"""
Discord Bot for HardwareFlare and others
@author: Tisboyo
"""

import logging
import asyncio
import datetime
from collections import namedtuple
import pyttsx3

import discord
from discord.ext import commands

from util.database import Database
from util.permissions import Permissions
from util.utils import Utils

logger = logging.getLogger(__name__)

# TODO Add guild specific settings, time to delete, Lobby, DM message, category name
# TODO Add announcement channel setting to keep a track of bot changes


class Voice(commands.Cog):
    """
    Voice Channels

    The bot will monitor text channels that it can see,
    when you join the Lobby voice channel it will create a
    channel and move you to it with the same name of your
    last text channel message.
    """

    def __init__(self, client):
        self.client = client
        self.name = self.qualified_name

        Database.readSettings(self)

        # Used for keeping track of members currently streaming
        self.currently_streaming = list()

        # Category for voice channels
        self.category = "Topical Voice Chat"

        self.message_ttl_delta = datetime.timedelta(minutes=5)

        self.tts_engine = pyttsx3.init()
        self.lock = dict()

        for guild_id in Database.Main:
            # Database.Cogs[self.name][guild.id] = dict()
            self.lock[guild_id] = asyncio.Lock()

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

    # @commands.command()
    # async def lobby(self, ctx):

    @commands.Cog.listener()
    async def on_message(self, message):

        # Guard Clause
        if (
            message.guild == None  # Not in a guild means DM or Group chat.
            or message.author.bot  # Ignore bots
        ):
            return

        last_message_channels = Database.Cogs[self.name][message.guild.id]

        nt = namedtuple("last_message", "channel time")
        last_message_channels[message.author.id] = nt(
            channel=message.channel, time=datetime.datetime.now()
        )

    @commands.command()
    @Permissions.check(role="everyone")
    async def tts(self, ctx, *, message):
        """
        Send a text to speech message in the voice channel associated with the text channel.
        """

        tts_engine = self.tts_engine
        voice_channel = self.get_voice_channel_by_name(
            ctx.guild, ctx.message.channel.name
        )

        if (
            # Unable to find a voice channel with the name of the current text channel
            voice_channel == None
            # Author is not in voice at all
            or ctx.message.author.voice == None
            # Author is not in the right voice channel
            or ctx.message.author.voice.channel != voice_channel
        ):

            await ctx.send(
                f"Sorry, you have to be in voice channel with the name `{ctx.message.channel.name}`"
            )
            await ctx.message.add_reaction("🚫")
            return

        remove_reaction = False

        if self.lock[ctx.guild.id]:
            await ctx.message.add_reaction("⏳")
            remove_reaction = True

        async with self.lock[ctx.guild.id]:
            # Remove wait emoji
            if remove_reaction:
                await ctx.message.remove_reaction("⏳", ctx.guild.me)

            # Connect to the appropriate voice channel
            voice_client = await voice_channel.connect()

            # Set the bot's voice
            voices = tts_engine.getProperty("voices")
            tts_engine.setProperty("voice", voices[1].id)

            # Set the bot's speed
            tts_engine.setProperty("rate", 110)

            # Set the bot's volume

            if len(message) > 300:
                message = (
                    message[:300]
                    + f"........ you know what, forget reading all this get a microphone {ctx.message.author.name}."
                )

            tts_engine.save_to_file(
                f"{ctx.message.author.name} says {message}", "voice.wav"
            )
            tts_engine.runAndWait()

            voice_client.play(discord.FFmpegPCMAudio("voice.wav"))

            while voice_client.is_playing():
                await asyncio.sleep(0.1)

            await voice_client.disconnect()

            await ctx.message.add_reaction("✔️")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """
        """
        # Guard Clause
        if member.bot:  # Ignore any bots in voice
            return

        guild = member.guild

        if before.channel and after.channel:
            if before.channel.id != after.channel.id:
                # User switched voice channels
                pass

            else:  # Something else happened
                if (
                    member.voice.self_stream
                    and member.id not in self.currently_streaming
                ):
                    # Member started streaming
                    Utils.starprint("Member started streaming")
                    self.currently_streaming.append(member.id)

                elif member.voice.self_deaf:
                    # Member self deafened
                    ...
                    Utils.starprint("Member self deafened")

                elif member.voice.self_mute:
                    # Member self muted
                    ...
                    Utils.starprint("Member self muted")

                else:
                    if (
                        member.id in self.currently_streaming
                        and not member.voice.self_stream
                    ):
                        # Member stopped streaming
                        Utils.starprint("Member stopped streaming")
                        self.currently_streaming.remove(member.id)

        if after.channel is not None:  # Member joined a voice channel
            if after.channel.name == "Lobby":  # Member joined the Lobby
                await self.member_joined_lobby(member, guild, after)

        if before.channel is not None:  # Member left the voice channel
            await self.member_left_voice_channel(member, guild, before)

    async def dm_member(
        self, member: discord.Member, expired_message: bool = False,
    ):
        if not expired_message:
            # DM the user a friendly note.
            await member.send(
                "Well this is embarrassing ... :flushed:\r\n"
                f"I haven't seen you talking in a channel in `{member.guild.name}` since I woke up. :sleeping: \r\n"
                "The next channel you speak in, will be the one I create for you. \r\n"
                "If you don't speak in a text channel in the next 60 seconds, I will "
                "remove you from the Lobby."
            )
        else:
            await member.send(
                f"I haven't seen a message from you in the last {self.message_ttl_delta}. \r\n"
                "Could you please send a message in the channel that you "
                "would like to create. \r\nIn 60 seconds you will be removed "
                "from the Lobby."
            )

    async def get_last_message(
        self,
        member: discord.Member,
        guild: discord.Guild,
        expired_message: bool = False,
    ):

        await self.dm_member(member, expired_message=expired_message)

        # Default to kicking the user, until we prove otherwise
        kick_from_lobby = True

        last_message_channels = Database.Cogs[self.name][guild.id]

        # TODO MAYBE! If a denied error occurs when sending the DM,
        # Join the voice channel as the bot and read them the message.
        # Or maybe just do that in all cases.

        # Wait and see if the user has said anything yet.
        for _ in range(60, 0, -1):
            await asyncio.sleep(1)

            if last_message_channels.get(member.id, False):
                last_message = last_message_channels[member.id]

                # Message is in the last five minutes, so it's valid.
                if not self.is_message_expired(last_message):
                    kick_from_lobby = False
                    break

        if kick_from_lobby:
            # No message in memory OR the message is more than 5 minutes old
            await self.kick_from_voice_channel(member)
            return None

        return last_message

    def is_message_expired(self, message) -> bool:
        """Check if the message is expired"""

        message_expires = datetime.datetime.now() - self.message_ttl_delta

        if message_expires <= message.time:
            return False
        elif message_expires > message.time:
            return True
        else:
            return None

    async def kick_from_voice_channel(self, member: discord.Member):
        await member.move_to(None, reason="Kicked by Bot")

    async def member_joined_lobby(
        self, member: discord.Member, guild: discord.Guild, after
    ):
        """
        Handles when a member joins the voice chat lobby
        """

        last_message_channels = Database.Cogs[self.name][guild.id]

        # Get the user last_message information
        try:
            # Retrieve the last message by the user
            last_message = last_message_channels[member.id]

        except KeyError:  # User doesn't have a last message sent.
            # Bot may have been offline or rebooted since the last message.
            last_message = await self.get_last_message(member, guild)

            if last_message is None:
                return

        # Check to make sure the message is not more than 5 minutes old
        if self.is_message_expired(last_message):
            last_message = await self.get_last_message(member, guild, True)

            # If last_message returns None, return.
            if not last_message:
                return

        category = self.get_category_by_name(guild, self.category)

        # Establish the permissions needed for the new channel
        overwrites = last_message.channel.overwrites

        # Check if the channel exists already
        channel = self.get_voice_channel_by_name(guild, last_message.channel.name)

        if channel is None:  # Create it
            # TODO Add reason for creation
            try:
                channel = await guild.create_voice_channel(
                    last_message.channel.name, category=category, overwrites=overwrites
                )
            except discord.HTTPException as e:
                if e.code == 50013:
                    logger.warning(
                        f"Missing Permissions to create voice channel in {guild}."
                    )

                    # TODO DM Server Owner for permissions.
                return

        # Checking to make sure the channel actually exists, in case of a creation error
        if channel is not None:
            try:
                await member.move_to(channel)

            except discord.HTTPException as e:
                if e.code == 50013:
                    # Missing Permissions error
                    logger.warning(
                        f"Missing Permissions to move a user to another channel in {guild}"
                    )
                    return

    async def member_left_voice_channel(self, member, guild, before):
        """
        Member left the voice channel
        """

        if before.channel.category == self.get_category_by_name(guild, self.category):
            if len(before.channel.members) == 0:
                text_channel = self.get_text_channel_by_name(guild, before.channel.name)

                # Either a channel wasn't found, or the bot doesn't have permissions in it
                if text_channel is None:
                    return

                await text_channel.send(
                    f"Voice channel `{before.channel.name}` is now empty, and will be deleted in 60 seconds. \r\n"
                    f"Joining `{before.channel.name}` will keep it active."
                )

                # Wait 60 seconds to allow someone to re-join
                for _ in range(60):
                    await asyncio.sleep(1)

                    # Someone has joined
                    if len(before.channel.members) > 0:
                        return

                # If the channel is still empty, delete it.
                if len(before.channel.members) == 0:
                    await before.channel.delete()
                    await text_channel.send(
                        "Voice channel has been deleted. Join `Lobby` to re-create."
                    )

    def get_text_channel_by_name(self, guild, channel_name):
        """
        Get text channel object by channel_name
        """
        for channel in guild.channels:
            if (
                channel.name == channel_name
                and channel.type == discord.ChannelType.text
            ):
                # Check for bot permissions
                if channel.permissions_for(guild.me).send_messages:
                    return channel

        return None

    def get_voice_channel_by_name(self, guild, channel_name):
        """
        Get voice channel object by channel_name
        """
        for c in guild.channels:
            if c.name == channel_name and c.type == discord.ChannelType.voice:
                return c

        return None

    def get_category_by_name(self, guild, category_name):
        """
        Get category object by category name
        """
        for c in guild.categories:
            if c.name == category_name:
                return c

        return None

    # @Template.error

    async def _error(self, ctx, error):
        await Utils.errors(self, ctx, error)


def setup(client):
    """
	TempVoice setup
	"""
    logger.info(f"Loading {__name__}...")
    client.add_cog(Voice(client))
    logger.info(f"Loaded {__name__}")
