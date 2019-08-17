#!/usr/bin/env python3
import asyncio
import urwid
import argparse
import json
import functools
from transitions import Machine

import logging
logging.basicConfig(filename="tui_debug.log", format='%(levelname)s: [TUI] %(message)s', level=logging.DEBUG)

logger = logging.getLogger('tui_client')

"""
tui_client.py - an example opuscule client using a text user interface.

This client is meant to be an example of how a python opuscule client might work 
using asyncio to manage the networking connections, and a text user interface
to present information to the user.

Using a TUI like this makes for a nice framework for developing solutions for
minimal hardware displays on appliances; we may have little more than a
two-line LCD display and a handful of indicator LEDs. This client
is useful for rapidly prototyping solutions for a particular hardware setup
before breaking out the breadboards.
"""

class TextLine:
    """
    Class to handle and manipulate lines of text to send to the display module.

    overflow can be either 'scroll' (to scroll text with advances) or 'truncate'
    (to shorten text to acceptable display size).
    """

    def __init__(self, cols, step_duration, rawmode=True, overflow="scroll"):
        self.rawmode = rawmode
        self.suppress_scrolling = False
        self.rawtext = ""
        self.rawlen = len(self.rawtext)
        self.disp_width = cols
        self.step_count = 0
        self.rendered_text = ""
        self.scroll_count = 0
        self.sequence_count = 0
        self.scroll_step_duration = step_duration
        self.pause_duration = 3
        self.blank_duration = 1
        self.pause_steps = self.pause_duration // self.scroll_step_duration
        self.blank_steps = self.blank_duration // self.scroll_step_duration
        self.mode = overflow
        self.gloss_text = ""

    def show(self):
        if self.rawmode:
            self.rendered_text = self.rawtext
        else:
            if self.mode == "truncate" or self.suppress_scrolling:
                self.truncate()
            elif self.mode == "scroll":
                self.scroll()

        return self.rendered_text

    def scroll(self):
        if len(self.rawtext) <= self.disp_width:
            # If the line is less than max, we don't need to scroll
            self.rendered_text = self.rawtext
        else:
            # Find transition points
            transition_to_scroll = self.pause_steps
            transition_to_pause = transition_to_scroll + len(self.rawtext) - self.disp_width
            transition_to_blank = transition_to_pause + self.pause_steps
            max_sequence_count = transition_to_blank + self.blank_steps

            # Scrolling
            if self.sequence_count < transition_to_scroll:
                # We are in initial pause
                left_edge = 0
                right_edge = self.disp_width
                self.rendered_text = self.gloss_text + self.rawtext[left_edge:right_edge]
                logging.debug("[P{}] {}{} ".format(str(self.sequence_count).zfill(2), self.gloss_text,
                                                   self.rendered_text))
            elif self.sequence_count < transition_to_pause:
                # We are in the scrolling phase
                left_edge = self.scroll_count
                right_edge = self.scroll_count + self.disp_width
                self.scroll_count += 1
                self.rendered_text = self.gloss_text + self.rawtext[left_edge:right_edge]
                logging.debug("[S{}] {}{} ".format(str(self.sequence_count).zfill(2), self.gloss_text,
                                                   self.rendered_text))
            elif self.sequence_count < transition_to_blank:
                # We are in the second pause
                left_edge = self.rawlen - self.disp_width
                right_edge = self.rawlen
                self.rendered_text = self.gloss_text + self.rawtext[left_edge:right_edge]
                logging.debug("[P{}] {}{} ".format(str(self.sequence_count).zfill(2), self.gloss_text,
                                                   self.rendered_text))
            elif self.sequence_count < max_sequence_count:
                # We are in the blank phase
                self.rendered_text = " "
                logging.debug("[B{}] {}{} ".format(str(self.sequence_count).zfill(2), self.gloss_text,
                                                   self.rendered_text))
            elif self.sequence_count > max_sequence_count:
                # reset
                self.reset_scroll()
                logging.debug("--- Got Scroll Reset ---")

    def advance_scroll(self, n=1):
        """ Advance one step through scroll sequence """
        self.sequence_count += n

    def reset_scroll(self):
        self.sequence_count = 0
        self.scroll_count = 0

    def truncate(self):
        """ Show truncated line with an elipsis """
        # TODO: Add gloss text
        if self.rawlen <= self.disp_width:
            self.rendered_text = self.rawtext
        else:
            self.rendered_text = self.rawtext[0:(self.disp_width - 2)] + '…'

    def update_text(self, text):
        self.rawtext = text
        self.rawlen = len(self.rawtext)

    def update_gloss_text(self, text):
        self.gloss_text = text

    def handle_scroll_event(self):
        if self.mode == "scroll":
            self.advance_scroll()
        # logging.debug("Got scroll event in the line.")


