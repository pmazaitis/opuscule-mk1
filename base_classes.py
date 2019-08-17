"""
These base classes support objects in the opuscule system.


"""

import logging

logger = logging.getLogger(__name__)


class MenuNode:
    """Objects in the menu tree should always have this attribute as a dictionary, with at least these keys."""

    def __init__(self, name, short_name, comment):
        self.menu_labels = {'name': name,
                            'shortname': short_name,
                            'comment': comment,
                            }


class MenuList(MenuNode):
    """The MenuList objects act as nodes of the menu tree."""

    def __init__(self, name, short_name, comment):
        super().__init__(name, short_name, comment)
        self.parent = None
        self.children = []
        self.index = 0
        self.component = "menulistbase"

    def selected_node(self):
        if self.children:
            return self.children[self.index]

    def has_child(self, node):
        return node in self.children

    def add_child(self, node):
        self.children.append(node)
        node.parent = self

    def reset_children(self):
        self.children = []

    def update_menu_labels(self, name, short_name, comment):
        self.menu_labels['name'] = name
        self.menu_labels['short_name'] = short_name
        self.menu_labels['comment'] = comment

    def sort_children(self):
        # https: // docs.python.org / 3 / howto / sorting.html
        # Sorts in place!
        self.children.sort(key=lambda name: name.labels['name'])

    def get_path(self, the_path):
        if self.menu_labels['name'] == 'root':
            return the_path
        else:
            the_path.insert(0, self.menu_labels)
            return self.parent.get_path(the_path)


class MenuComponent(MenuList):
    """
    Specialized MenuList that contains a (possibly optional) component.

    Components are a sectiong device to name sub-trees: all of the menus, operai, commands, or anything else
    to do with a particular component should be a descendant of that compnent node in the hierarchy.
    """

    def __init__(self, name, short_name, comment):
        super().__init__(name, short_name, comment)

    def requirements_met(self):
        """Test for things the component needs to work: external commands, etc.
        The base case is false; a module passing this should be an intentional thing."""
        return False


class AudioComponent(MenuList):
    """Specialized object that contains a (possibly optional) component

    These menu items can insert keyword shortcuts into the protocol?
    """

    def __init__(self, name, short_name, comment):
        super().__init__(name, short_name, comment)
        self.favorites_node = MenuList("Favorites", "Fav", "Generic Favorites")
        self.add_child(self.favorites_node)
        self.component = "audiocomponentbase"

    def requirements_met(self):
        """Test for things the component needs to work: external commands, etc.
        The base case is false; a module passing this should be an intentional thing."""
        return False

    def add_favorite(self, fav):
        if fav not in self.favorites_node.children:
            self.favorites_node.add_child(fav)

    def save_favorites(self):
        pass

    def load_favorites(self):
        pass


class Opus(MenuNode):
    """Parent class for playable objects.

    Every opus should have some sensible value for the following:

    menu labels, for ui construction:

    name       : the printable name of the opus for using the UI (string)
    short_name : Abbreviations shouldn't be used for operai
    comment    : extra information about the opus for use in the UI (string)

    nowplaying labels: a superset of any metadata that can be returned by any component.
    """

    def __init__(self, name, short_name, comment):
        super().__init__(name, short_name, comment)
        self.shuffle_support = False
        self.shuffle = 0
        self.repeat_support = False
        self.repeat = 0
        self.pause_support = False
        self.pause = 0
        self.parent = None
        self.children = False
        self.component = "opusbase"
        self.supported_data = []

    def __repr__(self):
        return "[Opus] {} ".format(self.menu_labels['name'])

    def opus_play(self):
        pass

    def opus_stop(self):
        pass

    def opus_pause(self):
        pass

    def opus_unpause(self):
        pass

    def opus_fast_forward(self):
        pass

    def opus_rewind(self):
        pass

    def opus_next(self):
        pass

    def opus_previous(self):
        pass

    def opus_update_repeat(self):
        pass

    def opus_update_shuffle(self):
        pass

    def opus_get_metadata(self):
        # Return metatdata for opus to serialize it and recreate from persistant store
        return {}


class Command(MenuNode):
    """Parent class for system commands."""

    def __init__(self, name, short_name, comment):
        super().__init__(name, short_name, comment)
        self.kind = "command"
        self.parent = None
        self.children = None

    def command_execute(self):
        pass
