# -*- coding: utf-8 -*-
"""
Discord Bot for HardwareFlare and others
@author: Tisboyo
"""

import logging
import asyncio

import discord
from discord.ext import commands

from util.database import Database
from util.permissions import Permissions
from util.utils import Utils

logger = logging.getLogger(__name__)

# TODO Add guild specific settings, time to delete, Lobby, DM message, category name
# TODO Add announcement channel setting to keep a track of bot changes


class TempVoice(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.name = "tempvoice"

        Database.readSettings(self)

        # Used for keeping track of members currently streaming
        self.currently_streaming = list()

        # Category for voice channels
        self.category = "Topical Voice Chat"

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
            or message.author.bot  # Ignore bots
        ):
            return

        try:
            last_message = Database.Cogs[self.name][message.guild.id]
        except KeyError:
            last_message = Database.Cogs[self.name][message.guild.id] = dict()

        last_message[message.author.id] = message.channel

    # @commands.group(hidden=True)
    # @Permissions.check()
    # async def Template(self, ctx):
    #     """

    # 	Default Permissions:
    # 	"""
    #     # Guard Clause
    #     if ctx.guild == None:  # Not in a guild means DM or Group chat.
    #         return

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

    async def member_joined_lobby(self, member, guild, after):
        """
        Handles when a member joins the voice chat lobby
        """
        try:  # Get the last channels that messages have been sent in this guild.
            last_message_channels = Database.Cogs[self.name][guild.id]
        except KeyError:  # No messages have been sent in the guild yet.
            last_message_channels = Database.Cogs[self.name][guild.id] = dict()

        try:  # Get the last channel that this member sent a message in
            last_message_channel = last_message_channels[member.id]
        except:  # User doesn't have a last message sent.
            # Bot may have been offline or rebooted since the last message.

            # DM the user a friendly note.
            await member.send(
                "Well this is embarrassing ... :flushed:\r\n"
                f"I haven't seen you talking in a channel in `{member.guild.name}` since I woke up. :sleeping: \r\n"
                "The next channel you speak in, will be the one I create for you. \r\n"
                "If you don't speak in a text channel in the next 60 seconds, I will "
                "remove you from the Lobby."
            )

            # TODO MAYBE! If a denied error occurs when sending the DM,
            # Join the voice channel as the bot and read them the message.
            # Or maybe just do that in all cases.

            # Wait and see if the user has said anything yet.
            for _ in range(60, 0, -1):
                await asyncio.sleep(1)
                if last_message_channels.get(member.id, False):
                    last_message_channel = last_message_channels[member.id]
                    break

            if not last_message_channels.get(member.id, False):
                # User still hasn't joined a channel.
                # Kick user from Lobby TODO
                Utils.starprint(f"Kicking {member} from Lobby")
                await member.move_to(None, reason="Idling in the Lobby")

                return

        category = self.get_category_by_name(guild, self.category)

        # Establish the permissions needed for the new channel
        overwrites = last_message_channel.overwrites

        # Check if the channel exists already
        channel = self.get_voice_channel_by_name(guild, last_message_channel.name)

        if channel is None:  # Create it
            # TODO Add reason for creation
            channel = await guild.create_voice_channel(
                last_message_channel.name, category=category, overwrites=overwrites
            )

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
        for c in guild.channels:
            if c.name == channel_name and c.type == discord.ChannelType.text:
                return c

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
    client.add_cog(TempVoice(client))
    logger.info(f"Loaded {__name__}")
