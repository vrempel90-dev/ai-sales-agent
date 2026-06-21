class User:
    def __init__(self, id=None, **kwargs):
        self.id = id
        self.__dict__.update(kwargs)

class Chat:
    def __init__(self, id=None, **kwargs):
        self.id = id
        self.__dict__.update(kwargs)

class Message:
    def __init__(self, text="", chat=None, from_user=None, bot=None, **kwargs):
        self.text = text
        self.chat = chat or Chat()
        self.from_user = from_user or User()
        self.bot = bot
        self.__dict__.update(kwargs)
    @classmethod
    def from_payload(cls, payload: dict, bot):
        return cls(
            text=payload.get("text", ""),
            chat=Chat(**payload.get("chat", {})),
            from_user=User(**payload.get("from", {})),
            bot=bot,
        )
    async def answer(self, text: str, **kwargs):
        return await self.bot.send_message(self.chat.id, text, **kwargs)

class CallbackQuery:
    pass

class InlineKeyboardButton:
    def __init__(self, **kwargs): self.__dict__.update(kwargs)

class InlineKeyboardMarkup:
    def __init__(self, **kwargs): self.__dict__.update(kwargs)
