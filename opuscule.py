#!/usr/bin/env python3

"""
Opuscule - a client/server solution for audio appliances.

The idea behind all of this: put a server on a computer that can manage and
manipulate audio of various kinds from various sources. The server manages the
state of both the audio and the appliance's interface state, so all clients
can usefully reflect current state.
"""

from base_classes import Opus, MenuList, Command, AudioComponent

import argparse

# For the server
import json
import asyncio

# For mpd updates
from mpd.asyncio import MPDClient

# Opuscule Audio Components
from components.library import LibraryComponent
from components.streaming import StreamingComponent
# from components.podcasts import PodcastsComponent
from components.sdr import FmRadioComponent, WxRadioComponent
from components.boodler import BoodlerComponent

# Opuscule System Components
from components.superfavorites import SuperFavoritesComponent
from system import SystemComponent
from settings import SettingsComponent
from radiostate import RadioState

from configparser import ConfigParser

# Uncomment the following when debugging asyncio
# import aiomonitor

import logging

logging.basicConfig(filename="opuscule_debug.log", format='%(levelname)s:%(message)s', level=logging.DEBUG)

logger = logging.getLogger(__name__)


# HEARTBEAT_RATE = 1

# TODO:
#
# ## Unimplemented components:
#
# shairport
#
# ## Features
#
# context menu for commands: play, pause, stop, add_favorite, volume, etc. Namely: how can we support a _minimal_
# set of ui controls:
# - dpad, select, esc
# - rotary controller, select, esc
# - ?
#
# ## Architecture
#
# The asyncio architecture needs some effort; this code was ported into asyncio from a previous synchronous solution,
# so the current solution could certainly be cleaner. But: it works!


