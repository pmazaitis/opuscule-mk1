#!/usr/local/bin/python3

from unidecode import unidecode
from socket import *
from threading import Thread
import json
import argparse
import cmd


import logging
logging.basicConfig(filename="cli_debug.log", format='%(levelname)s: TUI %(message)s', level=logging.DEBUG)

logger = logging.getLogger(__name__)

"""
cli_client.py - an example opuscule client using a command line interface.

This is meant to be a most basic example if how a python opuscule client might 
work, using threads to manage the network connections.
"""


class TextLine:
    """
    Class to handle and manipulate lines of text to send to the display module.
    """

    def __init__(self, text):
        self.rawtext = text

    def show(self):
        return unidecode(self.rawtext)

    def update_text(self, text):
        self.rawtext = text


class TestDisplay:
    """Display current status.

    """

    def __init__(self):
        self.width = 80
        self.lines = 2
        self.nothing_playing = True
        self.line1 = TextLine("")  # Menu, line one
        self.line2 = TextLine("")  # Menu, line two
        self.line3 = TextLine("")  # Now playing, line one
        self.line4 = TextLine("")  # Now playing, line two
        self.line5 = TextLine("")  # Messages, line one
        self.line6 = TextLine("")  # Messages, line two
        self.state = None
        self.opstate = {}

    def update_state(self, new_opstate):
        self.opstate = new_opstate
        self.compose_menu()
        self.compose_now_playing()

    def display_lines(self):
        print("M01: {}".format(self.line1.show()))
        print("M02: {}".format(self.line2.show()))
        print("P01: {}".format(self.line3.show()))
        print("P02: {}".format(self.line4.show()))
        
    def display_indicators(self):
        # self.label_list = ["power", "play", "pause", "stop", "repeat", "shuffle", "mute", "vol"]
        print("Power:   {}   Play: {}  Pause:   {}  Stop:   {}".format(
            self.ind_char(self.opstate['indicators']['power']),
            self.ind_char(self.opstate['indicators']['play']),
            self.ind_char(self.opstate['indicators']['pause']),
            self.ind_char(self.opstate['indicators']['stop']),
        ))
        print("Volume: {}   Mute: {}  Shuffle: {}  Repeat: {}".format(
            self.opstate['volume'],
            self.ind_char(self.opstate['indicators']['mute']),
            self.ind_char(self.opstate['indicators']['shuffle']),
            self.ind_char(self.opstate['indicators']['repeat']),
        ))

    @staticmethod
    def ind_char(indicator):
        if indicator:
            return "◼︎" 
        else:
            return "◻︎"

    def compose_messages(self):
        pass

    def compose_menu(self):
        menu_items = self.opstate['menu']['list']
        menu_index = self.opstate['menu']['index']
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

            if right_edge - left_edge > self.width:
                # The text can fit
                right_edge = left_edge + self.width
            else:
                # The selected menu is too big to fit; truncate to width
                selected_width = right_edge - left_edge
                remaining_width = self.width - selected_width
                first_side = remaining_width // 2
                left_edge = left_edge - first_side
                if left_edge < 0:
                    right_edge = right_edge - left_edge
                    left_edge = 0
                right_edge = right_edge + remaining_width - first_side
                if right_edge > len(menu_string):
                    left_edge = max(0, left_edge-(right_edge-len(menu_string)))
                    right_edge = len(menu_string)

            self.line1.update_text(menu_string[left_edge:right_edge])
            self.line2.update_text(helptext[0:39])
        else:
            # for vertical menus, we just want to scroll through the options
            ordinal_text = ""
            ordinal_text += "("
            ordinal_text += str(menu_index + 1)
            ordinal_text += "/"
            ordinal_text += str(len(menu_items))
            ordinal_text += ") "

            self.line1.update_text(ordinal_text + menu_items[menu_index]['name'])
            self.line2.update_text((" " * len(ordinal_text)) + menu_items[menu_index]['comment'])

    def compose_now_playing(self):

        logging.debug(f"Recieved comp state: {self.opstate['component']}")
        logging.debug(f"Recieved nply state: {self.opstate['now_playing']}")

        if self.opstate['component'] == 'library':
            self.line3.update_text(self.opstate['now_playing']['title'])
            self.line4.update_text(f"{self.opstate['now_playing']['album']}/{self.opstate['now_playing']['artist']}")
        elif self.opstate['component'] == 'streaming':
            self.line3.update_text(self.opstate['now_playing']['title'])
            self.line4.update_text(self.opstate['now_playing']['name'])
        elif self.opstate['component'] == 'boodler':
            self.line3.update_text(self.opstate['now_playing']['agent'])
            self.line4.update_text(self.opstate['now_playing']['package'])
        elif self.opstate['component'] == 'fmradio':
            self.line3.update_text(f"{self.opstate['now_playing']['callsign']} - \
            {self.opstate['now_playing']['freq']}{self.opstate['now_playing']['mode']}")
            self.line4.update_text("")
        elif self.opstate['component'] == 'wxradio':
            self.line3.update_text("")
            self.line4.update_text("")

        if self.opstate['playstate'] == "stopped":
            self.line3.update_text("Nothing Playing.")
            self.line4.update_text(" ")

        if self.opstate['playstate'] == "paused":
            self.line3.update_text("(Paused)")

    def compose_nav_breadcrumbs(self):
        path_list = self.opstate['menu']['path']
        index = self.opstate['menu']['index']
        opus_labels = self.opstate['menu']['list'][index]

        breadcrumbs = ""

        for bc in path_list:
            breadcrumbs += "{} > ".format(bc['name'])

        breadcrumbs += opus_labels['name']

        return breadcrumbs

    def compose_context_menu(self):
        # lines = []
        pass

    def compose_message(self):
        # lines = []
        pass

    @staticmethod
    def compose_blank():
        return ["", ""]


