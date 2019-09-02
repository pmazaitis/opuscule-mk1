# Startup
from base_classes import Opus, MenuList, Command

# To support opus history
from collections import deque

# Whee!
import asyncio

# Logging
import logging

# Handle alsa audio only if supported
NO_ALSA = False
try:
    # noinspection PyUnresolvedReferences
    import alsaaudio
except ImportError:
    NO_ALSA = True

logger = logging.getLogger(__name__)


class Menu:
    """
    Handle the menu tree
    """

    def __init__(self):
        self.tree = MenuList('root', 'root', "The root of all weevil.")
        self.current_node = self.tree
        self.selected_node = None

    def jump(self, requested_component):
        # """
        # Move directly to a specified component.
        # :param requested_component:
        # :return:
        # """
        # for comp in self.registered_components:
        #     if comp.labels['name'] == requested_component:
        #         self.current_node = comp
        #         # Reset selected mode; return to clean state
        #         self.current_node.index = 0
        #         self.selected_node = self.current_node.children[self.current_node.index]
        pass

    def compose_data(self):

        menu_list = []

        for item in self.current_node.children:
            menu_list.append(item.menu_labels)

        if isinstance(self.selected_node, Opus):
            selected_type = "opus"
        elif isinstance(self.selected_node, MenuList):
            selected_type = "menulist"
        elif isinstance(self.selected_node, Command):
            selected_type = "command"
        else:
            selected_type = "unknown"

        updated_menu_data = {'path': self.current_node.get_path([]),
                             'list': menu_list,
                             'index': self.current_node.index,
                             'selkind': selected_type}

        return updated_menu_data


class NowPlaying:
    """
    Keep track of things that have been played.
    """

    def __init__(self):
        null_opus = Opus('Null', '', "Null Opus")
        self.current_opus = null_opus
        self.play_history = deque('', 100)
        self.data = {}
        self.reset_data()

    def add_to_history(self, opus):
        self.play_history.append(opus)

    def revert(self):
        """Revert to the previous opus in the history without destroying the added state."""
        self.current_opus = self.play_history[1]
        self.current_opus.opus_play()

    def load(self, opus):
        self.add_to_history(self.current_opus)
        self.current_opus = opus

    def reset_data(self):
        self.data = {'file': "",
                     'last-modified': "",
                     'artist': "",
                     'album': "",
                     'title': "",
                     'name': "",
                     'track': "",
                     'genre': "",
                     'date': "",
                     'disc': "",
                     'albumartist': "",
                     'time': "",
                     'duration': "",
                     'pos': "",
                     'id': "",
                     'package': "",
                     'agent': "",
                     'callsign': "",
                     'freq': "",
                     'mode': "",
                     'error': "",
                     'component': "",
                     'type': "",
                     'comment': "",
                     'url': "",
                     'subgenre': "",
                     }

    def update_data(self, song_data):

        self.reset_data()

        opus_data = self.current_opus.opus_get_metadata()

        logger.debug("Got opus data: %s", str(opus_data))

        for key in opus_data:
            logger.debug("Adding opus state: {} updated to {}".format(key, opus_data[key]))
            if key in self.data:
                self.data[key] = opus_data[key]
            else:
                logger.error("Key name {} unsupported in now_playing.".format(key))

        for key in song_data:
            logger.debug("Adding opus state: {} updated to {}".format(key, song_data[key]))
            if key in self.data:
                self.data[key] = song_data[key]
            else:
                logger.error("Key name {} unsupported in now_playing.".format(key))

    def get_data(self):
        return self.data


class Messages:
    # Keep track of messages, add them to the outgoing state
    #
    # Something like:
    #
    # [
    #   {'type': "FAULT", 'dist': 'SENDER", 'text': "Can't find the weasels."}, -- something went wrong
    #   {'type': "INFO", 'dist': 'ALL", 'text': "The weasels are behind the couch."}, -- something all should know
    #   {'type': "ALERT", 'dist': 'ALL", 'text': "NOAA Weasel Warning."}, -- important thing that all should know
    # ]
    def __init__(self):
        self.valid_message_types = ['FAULT', 'INFO', 'ALERT']
        self.pending_batch = []

    def queue_message(self, msgtype, msgtext, msgdist='ALL'):
        if msgtype in self.valid_message_types:
            self.pending_batch.append({'type': msgtype, 'dist': msgdist, 'text': msgtext})

    def flush_pending_messages(self):
        self.pending_batch = []

    def compose_data(self):
        this_batch = list(self.pending_batch)
        self.flush_pending_messages()

        return this_batch


