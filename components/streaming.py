from base_classes import Opus, MenuList, AudioComponent
import json
import asyncio
from mpd.asyncio import MPDClient

import logging

logger = logging.getLogger(__name__)

"""
Opuscule streaming component: play streaming audio from remote sources.

This component requires mpd to play audio.

TODO: implement a way to pull feeds in from Dirble (in a kind, responsbile
way...).
"""

class StreamingComponent(AudioComponent):
    def __init__(self, sfavs, cpo):
        # Do Startup tasks
        super().__init__("Streaming", "Str", "Streaming Audio Services")

        # We have our own mpd client
        self.mpdc = MPDClient()
        self.loop = asyncio.get_event_loop()
        self.REQ_MET_MPD = False
        # Use a return value here to set up fitness?
        self.start_client()

        # Features
        self.enable_dirble = False

        # This is part of the Streaming hierarchy
        self.component = "streaming"
        # Config parser object
        self.cpo = cpo
        # Zero the client state on startup
        self.mpdc.clear()
        # Super favorites
        self.sfavs = sfavs

        # Set up the areas of the component

        self.favs_save_file = "saved/{}_favorites.json".format(self.component)
        self.favorites_node.menu_labels['comment'] = "Streaming Favorites"
        self.favorites_node.component = self.component
        self.load_favorites()

        self.custom_node = StreamingMenuList("Custom", "Cstm", "My custom stations")
        self.dirble_node = StreamingMenuList("Dirble", "Drbl", "Streaming Audio Directory")

        self.add_child(self.custom_node)
        if self.enable_dirble:
            self.add_child(self.dirble_node)

        # Reference Streaming menu in the superfavorites

        # Testing purposes, set up custom stations (backed from where?)
        custom_stations = [
            StreamingOpus("AncientFM", "Early music.",
                          "http://5.152.208.98:8058/", self.mpdc, genre="Classical", subgenre="Early"),
            StreamingOpus("Venice Classsic Radio", "Beautiful classical music.",
                          "http://174.36.206.197:8000/stream", self.mpdc, genre="Classical"),
            StreamingOpus("Bartok Radio", "Hungarian classical radio.",
                          "http://mr-stream.mediaconnect.hu/4741/mr3.mp3", self.mpdc, genre="Classical"),
        ]
        # Populate the custom menu
        for station in custom_stations:
            self.custom_node.add_child(station)

        # When we add an opus to a collection, we want to keep track of the genre/subgenre structure?

    def start_client(self):
        return self.loop.run_until_complete(self.__async__start_client())

    async def __async__start_client(self):
        try:
            await self.mpdc.connect('localhost', 6600)
        except Exception as e:
            print("Connection failed:", e)
            self.REQ_MET_MPD = False
        self.mpdc.consume(0)

    def requirements_met(self):
        # req_met = True
        #
        # if not self.REQ_MET_MPD:
        #     req_met = False

        return True

    def save_favorites(self):
        favs = []
        for fav in self.favorites_node.children:
            favs.append(fav.opus_get_metadata())

        json_favs = json.dumps(favs)

        with open(self.favs_save_file, mode='w', encoding='utf-8') as the_file:
            the_file.write(json_favs)

    def load_favorites(self):
        try:
            with open(self.favs_save_file, mode='r', encoding='utf-8') as the_file:
                favs = json.loads(the_file.read())
                for fav in favs:
                    this_opus = StreamingOpus(fav['name'], fav['comment'], fav['url'],
                                              self.mpdc, fav['genre'], fav['subgenre'])
                    self.favorites_node.add_child(this_opus)
                self.sfavs.update_one_favorite_menu(self)
        except json.JSONDecodeError:
            pass
        except FileNotFoundError:
            pass


class StreamingMenuList(MenuList):
    def __init__(self, name, short_name, comment):
        super().__init__(name, short_name, comment)
        self.component = "streaming"


class StreamingOpus(Opus):
    """A piece of streaming media.
    
    """

    playlist_name = "opus_streaming_playlist"

    def __init__(self, name, comment, url, mpd_client, genre="", subgenre=""):
        self.url = url

        if not name:
            name = self.url

        super().__init__(name, "", comment)

        self.mpdc = mpd_client
        self.genre = genre
        self.subgenre = subgenre
        self.component = "streaming"
        self.loop = asyncio.get_event_loop()
        self.file = ""
        self.title = ""
        self.name = ""
        self.pos = ""
        self.id = ""

    def opus_play(self):
        asyncio.run_coroutine_threadsafe(self._opus_play(), self.loop)

    async def _opus_play(self):
        await self.mpdc.clear()
        await self.mpdc.add(self.url)
        await self.mpdc.play()

    def opus_stop(self):
        asyncio.run_coroutine_threadsafe(self._opus_stop(), self.loop)

    async def _opus_stop(self):
        await self.mpdc.stop()
        await self.mpdc.clear()

    def opus_get_metadata(self):
        opus_metadata = {'component': self.component,
                         'type': 'stream',
                         'name': self.menu_labels['name'],
                         'comment': self.menu_labels['comment'],
                         'title': self.menu_labels['name'],
                         'url': self.url,
                         'genre': self.genre,
                         'subgenre': self.subgenre
                         }

        return opus_metadata
