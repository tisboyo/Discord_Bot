# -*- coding: utf-8 -*-
"""
Discord Bot for HardwareFlare and others
@author: Tisboyo
"""

import logging

# import sqlite3
import datetime
import json

import discord
import discord.utils
from discord.ext import commands

from util.database import Database
from util.utils import Utils
from util.permissions import Permissions

logger = logging.getLogger(__name__)


class JoinLeave(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.name = "joinleave"

        Database.Cogs[self.name] = dict()

        self.datetimeformat = "%H:%M:%S on %Y/%m/%d"

        Database.readSettings(self)

    @commands.Cog.listener()
    async def on_guild_join(self, guild):

        Database.readSettingsGuild(self, guild.id)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        # No point in holding stuff in memory for a guild we aren't in.
        Database.writeSettings(self, guild.id)
        if Database.Cogs[self.name].get(guild.id, False):
            del Database.Cogs[self.name][guild.id]

    @commands.group()
    @commands.guild_only()
    @Permissions.check()
    async def userannounce(self, ctx):
        """
        Announce when members join or leave.

        Default Permissions: Guild Administrator only
        """
        # Guard Clause
        if ctx.invoked_subcommand is not None:  # if subcommand was used.
            return

        await ctx.send_help(ctx.command)

    @commands.command()
    @commands.guild_only()
    @Permissions.check(role="everyone")
    async def userinfo(self, ctx):
        """
        Displays a users info.

        Default Permissions: Everyone role
        """

        for member in ctx.message.mentions:
            await ctx.send(embed=self.build_embed(member))

    @userannounce.command(name="channel")
    @commands.guild_only()
    @Permissions.check()
    async def userannounce_channel(self, ctx, channel: discord.TextChannel):
        """
        Sets Join and Leave notification channel.

        Usage: userannounce channel #ChannelName

        Default Permissions: Guild Administrator only
        """

        # Check to make sure the bot has read and send messages permissions
        if not await self.channel_permissions_check(ctx, channel):
            # Send a notification if the bot doesn't have permissions
            await ctx.send("I do not have send and/or recieve permissions for that channel.")

            # and quit..
            return

        # Save the channel
        Database.Cogs[self.name][ctx.guild.id]["settings"]["joinNotificationChannel"] = channel

        Database.writeSettings(self, ctx.guild.id)

        # Send to new channel.
        await channel.send(f"User notifications will now be sent to {channel.mention}")

    @userannounce_channel.error
    async def userannounce_channel_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):

            # Get the channel object
            channel = Utils.get_channel(self, ctx.guild, "joinNotificationChannel")

            if channel:
                message = f"Current channel is {channel.mention}"
            else:
                # The setting was not set.
                message = "Channel is not set."

            await ctx.send(message)

            return

        await Utils.errors(self, ctx, error)

    @userannounce.command()
    @commands.guild_only()
    @Permissions.check()
    async def disable(self, ctx):
        """
        Disables notifiations.

        Usage: userannounce disable

        Default Permissions: Guild Administrator only
        """

        # Check if a channel is currently set, if not notify user and return
        if not Database.Cogs[self.name][ctx.guild.id]["settings"].get("joinNotificationChannel", False):
            await ctx.send("No notification channel was set.")
            return

        # Get the channel ID, establish handle to send message
        notificationChannel = Utils.get_channel(self, ctx.guild, "joinNotificationChannel")

        # Remove guild entry from dictionary
        Database.Cogs[self.name][ctx.guild.id]["settings"]["joinNotificationChannel"] = None

        # Write the settings to the database
        Database.writeSettings(self, ctx.guild.id)

        # Check to make sure the bot has read and send messages permissions
        if await self.channel_permissions_check(ctx, notificationChannel):
            # Send notification to original channel if permissions are there.
            await notificationChannel.send(f"Join and leave notifications have been disabled for this channel.")

    @userannounce.group()
    @commands.guild_only()
    @Permissions.check()
    async def age_notify(self, ctx):
        """
        Settings to notify on specified account age.

        Usage:
                age 1 (Specify number of days for account age to be notified)
                channel #channelname (Specify the channel to send the message in)
                message Your custom message here for the notification channel
                disable (Disables the notifications)
                status (Shows the current settings)

        Default Permissions: Guild Administrator only
        """

        # Guard Clause
        if ctx.invoked_subcommand is not None:  # if subcommand was used.
            return

        await ctx.send_help(ctx.command)

    @age_notify.command(name="status")
    @commands.guild_only()
    @Permissions.check()
    async def age_status(self, ctx):
        """
        Displays the current status of the account age notifications

        Default Permissions: Guild Administrator only
        """

        await self.send_age_check_reminders(ctx)

    @age_notify.command(name="disable")
    @commands.guild_only()
    @Permissions.check()
    async def age_disable(
        self,
        ctx,
    ):
        """
        Disables the age check notifications.

        Usage: userannounce age_notify Disables

        To restore set a new age.

        Default Permissions: Guild Administrator only
        """

        Database.Cogs[self.name][ctx.guild.id]["settings"]["notifyAccountAgeDays"] = None

        Database.writeSettings(self, ctx.guild.id)

        await ctx.send("Account age notifications disabled. Set an account age to re-enable.")

    @age_notify.command()
    @commands.guild_only()
    @Permissions.check()
    async def age(self, ctx, days):
        """
        Sets how old an account has to be before the bot automatically notifies.

        Usage: userannounce age_notify age 1

        Default Permissions: Guild Administrator only
        """

        if not days.isnumeric():
            # If a number was not passed, throw an error.
            await ctx.send("Invalid input. You must use only a whole number of days.")
            return

        Database.Cogs[self.name][ctx.guild.id]["settings"]["notifyAccountAgeDays"] = days

        Database.writeSettings(self, ctx.guild.id)

        await ctx.send(f"Age check set to {days} days.")
        await self.send_age_check_reminders(ctx)

    @age_notify.command(name="channel")
    @commands.guild_only()
    @Permissions.check()
    async def age_channel(self, ctx, channel: discord.TextChannel):
        """
        Sets the channel to send the notification to

        Usage: userannounce age_notify channel #channelname

        Default Permissions: Guild Administrator only
        """

        if not await self.channel_permissions_check(ctx, channel):
            await ctx.send("I do not have permission to send messages in that channel.")
            return

        Database.Cogs[self.name][ctx.guild.id]["settings"]["notifyAccountAgeChannel"] = channel

        Database.writeSettings(self, ctx.guild.id)

        await ctx.send(f"Age notification channel set to {channel.mention}")
        await self.send_age_check_reminders(ctx)

    @age_channel.error
    async def age_channel_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):

            # Get the channel object
            channel = Utils.get_channel(self, ctx.guild, "notifyAccountAgeChannel")

            if channel:
                message = f"Current channel is {channel.mention}"
            else:
                # The setting was not set.
                message = "Channel is not set."

            await ctx.send(message)

            return

        await Utils.errors(self, ctx, error)

    @age_notify.command()
    @commands.guild_only()
    @Permissions.check()
    async def message(self, ctx, *, message):
        """
        Sets the message to precede the embed of user information.

        This is useful for pinging you or your moderation team.

        Default Permissions: Guild Administrator only
        """

        # Save the message to the datebase
        Database.Cogs[self.name][ctx.guild.id]["settings"]["notifyAccountAgeMessage"] = message

        # Set here so new message would be included, quick access to settings
        settings = Database.Cogs[self.name][ctx.guild.id]["settings"]

        Database.writeSettings(self, ctx.guild.id)

        await ctx.send(f"Message set to:")
        await ctx.send(f"{settings['notifyAccountAgeMessage']}")
        await self.send_age_check_reminders(ctx)

    async def send_age_check_reminders(self, ctx):
        """
        Checks to ensure all of the age check settings are set, and sends a reminder if not.
        """

        settings = Database.Cogs[self.name][ctx.guild.id]["settings"]
        message = ""
        good = True

        if not settings.get("notifyAccountAgeDays", False):
            message += f"Reminder: You need to run `{Database.Main[ctx.guild.id]['prefix']}userannounce age_notify age` \n"
            good = False

        if not settings.get("notifyAccountAgeChannel", False):
            message += (
                f"Reminder: You need to run `{Database.Main[ctx.guild.id]['prefix']}userannounce age_notify channel` \n"
            )
            good = False

        if not settings.get("notifyAccountAgeMessage", False):
            message += (
                f"Reminder: You need to run `{Database.Main[ctx.guild.id]['prefix']}userannounce age_notify message` \n"
            )
            good = False

        if good == True:
            channel = Utils.get_channel(self, ctx.guild, "notifyAccountAgeChannel")
            message = f"Notification of account age has been enabled. \n"
            message += f"Channel: {channel.mention} \n"
            message += f"Account Age: {settings['notifyAccountAgeDays']} day(s)\n"
            message += f"Message: {settings['notifyAccountAgeMessage']}"

        if message:
            await ctx.send(message)

    @commands.Cog.listener()
    async def on_member_join(self, member):

        user = f"{member.name}#{member.discriminator}"
        guild = f"{member.guild.name}"
        output = f"{member.mention} {user} has joined {guild}"

        # Declare the variables to prevent comparing undeclared variables
        notificationChannel = None
        ageNotificationChannel = None

        # Send to console
        print(output)

        # Read the settings from the database to make sure they are up to date.
        Database.readSettingsGuild(self, member.guild.id)

        # Check to make sure a channel is set
        if Database.Cogs[self.name][member.guild.id]["settings"].get("joinNotificationChannel", False):

            # Set a handle for the notification channel
            notificationChannel = Utils.get_channel(self, member.guild, "joinNotificationChannel")

            output = f"A user has joined {guild} \n"

        if (
            Database.Cogs[self.name][member.guild.id]["settings"].get("notifyAccountAgeChannel", False)
            and Database.Cogs[self.name][member.guild.id]["settings"].get("notifyAccountAgeMessage", False)
            and Database.Cogs[self.name][member.guild.id]["settings"].get("notifyAccountAgeDays", False)
        ):

            # Grab settings for quick use
            settings = Database.Cogs[self.name][member.guild.id]["settings"]

            if not (member.joined_at - member.created_at) > datetime.timedelta(days=int(settings["notifyAccountAgeDays"])):
                # Account is not older than our specified number of days
                # Set the channel so the message will send.
                ageNotificationChannel = Utils.get_channel(self, member.guild, "notifyAccountAgeChannel")

        if notificationChannel == ageNotificationChannel:
            # If both are set to the same channel, only send one message.

            if await self.channel_permissions_check(member, notificationChannel, True):
                await notificationChannel.send(
                    output + settings["notifyAccountAgeMessage"],
                    embed=self.build_embed(member),
                )

        else:
            # Send to notification channel after permissions check
            if Database.Cogs[self.name][member.guild.id]["settings"].get(
                "joinNotificationChannel", False
            ) and await self.channel_permissions_check(member, notificationChannel, True):

                await notificationChannel.send(output, embed=self.build_embed(member))

            # Send to age notification channel after permissions check
            if Database.Cogs[self.name][member.guild.id]["settings"].get(
                "notifyAccountAgeChannel", False
            ) and await self.channel_permissions_check(member, ageNotificationChannel, True):

                await ageNotificationChannel.send(settings["notifyAccountAgeMessage"], embed=self.build_embed(member))

    async def channel_permissions_check(self, ctx, channel: discord.TextChannel, notifyOwner: bool = False):
        """
        Checks the permissions to send and read messages for specificed channel.
        Sending either ctx or member object is supported.
        """

        if not hasattr(channel, "permissions_for"):
            # This isn't a valid channel object.
            logger.debug(f"[join_leave] Invalid channel object: {channel}")
            return False

        if (
            not channel.permissions_for(ctx.guild.me).send_messages
            or not channel.permissions_for(ctx.guild.me).read_messages
        ):

            if notifyOwner == True:
                # Send a notification to the owner if the bot doesn't have permissions
                serverOwner = ctx.guild.owner
                await serverOwner.send(
                    f"Hey {serverOwner.display_name}, I tried "
                    "to send a message to "
                    f"{channel.mention} as you requested, "
                    "but I do not have permissions in that channel "
                    "to Send Messages or Read Messages."
                )
            return False
        else:
            return True

    @commands.Cog.listener()
    async def on_member_remove(self, member):

        user = f"{member.display_name} {member.name}#{member.discriminator}"
        guild = f"{member.guild.name}"
        output = f"{user} has left {guild}"

        # Send to console
        print(output)

        # Read the settings from the database to make sure they are up to date.
        Database.readSettingsGuild(self, member.guild.id)

        # Check to make sure a channel is set, if it's not return
        if not Database.Cogs[self.name][member.guild.id]["settings"].get("joinNotificationChannel", False):
            return

        # Set a handle for the notification channel
        notificationChannel = Utils.get_channel(self, member.guild, "joinNotificationChannel")

        # Check to make sure the bot has read and send messages permissions
        if await self.channel_permissions_check(member, notificationChannel, True):
            output = "A user has left the server."
            embed_to_send = self.build_embed(member)
            await notificationChannel.send(output, embed=embed_to_send)

    def build_embed(self, member):

        time_format = "%H:%M:%S"
        date_format = "%Y/%m/%d"

        embed = discord.Embed(title="User Information")

        embed.set_author(name=member.name, icon_url=member.avatar_url)

        embed.add_field(name="Username", value=f"{member.name}#{member.discriminator}")
        embed.add_field(name="User ID", value=f"{member.id}")
        embed.add_field(
            name="Joined",
            value=f"{member.joined_at.strftime(time_format)} on {member.joined_at.strftime(date_format)}",
        )
        embed.add_field(
            name="Created Account",
            value=f"{member.created_at.strftime(time_format)} on {member.created_at.strftime(date_format)}",
        )
        embed.add_field(name="Account Age", value=f"{self.build_account_age(member)}")
        embed.add_field(name="Member for", value=f"{self.build_server_member_for(member)}")
        if Database.Cogs.get("levels", False) and Database.Cogs["levels"][member.guild.id]["settings"]["enabled"]:
            # database query
            cursor = Database.cursor[member.guild.id]
            query = "SELECT nickname_history FROM users WHERE user_id = ?"
            values = (member.id,)
            query_result = Database.dbExecute(self, cursor, member.guild.id, query, values)

            if query_result is not None:
                if query_result[0] is not None:
                    # Use a space between names as it is not a valid trailing character
                    # Split the query into a list of names previously used
                    nickname_history = json.loads(query_result[0])

                    # Fix a bug that D3Jake created somehow mysteriously inserting a blank list
                    if len(nickname_history) > 0:
                        # Build the list
                        nickname_history = ", ".join(nickname_history)

                        embed.add_field(name="Previous Nicknames", value=f"{nickname_history}")

        return embed

    def build_account_age(self, member):
        """Returns how old the account is"""
        today = datetime.datetime.utcnow()
        created = member.created_at
        age = today - created

        return age

    def build_server_member_for(self, member):
        """Returns how long a member has been a member of the server"""
        today = datetime.datetime.utcnow()
        joined = member.joined_at
        age = today - joined

        return age

    async def _error(self, ctx, error):
        await Utils.errors(self, ctx, error)

    def cog_unload(self):
        logger.info(f"{__name__} unloaded...")


def setup(client):
    """
    Join/leave notifications cog
    """
    logger.info(f"Loading {__name__}...")
    client.add_cog(JoinLeave(client))
    logger.info(f"Loaded {__name__}")
