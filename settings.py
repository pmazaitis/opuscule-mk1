from base_classes import MenuComponent, MenuList, Command


class SettingsComponent(MenuComponent):
    def __init__(self):
        # Do Startup tasks
        super().__init__("Settings", "Set", "System Settings")

        self.component = "settings"

    def requirements_met(self):
        return False
