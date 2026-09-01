from RioEra.core.bot import RioBot
from RioEra.core.dir import dirr
from RioEra.core.git import git
from RioEra.core.userbot import Userbot
from RioEra.misc import dbb, heroku

from SafoneAPI import SafoneAPI
from .logging import LOGGER

dirr()
git()
dbb()
heroku()

app = RioBot()
userbot = Userbot()
api = SafoneAPI()


from .platforms import *

Apple = AppleAPI()
Carbon = CarbonAPI()
SoundCloud = SoundAPI()
Spotify = SpotifyAPI()
Resso = RessoAPI()
Telegram = TeleAPI()
YouTube = YouTubeAPI()

APP = "RIOERA_BOT"  # connect music api key "Dont change it"
