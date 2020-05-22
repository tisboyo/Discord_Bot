export LC_ALL=C.UTF-8
export LANG=C.UTF-8
cd ~/Discord_Bot
git pull
pipenv sync
nodemon --watch ./ --watch ./cogs/ -e py --delay 5 main.py
