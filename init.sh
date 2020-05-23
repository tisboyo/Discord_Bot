export LC_ALL=C.UTF-8
export LANG=C.UTF-8
cd /workspaces/Discord_Bot

rm Pipfile Pipfile.lock

git init
git remote add origin https://github.com/tisboyo/Discord_Bot.git
git fetch origin
git checkout -b master --track origin/master

git checkout $branch

pipenv install
pipenv run python main.py