class Volume:
    """
    Keep track of how much is coming out of the speakers.

    If we have access to the alsaaudio module, use it to control the volume.
    """

    def __init__(self):
        self.mxr = None
        self.level = 80  # Recover volume from previous session?
        self.muted = False
        self.VOL_STEP = 5
        self.VOL_MIN = 0
        self.VOL_MAX = 100
        # Set alsa volume on initialization
        if not NO_ALSA:  # Sigh
            self.mxr = alsaaudio.Mixer('Power Amplifier')
            self.mxr.setvolume(self.level)

    def louder(self):
        # Increase volume
        if self.level + self.VOL_STEP > self.VOL_MAX:
            self.level = self.VOL_MAX
        else:
            self.level += self.VOL_STEP

        if self.mxr:
            self.mxr.setvolume(self.level)

    def softer(self):
        # Decrease volume
        if self.level - self.VOL_STEP < self.VOL_MIN:
            self.level = self.VOL_MIN
        else:
            self.level -= self.VOL_STEP

        if self.mxr:
            self.mxr.setvolume(self.level)

    def toggle_mute(self):
        if self.muted:
            self.muted = False
            if self.mxr:
                self.mxr.setvolume(self.level)
        else:
            self.muted = True
            if self.mxr:
                self.mxr.setvolume(0)

    def get_level(self):
        return self.level

    def compose_data(self):
        return self.level


class Indicators:
    def __init__(self):
        self.inds = {
            "power": True,
            "play": False,
            "pause": False,
            "stop": True,
            "repeat": False,
            "shuffle": False,
            "mute": False,
        }

    def set_power(self, state):
        self.inds['power'] = state

    def set_play(self, state):
        self.inds['play'] = state

    def set_pause(self, state):
        self.inds['pause'] = state

    def set_stop(self, state):
        self.inds['stop'] = state

    def set_repeat(self, state):
        self.inds['repeat'] = state

    def set_shuffle(self, state):
        self.inds['shuffle'] = state

    def set_mute(self, state):
        self.inds['mute'] = state

    def get_indicator_state(self):
        return self.inds

    def compose_data(self):
        return self.inds


