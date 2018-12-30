"""
The superfavorites module collects a copy of the favorites tree from every
component. The goal is to make favorites access easy from the root menu
of the menu tree.

One wrinkle to this implementation is that we have to make a copy to avoid 
surprises with the navigation: we don't want to enter a menu from the
superfavorites, only to escape out into the parent component.
"""

from base_classes import MenuList, MenuComponent

class SuperFavoritesComponent(MenuComponent):
    def __init__(self):
        super().__init__("Favorites", "Fav", "Collected Favorites from all Components")
        self.component = "superfavorites"

    def requirements_met(self):
        return True

    def add_child_menu(self, node):
        subfavlist = SuperFavoritesMenuList(node)
        self.children.append(subfavlist)
        subfavlist.parent = self

    def update_all_favorite_menus(self):
        for node in self.children:
            node.update_favorites()

    def update_one_favorite_menu(self, node):
        for n in self.children:
            if n.origin_node == node:
                n.update_favorites()

    def save_all_favorites(self):
        pass

    def restore_allfavorites(self):
        pass


class SuperFavoritesMenuList(MenuList):
    def __init__(self, origin_node):
        super().__init__("{} Favorites".format(origin_node.parent.menu_labels['name']), "", "")
        self.origin_node = origin_node
        self.component = "superfavorites"
        self.update_favorites()

    def add_child(self, node):
        child_node = SuperFavoritesMenuList(node.favorites_node)
        self.children.append(child_node)
        child_node.parent = self

    def update_favorites(self):
        self.children = list(self.origin_node.children)
