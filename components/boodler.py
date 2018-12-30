
from base_classes import Opus, MenuList, AudioComponent
import subprocess
import json

"""
Opuscule boodler component: play generated soundscapes.

This component requires boodler to generate the soundscapes.
"""

class BoodlerComponent(AudioComponent):
    def __init__(self, sfavs):

        # Do Startup tasks
        super().__init__("Boodler", "Boo", "Generated Soundscapes")
        self.sfavs = sfavs

        self.component = "boodler"

        self.favs_save_file = "saved/{}_favorites.json".format(self.component)
        self.favorites_node.menu_labels['comment'] = "Boodler Favorites"
        self.favorites_node.component = self.component
        self.load_favorites()

        self.available_node = BoodlerMenuList("Available", "Avbl", "My custom stations")

        self.add_child(self.available_node)

        # Populate the menu
        # subprocess.run(["boodle-mgr", "list"])

        test_operai = [
            BoodlerOpus('Crows', 'A Parliament of Crows.', "com.eblong.zarf.crows", "ParliamentOfCrows"),
            BoodlerOpus('Thunderstorms.', 'A storm an hour.', "com.eblong.ow.storm", "RainForever")
        ]

        for opus in test_operai:
            self.available_node.add_child(opus)

    def requirements_met(self):
        return True

    def save_favorites(self):
        favs = []
        for fav in self.favorites_node.children:
            favs.append(fav.get_metadata())

        json_favs = json.dumps(favs)

        with open(self.favs_save_file, mode='w', encoding='utf-8') as the_file:
            the_file.write(json_favs)

    def load_favorites(self):
        try:
            with open(self.favs_save_file, mode='r', encoding='utf-8') as the_file:
                favs = json.loads(the_file.read())
                for fav in favs:
                    this_opus = BoodlerOpus(fav['name'], fav['comment'], fav['package'], fav['agent'])
                    self.favorites_node.add_child(this_opus)
                self.sfavs.update_one_favorite_menu(self)
        except json.JSONDecodeError:
            pass
        except FileNotFoundError:
            pass


class BoodlerMenuList(MenuList):
    def __init__(self, name, short_name, comment):
        super().__init__(name, short_name, comment)
        self.component = "boodler"


class BoodlerOpus(Opus):
    """A boodler soundscape.

    """
    # TODO: port boodler to python3 so we can get more elegant solutions to populating the display with nice text
    def __init__(self, name, comment, package, agent):
        super().__init__(name, "", comment)
        self.package = package
        self.agent = agent
        self.component = "boodler"
        self.boo = None
        self.command = "boodler {}/{}".format(self.package, self.agent)

    def opus_play(self):
        self.boo = subprocess.Popen(self.command, shell=True)

    def opus_stop(self):
        if self.boo:
            self.boo.kill()
            self.boo = None

    # def opus_update_info(self):
    #     self.nowplaying_data['agent'] = self.package
    #     self.nowplaying_data['package'] = self.agent

    # def opus_get_info(self):
    #     self.opus_update_info()
    #     return self.nowplaying_data

    def opus_get_metadata(self):
        md = {'component': self.component,
              'type': 'soundscape',
              'name': self.menu_labels['name'],
              'comment': self.menu_labels['comment'],
              'package': self.package,
              'agent': self.agent,
              }
        return md
