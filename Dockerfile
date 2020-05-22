FROM python:3.6
# FROM nikolaik/python-nodejs:python3.6-nodejs14

# Set pip to have cleaner logs and no saved cache
ENV PIP_NO_CACHE_DIR=false \
    PIPENV_HIDE_EMOJIS=1 \
    PIPENV_IGNORE_VIRTUALENVS=1 \
    PIPENV_NOSPIN=1 \
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
    branch='docker'


# Pull bot from github # && chmod +x -R ~/Discord_Bot/*.py
RUN git clone https://github.com/tisboyo/Discord_Bot.git /root/Discord_Bot

# Create the working directory
WORKDIR /root/Discord_Bot

# Switch Branches
RUN git checkout ${branch}

# Install needed libraries
RUN apt-get update && apt-get install -y \
	git \
    libespeak1 \
    ffmpeg

# Install nodemon
# RUN npm install -g nodemon

# Setup pipenv
RUN pip install pipenv
RUN pipenv install

# Set init.sh to executable
RUN chmod +x /root/Discord_Bot/init.sh

# Database volume
VOLUME /root/Discord_Bot/db

ENTRYPOINT ["/bin/sh"]
CMD ["-c", "~/Discord_Bot/init.sh"]
