#!/usr/local/bin/python3

# https://stackoverflow.com/questions/31639824/python-3-4-asynchio-chat-server-client-how

from unidecode import unidecode
from socket import *
from threading import Thread
import json
import argparse

import logging
logging.basicConfig(filename="opuscule_debug.log", format='%(levelname)s: TUI %(message)s', level=logging.INFO)


class TextLine:
    """
    Class to handle and manipulate lines of text to send to the display module.
    """

    def __init__(self, text, max_length, mode="raw"):
        self.rawtext = text
        self.rawlen = len(self.rawtext)
        self.maxlen = max_length
        self.scroll_count = 0
        self.mode = mode
        self.text = ""
        self.valid_modes = ['scroll', 'truncate', 'raw']

    def show(self):
        # if self.mode == "scroll":
        #     if self.maxlen <= self.rawlen < (self.maxlen + 4):
        #         self.truncate()
        #     else:
        #         self.scroll()
        if self.mode == "truncate":
            self.truncate()
        else:
            self.text = self.rawtext

        return unidecode(self.text)

    def scroll(self):
        """ Display one frame of scrolling line text. """

        if self.rawlen <= self.maxlen:
            self.text = self.rawtext
        else:
            # We went over; reset the scroll counter
            if self.scroll_count > self.maxlen:
                logging.debug("(got scroll reset)")
                self.reset_scroll()
            else:
                # Handle scrolling
                # Define left edge and right edge
                left_edge = self.scroll_count
                right_edge = self.scroll_count + self.maxlen
                self.text = self.rawtext[left_edge:right_edge]
                self.advance_scroll()

    def advance_scroll(self, n=1):
        """ Advance one step through scroll sequence """
        self.scroll_count += n

    def reset_scroll(self):
        self.scroll_count = 0

    def truncate(self):
        """ Show truncated line with an elipsis """
        if self.rawlen <= self.maxlen:
            self.text = self.rawtext
        else:
            self.text = self.rawtext[0:(self.maxlen - 1)] + "_"

    def update_text(self, text):
        if text:
            self.rawtext = text
            self.rawlen = len(self.rawtext)

    def update_mode(self, mode):
        if mode in self.valid_modes:
            self.mode = mode


class TestDisplay:
    """Display current status.

    """

    def __init__(self):
        self.width = 80
        self.lines = 2
        self.nothing_playing = True
        self.line1 = TextLine("", self.width)  # Menu, line one
        self.line2 = TextLine("", self.width)  # Menu, line two
        self.line3 = TextLine("", self.width)  # Now playing, line one
        self.line4 = TextLine("", self.width)  # Now playing, line two
        self.line5 = TextLine("", self.width)  # Messages, line one
        self.line6 = TextLine("", self.width)  # Messages, line two
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

    # def recompute_display(self):
    #     # Depending on the display state, decide what to do
    #     if self.state == 'menu':
    #         self.compose_menu(self.state)
    #     elif self.state == 'play':
    #         self.compose_now_playing(self.state)
    #         self.line2.advance_scroll()
    #     elif self.state == 'context':
    #         self.compose_context_menu()
    #     elif self.state == "message":
    #         self.compose_message()
    #     elif self.state == "blank":
    #         self.compose_blank()

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

            self.line1.update_mode("truncate")
            self.line1.update_text(ordinal_text + menu_items[menu_index]['name'])
            self.line2.update_mode("truncate")
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


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Client settings")
    parser.add_argument("--addr", default="127.0.0.1", type=str)
    parser.add_argument("--port", default=8888, type=int)
    args = vars(parser.parse_args())

    s = socket(AF_INET, SOCK_STREAM)
    s.connect((args["addr"], args["port"]))

    disp = TestDisplay()

    def listener():
        try:
            while True:
                datas = s.recv(8192).decode('utf-8')
                data = json.loads(datas)
                if data['response'] != 'ERROR':
                    disp.update_state(data)
                    print()
                    disp.display_lines()
                    disp.display_indicators()
                    print()
                else:
                    print("(Got a error.)")
                # print('> ', data)
        except ConnectionAbortedError:
            pass

    t = Thread(target=listener)
    t.start()

    try:
        while True:
            message = input('% ')
            if message == "quit":
                break
            command = {"command": message, "message": None}
            commands = json.dumps(command) + "\n"
            s.send(commands.encode('utf-8'))
    except EOFError:
        pass
    finally:
        s.close()