class RadioState:
    """
    Object to handle every aspect of the current state of the radio.
    """

    def __init__(self):
        self.menu = Menu()
        self.now_playing = NowPlaying()
        self.volume = Volume()
        self.messages = Messages()
        self.indicators = Indicators()
        self.prev_playstate = ""
        self.prev_component = ""
        self.valid_actions = ['play', 'stop', 'pause']
        self.current_state = 'stopped'
        self.loop = asyncio.get_event_loop()
        self.changes = asyncio.Queue()

    # State machine for play state

    def update(self, action):
        """
        This is our simole state machine for the play/pause/stop state of the audio player.

        The idea here is to do the least suprising thing, in accordance with the past few decades of
        audio equipment UI.
        """

        if action not in self.valid_actions:
            return

        if self.current_state == 'playing':
            if action == 'play':
                self.reset_playing()
            elif action == 'stop':
                self.set_stopped()
            elif action == 'pause':
                self.set_paused()
        elif self.current_state == 'paused':
            if action == 'play':
                self.set_unpaused()
            elif action == 'stop':
                self.set_stopped()
            elif action == 'pause':
                self.set_unpaused()
        elif self.current_state == 'stopped':
            if action == 'play':
                self.set_playing()
            elif action == 'stop':
                pass
            elif action == 'pause':
                pass

    def set_playing(self):
        """
        Set the state to playing, while forcing a reload of the now_playing opus.

        We need this state transition for those cases when a new opus needs to be loaded as part of the state
        transition.

        TODO: make this async to solve shoutcast race condition?
        """

        self.current_state = 'playing'
        if isinstance(self.menu.selected_node, Opus):
            # self.now_playing.current_opus.opus_stop()
            # self.now_playing.load(self.menu.selected_node)
            # self.now_playing.current_opus.opus_play()
            asyncio.run_coroutine_threadsafe(self._set_playing(self.menu.selected_node), self.loop)
            self.set_playing_indicators()

    async def _set_playing(self, node_to_play):
        """

        """
        await self.now_playing.current_opus.opus_stop()
        await self.now_playing.load(node_to_play)
        await self.now_playing.current_opus.opus_play()


    def reset_playing(self):
        """
        Set the state to playing, but do not reload the current opus if it is already playing or paused.

        We need this state transition to preserve any seek values that may be extant for the track; if we
        reload the opus, it will seek to the start of the media.
        """

        if self.now_playing.current_opus != self.menu.selected_node:
            self.set_playing()

    def set_paused(self):
        """Set the state to paused, but only if the current opus supports it.

        Operai like streaming radio feeds and boodler soundscapes don't have a meaningful pause state; it's
        less confusing to simply not support the operation in these cases, rather than imply some kind of state
        preservation which isn't feasible.
        """

        if self.current_opus_supports_pause():
            self.current_state = 'paused'
            self.set_paused_indicators()
            self.now_playing.current_opus.opus_pause()

    def set_unpaused(self):
        """
        Revert the paused state to playing.
        """

        self.current_state = 'playing'
        self.set_playing_indicators()
        self.now_playing.current_opus.opus_unpause()

    def set_stopped(self):
        """
        Set the state to stopped.
        """

        self.current_state = 'stopped'
        self.set_stopped_indicators()
        self.now_playing.current_opus.opus_stop()

    def current_opus_supports_pause(self):
        """
        Return attribute of the current opus to see if it supports the pause operation.
        """

        return self.now_playing.current_opus.pause_support

    # Updating indicators

    def set_playing_indicators(self):
        """
        In the playing state, only the play indicator should be lit.
        """

        self.indicators.set_stop(False)
        self.indicators.set_play(True)
        self.indicators.set_pause(False)

    def set_paused_indicators(self):
        """
        In the paused state, both the play and the pause indicators should be lit.
        """

        self.indicators.set_stop(False)
        self.indicators.set_play(True)
        self.indicators.set_pause(True)

    def set_stopped_indicators(self):
        """
        In the stopped state, only the stop indicator should be lit.
        """

        self.indicators.set_stop(True)
        self.indicators.set_play(False)
        self.indicators.set_pause(False)

    # Play back modifiers

    def toggle_repeat(self):
        """
        Toggle the repeat status for the current opus.

        Note that repeat status is considered part of the opus' state, not the radio; this lets us bookmark
        the state for retrieval with the opus later.

        We're using an alias here for clarity.
        """

        co = self.now_playing.current_opus
        if co.repeat_support:
            if co.repeat:
                co.repeat = 0
                self.indicators.set_repeat(False)
            else:
                co.repeat = 1
                self.indicators.set_repeat(True)
            co.opus_update_repeat()

    def toggle_shuffle(self):
        """
        Toggle the shuffle status for the current opus.

        Note that shuffle status is considered part of the opus' state, not the radio; this lets us bookmark
        the state for retrieval with the opus later.

        We're using an alias here for clarity.
        """

        co = self.now_playing.current_opus
        if co.shuffle_support:
            if co.shuffle:
                co.shuffle = 0
                self.indicators.set_shuffle(False)
            else:
                co.shuffle = 1
                self.indicators.set_shuffle(True)
            co.opus_update_shuffle()

    def menu_advance(self):
        """
        Move selection point one item forward, if possible.
        :return:
        """
        if self.menu.current_node.index < (len(self.menu.current_node.children) - 1):
            self.menu.current_node.index += 1
            self.menu.selected_node = self.menu.current_node.children[self.menu.current_node.index]

    def menu_retreat(self):
        """
        Move selection point one menu item back, if possible.
        :return:
        """
        if self.menu.current_node.index > 0:
            self.menu.current_node.index -= 1
            self.menu.selected_node = self.menu.current_node.children[self.menu.current_node.index]

    def menu_select(self):
        """
        Process node selection.
        """
        if self.menu.selected_node.children:
            new_parent_node = self.menu.current_node
            self.menu.current_node = self.menu.selected_node
            self.menu.selected_node = self.menu.current_node.children[self.menu.current_node.index]
            self.menu.current_node.parent = new_parent_node

    def menu_escape(self):
        """
        Make the parent menu the selected menu.
        """
        if self.menu.current_node.parent:
            self.menu.current_node = self.menu.current_node.parent
            self.menu.selected_node = self.menu.current_node.children[self.menu.current_node.index]

    def schedule_state_update(self):
        """
        Returns a dict of minimal state, suitable for appliance clients."
        """

        minimal = {'response': "OK",
                   'playstate': self.current_state,
                   'component': self.menu.current_node.component,
                   'messages': self.messages.compose_data(),
                   'menu': self.menu.compose_data(),
                   'now_playing': self.now_playing.get_data(),
                   'volume': self.volume.compose_data(),
                   'indicators': self.indicators.compose_data(),
                   }

        self.changes.put_nowait(minimal)

    async def idle(self):
        """
        Support for async not calls.
        """

        while True:
            yield await self.changes.get()