class OpusculeController:
    """Control object for the audio device; a singleton that manages all device functions."""

    def __init__(self, cpo):
        """

        :return: an opuscule_controller object.
        """

        self.commands = {  # Valid commands
            'advance': self.do_advance,
            'retreat': self.do_retreat,
            'select': self.do_select,
            'escape': self.do_escape,
            'shutdown': self.do_shutdown,
            'play': self.do_play,
            'pause': self.do_pause,
            'stop': self.do_stop,
            'add_favorite': self.do_add_favorite,
            'shuffle': self.do_shuffle,
            'repeat': self.do_repeat,
            'next': self.do_next,
            'previous': self.do_previous,
            'louder': self.do_louder,
            'softer': self.do_softer,
            'mute': self.do_mute,
            'refresh': self.do_refresh,
        }

        # Do Startup tasks

        # Configuration Parser object for those that need it
        self.cpo = cpo
        # Radio state object
        self.rs = RadioState()

        # Components
        self.registered_components = []

        # We don't want to add a sfavs MenuList to sfavs...
        self.sfavs = SuperFavoritesComponent()
        self.rs.menu.current_node.add_child(self.sfavs)
        self.rs.menu.selected_node = self.sfavs

        # Attempt to register the remainder of the available components
        self.register_component(LibraryComponent(self.sfavs))

        # self.register_component(PodcastsComponent(self.sfavs))

        self.register_component(StreamingComponent(self.sfavs, self.cpo))

        self.register_component(BoodlerComponent(self.sfavs))

        self.register_component(FmRadioComponent(self.sfavs))

        self.register_component(WxRadioComponent(self.sfavs))

        self.register_component(SettingsComponent())

        self.register_component(SystemComponent())

    def register_component(self, component):
        """
        Check component dependancies, and add component to the UI.

        With each component, we need to make sure it reports that all requirements are fulfilled (hardware is available
        for things like SDR, software subsystems are available for things like MPD and Boodler, etc.).

        :param component:
        :return:
        """
        if component.requirements_met():
            logger.info("Requirements for {} component met; loading component.".format(component.component))
            self.registered_components.append(component)
            self.rs.menu.current_node.add_child(component)
            if isinstance(component, AudioComponent):
                self.sfavs.add_child_menu(component.favorites_node)

    def handle(self, command):
        """Handle incoming commands.

        We have a simple guard to sanity check the input, and then run the function associated with the command.
        """

        logger.debug("[Opuscule] Got command {}".format(command))
        if command in self.commands:
            # change state
            self.commands[command]()
            return {"response": "OK", "text": "Command accepted."}
        else:
            return {"response": "ERROR", "text": "Unknown command."}

    # Commands that manipulate the menu state

    def do_advance(self):
        """Increment the active menu item in the active menu."""
        self.rs.menu_advance()

    def do_retreat(self):
        """Decrement the active item in the active menu."""
        self.rs.menu_retreat()

    def do_escape(self):
        """Move to the parent menu."""
        self.rs.menu_escape()

    def do_select(self):
        """ The select command can affect either menu state, play state, or execute a command, depending on the
        current selected node

        We want to handle different select behaviors here; namely, we need to decide
        if the command should be sent as a menu select (if it's a MenuList) or
        a play (if it's an opus) or a command.
        """

        if isinstance(self.rs.menu.selected_node, MenuList):
            self.rs.menu_select()
        elif isinstance(self.rs.menu.selected_node, Opus):
            self.rs.update('play')
        elif isinstance(self.rs.menu.selected_node, Command):
            self.rs.menu.selected_node.command_execute()
        else:
            pass

    # Commands to manipulate the play state of the server

    def do_play(self):
        self.rs.update('play')

    def do_stop(self):
        self.rs.update('stop')

    def do_pause(self):
        self.rs.update('pause')

    def do_repeat(self):
        self.rs.toggle_repeat()

    def do_shuffle(self):
        self.rs.toggle_shuffle()

    def do_next(self):
        self.rs.now_playing.current_opus.opus_next()

    def do_previous(self):
        self.rs.now_playing.current_opus.opus_previous()

    # Commands that affect volume of playback (possibly supported)

    def do_louder(self):
        self.rs.volume.louder()

    def do_softer(self):
        self.rs.volume.softer()

    def do_mute(self):
        self.rs.volume.toggle_mute()
        self.rs.indicators.set_mute(self.rs.volume.muted)

    # Utility commands

    def do_add_favorite(self):
        """
        Add the current opus to the favorites menu for that component, and then
        update the super favorites.

        :return:
        """
        # home_comp = None FIXME do we no longer need this guard?

        # on startup, we might be in a state without a current opus
        if self.rs.now_playing.current_opus:
            for c in self.registered_components:
                if c.component == self.rs.now_playing.current_opus.component:
                    home_comp = c
                    break
            else:
                logger.error("Tried to add opus as a favorite, but current opus has no component.")
                return

            if home_comp == "superfavorites":
                return {"response": "ERROR", "text": "Operai in the super favorites are already favorites."}
            else:
                home_comp.add_favorite(self.rs.now_playing.current_opus)
                home_comp.save_favorites()
                self.sfavs.update_all_favorite_menus()
        else:
            return {"response": "ERROR", "text": "Only operai can be added as favorites."}

    def do_refresh(self):
        """
        Trigger a refresh for the requesting client

        :return:
        """
        pass

    def handle_internal(self):
        """
        Future hook for handling internal commands.

        """
        pass

    @staticmethod
    def do_shutdown():
        loop.stop()


class OpusculeProtocol(asyncio.Protocol):
    """
    A fairly straight forward implementation of the asyncio connection handling
    , cribbed from the boilerplate.
    """

    def __init__(self):
        self.transport = None
        self.peername = None

    def connection_made(self, transport):
        """
        Upon connecting, we want to keep track of the client and push a
        state update to all connected clients.
        :param transport:
        :return:
        """
        self.transport = transport
        self.peername = transport.get_extra_info("peername")
        logger.info("connection_made: {}".format(self.peername))
        connected_clients.append(self)

        op.rs.schedule_state_update()

    def data_received(self, data):
        """
        If a client sends us a command, validate it, and then apply it to the
        radio state. Let the client know how that went.
        :param data:
        :return:
        """
        curr_command = json.loads(data.decode())

        cmd_response = op.handle(curr_command['command'])

        if cmd_response is None:
            cmd_response = [{"response": "OK"}]

        logger.debug("Response from handling command " + curr_command['command'] + ": " + json.dumps(cmd_response))

        if cmd_response['response'] == "OK":
            op.rs.schedule_state_update()
        elif cmd_response['response'] == "ERROR":
            lading = json.dumps(cmd_response)
            self.transport.write(lading)

    def connection_lost(self, ex):
        """
        If we lose the connection, remove the client form the active list.
        :param ex:
        :return:
        """
        logger.info("connection_lost: {}".format(self.peername))
        connected_clients.remove(self)


