# -*- coding: utf-8 -*-
"""
Discord Bot for HardwareFlare and others
@author: Tisboyo
"""

import json
import logging

import discord
from discord.ext import commands

from util.database import Database
from util.utils import Utils, dotdict

logger = logging.getLogger(__name__)


class Permissions(commands.Cog):
    """
    Use by calling Permissions.check() before a command declaration similar to commands.check()

    Usage: In order of priority
            Permissions.check() #Will only allow Administrator and Bot Owner to use command

            #Restrict a command to only a specific guild, mainly for testing.
            Permissions.check(guild = [GUILD_ID_AS_INT, GUILD2_ID_AS_INT]) #Must pass a list of integers

            #Explicit user permissions are then checked, there is no hard code override available.

            #Roles are checked next, if 'any' or 'everyone' is defined in the bot, it can be overridden
            #by assigning a role manually to the command.
            Permissions.check(role="any") or Permissions.check(role="everyone") #Any role or everyone can use command

            #Lastly is permissions checks
            #Can be passed as a list of strings of valid discord permissions.
            #See Permissions.perm_list for valid arguments.
            Permissions.check(permission='read_messages') or (permission=['read_messages', 'send_messages'])

            Any of the 3, (guild, role, permission) can be combined into a single check, but will execute
            in the above order.
    """

    perms_list = [
        "administrator",
        "create_instant_invite",
        "ban_members",
        "manage_channels",
        "manage_guild",
        "add_reactions",
        "view_audit_log",
        "priority_speaker",
        "stream",
        "read_messages",
        "send_messages",
        "send_tts_messages",
        "manage_messages",
        "embed_links",
        "attach_files",
        "read_message_history",
        "mention_everyone",
        "external_emojis",
        "connect",
        "speak",
        "mute_members",
        "deafen_members",
        "move_members",
        "use_voice_activation",
        "change_nickname",
        "manage_nicknames",
        "manage_roles",
        "manage_webhooks",
        "manage_emojis",
        "kick_members",
    ]

    perms_error_messages = {
        "MissingPermissions": f"You do not have permissions to use that command.",
        "NotAvailableInThisGuild": "This command is guild specific in the bot, and is unavailable here.",
    }

    def __init__(self, client):
        self.client = client

        #'permissions' is used explicitly in check_test because only ctx is passed in.
        self.name = "permissions"

        Database.Cogs[self.name] = dict()

        Database.readSettings(self)

        for guild_id in Database.Main:
            self.load_permissions(guild_id)

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        self.load_permissions(guild.id)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        # No point in holding stuff in memory for a guild we aren't in.
        if Database.Cogs[self.name].get(guild.id, False):
            del Database.Cogs[self.name][guild.id]

    def load_permissions(self, guild_id):
        cursor = Database.cursor[guild_id]
        query = f"SELECT setting_data FROM {self.name}_settings WHERE setting_id = 'permissions' LIMIT 1"
        result = Database.dbExecute(self, cursor, guild_id, query)
        if result is not None:
            permissions_load = json.loads(result[0])
        else:
            permissions_load = {}

        Database.Cogs[self.name][guild_id]["permissions"] = permissions_load

    # Passing self into check causes an error, and since it's not needed, ignore the linter error
    def check(**kwargs):  # pylint: disable=no-method-argument
        # https://discordpy.readthedocs.io/en/latest/ext/commands/api.html?highlight=check#discord.ext.commands.check

        # Disable all the no-member violations in this function
        # pylint: disable=no-member

        async def predicate(ctx):

            author = ctx.author
            qualified_name = ctx.command.qualified_name.split()

            # Bot owner is permitted all commands
            if await ctx.bot.is_owner(author):
                return True

            # Check if the bot is sleeping
            elif Database.Bot["sleeping"]:
                raise commands.commandError(message="BotIsSleeping")

            # Bot's can't run commands
            elif author.bot:
                return False

            # Administrator permissions are allowed all commands
            elif author.guild_permissions.administrator:
                return True

            else:

                # Create a fake self so it can be passed to load_permissions and the name be there.
                self_ = dict(name="permissions")
                self_ = dotdict(self_)

                # Read the permissions from the database
                Permissions.load_permissions(self_, ctx.guild.id)

                handle = Database.Cogs["permissions"][ctx.guild.id]["permissions"]

                # Loop through all levels of the command to make sure all of
                # the variables exist.
                for x in range(0, len(qualified_name)):

                    # Create defaults if they don't exist.
                    if not handle.get(qualified_name[x], False):
                        handle[qualified_name[x]] = dict()

                    if not handle[qualified_name[x]].get("_roles", False):
                        handle[qualified_name[x]]["_roles"] = list()

                    if not handle[qualified_name[x]].get("_users", False):
                        handle[qualified_name[x]]["_users"] = list()

                    if not handle[qualified_name[x]].get("_permissions", False):
                        handle[qualified_name[x]]["_permissions"] = list()

                    # Move the handle to the next sub command
                    handle = handle[qualified_name[x]]

                if kwargs.get("guild", False):
                    if ctx.guild.id not in kwargs["guild"]:
                        raise commands.CommandError(message="NotAvailableInThisGuild")

                # All previous levels have already been checked as
                # each previous command is authenticated first.

                # Check if the user is in a permitted users list
                if ctx.message.author.id in handle["_users"]:
                    return True

                # Check if user is in role
                for role in ctx.message.author.roles:

                    # Check if the users role is in the permitted roles.
                    if role.id in handle["_roles"]:
                        return True

                    if "any" in handle["_roles"]:
                        # Any role,except everyone can use this command
                        # If everyone is set, it is covered above
                        if role.name == "@everyone":
                            continue
                        return True

                    # This is inside the loop so we can check it against the users roles
                    # No roles are set for the command, use the bot defaults
                    # If 'none' is in the list of roles, this will not fire
                    # as a way of overriding bot defaults
                    if len(handle["_roles"]) == 0:
                        # Command has any role set
                        if kwargs.get("role", "") == "any":
                            # Skip the everyone role for any check
                            if role.name == "@everyone":
                                continue
                            return True  # All other roles are true

                        # Everyone role is set by bot default
                        elif kwargs.get("role", "") == "everyone":
                            return True

                # Check if the user has an individual permission
                # Dictionary to load all permissions in to.
                perm_dict = dict()

                # Read all of the authors permissions
                for perm, values in ctx.message.author.permissions_in(ctx.message.channel):
                    perm_dict[perm] = values

                for perm in handle["_permissions"]:
                    # If the permission has been overridden to none, keep checking
                    if perm == "none":
                        continue
                    if perm_dict.get(perm, False):
                        return True

                # Use bot default if nothing is set by the server
                if len(handle["_permissions"]) == 0:

                    for perm in kwargs.get("permission", []):
                        if perm_dict[perm]:
                            print(perm_dict[perm])
                            return True

            # Nothing returned True yet, so return False
            raise commands.CommandError(message="MissingPermissions")

        # Calls the command check handler
        return commands.check(predicate)

    @commands.group()
    @commands.guild_only()
    @check()  # Can't use Permissions.Check inside the Permissions class
    async def permissions(self, ctx):
        """
        Used to set permissions for commands.

        Default Permissions: Guild Administrator only
        """

        # Guard Clause
        if (
            ctx.guild == None  # Not in a guild means DM or Group chat.
            or Database.Bot["sleeping"]  # If the bot is sleeping, don't do anything.
            or ctx.invoked_subcommand is not None  # A subcommand was used as intended.
        ):
            return

        await ctx.send_help(ctx.command)

    @permissions.group(name="add")
    @commands.guild_only()
    @check()
    async def permissions_add(self, ctx):
        """
        Add user, role or permissions

        Default Permissions: Guild Administrator only
        """
        # Guard Clause
        if (
            ctx.guild == None  # Not in a guild means DM or Group chat.
            or Database.Bot["sleeping"]  # If the bot is sleeping, don't do anything.
            or ctx.invoked_subcommand is not None  # A subcommand was used as intended.
        ):
            return

        await ctx.send_help(ctx.command)

    @permissions_add.command(name="role")
    @commands.guild_only()
    @check()
    async def permissions_add_role(self, ctx, role, *, command):
        """
        Gives the Role permissions to use the command.

        Role can be either mentioned, or just the name.
        Can also be 'any', 'everyone' or 'none'

        Default Permissions: Guild Administrator only
        """
        # Guard Clause
        if (
            ctx.guild == None  # Not in a guild means DM or Group chat.
            or Database.Bot["sleeping"]  # If the bot is sleeping, don't do anything.
            or not self.valid_command(ctx.guild, command)  # Check if the command is valid
        ):
            return

        handle = self.perm_handle(ctx, command)

        if (role == "any") or (role == "none"):
            if role not in handle["_roles"]:
                handle["_roles"].append(role)
                self.save_permissions(ctx)

        elif role == "everyone":  # This only fires if everyone isn't mentioned,
            # if @everyone is mentioned it is caught in the else.

            if ctx.guild.id not in handle["_roles"]:  # Everyone role uses the guild id
                handle["_roles"].append(ctx.guild.id)
                self.save_permissions(ctx)

        else:
            # Make sure the role passed is a role object, unless it's any of everyone
            role = await commands.RoleConverter().convert(ctx, role)

            if role.id not in handle["_roles"]:
                handle["_roles"].append(role.id)
                self.save_permissions(ctx)

        # If none is in the list, go ahead and remove it.
        if "none" in handle["_roles"]:
            handle["_roles"].remove("none")
            self.save_permissions(ctx)

        await ctx.message.add_reaction("\u2611")  # ballot_box_with_check

    @permissions_add.command(name="user")
    @commands.guild_only()
    @check()
    async def permissions_add_user(self, ctx, member, *, command):
        """
        Gives the User permissions to use the command.

        You can either mention a user, use their name or
        name#discriminator without mentioning the user.
        If name#discriminator has a space, wrap it in quotes.

        Default Permissions: Guild Administrator only
        """

        # Guard Clause
        if (
            ctx.guild == None  # Not in a guild means DM or Group chat.
            or Database.Bot["sleeping"]  # If the bot is sleeping, don't do anything.
            or not self.valid_command(ctx.guild, command)  # Check if the command is valid
        ):
            return

        # Read in any mentions
        mentions = ctx.message.mentions

        # Check if a user was mentioned, if not convert member to a mention
        if len(mentions) == 0:
            mentions.append(await commands.MemberConverter().convert(ctx, member))

        # Now that we have our mentioned user
        if len(mentions) == 1:
            # We have our user and a valid command, add them to the database
            member = mentions[0]

            handle = self.perm_handle(ctx, command)

            if member.id not in handle["_users"]:
                handle["_users"].append(member.id)
                self.save_permissions(ctx)

            await ctx.message.add_reaction("\u2611")  # ballot_box_with_check

        else:
            # More then one user was mentioned for some reason
            raise commands.BadArgument

    @permissions_add.command(name="permission")
    @commands.guild_only()
    @check()
    async def permissions_add_permission(self, ctx, permission, *, command):
        """
        Gives all users with the specified permission access to the command.

        Available permissions
        'administrator', 'create_instant_invite', 'ban_members', 'manage_channels',
        'manage_guild', 'add_reactions', 'view_audit_log', 'priority_speaker',
        'stream', 'read_messages', 'send_messages', 'send_tts_messages',
        'manage_messages', 'embed_links', 'attach_files', 'read_message_history',
        'mention_everyone', 'external_emojis', 'connect', 'speak', 'mute_members',
        'deafen_members', 'move_members', 'use_voice_activation', 'change_nickname',
        'manage_nicknames', 'manage_roles', 'manage_webhooks', 'manage_emojis', 'kick_members'

        Default Permissions: Guild Administrator only
        """
        # Guard Clause
        if (
            ctx.guild == None  # Not in a guild means DM or Group chat.
            or Database.Bot["sleeping"]  # If the bot is sleeping, don't do anything.
            or not self.valid_command(ctx.guild, command)  # Check if the command is valid
        ):
            return

        handle = self.perm_handle(ctx, command)

        # Check to make sure it's a valid permission
        if permission in Permissions.perms_list:

            if permission not in handle["_permissions"]:
                handle["_permissions"].append(permission)
            if "none" in handle["_permissions"]:
                handle["_permissions"].remove("none")
            self.save_permissions(ctx)

            await ctx.message.add_reaction("\u2611")  # ballot_box_with_check

        elif permission == "none":  # Disable default permissions
            if permission not in handle["_permissions"]:
                handle["_permissions"].append(permission)
                self.save_permissions(ctx)

            await ctx.message.add_reaction("\u2611")  # ballot_box_with_check

        else:
            await ctx.message.add_reaction("🚫")

    @permissions.command(name="list")
    @commands.guild_only()
    @check()
    async def permissions_list(self, ctx, *, command):
        """
        List permissions for the specified command

        Default Permissions: Guild Administrator only
        """
        # Guard Clause
        if (
            ctx.guild == None  # Not in a guild means DM or Group chat.
            or Database.Bot["sleeping"]  # If the bot is sleeping, don't do anything.
            or not self.valid_command(ctx.guild, command)  # Check if the command is valid
        ):
            return

        handle = self.perm_handle(ctx, command)

        # Members
        member_list = ""

        for member in handle["_users"]:
            member = str(member)
            member_obj = await commands.MemberConverter().convert(ctx, member)
            member_list += member_obj.display_name + ", "

        # Roles
        role_list = ""
        for role in handle["_roles"]:

            if (role != "any") and (role != "none"):
                if role == ctx.guild.id:
                    # Clean up the everyone role so listing doesn't ping people.
                    role_list += "everyone, "

                else:
                    role_obj = await commands.RoleConverter().convert(ctx, str(role))
                    role_list += role_obj.name + ", "

            else:
                role_list += role + ", "

        # Permissions
        permission_list = ""
        for permission in handle["_permissions"]:
            permission_list += permission + ", "

        msg = f"Who has access to the command: {command} \n"
        if len(member_list) > 0:
            msg += f"Users: {member_list[:-2]}\n"
        if len(role_list) > 0:
            msg += f"Roles: {role_list[:-2]}\n"
        if len(permission_list) > 0:
            msg += f"Permissions: {permission_list[:-2]}"

        await ctx.send(msg)

    @permissions.group(name="del", aliases=["remove"])
    @commands.guild_only()
    @check()
    async def permissions_del(self, ctx):
        """
        Add user, role or permissions

        Default Permissions: Guild Administrator only
        """
        # Guard Clause
        if (
            ctx.guild == None  # Not in a guild means DM or Group chat.
            or Database.Bot["sleeping"]  # If the bot is sleeping, don't do anything.
            or ctx.invoked_subcommand is not None  # A subcommand was used as intended.
        ):
            return

        await ctx.send_help(ctx.command)

    @permissions_del.command(name="role")
    @commands.guild_only()
    @check()
    async def permissions_del_role(self, ctx, role, *, command):
        """
        Removes the Role's permission to use the command.

        Role can be either mentioned, or just the name.
        Can also be 'any', 'everyone' or 'none'

        Default Permissions: Guild Administrator only
        """
        # Guard Clause
        if (
            ctx.guild == None  # Not in a guild means DM or Group chat.
            or Database.Bot["sleeping"]  # If the bot is sleeping, don't do anything.
            or not self.valid_command(ctx.guild, command)  # Check if the command is valid
        ):
            return

        handle = self.perm_handle(ctx, command)

        if (role == "any") or (role == "none"):
            if role in handle["_roles"]:
                handle["_roles"].remove(role)
                self.save_permissions(ctx)

        elif role == "everyone":  # This only fires if everyone isn't mentioned,
            # if @everyone is mentioned it is caught in the else.

            if ctx.guild.id in handle["_roles"]:  # Everyone role uses the guild id
                handle["_roles"].remove(ctx.guild.id)
                self.save_permissions(ctx)

        else:
            # Make sure the role passed is a role object, unless it's any of everyone
            role = await commands.RoleConverter().convert(ctx, role)

            if role.id in handle["_roles"]:
                handle["_roles"].remove(role.id)
                self.save_permissions(ctx)

        if len(handle["_roles"]) == 0:
            message = (
                f"The last role for `{command}` has been deleted, reverting to bot default settings. "
                f"To disable default use `permissions add role none {command}`"
            )
            await ctx.send(message)
        await ctx.message.add_reaction("\u2611")  # ballot_box_with_check

    @permissions_del.command(name="user")
    @commands.guild_only()
    @check()
    async def permissions_del_user(self, ctx, member, *, command):
        """
        Gives the User permissions to use the command.

        You can either mention a user, use their name or
        name#discriminator without mentioning the user.
        If name#discriminator has a space, wrap it in quotes.

        Default Permissions: Guild Administrator only
        """

        # Guard Clause
        if (
            ctx.guild == None  # Not in a guild means DM or Group chat.
            or Database.Bot["sleeping"]  # If the bot is sleeping, don't do anything.
            or not self.valid_command(ctx.guild, command)  # Check if the command is valid
        ):
            return

        # Read in any mentions
        mentions = ctx.message.mentions

        # Check if a user was mentioned, if not convert member to a mention
        if len(mentions) == 0:
            mentions.append(await commands.MemberConverter().convert(ctx, member))

        # Now that we have our mentioned user
        if len(mentions) == 1:
            # We have our user and a valid command, add them to the database
            member = mentions[0]

            handle = self.perm_handle(ctx, command)

            if member.id in handle["_users"]:
                handle["_users"].remove(member.id)
                self.save_permissions(ctx)

            await ctx.message.add_reaction("\u2611")  # ballot_box_with_check

        else:
            # More then one user was mentioned for some reason
            raise commands.BadArgument

    @permissions_del.command(name="permission")
    @commands.guild_only()
    @check()
    async def permissions_del_permission(self, ctx, permission, *, command):
        """
        Removes permissions for all users with the specified permission access to the command.

        Available permissions
        'administrator', 'create_instant_invite', 'ban_members', 'manage_channels',
        'manage_guild', 'add_reactions', 'view_audit_log', 'priority_speaker',
        'stream', 'read_messages', 'send_messages', 'send_tts_messages',
        'manage_messages', 'embed_links', 'attach_files', 'read_message_history',
        'mention_everyone', 'external_emojis', 'connect', 'speak', 'mute_members',
        'deafen_members', 'move_members', 'use_voice_activation', 'change_nickname',
        'manage_nicknames', 'manage_roles', 'manage_webhooks', 'manage_emojis', 'kick_members'

        Default Permissions: Guild Administrator only
        """
        # Guard Clause
        if (
            ctx.guild == None  # Not in a guild means DM or Group chat.
            or Database.Bot["sleeping"]  # If the bot is sleeping, don't do anything.
            or not self.valid_command(ctx.guild, command)  # Check if the command is valid
        ):
            return

        # Check to make sure it's a valid permission
        if permission in Permissions.perms_list:
            handle = self.perm_handle(ctx, command)

            if permission in handle["_permissions"]:
                handle["_permissions"].remove(permission)
                self.save_permissions(ctx)

            if len(handle["_permissions"]) == 0:
                message = (
                    f"The last permission for `{command}` has been deleted, reverting to bot default settings. "
                    f"To disable default use `permissions add permission none {command}`"
                )

                await ctx.send(message)

            await ctx.message.add_reaction("\u2611")  # ballot_box_with_check

        elif permission == "none":  # Disable default permissions
            if permission in handle["_permissions"]:
                handle["_permissions"].remove("none")
                self.save_permissions(ctx)

            await ctx.message.add_reaction("\u2611")  # ballot_box_with_check

        else:
            await ctx.message.add_reaction("🚫")

    @permissions.error
    @permissions_add.error
    @permissions_add_role.error
    @permissions_add_user.error
    @permissions_add_permission.error
    @permissions_list.error
    @permissions_del.error
    @permissions_del_role.error
    @permissions_del_user.error
    @permissions_del_permission.error
    async def _errors(self, ctx, error):

        await Utils.errors(self, ctx, error)

    def save_permissions(self, ctx):
        """
        Saves all of the permissions settings to the database
        """

        save = json.dumps(Database.Cogs[self.name][ctx.guild.id]["permissions"])
        Database.Cogs[self.name][ctx.guild.id]["settings"]["permissions"] = save

        # Set database handle
        cursor = Database.cursor[ctx.guild.id]

        query = f"UPDATE {self.name}_settings SET setting_data = ? WHERE setting_id = ? "
        values = (save, "permissions")
        _, rows = Database.dbExecute(self, cursor, ctx.guild.id, query, values, False, True)

        # Entry was not in the database, insert it.
        if rows == 0:
            query = f"INSERT INTO {self.name}_settings (setting_id, setting_data) VALUES (?, ?)"
            values = ("permissions", save)
            Database.dbExecute(self, cursor, ctx.guild.id, query, values)

    def perm_handle(self, ctx, command):
        """
        Returns a handle for the permission of the qualified command
        """

        qualified_name = command.split()

        # Read the permissions from the database
        self.load_permissions(ctx.guild.id)

        handle = Database.Cogs["permissions"][ctx.guild.id]["permissions"]

        for x in range(0, len(qualified_name)):

            # Create defaults if they don't exist.
            if not handle.get(qualified_name[x], False):
                handle[qualified_name[x]] = dict()

            if not handle[qualified_name[x]].get("_roles", False):
                handle[qualified_name[x]]["_roles"] = list()

            if not handle[qualified_name[x]].get("_users", False):
                handle[qualified_name[x]]["_users"] = list()

            if not handle[qualified_name[x]].get("_permissions", False):
                handle[qualified_name[x]]["_permissions"] = list()

            # Move the handle to the next sub command
            handle = handle[qualified_name[x]]

            if x == len(qualified_name) - 1:
                return handle

    def valid_command(self, guild: discord.Guild, command=str):
        """
        Builds a command list and saves it in a dictionary
        Does not check if command is enabled, just that it's a valid command.
        Raises commands.BadCommand if the command is not valid.
        """

        # Not saved for later use because I want to check it every time, in case commands are disabled
        db = dict()

        # Build the command dictionary
        for each in self.client.walk_commands():

            if each.parent != None:

                command_name = each.name.lower()

                # Save to work with so we don't change each accidentally
                root = each

                while root.parent != None:
                    command_name = root.parent.name.lower() + " " + command_name

                    # Move up the tree
                    root = root.parent

                if each.enabled:
                    db[command_name] = True
                else:
                    db[command_name] = False

            else:
                # Root command
                # print(f'Command: {each.name}')

                db[each.name.lower()] = True

        if db.get(command, False):
            return True

        else:
            raise commands.BadArgument


def setup(client):
    """
    Permissions setup
    """
    logger.info(f"Loading {__name__}...")
    client.add_cog(Permissions(client))
    logger.info(f"Loaded {__name__}")
