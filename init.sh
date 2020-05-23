# Make sure to re-create docker container when changing this file.

export LC_ALL=C.UTF-8
export LANG=C.UTF-8
cd /workspaces/Discord_Bot

git init
git remote add origin https://github.com/tisboyo/Discord_Bot.git
git fetch --all
git reset --hard origin/$branch
git checkout $branch

pipenv install
pipenv run python main.py