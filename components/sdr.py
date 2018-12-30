from base_classes import Opus, MenuList, AudioComponent
import subprocess
import logging
import asyncio
import os
import json


async def play_fm_station(freq, kill=0):
    logging.debug('creating rtlfm_pipe')
    rtlfm_pipe = asyncio.create_subprocess_exec(['rtl_fm', '-M', 'wbfm', '-f', str(freq) + 'M', '-g', '10'],
                                                stdout=subprocess.PIPE)
    logging.debug('creating play_pipe')
    play_pipe = asyncio.create_subprocess_exec(['play', '-r', '32k', '-t', 'raw', '-e', 's', '-b', '16', '-c', '1',
                                                '-V1', '-'], stdin=rtlfm_pipe.stdout, stdout=subprocess.PIPE)
    logging.debug('creating third_pipe')
    third_pipe = play_pipe.stdout

    rtlfm_pid = rtlfm_pipe.pid
    await rtlfm_pid, rtlfm_pipe


class FmRadioComponent(AudioComponent):
    def __init__(self, sfavs):
        # Do Startup tasks
        super().__init__("FM Radio", "FM", "FM Radio Stations")
        self.sfavs = sfavs

        # This is part of the Streaming hierarchy
        self.component = "fmradio"

        self.favs_save_file = "saved/{}_favorites.json".format(self.component)
        self.favorites_node.menu_labels['comment'] = "FM radio favorites"
        self.favorites_node.component = self.component
        self.load_favorites()

        self.custom_node = FmRadioMenuList("Custom", "Ctm", "My custom stations")

        self.add_child(self.custom_node)

        custom_stations = [
            FmOpus("WRCT", "88.3", "Radio Carnegie Tech"),
            FmOpus("WQED", "89.3", "Pittsburgh's Classical Music"),
            FmOpus("WESA", "90.5", "NPR Radio"),
            FmOpus("WYEP", "91.3", "Alternative"),
            FmOpus("WPTS", "92.1", "Hail to Pitt"),
        ]

        for item in custom_stations:
            self.custom_node.add_child(item)

    def requirements_met(self):
        # figure out where the rtl_fm and play utilities live
        return True

    def save_favorites(self):
        favs = []
        for fav in self.favorites_node.children:
            favs.append(fav.export_metadata())

        json_favs = json.dumps(favs)

        with open(self.favs_save_file, mode='w', encoding='utf-8') as the_file:
            the_file.write(json_favs)

    def load_favorites(self):
        try:
            with open(self.favs_save_file, mode='r', encoding='utf-8') as the_file:
                favs = json.loads(the_file.read())
                for fav in favs:
                    this_opus = FmOpus(fav['name'], fav['comment'], fav['freq'])
                    self.favorites_node.add_child(this_opus)
                self.sfavs.update_one_favorite_menu(self)
        except json.JSONDecodeError:
            pass
        except FileNotFoundError:
            pass


class FmRadioMenuList(MenuList):
    def __init__(self, name, short_name, comment):
        super().__init__(name, short_name, comment)
        self.component = "fmradio"


class WxRadioComponent(AudioComponent):
    def __init__(self, sfavs):
        # Do Startup tasks
        # Do Startup tasks
        super().__init__("WX Radio", "WX", "NOAA Weather Radio Stations")
        self.sfavs = sfavs

        # This is part of the Streaming hierarchy
        self.component = "wxradio"

        self.favorites_node.menu_labels['comment'] = "Weather Station Favorites"
        self.favorites_node.component = self.component
        self.stations_node = WxRadioMenuList("All", "All", "All Weather Stations")

    def requirements_met(self):
        return False


class WxRadioMenuList(MenuList):
    def __init__(self, name, short_name, comment):
        super().__init__(name, short_name, comment)
        self.component = "wxradio"


class SdrOpus(Opus):
    """Use rtl_fm to play a weather stationstation

    """

    def __init__(self, name, comment, freq):
        super().__init__(name, "", comment)
        self.freq = freq
        self.component = "sdr"
        self.sdrproc = None

    def opus_play(self):
        pass

    def opus_stop(self):
        pass

    def opus_pause(self):
        self.stop()

    def opus_export_metadata(self):
        md = {'component': self.component,
              'type': 'sdr',
              'name': self.menu_labels['name'],
              'comment': self.menu_labels['comment'],
              'freq': self.freq,
              }
        return md


class FmOpus(Opus):
    """Use rtl_fm to play a station

        Command Format
        rtl_fm -M wbfm -s 256000 -r 48k -f 90.5M | play -r 48k -t raw -e s -b 16 -c 1 -V1 -

        Might need https://pymotw.com/3/subprocess/ for this
    """

    def __init__(self, name, comment, freq):
        super().__init__(name, "", comment)
        self.freq = freq
        self.component = "fmradio"
        self.pid = None
        self.process = None
        self.sdrproc = None
        self.rtlfm_proc = None
        self.play_proc = None
        self.rtlfm_command = [
                        '/usr/local/bin/rtl_fm',
                        '-M',
                        'wbfm',
                        '-s',
                        '256000',
                        '-r',
                        '48k',
                        '-f ',
                        self.freq + "M",
                        ]
        self.play_command = [
                        '/usr/local/bin/play',
                        '-r',
                        '48k',
                        '-t',
                        'raw',
                        '-e',
                        's',
                        '-b',
                        '16',
                        '-c',
                        '1',
                        '-V1',
                        '-']

    def opus_play(self):
        # self.rtlfm_proc = asyncio.subprocess.Popen(self.rtlfm_command, stdout=subprocess.PIPE)
        # self.play_proc = subprocess.Popen(self.play_command, stdin=self.rtlfm_proc.stdout, stdout=subprocess.PIPE)
        # self.third_pipe = self.play_proc.stdout
        #
        # self.rtlfm_pid = self.rtlfm_proc.pid
        # self.play_pid = self.play_proc.pid
        self.pid, self.process = play_fm_station(self.freq)

    def opus_stop(self):
        logging.debug('terminating process:')
        self.process.terminate()
        try:
            os.kill(self.pid, 0)
            self.process.kill()
        except OSError:
            logging.debug('Terminated gracefully')

    def opus_pause(self):
        self.stop()

    def opus_export_metadata(self):
        md = {'component': self.component,
              'type': 'fmradio',
              'name': self.menu_labels['name'],
              'comment': self.menu_labels['comment'],
              'freq': self.freq,
              }
        return md
