import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from admin import router as admin_router
from config import BOT_TOKEN, DATA_DIR, get_map_file_path
from database import has_received_map, init_db, mark_map_sent, upsert_user

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

BOT_DESCRIPTION = "Чтобы скачать карту состояний, начни работать с ботом🤗"

WELCOME_TEXT = (
    "Привет, прекрасная женщина! ♥️\n"
    "Меня зовут Наталья. Я фотограф, психолог и телесно-ориентированный терапевт.\n"
    "Я подготовила для тебя Карту состояний - 9 образов, которые помогут тебе понять, "
    "какая ты сейчас. Что тебе нужно. Что живёт внутри.\n"
    "Хочешь получить её бесплатно? Просто нажми кнопку ниже 👇"
)

MAP_INTRO_TEXT = "Отлично! Лови Карту состояний 👇"

MAP_FOLLOWUP_TEXT = (
    "Сохрани её, перечитай, отметь те состояния, которые откликаются тебе.\n"
    "А если захочешь прожить их в кадре — просто напиши мне 🤗\n"
    "✍️ @khoruzhenko_nataly"
)

CALLBACK_WANT_MAP = "want_map"
MAP_FILE_ID_PATH = DATA_DIR / "map_file_id.txt"
_map_file_id: str | None = None


def _load_map_file_id() -> str | None:
    if MAP_FILE_ID_PATH.exists():
        file_id = MAP_FILE_ID_PATH.read_text(encoding="utf-8").strip()
        if file_id:
            return file_id
    return None


def _save_map_file_id(file_id: str) -> None:
    MAP_FILE_ID_PATH.parent.mkdir(parents=True, exist_ok=True)
    MAP_FILE_ID_PATH.write_text(file_id, encoding="utf-8")


async def send_map_document(bot: Bot, chat_id: int) -> None:
    global _map_file_id

    if _map_file_id:
        await bot.send_document(chat_id=chat_id, document=_map_file_id)
        return

    map_path = get_map_file_path()
    document = FSInputFile(map_path, filename="Карта состояний.pdf")
    sent = await bot.send_document(chat_id=chat_id, document=document)

    if sent.document:
        _map_file_id = sent.document.file_id
        _save_map_file_id(_map_file_id)


dp = Dispatcher(storage=MemoryStorage())
dp.include_router(admin_router)


def want_map_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Да, хочу!", callback_data=CALLBACK_WANT_MAP)]
        ]
    )


@dp.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user = message.from_user
    if not user:
        return

    upsert_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )

    await message.answer(WELCOME_TEXT, reply_markup=want_map_keyboard())


@dp.callback_query(F.data == CALLBACK_WANT_MAP)
async def on_want_map(callback: CallbackQuery, bot: Bot) -> None:
    if not callback.from_user or not callback.message:
        await callback.answer()
        return

    user_id = callback.from_user.id
    already_received = has_received_map(user_id)
    map_path = get_map_file_path()

    if not map_path.exists():
        logger.error("Файл карты не найден: %s", map_path)
        await callback.answer(
            "Файл временно недоступен. Попробуйте позже.",
            show_alert=True,
        )
        return

    await callback.answer()
    await callback.message.answer(MAP_INTRO_TEXT)

    try:
        await send_map_document(bot, callback.message.chat.id)
    except Exception:
        logger.exception("Не удалось отправить PDF")
        await callback.message.answer(
            "Не удалось отправить файл. Попробуйте ещё раз чуть позже."
        )
        return

    await callback.message.answer(MAP_FOLLOWUP_TEXT)

    if not already_received:
        mark_map_sent(user_id)


async def main() -> None:
    global _map_file_id

    if not BOT_TOKEN:
        logger.error("Укажите BOT_TOKEN в файле .env")
        sys.exit(1)

    init_db()
    _map_file_id = _load_map_file_id()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    await bot.set_my_description(description=BOT_DESCRIPTION)
    await bot.set_my_description(description=BOT_DESCRIPTION, language_code="ru")
    logger.info("Бот запущен")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
    