class ApplianceVolumeIndicator(urwid.Text):
    def __init__(self, volume, align='left', wrap='space', layout=None):
        self.volume = volume
        super().__init__([' Volume: ', str(self.volume).zfill(2)], align, wrap, layout)

    def set_volume(self, volume):
        self.volume = volume
        self.set_text(['Volume: ', str(self.volume).zfill(2)])


class ApplianceLedIndicator(urwid.Text):
    def __init__(self, label, ledstate=False, align='left', wrap='space', layout=None):
        self.label = label
        self.ledstate = ledstate
        super().__init__([self.label, ': ', self.ind_char(self.ledstate)], align, wrap, layout)

    def set_ledstate(self, new_ledstate):
        self.ledstate = new_ledstate
        self.set_text([self.label, ': ', self.ind_char(self.ledstate)])

    @staticmethod
    def ind_char(indicator):
        if indicator:
            return "◼︎"
        else:
            return "◻︎"


class MenuContent:
    def __init__(self, cols):
        self.cols = cols

    def compose_menu_lines(self, new_menu_state):
        # First, construct the menu strings
        menu_items = new_menu_state['list']
        menu_index = new_menu_state['index']
        menu_string = ""
        helptext = ""
        menu_boundary_map = []

        # If any item in the menu is too long (by an arbitrary cutoff), flip the
        # menu display to vertical
        menu_type = "horizontal"
        for item in menu_items:
            if len(item['name']) > 10:
                menu_type = "vertical"

        if menu_type == "horizontal":
            # Build the full string of the horizontal menu, with a map of the menu boundaries
            # Index by the boundaries to decide where to start the display window, and where to stop.

            # We may want to use shortnames if we have very few characters to work with in our display
            label_to_use = "name"

            for left_edge, item in enumerate(menu_items):
                if left_edge == menu_index:
                    item_string = '>' + item[label_to_use] + '< '
                    helptext = item['comment']
                else:
                    item_string = ' ' + item[label_to_use] + '  '
                # logging.debug("Item Label: " + item.label)
                offset_start = len(menu_string)
                menu_string += item_string
                menu_boundary_map.append((offset_start, len(menu_string)))

            # Use menu_boundary_map and menu_index to decide where our n-char window is

            left_edge, right_edge = menu_boundary_map[menu_index]

            if right_edge - left_edge > self.cols:
                # The text can fit
                right_edge = left_edge + self.cols
            else:
                # The selected menu is too big to fit; truncate to width
                selected_width = right_edge - left_edge
                remaining_width = self.cols - selected_width
                first_side = remaining_width // 2
                left_edge = left_edge - first_side
                if left_edge < 0:
                    right_edge = right_edge - left_edge
                    left_edge = 0
                right_edge = right_edge + remaining_width - first_side
                if right_edge > len(menu_string):
                    left_edge = max(0, left_edge-(right_edge-len(menu_string)))
                    right_edge = len(menu_string)

            menu_one = menu_string[left_edge:right_edge]
            menu_two = helptext[0:(self.cols - 1)]
        else:
            # for vertical menus, we just want to scroll through the options
            ordinal_text = ""
            ordinal_text += "("
            ordinal_text += str(menu_index + 1)
            ordinal_text += "/"
            ordinal_text += str(len(menu_items))
            ordinal_text += ") "

            if menu_index == 0:
                scrollbar_text = " -->"
            elif menu_index == (len(menu_items) - 1):
                scrollbar_text = " <--"
            else:
                scrollbar_text = " <->"

            scrollbar_padding = (" " * (len(ordinal_text) - len(scrollbar_text)))

            menu_one = ordinal_text + menu_items[menu_index]['name']
            menu_two = scrollbar_text + scrollbar_padding + menu_items[menu_index]['comment']

        return menu_one, menu_two


class NowPlayingContent:
    def __init__(self):
        pass

    @staticmethod
    def compose_now_playing_lines(new_state):
        comp_state = new_state['component']
        np_state = new_state['now_playing']
        np_one = " "
        np_two = " "

        if comp_state == 'library':
            np_one = np_state['title']
            np_two = "{}/{}".format(np_state['album'], np_state['artist'])
        elif comp_state == 'streaming':
            np_one = np_state['title']
            np_two = np_state['name']
        elif comp_state == 'boodler':
            np_one = np_state['agent']
            np_two = np_state['package']
        elif comp_state == 'fmradio':
            np_one = "{} - {}{}".format(np_state['callsign'], np_state['freq'], np_state['mode'])
            np_two = " "
        elif comp_state == 'wxradio':
            np_one = " "
            np_two = " "

        return np_one, np_two


