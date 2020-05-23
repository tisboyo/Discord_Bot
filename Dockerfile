FROM python:3.6
# FROM nikolaik/python-nodejs:python3.6-nodejs14

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



# Pull bot from github if on master
RUN if [ "{$branch}" = "master"]; then git clone https://github.com/tisboyo/Discord_Bot.git /root/Discord_Bot; fi

# Create the working directory
#RUN mkdir /workspaces
WORKDIR /workspaces/Discord_Bot

# Switch Branches
# RUN git checkout ${branch}

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
# RUN chmod +x /root/Discord_Bot/init.sh

# Expose port for debugging
EXPOSE 5678:5678

# Database volume
VOLUME /workspaces/Discord_Bot/db

ENTRYPOINT ["/bin/sh"]
CMD ["-c", "~/Discord_Bot/init.sh"]