async def send_state(new_state):
    """
    Broadcast state to all connected clients.
    :param new_state:
    :return:
    """
    lading = json.dumps(new_state)
    for client in connected_clients:
        logger.debug("Sending to client {}".format(client.peername))
        client.transport.write(lading.encode('utf-8'))


def start_mpd_client():
    """
    Some of the components need an MPD client; we want to use the asyncio
    aware version.
    :return:
    """
    return loop.run_until_complete(_start_mpd_client())


async def _start_mpd_client():
    """
    Start the MPD client, and make sure it's not in consume mode (we want
    to be able to reverse through our playlists.
    :return:
    """
    try:
        await mpdc.connect('localhost', 6600)
    except Exception as e:
        logger.error("Connection to mpd process failed:", e)
    mpdc.consume(0)


async def _monitor_mpd():
    """
    Look for changes in the MPD subsystem, and update the radio state as
    necessary.
    :return:
    """
    curr_song = None
    curr_status = None

    while True:
        logger.debug("entering async for loop for mpd monitoring")

        try:
            curr_song = await mpdc.currentsong()
        except Exception as e:
            logger.error("Current song error: %s", e)
        else:
            logger.debug("Current song success!")

        logger.debug("Data from monitor_mpd, mpdc.currentsong: " + str(curr_song))

        op.rs.now_playing.update_data(curr_song)

        try:
            curr_status = await mpdc.status()
        except Exception as e:
            logger.error("Status error: %s", e)
        else:
            logger.debug("Status success!")

        logger.debug("Data from monitor_mpd, mpdc.status: " + str(curr_status))

        # If mpd stops the player, we need to inform opuscule
        if curr_status['state'] == 'stop':
            logger.debug("MPD has requested a stop.")
            op.rs.update('stop')
            logger.debug("Radio state stopped.")

        op.rs.schedule_state_update()

        async for subsystem in mpdc.idle():
            logger.debug("Idle change in %s", subsystem)

            if 'player' in subsystem:
                break


async def _monitor_radio_state():
    """
    If there are any changes to the radio state from user input or
    internal change, alert all connected clients.
    :return:
    """
    logger.debug("starting up monitor for menu")
    while True:
        async for update in op.rs.idle():
            logger.debug("Processing updated menu state")
            # ??? How does this effect the JSON encoding?
            asyncio.run_coroutine_threadsafe(send_state(update), loop)


def startup():
    # Make sure MPD is running?
    pass


def shutdown():
    # Kill MPD if necessary?
    pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Server settings")
    parser.add_argument("--port", type=int)
    args = vars(parser.parse_args())

    logger.info("Starting up..")

    cp = ConfigParser()

    cp.read('opuscule-config.ini')

    mpdc = MPDClient()

    op = OpusculeController(cp)

    connected_clients = []

    startup()

    op_port = cp.get('main', 'port')

    if args['port']:
        op_port = args['port']

    loop = asyncio.get_event_loop()

    start_mpd_client()

    opserver = loop.create_server(OpusculeProtocol, port=op_port)
    server = loop.run_until_complete(opserver)

    for socket in server.sockets:
        logger.info("Serving on {}".format(socket.getsockname()))

    mpdmon_task = asyncio.Task(_monitor_mpd())

    menumon_task = asyncio.Task(_monitor_radio_state())

    # Uncomment the following when debugging asyncio
    # with aiomonitor.start_monitor(loop=loop):
    #     loop.run_forever()

    # Comment the following when debugging asyncio
    loop.run_forever()

    for comp in op.registered_components:
        comp.save_favorites()

    shutdown()
