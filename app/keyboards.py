from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

def threads_post_keyboard(post_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"threads:publish:{post_id}"), InlineKeyboardButton(text="🔁 Переделать", callback_data=f"threads:rewrite:{post_id}")],
        [InlineKeyboardButton(text="🧹 Убрать как слабый", callback_data=f"threads:skip:{post_id}"), InlineKeyboardButton(text="➡️ Следующий", callback_data="threads:next")],
    ])
