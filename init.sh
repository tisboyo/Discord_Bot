export LC_ALL=C.UTF-8
export LANG=C.UTF-8
cd /workspaces/Discord_Bot
git pull
git checkout $branch
pipenv sync
pipenv run python main.py
