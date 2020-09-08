FROM python:3.8

# Set pip to have cleaner logs and no saved cache
ENV PIP_NO_CACHE_DIR=false \
    PIPENV_HIDE_EMOJIS=1 \
    PIPENV_IGNORE_VIRTUALENVS=1 \
    PIPENV_NOSPIN=1 \
    PIPENV_VENV_IN_PROJECT=1\
    PYTHONUNBUFFERED=1\
    discord_token='' \
    twitter_consumer_key='' \
    twitter_consumer_secret='' \
    twitter_access_token='' \
    backup_method='ftp' \
    backup_path='./db_backup' \
    backup_server='' \
    backup_port=21 \
    backup_upload_path='/' \
    backup_ftp_username='' \
    backup_ftp_passwd='' \
    branch='dev'



# Create the working directory
WORKDIR /workspaces/Discord_Bot

# Pull bot from github
RUN wget https://raw.githubusercontent.com/tisboyo/Discord_Bot/$branch/init.sh -O /workspaces/Discord_Bot/init.sh && chmod +x /workspaces/Discord_Bot/init.sh

# Install needed libraries
RUN apt-get update && apt-get install -y \
	git \
    libespeak1 \
    ffmpeg

# Setup pipenv
RUN pip install pipenv

# Expose port for debugging
EXPOSE 5678:5678

# Database volume
VOLUME /workspaces/Discord_Bot/db

ENTRYPOINT ["/bin/sh"]
CMD ["-c", "chmod +x /workspaces/Discord_Bot/init.sh && /workspaces/Discord_Bot/init.sh"]
