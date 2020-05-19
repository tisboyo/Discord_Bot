# -*- coding: utf-8 -*-
"""
Discord Bot for HardwareFlare and others
@author: Tisboyo
"""

import logging
import os


# Logging level
logging_level = logging.INFO

# Authentication Keys
# Discord API Key
discord = dict(token=os.getenv("discord_token"),)

# Twitter API Key
twitter = dict(
    consumer_key=os.getenv("twitter_consumer_key"),
    consumer_secret=os.getenv("twitter_consumer_secret"),
    access_token=os.getenv("twitter_access_token"),
    access_token_secret=os.getenv("twitter_access_token_secret"),
)

# Backup Server
backup = dict(
    # Valid methods are none, ftp or copyonly
    method=os.getenv("backup_method"),
    # Path where files are copied to locally for backup, leave trailing slash
    backup_path=os.getenv("backup_path"),
    # Host to upload to for ftp
    upload_server=os.getenv("backup_server"),
    upload_port=int(os.getenv("backup_port")),
    # Full Path on ftp server, with trailing slash
    upload_path=os.getenv("backup_upload_path"),
    # FTP Username
    user=os.getenv("backup_ftp_username"),
    # FTP Password
    passwd=os.getenv("backup_ftp_passwd"),
)
