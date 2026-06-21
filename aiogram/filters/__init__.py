class Command:
    def __init__(self, *commands, **kwargs):
        self.commands = commands
        self.command = commands[0] if commands else ""

class CommandStart(Command):
    def __init__(self, *args, **kwargs):
        super().__init__("start")