class ApplianceClient(object):
    def __init__(self, cols, step_duration):
        # Here we make decisions about what gets put into the two lines we send to urwid
        self.cols = cols
        self.server_state = None
        self.line_one_text = TextLine(self.cols, step_duration, rawmode=False)
        self.line_two_text = TextLine(self.cols, step_duration, rawmode=False)
        self.lines = [self.line_one_text, self.line_two_text]
        #
        # Keeping track of all of our states
        #
        self.menu = MenuContent(self.cols)
        self.nply = NowPlayingContent()

        # Set up the areas of the mock-up display
        self.display_line_one = urwid.Text("Indeed!", align='left')
        self.display_line_two = urwid.Text(" ", align='left')
        self.divider = urwid.Divider(div_char=' ', top=0, bottom=0)
        self.volume = ApplianceVolumeIndicator(00)
        self.power_ind = ApplianceLedIndicator("  Power",   ledstate=False)
        self.play_ind = ApplianceLedIndicator("   Play",    ledstate=False)
        self.pause_ind = ApplianceLedIndicator("  Pause",   ledstate=False)
        self.stop_ind = ApplianceLedIndicator("   Stop",    ledstate=False)
        self.repeat_ind = ApplianceLedIndicator(" Repeat",  ledstate=False)
        self.shuffle_ind = ApplianceLedIndicator("Shuffle", ledstate=False)
        self.mute_ind = ApplianceLedIndicator("   Mute",    ledstate=False)

        self.layout = urwid.Pile([self.display_line_one,
                                  self.display_line_two,
                                  self.divider,
                                  self.volume,
                                  self.divider,
                                  self.power_ind,
                                  self.play_ind,
                                  self.pause_ind,
                                  self.stop_ind,
                                  self.repeat_ind,
                                  self.shuffle_ind,
                                  self.mute_ind,
                                  ])
        self.top = urwid.Filler(self.layout, valign='top')

    def process_state(self, new_state):

        is_there_previous_state = True
        # On start up, set the approriate view for whatever the server is doing upon connect
        if self.server_state is None:
            is_there_previous_state = False

        self.server_state = new_state

        if not is_there_previous_state:
            if new_state['playstate'] == 'playing':
                self.to_play()
            elif new_state['playstate'] == 'stopped':
                self.to_menu()

        # Deal With Indicators, First
        self.update_indicators()
        self.volume.set_volume(self.server_state['volume'])
        # Handle any messages
        self.display_messages()
        # Update the display
        self.update_text()

    def update_indicators(self):
        self.power_ind.set_ledstate(self.server_state['indicators']['power'])
        self.play_ind.set_ledstate(self.server_state['indicators']['play'])
        self.pause_ind.set_ledstate(self.server_state['indicators']['pause'])
        self.stop_ind.set_ledstate(self.server_state['indicators']['stop'])
        self.repeat_ind.set_ledstate(self.server_state['indicators']['repeat'])
        self.shuffle_ind.set_ledstate(self.server_state['indicators']['shuffle'])
        self.mute_ind.set_ledstate(self.server_state['indicators']['mute'])

    def display_messages(self):
        # if there are any messages in the messages list
        # Show one for MESSAGE_DURATION
        # Puzzle: accept 'esc' to get out of the message (save the coro object?)
        pass

    def compute_text(self):
        line_one = " "
        line_two = " "

        if self.state == 'menu':
            line_one, line_two = self.menu.compose_menu_lines(self.server_state['menu'])
        elif self.state == 'play':
            # logger.debug("Server state for playing comp: " + str(self.server_state))
            line_one, line_two = self.nply.compose_now_playing_lines(self.server_state)
            if self.server_state['playstate'] == "stopped":
                line_one = "Nothing Playing."
                line_two = " "
            if self.server_state['playstate'] == "paused":
                line_one = "(Paused)"
        elif self.state == 'context':
            line_one = "Context Menu"
            line_two = " "
        elif self.state == "message":
            line_one = "Message Display"
            line_two = " "
        elif self.state == "blank":
            line_one = " "
            line_two = " "

        self.line_one_text.update_text(line_one)
        self.line_two_text.update_text(line_two)

    def display_text(self):
        self.display_line_one.set_text(self.line_one_text.show())
        self.display_line_two.set_text(self.line_two_text.show())

    def update_text(self):
        self.compute_text()
        self.display_text()

    def handle_keypress(self, key):
        if key in ('q', 'Q'):
            raise urwid.ExitMainLoop()
        elif key in ('p', 'P'):
            self.start_playback()
            clients[0].send_command('play')
        elif key in ('u', 'U'):
            clients[0].send_command('pause')
        elif key in ('s', 's'):
            clients[0].send_command('stop')
        elif key in ('x', 'X'):
            clients[0].send_command('shuffle')
        elif key in ('t', 'T'):
            clients[0].send_command('repeat')
        elif key in ('v', 'V'):
            clients[0].send_command('add_favorite')
        elif key in ('up', 'esc'):
            if self.state != 'menu':
                self.to_menu()
            else:
                clients[0].send_command('escape')
        elif key in ('down', 'enter'):
            if self.server_state['menu']['selkind'] == "opus":
                self.start_playback()
            clients[0].send_command('select')
        elif key == 'left':
            if self.state == 'play':
                clients[0].send_command('softer')
            else:
                clients[0].send_command('retreat')
        elif key == 'right':
            if self.state == 'play':
                clients[0].send_command('louder')
            else:
                clients[0].send_command('advance')
        elif key == '0':
            clients[0].send_command('mute')
        elif key == '-':
            clients[0].send_command('softer')
        elif key in ('+', '='):
            clients[0].send_command('louder')
        elif key in ('y', 'Y'):
            self.toggle_menu()
        elif key in ('>', '.'):
            clients[0].send_command('next')
        elif key in ('<', ','):
            clients[0].send_command('previous')
        elif key in ('g', 'G'):
            clients[0].send_command('refresh')
        # elif key in ('z', 'Z'):
        #     clients[0].send_command('z')


