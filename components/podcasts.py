
from base_classes import Opus, MenuList, AudioComponent

import logging


# TODO:
# - mpd interaction? Key on a particular genre?


class PodcastsComponent(AudioComponent):
    def __init__(self, mpd_client):
        # Do Startup tasks
        super().__init__("Podcasts", "Pod", "Serialized Audio")

        # Our hierarchy
        self.component = "podcasts"
        # Local pointers into the radio state and the streaming client
        self.mpdc = mpd_client
        # Zero the client state on startup
        self.mpdc.clear()
        # Set up the areas of the component

        self.favorites_node.menu_labels['comment'] = "Podcast Favorites"
        self.favorites_node.component = self.component

    def requirements_met(self):
        return False


class PodcastsMenuList(MenuList):
    def __init__(self, name, short_name, comment):
        super().__init__(name, short_name, comment)
        self.component = "podcasts"


class PodcastsOpus(Opus):
    """A piece of streaming media.

    """
    pass
