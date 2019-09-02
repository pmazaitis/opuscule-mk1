from base_classes import Opus, MenuList, AudioComponent
import json
import asyncio
from mpd.asyncio import MPDClient

from pyparsing import *

#from components.shoutcast import ShoutCast

from components.aioshoutcast import ShoutCast, PlsPlaylist

from urllib.parse import quote_plus

import random

import logging

logger = logging.getLogger(__name__)

"""
Opuscule streaming component: play streaming audio from remote sources.

This component requires mpd to play audio.

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

        # This is part of the Streaming hierarchy
        self.component = "streaming"
        # Config parser object
        self.cpo = cpo
        # Zero the client state on startup
        self.mpdc.clear()
        # Super favorites
        self.sfavs = sfavs

        # Features
        self.enable_crd = self.cpo.getboolean('streaming', 'crd_enable')
        self.enable_shoutcast = self.cpo.getboolean('streaming', 'shoutcast_enable')

        if self.enable_shoutcast:
            self.shoutcast_api_key = self.cpo.get('streaming', 'shoutcast_api_key')
            self.sc = ShoutCast(self.shoutcast_api_key)

        # Set up the areas of the component

        self.favs_save_file = "saved/{}_favorites.json".format(self.component)
        self.favorites_node.menu_labels['comment'] = "Streaming Favorites"
        self.favorites_node.component = self.component
        self.load_favorites()

        self.custom_node = StreamingMenuList("Custom", "Cstm", "My custom stations")
        self.add_child(self.custom_node)

        if self.enable_crd:
            self.crd_node = StreamingMenuList("Community Radio", "CRD", "Community-driven radio directory")
            self.add_child(self.crd_node)

        if self.enable_shoutcast:
            self.shoutcast_node = StreamingMenuList("Shoutcast", "SC", "Shoutcast radio directory")
            self.add_child(self.shoutcast_node)
            # TODO: re-implement this without the library to decouple XML retreival and tree building
            self.init_shoutcast()

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

    def init_shoutcast(self):

        genre_node = StreamingMenuList("Genres", "Gnr", "Shoutcast radio directory genres")

        logger.debug(f"Getting genre list.")

        # for genre in self.sc.genres():
        for genre in ['Classical', 'Dance', 'Early Classical']:
            logger.debug(f"Populating node for genre: {genre}")
            this_genre_node = StreamingMenuList(genre, "", "")
            qgenre = quote_plus(genre)
            for station in self.sc.stations(qgenre):
                logger.debug(f"Populating node for genre: {genre} with station: {station[0]}")
                this_station = ShoutcastOpus(self.sc,
                                             self.mpdc,
                                             station[0],
                                             station[1],
                                             station[2],
                                             genre,
                                             station[3],
                                             station[4],
                                             )
                this_genre_node.add_child(this_station)
            genre_node.add_child(this_genre_node)
        self.shoutcast_node.add_child(genre_node)

    # def init_crd(self):
    #
    #     self.crb_genres = [
    #         'adult contemporary',
    #         'alternative',
    #         'ambient',
    #         'anime',
    #         'blues',
    #         'chillout',
    #         'classical',
    #         'community radio',
    #         'country',
    #         'dance',
    #         'edm',
    #         'electronic',
    #         'hard rock',
    #         'hiphop',
    #         'house',
    #         'lounge',
    #         'pop',
    #         'progressive',
    #         'reggae',
    #         'techno',
    #         'trance',
    #         'world music',
    #     ]
    #
    #     self.crb_eras = [
    #         '20s',
    #         '30s',
    #         '40s',
    #         '50s',
    #         '60s',
    #         '70s',
    #         '80s',
    #         '90s',
    #         '00s',
    #     ]
    #
    #     self.crb_regions = [
    #         '',
    #         '',
    #         '',
    #         '',
    #         '',
    #         '',
    #         '',
    #         '',
    #         '',
    #         '',
    #         '',
    #         '',
    #         '',
    #         '',
    #         '',
    #         '',
    #         '',
    #         '',
    #         '',
    #         '',
    #         '',
    #         '',
    #         '',
    #         '',
    #         '',
    #         '',
    #         '',
    #         '',
    #         '',
    #     ]


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


# Shoutcast support


class ShoutcastOpus(Opus):
    playlist_name = "opus_streaming_playlist"

    def __init__(self, sc, mpd_client, name, streamid, br, genre, ct, lc, subgenre=""):
        super().__init__(name, "", "")

        self.sc = sc
        self.mpdc = mpd_client
        self.name = name
        self.streamid = streamid
        self.br = br
        self.genre = genre
        self.ct = ct
        self.lc = lc
        self.subgenre = subgenre
        self.component = "streaming"
        self.loop = asyncio.get_event_loop()
        self.file = ""
        self.title = ct
        self.url = None
        self.file = ""
        self.pos = ""
        self.id = ""

    def opus_play(self):
        logger.debug(f"Getting stream for {self.name} (ID: {self.streamid})")

        station_obj = self.sc.tune_in(self.streamid)

        playlist_string = station_obj.read().decode('ascii')

        pls = PlsPlaylist(playlist_string)

        self.url = pls.get_load_balanced_url()

        logger.debug(f"Got URL for {self.name}: {self.url}")

        asyncio.run_coroutine_threadsafe(self._opus_play(), self.loop)

    async def _opus_play(self):
        logger.debug(f"Playing stream for {self.name} (URL: {self.url})")
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



class PlsPlaylist(object):
    def __init__(self, pls):
        # Our grammar for parsing a pls into an object:
        #
        # pls_file    ::= header + num_entries + stanza* + version
        # header      ::= "[playlist]"
        # num_entries ::= "numberofentries=" + nums+
        # stanza      ::= file + title + length
        # file        ::= "file" + nums+ + "=" + stream_url
        # stream_url  ::= alphanums+
        # title       ::= "title" + nums+ + "=" + title_text
        # title_text  ::= alphanums+
        # length      ::= "length" + nums+ + "=" + length_val
        # length_val  ::= ["-"] + nums+
        # version     ::= "version=" + version_val
        # version_val ::= nums+

        logger.debug(f"PLS File: {pls}")

        equals = Suppress(Literal('='))

        header = Suppress(Literal('[playlist]')) + Suppress(LineEnd())
        num_entries = Word(nums)("num_entries")
        num_entries_line = Suppress(Literal('numberofentries=')) + num_entries + Suppress(LineEnd())
        stream_url = Word(printables)("stream_url")
        file_num = Word(nums)("entry_num")
        file_line = Suppress(Literal('File')) + file_num + equals + stream_url + Suppress(LineEnd())
        title_text = Combine(OneOrMore(Word(printables) | White(' ', max=1) + ~White()))("title_text")
        title_num = Word(nums)
        title_line = Suppress(Literal('Title')) + Suppress(title_num) + equals + title_text + Suppress(LineEnd())
        length_num = Word(nums)
        length_val = Combine(Optional(Literal('-')) + Word(nums))
        length_line = Suppress(Literal('Length')) + Suppress(length_num) + equals + length_val + Suppress(LineEnd())
        stream_stanza = Group(file_line + title_line + length_line)
        version_num = Word(nums)("version_num")
        version_line = Suppress(Literal('Version')) + equals + version_num + Suppress(LineEnd())
        po = header + num_entries_line + Dict(ZeroOrMore(stream_stanza)) + version_line

        self.playlist = po.parseString(pls)

        logger.debug(self.playlist)

    def get_load_balanced_url(self):
        i = random.randint(1, int(self.playlist['num_entries']))

        return self.playlist[i]['stream_url']
