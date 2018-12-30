from base_classes import Opus, AudioComponent, MenuList
import json
import asyncio
from mpd.asyncio import MPDClient

import logging

logger = logging.getLogger(__name__)

"""
Opuscule library component: play audio from local sources.

This component requires mpd to play audio.
"""

class LibraryComponent(AudioComponent):
    def __init__(self, sfavs):
        # Do Startup tasks
        super().__init__("Library", "Lib", "Locally Stored Audio")
        self.sfavs = sfavs

        self.mpdc = MPDClient()
        self.loop = asyncio.get_event_loop()
        self.REQ_MET_MPD = False

        self.start_client()

        # This is part of the Streaming hierarchy
        self.component = "library"
        # Local pointers into the radio state and the streaming client
        # Zero the client state on startup
        self.clear_client()

        # Setup the menu items
        self.favs_save_file = "saved/{}_favorites.json".format(self.component)
        self.favorites_node.menu_labels['comment'] = "Library Favorites"
        self.favorites_node.component = self.component
        self.load_favorites()

        self.playlists_node = LibraryMenuList("Playlists", "Pls", "My playlists.")
        self.add_child(self.playlists_node)
        self.genres_node = LibraryMenuList("Genres", "Gnr", "Library By Genre")
        self.add_child(self.genres_node)
        self.artists_node = LibraryMenuList("Artists", "Art", "Library By Artist")
        self.add_child(self.artists_node)
        self.albums_node = LibraryMenuList("Albums", "Alb", "Library By Album")
        self.add_child(self.albums_node)

        # Populate the Library
        asyncio.run_coroutine_threadsafe(self.refresh_library(), self.loop)

    def start_client(self):
        return self.loop.run_until_complete(self.__async__start_client())

    async def __async__start_client(self):
        try:
            await self.mpdc.connect('localhost', 6600)
        except Exception as e:
            print("Connection failed:", e)
            self.REQ_MET_MPD = False
        await self.mpdc.consume(0)

    def clear_client(self):
        return self.loop.run_until_complete(self._clear_client())

    async def _clear_client(self):
        await self.mpdc.clear()

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
                    if fav['type'] == 'playlist':
                        this_opus = PlaylistOpus(fav['name'], self.mpdc)
                        self.favorites_node.add_child(this_opus)
                    elif fav['type'] == 'slice':
                        this_opus = SliceOpus(fav['name'], self.mpdc, fav['terms'])
                        self.favorites_node.add_child(this_opus)
                self.sfavs.update_one_favorite_menu(self)
        except json.JSONDecodeError:
            pass  # log an error message
        except FileNotFoundError:
            pass  # log an error message

    async def refresh_library(self):
        await self.refresh_playlists()
        await self.refresh_genres()
        await self.refresh_artists()
        await self.refresh_albums()

    async def refresh_playlists(self):
        logger.debug("LIBRARY: checking for playlists")

        available_playlists = await self.mpdc.listplaylists()

        self.playlists_node.reset_children()

        for playlist in available_playlists:
            # Add a Playlist opera to the playlist menu
            playlist_name = playlist['playlist']
            logger.debug("LIBRARY: found playlist " + playlist_name)
            self.playlists_node.add_child(PlaylistOpus(playlist_name, self.mpdc))

        logger.debug("LIBRARY: playlist check complete")

    async def refresh_genres(self):

        logger.debug("LIBRARY: building genre list")

        self.genres_node.reset_children()

        genres = await self.mpdc.list('genre')

        for genre in genres:
            this_genre = LibraryMenuList(genre, "", "")
            self.genres_node.add_child(this_genre)
            this_genre.add_child(SliceOpus("All songs in {}".format(genre), self.mpdc, ['genre', genre]))

            # By Album

            by_album = LibraryMenuList("By Album", "", "")
            this_genre.add_child(by_album)

            albums = await self.mpdc.list('album', 'genre', genre)
            for album in albums:
                by_album.add_child(SliceOpus(album, self.mpdc, ['genre', genre, 'album', album]))

            # By Artist

            by_artist = LibraryMenuList("By Artist", "", "")
            this_genre.add_child(by_artist)

            artists = await self.mpdc.list('artist', 'genre', genre)
            for artist in artists:
                this_artist = LibraryMenuList(artist, "", "")
                by_artist.add_child(this_artist)
                this_artist.add_child(SliceOpus("All songs by {}".format(artist), self.mpdc,
                                                ['artist', artist, 'genre', genre]))
                this_artist_albums = LibraryMenuList("By Album", "", "")
                this_artist.add_child(this_artist_albums)
                artist_albums = await self.mpdc.list('album', 'artist', artist, 'genre', genre)
                for artist_album in artist_albums:
                    this_artist_albums.add_child(SliceOpus(artist_album,
                                                           self.mpdc, ['album', artist_album, 'artist', artist,
                                                                       'genre', genre]))

        logger.debug("LIBRARY: genre list complete")

    async def refresh_artists(self):

        logger.debug("LIBRARY: building artist list")

        self.artists_node.reset_children()

        artists = await self.mpdc.list('artist')

        for artist in artists:
            this_artist = LibraryMenuList(artist, "", "")
            self.artists_node.add_child(this_artist)
            this_artist.add_child(SliceOpus("All songs by {}".format(artist), self.mpdc,
                                            ['artist', artist]))
            this_artist_albums = LibraryMenuList("By Album", "", "")
            this_artist.add_child(this_artist_albums)
            artist_albums = await self.mpdc.list('album', 'artist', artist)
            for artist_album in artist_albums:
                this_artist_albums.add_child(SliceOpus(artist_album,
                                                       self.mpdc, ['album', artist_album, 'artist', artist]))

        logger.debug("LIBRARY: artist list complete")

    async def refresh_albums(self):

        logger.debug("LIBRARY: building album list")

        self.albums_node.reset_children()

        albums = await self.mpdc.list('album')
        for album in albums:
            self.albums_node.add_child(SliceOpus(album, self.mpdc,
                                                 ['album', album]))

        logger.debug("LIBRARY: ablum list complete")

    def requirements_met(self):
        return True


