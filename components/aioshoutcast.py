"""aioshoutcast - shoutcast interface for python3 asyncio"""

import xml.etree.ElementTree as etree
from urllib.parse import urlencode, quote_plus

import os
import glob

from pyparsing import *

import asyncio

import aiohttp

import random

import logging

logger = logging.getLogger(__name__)


class ShoutCast(object):
    def __init__(self, dev_id):
        """ Creates a Shoutcast API instance """

        self.loop = asyncio.get_event_loop()

        self.dev_id = dev_id

        self.save_dir = "components/saved"
        self.cache_subdir = "shoutcast_cache"

        self.full_cache_dir = self.save_dir + '/' + self.cache_subdir

        if not os.path.exists(self.full_cache_dir):
            os.makedirs(self.full_cache_dir)

        self.url_base = ""
        self.search_url = 'http://api.shoutcast.com/legacy/stationsearch?k={0}&search={1}'
        self.get_all_genres_url = 'http://api.shoutcast.com/legacy/genrelist?k={0}'
        self.get_stations_by_genre_url = 'http://api.shoutcast.com/legacy/genresearch?k={0}&genre={1}'
        self.tune_in_url = 'http://yp.shoutcast.com/{0}?id={1}'

    async def fetch(self, session, url):
        async with session.get(url) as response:
            return await response.text()

    async def update_cache_all(self):

        full_file_path = self.full_cache_dir + "/*.xml"

        files = glob.glob(full_file_path)
        for f in files:
            os.remove(f)

        genre_list = await self.get_list_of_genres()

        for genre in genre_list:
            await self.update_cache_by_genre(genre)

    def genres(self):
        return asyncio.run_coroutine_threadsafe(self.get_list_of_genres(), self.loop)

    async def get_list_of_genres(self):
        url = self.get_all_genres_url.format(self.dev_id)

        async with aiohttp.ClientSession() as session:
            genre_xml = await self.fetch(session, url)

        genre_list = etree.fromstring(genre_xml)

        result = tuple(genre.get('name') for genre in genre_list.findall('genre') if genre.get('name'))

        return result

    async def update_cache_by_genre(self, genre):
        """fetch and cache the xml file for a particular genre."""

        url = self.get_stations_by_genre_url.format(self.dev_id, genre)

        async with aiohttp.ClientSession() as session:
            genre_stations_xml = await self.fetch(session, url)

        full_file_path = self.full_cache_dir + '/' + genre + ".xml"

        try:
            os.remove(full_file_path)
        except OSError:
            logger.debug("unable to remove old cache file")

        with open(full_file_path, 'w') as f:
            print(f"Updating xml cache for the genre {genre}")
            logger.debug(f"Updating xml cache for the genre {genre}")
            f.write(genre_stations_xml)

    def load_cached_stations_by_genre(self, genre):

        result = []

        full_file_path = self.full_cache_dir + '/' + genre + ".xml"

        with open(full_file_path, 'r') as f:
            stationlist = etree.parse(f)

        self.url_base = stationlist.find('./tunein').attrib['base']

        for station in stationlist.findall('station'):
            entry = (station.get('name'),
                     station.get('id'),
                     station.get('br'),
                     station.get('ct'),
                     station.get('lc'))
            result.append(entry)

        return tuple(result)

    def tunein(self, station_id):
        return asyncio.run_coroutine_threadsafe(self.get_station_playlist(station_id), self.loop)

    async def get_station_playlist(self, station_id):
        """ Returns a pls playlist object"""
        url = self.tune_in_url.format(self.url_base, station_id)

        async with aiohttp.ClientSession() as session:
            pls_obj = await self.fetch(session, url)

        pls_txt = pls_obj.read().decode('ascii')

        pls = PlsPlaylist(pls_txt)

        return pls


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

        self.text = pls

        # logger.debug(f"PLS File: {pls}")

        equals = Suppress(Literal('='))

        header = Suppress(Literal('[playlist]')) + Suppress(LineEnd())
        num_entries = Word(nums)("num_entries")
        num_entries_line = Suppress(Literal('numberofentries=')) + num_entries + Suppress(LineEnd())
        stream_url = Word(printables)("stream_url")
        file_num = Word(nums)("entry_num")
        file_line = Suppress(Literal('File')) + file_num + equals + stream_url + Suppress(LineEnd())
        title_text = Combine(OneOrMore(Word(printables) | White(' ', max=1) + ~White()))("title_text")
        title_num = Word(nums)
        title_line = Suppress(Literal('Title')) + Suppress(title_num) + equals + title_text + Suppress(
            LineEnd())
        length_num = Word(nums)
        length_val = Combine(Optional(Literal('-')) + Word(nums))
        length_line = Suppress(Literal('Length')) + Suppress(length_num) + equals + length_val + Suppress(
            LineEnd())
        stream_stanza = Group(file_line + title_line + length_line)
        version_num = Word(nums)("version_num")
        version_line = Suppress(Literal('Version')) + equals + version_num + Suppress(LineEnd())
        po = header + num_entries_line + Dict(ZeroOrMore(stream_stanza)) + version_line

        self.playlist = po.parseString(self.text)

        # logger.debug(self.playlist)

    def get_first_url(self):
        return self.playlist[1]['stream_url']

    def get_load_balanced_url(self):
        i = random.randint(1, int(self.playlist['num_entries']) - 1)

        return self.playlist[i]['stream_url']


async def main():
    # async with aiohttp.ClientSession() as session:
    #     html = await fetch(session, 'http://python.org')
    #     print(html)

    sc = ShoutCast('3lQLf69cLNZK2XwP')

    # await sc.update_cache_all()
    # await sc.update_cache_by_genre('Classical')


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