class OpusCmd(cmd.Cmd):
    """Simple command processor example."""

    def do_refresh(self, line):
        send_command("refresh")

    def help_refresh(self):
        print("Forces a refresh of the server state for the client.")

    def do_advance(self, line):
        send_command("advance")

    def help_advance(self):
        print("Advance the menu selector.")

    def do_retreat(self, line):
        send_command("retreat")

    def help_retreat(self):
        print("Retreat the menu selector.")

    def do_select(self, line):
        send_command("select")

    def help_select(self):
        print("Select the current menu item.")

    def do_escape(self, line):
        send_command("escape")

    def help_escape(self):
        print("Go to the parent menu.")

    def do_play(self, line):
        send_command("play")

    def help_play(self):
        print("Start the current opus.")

    def do_pause(self, line):
        send_command("pause")

    def help_pause(self):
        print("Pause the current opus.")

    def do_stop(self, line):
        send_command("stop")

    def help_stop(self):
        print("Stop the current opus.")

    def do_fav(self, line):
        send_command("add_favorite")

    def help_fav(self):
        print("Add the current opus to the favorites.")

    def do_shuffle(self, line):
        send_command("shuffle")

    def help_shuffle(self):
        print("Toggle shuffle for the current opus (if supported).")

    def do_repeat(self, line):
        send_command("repeat")

    def help_repeat(self):
        print("Toggle repeat for the current opus (if supported).")

    def do_next(self, line):
        send_command("next")

    def help_next(self):
        print("Go to the next track (if applicable).")

    def do_previous(self, line):
        send_command("previous")

    def help_previous(self):
        print("Go to the previous track (if applicable).")

    def do_louder(self, line):
        send_command("louder")

    def help_louder(self):
        print("Increase the volume.")

    def do_softer(self, line):
        send_command("softer")

    def help_softer(self):
        print("Decrease the volume.")

    def do_mute(self, line):
        send_command("mute")

    def help_mute(self):
        print("Toggle mute.")

    def do_EOF(self, line):
        return True

    def do_quit(self, line):
        return True

    def help_quit(self):
        print("Quit the client")

def send_command(command, message=""):
    command = {"command": command, "message": message}
    commands = json.dumps(command) + "\n"
    s.send(commands.encode('utf-8'))


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Client settings")
    parser.add_argument("--addr", default="127.0.0.1", type=str)
    parser.add_argument("--port", default=7399, type=int)
    args = vars(parser.parse_args())

    s = socket(AF_INET, SOCK_STREAM)
    s.connect((args["addr"], args["port"]))

    disp = TestDisplay()

    def listener():
        try:
            while True:
                datas = s.recv(8192).decode('utf-8')
                data = json.loads(datas)
                # logger.debug(data)
                if data['response'] != 'ERROR':
                    disp.update_state(data)
                    print()
                    disp.display_lines()
                    disp.display_indicators()
                    print()
                else:
                    print("(Got a error.)")
        except ConnectionAbortedError:
            pass

    t = Thread(target=listener)
    t.start()

    try:
        OpusCmd().cmdloop()
    finally:
        s.close()