class LibraryMenuList(MenuList):
    def __init__(self, name, short_name, comment):
        super().__init__(name, short_name, comment)
        self.component = "library"


class PlaylistOpus(Opus):
    def __init__(self, name, mpd_client):
        super().__init__(name, "", "")

        self.mpdc = mpd_client
        self.component = "library"
        # Initial play preferences
        self.random = "none"
        self.repeat = "none"
        self.playlist_name = name
        self.pause_support = True

    def opus_play(self):
        self.mpdc.clear()
        self.mpdc.load(self.playlist_name)
        self.mpdc.play()

    def opus_stop(self):
        self.mpdc.stop()
        self.mpdc.clear()

    def opus_pause(self):
        self.mpdc.pause(1)

    def opus_unpause(self):
        self.mpdc.pause(0)

    def opus_get_metadata(self):
        md = {'component': self.component,
              'type': 'playlist',
              'name': self.menu_labels['name'],
              }
        return md


class SliceOpus(Opus):
    """A library collection.

    """

    def __init__(self, name, mpd_client, find_terms):
        super().__init__(name, "", "")

        self.find_terms = find_terms
        self.component = "library"
        self.mpdc = mpd_client
        self.loop = asyncio.get_event_loop()
        self.pause_support = True
        self.repeat_support = True
        self.shuffle_support = True

    def opus_play(self):
        asyncio.run_coroutine_threadsafe(self._opus_play(), self.loop)

    async def _opus_play(self):
        await self.mpdc.clear()
        await self.mpdc.findadd(*self.find_terms)
        await self.mpdc.random(self.shuffle)
        await self.mpdc.repeat(self.repeat)
        await self.mpdc.play()

    def opus_stop(self):
        asyncio.run_coroutine_threadsafe(self._opus_stop(), self.loop)

    async def _opus_stop(self):
        await self.mpdc.stop()
        await self.mpdc.clear()

    def opus_pause(self):
        asyncio.run_coroutine_threadsafe(self._opus_pause(), self.loop)

    async def _opus_pause(self):
        await self.mpdc.pause(1)

    def opus_unpause(self):
        asyncio.run_coroutine_threadsafe(self._opus_unpause(), self.loop)

    async def _opus_unpause(self):
        await self.mpdc.pause(0)

    def opus_next(self):
        asyncio.run_coroutine_threadsafe(self._opus_next(), self.loop)

    async def _opus_next(self):
        curr_status = {}
        try:
            curr_status = await self.mpdc.status()
        except Exception as e:
            logger.error("Status error: %s", e)
        else:
            logger.debug("Status success!")

        if 'nextsong' in curr_status:
            await self.mpdc.next()

    def opus_previous(self):
        asyncio.run_coroutine_threadsafe(self._opus_previous(), self.loop)

    async def _opus_previous(self):
        # if we find more than 5 seconds into the track, previous restarts the track; elsewise,
        # we go to the previous track in the playlist
        curr_status = {}
        try:
            curr_status = await self.mpdc.status()
        except Exception as e:
            logger.error("Status error: %s", e)
        else:
            logger.debug("Status success!")

        if 'time' in curr_status:
            elapsed_secs = curr_status['time'].split(':')[0]
            if int(elapsed_secs) > 5:
                await self.mpdc.seekcur(0)
            else:
                await self.mpdc.previous()

    def opus_update_shuffle(self):
        self.mpdc.random(self.shuffle)

    def opus_update_repeat(self):
        self.mpdc.repeat(self.repeat)

    def opus_get_metadata(self):
        md = {'component': self.component,
              'type': 'slice',
              'name': self.menu_labels['name'],
              'terms': self.find_terms,
              }
        return md
