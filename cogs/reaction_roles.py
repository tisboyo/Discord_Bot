# -*- coding: utf-8 -*-
"""
Discord Bot for HardwareFlare and others
@author: Tisboyo
"""

import logging
import asyncio
import time
import sqlite3

import discord
from discord.ext import commands

from util.database import Database
from util.permissions import Permissions
from util.utils import Utils

logger = logging.getLogger(__name__)


class ReactionRoles(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.name = "reaction_roles"

        Database.readSettings(self)

        for guild_id in Database.Main:

            Database.Cogs[self.name][guild_id]["list"] = dict()

            # Used for tracking when the user last clicked on a reaction, and
            # the last time a DM was sent to the user asking them to slow down.
            Database.Cogs[self.name][guild_id]["anti_spam"] = dict()
            Database.Cogs[self.name][guild_id]["anti_spam_message"] = dict()

            self.setup_database(guild_id)

    def setup_database(self, guild_id):

        cursor = Database.cursor[guild_id]
        handle = Database.Cogs[self.name][guild_id]

        # Read the lists
        try:
            query = "SELECT emoji, role, description FROM reaction_roles_values"
            result = Database.dbExecute(self, cursor, guild_id, query, list(), True, hide_error=True)
            settingNum = 0
            for each_result in result:
                handle["list"][each_result[0]] = [
                    each_result[1],
                    each_result[2],
                ]
                settingNum += 1
            logger.debug(f"Reaction role values loaded.")

        except sqlite3.OperationalError as e:
            # The table doesn't exist, so we're going to create it and re-run the query.
            if "no such table" in e.args[0]:
                insert_query = f"""CREATE TABLE IF NOT EXISTS {self.name}_values(
									emoji TEXT, role TEXT, description TEXT,
									PRIMARY KEY(role) )"""
                Database.dbExecute(self, cursor, guild_id, insert_query)
                logger.info(f"{self.name}_values table created for {guild_id}.")

                Database.dbExecute(self, cursor, guild_id, query)

        if not handle["settings"].get("role_channel", False):
            handle["settings"]["role_channel"] = None

        if not handle["settings"].get("message_id", False):
            handle["settings"]["message_id"] = None

        Database.writeSettings(self, guild_id)

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        # Have to reload Database.Cogs when joining a new guild to prevent errors.
        Database.readSettingsGuild(self, guild.id)
        self.setup_database(guild.id)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        # No point in holding stuff in memory for a guild we aren't in.
        Database.writeSettings(self, guild.id)
        if Database.Cogs[self.name].get(guild.id, False):
            del Database.Cogs[self.name][guild.id]

    @commands.group()
    @commands.guild_only()
    @Permissions.check(permission=["manage_roles"])
    async def reacttorole(self, ctx):
        """
        Base command, use help reacttorole for sub-commands

        Default Permissions: manage_roles permission
        """

        # Guard Clause
        if ctx.invoked_subcommand is not None:  # A subcommand was used.
            return

        await ctx.send_help(ctx.command)

    @reacttorole.command()
    @commands.guild_only()
    @Permissions.check(permission=["manage_channels"])
    async def channel(self, ctx, textchannel: discord.TextChannel, message=None):
        """
        Sets a channel for the bot to post the messages to react to.

        Default Permissions: manage_channels permission
        """

        # Check for posting permissions, if not allowed notify owner/channel
        if (
            not textchannel.permissions_for(ctx.guild.me).send_messages
            or not textchannel.permissions_for(ctx.guild.me).read_messages
        ):

            if ctx.message.channel.permissions_for(ctx.guild.me).send_messages:
                await ctx.send(f"I am unable to send messages in {textchannel.mention}")
            else:
                serverOwner = ctx.message.guild.owner
                await serverOwner.send(f"I am unable to send messages in {textchannel.mention} for React To Role")

            return

        # Check if current messages exist, inform user and ask for confirmation
        if Database.Cogs[self.name][ctx.guild.id]["settings"].get("message_id", False):
            if message != "confirm":
                await ctx.send(
                    "WARNING: This will delete the existing role message. Please send "
                    f'`{Database.Main[ctx.guild.id].get("prefix", ".")}reacttorole channel #{textchannel} '
                    "confirm` to confirm."
                )
                return
            else:
                # Delete the message
                await self.del_message(ctx.guild)

        Database.Cogs[self.name][ctx.guild.id]["settings"]["role_channel"] = textchannel

        Database.writeSettings(self, ctx.guild.id)

        await Utils.send_confirmation(self, ctx.message)

        await ctx.send(f"Channel has been set to {textchannel.mention}")

    @reacttorole.command(aliases=["add"])
    @commands.guild_only()
    @Permissions.check(permission=["manage_roles"])
    async def create(self, ctx, role: discord.Role, emoji, *, message):
        """
        create @role emoji Text string for message

        Default Permissions: manage_roles permission
        """

        # Get channel messages are sent to.
        channel = Utils.get_channel(self, ctx.guild, "role_channel")

        # Check if the channel is set, if not notify and return
        if not channel:
            await ctx.send("No channel is set for the role messages to live in.")
            await Utils.send_failure(self, ctx.message)
            return

        # Check for posting permissions to channel, if not allowed
        if not channel.permissions_for(ctx.guild.me).send_messages:
            # Remove the channel from the database
            Database.Cogs[self.name][ctx.guild.id]["settings"]["role_channel"] = None
            Database.writeSettings(self, ctx.guild.id)

            # Notify server owner
            await self.message_server_owner(ctx.guild, 2048, "bad_channel_perms", channel.mention)

            # Return Stop
            await Utils.send_failure(self, ctx.message)
            # Bail on creating the channel
            return

        try:  # Check if it is a custom emoji.
            emoji = await commands.EmojiConverter().convert(ctx, emoji)
            emoji = str(emoji)

        except:  # Not a custom on this server, must be a regular emoji
            emoji = emoji

        # Check if the emoji is already in the list so we don't add it a second time.
        # if emoji not in Database.Cogs[self.name][ctx.guild.id]['list'].get(emoji, list()):
        if emoji not in Database.Cogs[self.name][ctx.guild.id]["list"]:

            try:
                # We are responding with the emoji the user requested, primarily as a test
                # to see if the emoji is valid. If it's not, it throws a HTTPException code 10014
                await ctx.message.add_reaction(emoji)  # Add the emoji the user requested.

            except discord.HTTPException as e:
                if e.code == 10014:
                    await ctx.send(f"Sorry, but discord doesn't have that emoji in it's reaction library.")

                    # Send failure to the user
                    await Utils.send_failure(self, ctx.message)

                    # We don't want to try adding the bad emoji to the database, so returning.
                    return

                elif e.code == 50013:
                    await ctx.send(f"I'm sorry, but I'm not allowed to add reactions to messages.")
                    return

                else:  # A different error code
                    # Send failure to the user
                    await Utils.send_failure(self, ctx.message)

                    # Send the error to the console so we can figure out the cause of it.
                    Utils.error_to_console(ctx, e)
                    return

            # Add the new message / role to the dictionary
            Database.Cogs[self.name][ctx.guild.id]["list"][emoji] = [
                str(role.id),
                str(message),
            ]

            # Add to database
            cursor = Database.cursor[ctx.guild.id]
            query = "INSERT INTO reaction_roles_values (emoji, role, description) VALUES (?, ?, ?)"
            values = emoji, str(role.id), str(message)
            Database.dbExecute(self, cursor, ctx.guild.id, query, values)

            await Utils.send_confirmation(self, ctx.message)

            # Call build_message
            await self.build_message(ctx)

        else:
            # Emoji is in the list, so send a negative result.
            await Utils.send_failure(self, ctx.message)
            await ctx.send(f"{emoji} is already in use.")

    @reacttorole.command(aliases=["del"])
    @commands.guild_only()
    @Permissions.check(permission=["manage_roles"])
    async def remove(self, ctx, role: discord.Role, emoji):
        """
        Removes a role from the message the bot posted.

        Usage: remove @role emoji

        Running this command does not remove the users from said roles,
        Nor does it remove the role from the server.

        Default Permissions: manage_roles permission
        """

        try:  # Check if it is a custom emoji.
            emoji = await commands.EmojiConverter().convert(ctx, emoji)
            emoji = str(emoji)

        except:  # Not a custom on this server, must be a regular emoji
            pass

        # Check if we have a role associated with that emoji
        if not Database.Cogs[self.name][ctx.guild.id]["list"].get(emoji, False):
            await Utils.send_failure(self, ctx.message)
            await ctx.send(f"{emoji} is not currently associated with a role.")

            return

        # Check to make sure the role and emoji match
        if Database.Cogs[self.name][ctx.guild.id]["list"][emoji][0] == str(role.id):
            cursor = Database.cursor[ctx.guild.id]
            # Normally would limit this to 1, however if there is more then
            # one entry matching the emoji, they all need removed.
            query = "DELETE FROM reaction_roles_values WHERE emoji = ?"
            values = (emoji,)
            Database.dbExecute(self, cursor, ctx.guild.id, query, values)

            # Remove the emoji from the dictionary
            del Database.Cogs[self.name][ctx.guild.id]["list"][emoji]

            # The list is empty, delete the message instead of attempting to
            # build a new message
            if len(Database.Cogs[self.name][ctx.guild.id]["list"]) == 0:
                await self.del_message(ctx.guild)
            else:
                # Build and post/edit the message
                await self.build_message(ctx)

            await Utils.send_confirmation(self, ctx.message)

        else:
            await Utils.send_failure(self, ctx.message)
            await ctx.send(f"{emoji} is not currently associated with that role.")

    async def del_message(self, guild):
        # Need the channel to deal with the old message
        channel = Utils.get_channel(self, guild, "role_channel")

        # Check if message is set
        if Database.Cogs[self.name][guild.id]["settings"].get("message_id", False):
            # Load old message data
            message_id = int(Database.Cogs[self.name][guild.id]["settings"]["message_id"])

            # Delete the old message
            try:
                message = await channel.fetch_message(message_id)
                # Set flag to stop self.on_raw_message_delete from running
                Database.Cogs[self.name][guild.id]["settings"]["working"] = True

                await message.delete()
                await self.cleanup_deleted_message(guild.id)

                # Sleep for .25 seconds to allow the message to be deleted and
                # to let the on_raw_message_delete event see the 'working' flag
                # before we turn it back off
                await asyncio.sleep(0.25)

                # Clear the working flag
                del Database.Cogs[self.name][guild.id]["settings"]["working"]

            except discord.HTTPException as e:
                if e.code == 10008:
                    logging.warning("Message was missing when delete attempted.")

    async def cleanup_deleted_message(self, guild_id):
        """
        Cleans up the database when the role/reaction message is deleted.
        """

        Database.Cogs[self.name][guild_id]["settings"]["message_id"] = None

        Database.writeSettings(self, guild_id)

    @reacttorole.command()
    @commands.guild_only()
    @Permissions.check(permission=["manage_channels"])
    async def repost(self, ctx):
        """
        Reposts the message to the channel. (Deletes old message)

        This command is useful when the channel has been changed or the message deleted.

        This will delete all current reactions to the message.

        Default Permissions: manage_channels permission
        """

        channel = Utils.get_channel(self, ctx.guild, "role_channel")

        # Check if the channel is set, if not notify and return
        if not channel:
            await ctx.send("No channel is set for the role messages to live in.")
            await ctx.message.add_reaction("🚫")  # Stop emoji

            return

        # Check if message is set
        if Database.Cogs[self.name][ctx.guild.id]["settings"]["message_id"]:
            await ctx.send("The message already exists, delete it before reposting.")
            await Utils.send_failure(self, ctx.message)
        else:
            # Call build_message to post a new message
            await self.build_message(ctx)

    async def build_message(self, ctx):
        """
        Build and post the message to the appropriate channel
        """
        # emoji, role, description

        # Send message permission check

        # Create a handle to use
        entries = Database.Cogs[self.name][ctx.guild.id]["list"]

        # Start the embed
        embed = discord.Embed(
            title="Join channels",
            description="Select a channel to join by clicking on the reaction below.",
        )

        for each in entries:  # Loop through each emoji

            role = ctx.guild.get_role(int(entries[each][0]))
            description = entries[each][1]  # Description text
            name = f"{each} - {str(role)}"
            embed.add_field(name=name, value=f"{description}", inline=True)

        embed.set_footer(text="Select a reaction below to join the appropriate channel.")

        # Get channel
        channel = Utils.get_channel(self, ctx.guild, "role_channel")

        # Check if message exists, if so edit it
        if Database.Cogs[self.name][ctx.guild.id]["settings"]["message_id"]:
            message_id = int(Database.Cogs[self.name][ctx.guild.id]["settings"]["message_id"])
            message = await channel.fetch_message(message_id)
            await message.edit(content=None, embed=embed)

        else:
            # Send to channel, and save it
            message = await channel.send(content=None, embed=embed)
            Database.Cogs[self.name][ctx.guild.id]["settings"]["message_id"] = message.id

            Database.writeSettings(self, ctx.guild.id)

        # Loop through emojis and add each one to the message
        # Do an await sleep between each one to add them slowly so they show up in order(hopefully)
        for each in entries:  # Loop through each emoji again
            await message.add_reaction(each)
            await asyncio.sleep(0.50)

        # Remove any emojis that are no longer needed
        # Requires manage messages permission to remove others reactions
        # this doesn't get triggered when adding a message, I suspect because the
        # message hasn't been pulled from the server again, but that doesn't really
        # matter as long as it's run when the reaction/role is removed.
        for eachReaction in message.reactions:
            # Check each reaction currently on the message to see if it is in the new entries.
            if str(eachReaction) not in entries.keys():
                # Check to make sure the bot has manage_messages permission,
                # If not, remove our own message and bail.
                if not ctx.message.channel.permissions_for(ctx.guild.me).manage_messages:
                    await message.remove_reaction(eachReaction, ctx.me)
                    await self.message_server_owner(ctx.guild, 8192, "remove_reaction")
                    continue

                # Flatten out the users on each reaction to get a list
                # The bot should be included in this list.
                users = await eachReaction.users().flatten()
                for user in users:
                    await message.remove_reaction(eachReaction, user)
                    # Rate limited during testing, so slowing down on our own.
                    await asyncio.sleep(0.50)

    @commands.Cog.listener()
    @commands.guild_only()
    async def on_raw_message_delete(self, payload):
        """
        #Delete message event
        #If the message is deleted manually, clean up the database
        """

        settings = Database.Cogs[self.name][payload.guild_id]["settings"]

        # Guard clause
        if (  # We don't care unless it's our message
            payload.message_id != settings["message_id"]
            or
            # The bot is currently deleting or doing something with the message.
            # So we aren't going to do anything here, yet...
            settings.get("working", False)
        ):
            return

        await self.cleanup_deleted_message(payload.guild_id)

        channel = Utils.get_channel(self, payload.guild_id, "role_channel")

        message = (
            "The Role/Reaction message has been deleted. You can create or "
            f'delete a Role/Reaction combo or use `{Database.Main[payload.guild_id].get("prefix", ".")}'
            "reacttorole repost` to repost it."
        )

        await channel.send(message)

    @commands.Cog.listener()
    @commands.guild_only()
    async def on_raw_reaction_add(self, payload):
        """
        Adds a role to a user based on a reaction to a specified message.
        """
        # Guard Clause is done inside on_raw_reaction_work
        role, member = await self.on_raw_reaction_work(payload)
        if role == None:  # Happens when Guard Clause is hit
            return

        try:
            await member.add_roles(role, reason="User request")
        except discord.Forbidden:
            await self.reaction_role_failure(payload, "add_role")

    @commands.Cog.listener()
    @commands.guild_only()
    async def on_raw_reaction_remove(self, payload):
        """
        Removes a role from a user based on a reaction to a specified message
        """
        # Guard Clause is done inside on_raw_reaction_work

        role, member = await self.on_raw_reaction_work(payload)
        if role == None:  # Happens when Guard Clause is hit
            return

        try:
            await member.remove_roles(role, reason="User request")
        except discord.Forbidden:
            await self.reaction_role_failure(payload, "remove_role")

    async def on_raw_reaction_work(self, payload):
        """
        This function performs all of the actual work for both adding and removing a role
        """
        settings = Database.Cogs[self.name][payload.guild_id]["settings"]

        # Guard Clause
        if (  # The bot is currently deleting or doing something with the message.
            settings.get("working", False)
            or
            # Check if the reaction was done by a bot
            self.client.get_user(payload.user_id).bot
            or
            # Check to make sure message matches set message
            payload.message_id != settings.get("message_id", False)
        ):
            return None, None

        # Cooldown to prevent spamming API
        last_run = Database.Cogs[self.name][payload.guild_id]["anti_spam"].get(payload.user_id, 0)
        last_anti_spam_message = Database.Cogs[self.name][payload.guild_id]["anti_spam_message"].get(payload.user_id, 0)
        current_time = time.time()

        # Update anti_spam
        Database.Cogs[self.name][payload.guild_id]["anti_spam"][payload.user_id] = current_time

        # One second delay to prevent rapid spamming by a user.
        # 5 Minute delay on warning the user to slow down.
        if last_run + 1 > current_time and last_anti_spam_message + 300 > current_time:
            return None, None

        # First time they have hit the limit in the last 5 minutes
        elif last_run + 1 > current_time:
            # Add anti_spam_message tracking
            Database.Cogs[self.name][payload.guild_id]["anti_spam_message"][payload.user_id] = current_time

            # Tell user to slow down
            member = self.client.get_user(payload.user_id)
            await member.send(
                "Please slow down on that button. Click it only once per second. "
                "Your last request may not have worked, you can "
                "try again to add or remove it by clicking the reaction "
                "again twice with a delay between."
            )
            return None, None

        # Get the message id
        message_id = payload.message_id

        reaction_message = int(settings["message_id"])

        # Check if the reaction is the same as the message
        if message_id == reaction_message:
            # Get the guild
            guild = self.client.get_guild(payload.guild_id)

            try:
                # Try to fetch the emoji, only works when it is a guild custom
                emoji = await guild.fetch_emoji(payload.emoji.id)
                # Convert it to a straight string, as that's what is in the database
                emoji = str(emoji)

            except discord.HTTPException as e:
                # Error caused when not a guild custom emoji
                if e.code == 50035:
                    emoji = payload.emoji.name

            # Get the role id associated with the emoji
            role_id = int(Database.Cogs[self.name][payload.guild_id]["list"][emoji][0])

            role = guild.get_role(role_id)

            # Get the member that requested the role change,
            # and the bot so we can check it's permissions.
            member = guild.get_member(payload.user_id)

            if role is not None and member is not None:
                return role, member

            else:
                logger.warning(f"{guild}-{role} role not found")
                return None, None

    async def reaction_role_failure(self, payload, method):

        # Send a notification to the owner if the bot doesn't have permissions
        guild_id = payload.guild_id
        guild = self.client.get_guild(guild_id)

        # Manage Roles Permission value
        permissions = 268435456  # Manage Roles

        await self.message_server_owner(guild, permissions, method)

    async def message_server_owner(self, guild, permissions: int, method, extra_data=None):
        """
        Sends a message to the server owner asking for permissions.

        guild = discord.Guild object
        permissions = Value to be passed to discord.Permissions(permissions = ?)
        method = The specific error message to send the owner.
        extra_data = Extra data needed for the message (Optional)

        """
        serverOwner = guild.owner
        new_permission = discord.Permissions(guild.me.guild_permissions.value + permissions)

        # Get invite link with Permissions requested and Guild auto selected
        inviteLink = discord.utils.oauth_url(guild.me.id, permissions=new_permission, guild=guild)

        # Dictionary of method that caused the failure, to send appropriate message
        # Created so multiple messages can be used easily
        messages = {
            "add_role": f"Hey {serverOwner.display_name}, I tried "
            "to add a user to a role as they requested but "
            "I do not have the Manage Roles permission. "
            f"For convienence you can use this link to fix it: "
            f"{inviteLink} (Includes current permissions) \n\n "
            "Also a reminder the bot role "
            "must be above any roles you wish to add or remove.",
            "remove_role": f"Hey {serverOwner.display_name}, I tried "
            "to remove a user from a role as they requested but "
            "I do not have the Manage Roles permission. "
            f"For convienence you can use this link to fix it: "
            f"{inviteLink} (Includes current permissions) \n\n "
            "Also a reminder the bot role "
            "must be above any roles you wish to add or remove.",
            "remove_reaction": f"Hey {serverOwner.display_name}, I tried "
            "to remove the other users reactions from the Role/Reaction "
            "message and was unable to. I lack the Manage Messages "
            "permission to do so. Please either manually allow "
            "me to do so in the channel, or for your "
            "convinence you can use this link to add the permission "
            f"for the entire server {inviteLink} (Includes "
            "current permissions). \n\nThis message "
            "was generated because a role/reaction combo was removed.",
            "bad_channel_perms": f"Hey {serverOwner.display_name}, I tried "
            "to update the role/reaction message but I don't have "
            f"permissions in {extra_data} to send messages.",
        }

        # For testing only.
        # messages = {'add_role':'add_role', 'remove_role':'remove_role',
        #            'remove_reaction':'remove_reaction','bad_channel_perms':'bad_channel_perms'}

        message = messages[method] + f"\n\nIf you would like to stop all DM's from the bot, send the command .silencedm."
        await serverOwner.send(message)

    @reacttorole.error
    @channel.error
    @create.error
    @remove.error
    @repost.error
    async def _errors(self, ctx, error):
        await Utils.errors(self, ctx, error)

    def cog_unload(self):
        logger.info(f"{__name__} unloaded...")


def setup(client):
    """
    Reaction Roles setup
    """
    logger.info(f"Loading {__name__}...")
    client.add_cog(ReactionRoles(client))
    logger.info(f"Loaded {__name__}")
