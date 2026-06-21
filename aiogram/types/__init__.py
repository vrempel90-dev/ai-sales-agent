class Message:
    pass

class CallbackQuery:
    pass

class InlineKeyboardButton:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

class InlineKeyboardMarkup:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
