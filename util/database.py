# -*- coding: utf-8 -*-
"""
Discord Bot for HardwareFlare and others
@author: Tisboyo
"""

"""
        #database query
        cursor = Database.cursor[ctx.guild.id]
        query = "UPDATE table SET setting_data = ? WHERE setting_id = ? "
        values = (setting_data, setting_id)
        Database.dbExecute(self, cursor, ctx.guild.id, query, values)

"""
import sqlite3
import os
import datetime
import traceback
import logging
import json

# import discord
from discord.ext import commands, tasks


# run_backup function
from shutil import copyfile
import aioftp
from keys import backup

logger = logging.getLogger(__name__)


class Database(commands.Cog):

    # These need to be accessible from every instance.

    # Storage for Guild settings (Main) and Cog settings (Cogs)
    Bot = dict()
    Main = dict()
    Cogs = dict()

    # Database
    connection = dict()  # Database connection
    cursor = dict()  # Dictionary to hold all of the database cursors

    def __init__(self, client):
        self.client = client
        self.loadDatabase()

        # Ignoring pylint error about run_backup_loop not having a start member
        # the parent loop has the .start member
        self.run_backup_loop.start()  # pylint: disable=no-member

    def loadDatabase(self):
        # Load all of the guild settings
        for filename in os.listdir("./db"):
            if filename.endswith(".db3"):
                # Find the guild ID based on filename
                guild_id = int(f"{filename[:-4]}")
                self.loadGuildDatabase(guild_id)

    def loadGuildDatabase(self, guild_id):
        # Create the guild
        Database.Main[guild_id] = dict()

        # Create a handle for the database
        cursor = Database.cursor[guild_id] = Database.dbOpen(self, guild_id)

        query = "SELECT setting_id, setting_data FROM main"

        # Read the settings from the database
        result = Database.dbExecute(self, cursor, guild_id, query, list(), True)

        # Read all of the settings, and store them in a dictionary
        for each_result in result:
            # Save all of the settings
            Database.Main[guild_id][each_result[0]] = each_result[1]

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        # Check if we have been here before.
        if not Database.Main.get(guild.id, False):
            # Create a new entry in the Main dictionary for the new guild
            Database.Main[guild.id] = dict()

            # Open then close a database file, to create it.
            Database.cursor[guild.id] = self.dbOpen(guild.id)
            self.dbClose(guild.id)

            # Reload the databases
            self.loadGuildDatabase(guild.id)

    def dbUpdateSchema(self, guild_id: int, cursor):
        """
        dbUpdateSchema(self, guild_id as Integer, cursor as Database handle)
        Updates the schema of the guild if it hasn't been updated since the bot rebooted.
        Returns nothing.
        """

        # Read the current version, on new it shouldn't return anything.
        try:
            cursor.execute(
                "SELECT setting_data FROM main WHERE setting_id = 'schemaVersion'"
            )
            schemaVersion = cursor.fetchone()
            schemaVersion = int(schemaVersion[0])

        except sqlite3.Error:
            schemaVersion = 0

        # Record the original version
        originalSchemaVersion = schemaVersion

        if schemaVersion < 1:  # Create main tables, for settings storage.
            cursor.execute(
                """
                           CREATE TABLE IF NOT EXISTS main(
                           setting_id TEXT,
                           setting_data TEXT,
                           PRIMARY KEY("setting_id")
                           )
                           """
            )

        if schemaVersion < 6:
            # Add guild name to database
            schemaVersion = 6
            guildName = str(self.client.get_guild(guild_id))
            cursor.execute(
                "INSERT INTO main(setting_id, setting_data) VALUES(?,?)",
                ("serverName", guildName),
            )

        if schemaVersion < 12:
            # Added change_prefix support.
            schemaVersion = 12
            cursor.execute(
                "INSERT INTO main(setting_id, setting_data) VALUES ('prefix', '.')"
            )

        if schemaVersion < 15:
            # Add levels_settings table
            schemaVersion = 15
            cursor.execute(
                f"""
                            CREATE TABLE IF NOT EXISTS levels_settings(
                            setting_id TEXT,
                            setting_data TEXT
                            )
                           """
            )

            cursor.execute(
                f"""
                            INSERT INTO levels_settings(setting_id, setting_data)
                            VALUES ('initialRun', 1)
                           """
            )

        if schemaVersion < 16:
            # Add reddit autolink
            schemaVersion = 16
            cursor.execute(
                f"""
                            CREATE TABLE IF NOT EXISTS reddit_settings(
                            setting_id TEXT,
                            setting_data TEXT
                            )
                           """
            )
            cursor.execute(
                f"""
                           INSERT INTO reddit_settings(setting_id, setting_data)
                           VALUES ('autolink', '1')
                           """
            )

        if originalSchemaVersion != schemaVersion:
            # If this is a new database, we have to insert first.
            if originalSchemaVersion == 0:
                cursor.execute(
                    "INSERT INTO main(setting_id, setting_data) VALUES(?,?)",
                    ("schemaVersion", schemaVersion),
                )
            else:  # Otherwise update the database
                cursor.execute(
                    "UPDATE main SET setting_data = ? WHERE setting_id = ?",
                    (schemaVersion, "schemaVersion"),
                )

            print(
                f"Database updated from {originalSchemaVersion} to {schemaVersion} for {self.client.get_guild(guild_id)} - {guild_id}"
            )

        Database.Main[guild_id]["SchemaUpToDate"] = True

    def dbOpen(self, guild_id: int):
        """
        Opens the database based on the guild_id
        guild_id - ctx.guild.id or message.guild.id
        """
        db_file_name = f"db/{guild_id}.db3"

        # Open database file
        db = Database.connection[guild_id] = sqlite3.connect(db_file_name)
        cursor = db.cursor()

        return cursor

    def dbClose(self, guild_id):
        """
        Commits and closes the database
        """
        # Save and close the database
        Database.connection[int(guild_id)].commit()
        Database.cursor[int(guild_id)].close()
        Database.connection[int(guild_id)].close()

    @commands.command(hidden=True)
    @commands.is_owner()
    @commands.dm_only()
    async def unloaddb(self, ctx, guild_id):
        """
            DANGER WILL ROBINSON

            This is used to close a database forcefully

            You will have major problems after running this.
            And then the bot will exit.
        """
        import time

        self.dbClose(guild_id)

        for x in range(5, 0, -1):
            print("DATABASE FORCEFULLY CLOSED. YOU ARE ABOUT TO HAVE PROBLEMS.")
            print(f"Exiting in {x} seconds.")
            time.sleep(1)
        quit()

    def dbExecute(
        self,
        cursor,
        guild_id: int,
        query: str,
        values: list = (),
        fetchAll: bool = False,
        returnRows: bool = False,
        **kwargs,
    ):
        """
        dbExecute(self, guild_id as Integer, query as String, values as List, fetchAll as boolean)

        self - self
        cursor - Database handle
        guild_id - ctx.guild.id or message.guild.id
        query - SQL formatted query
        values - Values for the sql query.
        fetchAll - True to return all rows, False to return one row. Default to False

        Function will create database if one does not exist.
        Database filename will be  {guild_id}.db3

        returns None if an error occours
        returns result of query if successful
        """

        # Run dbUpdateSchema if the file is new or hasn't been checked since bot startup.
        if not Database.Main[guild_id].get("SchemaUpToDate", False):
            Database.dbUpdateSchema(self, guild_id, cursor)

        try:
            # Run our query
            cursor.execute(query, values)

        except sqlite3.Error as error:
            # Pass hide_error = True in call to hide error output
            if not kwargs.get("hide_error", False):
                # If there is an error, will print to console and return None
                logger.warning(
                    f"SQL Error\nquery: {query} \nvalues: {values}\nerror: {error}"
                )
            raise  # re-raise exception.

        # Return all rows, or just one.
        if fetchAll:
            result = cursor.fetchall()
        else:
            result = cursor.fetchone()

        # Commit the database
        Database.connection[guild_id].commit()

        if returnRows:
            return result, cursor.rowcount

        return result

    @commands.command(hidden=True)
    @commands.is_owner()
    @commands.dm_only()
    async def run_backup(self, ctx):
        """
        Manually runs database backups
        """
        logger.info("Manual Backup Run")
        await self.run_backup_work()

    @tasks.loop(hours=1)
    async def run_backup_loop(self):
        """
        Automatically run the backup script
        """
        if datetime.datetime.utcnow().hour == 5:
            logger.info("Automatic Backup Run")
            await self.run_backup_work()

    async def run_backup_work(self):

        # Make sure the bot is ready before starting
        await self.client.wait_until_ready()

        # Guard Clause
        if backup["method"] == "none":
            return
        if not backup["method"] == "ftp" or backup["method"] == "copyonly":
            return

        upload_files = list()
        successful_upload = list()

        # Check if backup directory exists, if not create it
        if not os.path.exists(backup["backup_path"]):
            os.mkdir(backup["backup_path"])

        # Loop through the active databases
        for filename in os.listdir("./db"):
            if filename.endswith(".db3"):
                # Find the guild ID based on filename
                guild_id = int(f"{filename[:-4]}")

                new_filename = (
                    f'{guild_id}-{datetime.datetime.now().strftime("%Y%m%d%H%M%S")}.db3'
                )

                try:
                    # Make a copy of the file
                    copyfile(
                        f"./db/{filename}", f"{backup['backup_path']}{new_filename}"
                    )
                    logger.info(
                        f"File {guild_id}.db3 copied to {backup['backup_path']}."
                    )

                    upload_files.append(new_filename)

                except OSError:
                    logger.warning(
                        ">>>>>>>>OS Error when copying to backup file.<<<<<<<<"
                    )

        if backup["method"] == "ftp":
            try:
                async with aioftp.ClientSession(
                    backup["upload_server"],
                    backup["upload_port"],
                    backup["user"],
                    backup["passwd"],
                ) as client:
                    for each in upload_files:
                        try:
                            logger.info(f"Uploading {each}...")
                            await client.upload(
                                f"{backup['backup_path']}{each}",
                                f"{backup['upload_path']}{each}",
                                write_into=True,
                            )

                            successful_upload.append(each)
                        except:
                            logger.warning(">>>>>>>>Upload error.<<<<<<<<")
            except:
                logger.warning(">>>>>>>>FTP Connection error to backup server.<<<<<<<<")
                return

            for each in successful_upload:
                os.remove(f"{backup['backup_path']}{each}")

        logger.info("Backup complete")

    def writeSettings(self, guild_id):
        """
        Write settings to the database.
        """
        # Disable all the no-member violations in this function for references to self.name
        # pylint: disable=no-member

        if hasattr(guild_id, "id"):
            guild_id = guild_id.id

        cursor = Database.cursor[guild_id]

        values = list()

        for setting_key in Database.Cogs[self.name][guild_id]["settings"]:

            setting_data = Database.Cogs[self.name][guild_id]["settings"][setting_key]

            # Check if the setting has an id attribute, if so save that instead of the object.
            if hasattr(
                Database.Cogs[self.name][guild_id]["settings"][setting_key], "id"
            ):
                setting_data = setting_data.id

            query = f"UPDATE {self.name}_settings SET setting_data = ? WHERE setting_id = ? "
            values = (setting_data, setting_key)
            _, rows = Database.dbExecute(  # Not using the result, so not saving it.
                self, cursor, guild_id, query, values, False, True
            )

            # Setting has not been saved before
            if rows == 0:
                # Insert the row
                query = f"INSERT INTO {self.name}_settings (setting_id, setting_data) VALUES (?, ?)"
                values = (setting_key, setting_data)
                Database.dbExecute(self, cursor, guild_id, query, values)

    def readSettings(self):
        """Used to read all of the guilds settings."""
        # Disable all the no-member violations in this function for references to self.name
        # pylint: disable=no-member

        # Create the dictionary if it doesn't exist for the cog
        if not Database.Cogs.get(self.name, False):
            Database.Cogs[self.name] = dict()

        for guild_id in Database.Main:
            Database.readSettingsGuild(self, guild_id)

    def readSettingsGuild(self, guild_id):
        """Used to read a specific guilds settings"""
        # Disable all the no-member violations in this function for references to self.name
        # pylint: disable=no-member

        Database.Cogs[self.name][guild_id] = dict()
        Database.Cogs[self.name][guild_id]["settings"] = dict()

        # Set database handle
        cursor = Database.cursor[guild_id]

        # Query the database
        query = f"SELECT setting_id, setting_data FROM {self.name}_settings"

        try:
            result = Database.dbExecute(self, cursor, guild_id, query, list(), True)

        except sqlite3.OperationalError as e:
            # The table doesn't exist, so we're going to create it and re-run the query.
            if "no such table" in e.args[0]:
                insert_query = f"""CREATE TABLE IF NOT EXISTS {self.name}_settings(
                                    setting_id TEXT, setting_data TEXT)"""
                Database.dbExecute(self, cursor, guild_id, insert_query)
                logger.info(f"{self.name}_settings table created for {guild_id}.")

                result = Database.dbExecute(self, cursor, guild_id, query, list(), True)

        # Handle to access guild
        handle = Database.Cogs[self.name][guild_id]

        # Read all of the settings, and store them in a dictionary
        for each_result in result:
            # Save all of the settings

            # If the setting is completely numeric, save it as an integer, otherwise leave it a string
            if each_result[1] == None:
                # Check for None before allowing .isnumeric to run to prevent error
                handle["settings"][each_result[0]] = None

            elif each_result[1].isnumeric():
                handle["settings"][each_result[0]] = int(each_result[1])

            else:
                handle["settings"][each_result[0]] = each_result[1]

        # If the cog does not have the enabled flag stored in memory, set it to True
        if not Database.Cogs[self.name][guild_id]["settings"].get("enabled", False):
            Database.Cogs[self.name][guild_id]["settings"]["enabled"] = True


def setup(client):
    """
    DatabaseSetup setup
    """
    logger.info(f"Loading {__name__}...")
    client.add_cog(Database(client))
    logger.info(f"Loaded {__name__}")
