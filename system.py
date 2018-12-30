from base_classes import MenuComponent, MenuList, Command

import logging



class SystemComponent(MenuComponent):
    def __init__(self):
        # Do Startup tasks
        super().__init__("System", "Sys", "System Commands")

        self.component = "system"

        self.add_child(GenericCommand("Logs", "Log", "Display the logs.", "logging command"))
        self.add_child(SleepCommand())
        self.add_child(GenericCommand("Restart", "Rst", "Restart the system.", "restart command"))
        self.add_child(GenericCommand("Shutdown", "Stdn", "Shutdown the system.", "shutdown command"))

    def requirements_met(self):
        return True


class GenericCommand(Command):

    def __init__(self, name, short_name, comment, command_string):

        super().__init__(name, short_name, comment)
        self.cmd = command_string
        self.component = "system"

    def execute(self):
        logging.debug("System command: {}".format(self.menu_labels['comment']))


class SleepCommand(Command):

    def __init__(self):
        super().__init__("Sleep", "Slp", "Put the system to sleep.")
        self.cmd = "Foo"
        self.component = "system"

    def execute(self):
        logging.debug("System command: {}".format(self.menu_labels['comment']))