class ApplianceClientProtocol(asyncio.Protocol):
    def __init__(self, app_client):
        super().__init__()
        self.app_client = app_client
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport
        logger.debug("Connection setting up.")
        clients.append(self)
        # We need to get initial state here
        self.send_command("refresh")

    def data_received(self, datas):
        # logger.debug('(Data received from server.)')
        # data = json.loads(datas)
        # logger.debug(data)
        # if data['response'] != "ERROR":
        #     ac.process_state(data)
        # else:
        #     logger.debug("(Got a error.)")

        logger.debug('(Data received from server.)')
        try:
            data = json.loads(datas)

            if data['response'] != 'ERROR':
                ac.process_state(data)
            else:
                logger.debug("Got a error before processing the command.)")
        except json.JSONDecodeError:
            logger.debug("Error in JSON data: sending refresh")
            self.send_refresh()

    def send_refresh(self):
        command = {"command": "refresh", "message": ""}
        commands = json.dumps(command) + "\n"
        self.transport.write(commands.encode())
        logging.debug('Data sent: {!r}'.format(command))

    def send_command(self, command, option=""):
        command = {"command": command, "message": option}
        commands = json.dumps(command) + "\n"
        self.transport.write(commands.encode())
        logging.debug('Data sent: {!r}'.format(command))

    def connection_lost(self, exc):
        print('The server closed the connection')
        loop.stop()


async def scroll_event_generator(step_duration):
    while True:
        # logger.debug("Generating scrolling event")
        await asyncio.sleep(step_duration)
        for line in ac.lines:
            # logger.debug("Sending scroll event to {}.".format(line.rawtext))
            line.handle_scroll_event()
        ac.update_text()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Client settings")
    parser.add_argument("--addr", default="127.0.0.1", type=str)
    parser.add_argument("--port", default=7399, type=int)
    parser.add_argument("--cols", default=40, type=int)
    args = vars(parser.parse_args())

    SCROLL_STEP_DURATION = .5

    clients = []

    ac = ApplianceClient(args['cols'], SCROLL_STEP_DURATION)

    display_states = ['menu', 'play', 'context', 'message', 'blank']

    display_transitions = [
        {'trigger': 'start_playback', 'source': ['play', 'menu', 'context',  'message', 'blank'], 'dest': 'play',
         'after': 'update_text'},
        {'trigger': 'toggle_menu', 'source': 'menu', 'dest': 'play', 'after': 'update_text'},
        {'trigger': 'toggle_menu', 'source': ['play', 'context',  'message', 'blank'], 'dest': 'menu',
         'after': 'update_text'},
        {'trigger': 'to_menu', 'source': ['menu', 'play', 'context',  'message', 'blank'], 'dest': 'menu',
         'after': 'update_text'},
        {'trigger': 'to_play', 'source': ['menu', 'play', 'context', 'message', 'blank'], 'dest': 'play',
         'after': 'update_text'},
        {'trigger': 'stop_playback', 'source': ['play', 'menu', 'context',  'message', 'blank'], 'dest': 'menu',
         'after': 'update_text'},
    ]

    machine = Machine(model=ac, states=display_states, transitions=display_transitions, initial='menu')

    machine.on_enter_menu(ac.update_text)

    loop = asyncio.get_event_loop()

    client_factory = functools.partial(
        ApplianceClientProtocol,
        ac
    )

    SERVER_ADDRESS = (args['addr'], args['port'])

    acp = loop.create_connection(client_factory, *SERVER_ADDRESS)
    loop.run_until_complete(acp)

    seg = loop.create_task(scroll_event_generator(SCROLL_STEP_DURATION))

    evl = urwid.AsyncioEventLoop(loop=loop)
    urwid_main_loop = urwid.MainLoop(ac.top, event_loop=evl, unhandled_input=ac.handle_keypress, handle_mouse=False)

    urwid_main_loop.run()
