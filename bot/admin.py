from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import BaseFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import ADMIN_IDS
from database import (
    count_downloaders,
    count_starters,
    get_all_users,
    get_downloaders,
    get_user_by_id,
)

router = Router()
PAGE_SIZE = 8


class AdminFilter(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user = event.from_user
        return bool(user and user.id in ADMIN_IDS)


class AdminStates(StatesGroup):
    waiting_message = State()


def format_user_label(row) -> str:
    parts = [row["first_name"] or "", row["last_name"] or ""]
    name = " ".join(part for part in parts if part).strip() or "Без имени"
    if row["username"]:
        return f"{name} (@{row['username']})"
    return f"{name} (id: {row['user_id']})"


def format_datetime(iso_value: str | None) -> str:
    if not iso_value:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_value)
        return dt.strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return iso_value[:16].replace("T", " ")


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    downloaders = count_downloaders()
    starters = count_starters()
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"📥 Скачали карту ({downloaders})",
                    callback_data="admin:list:0",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"👥 Все пользователи ({starters})",
                    callback_data="admin:all:0",
                )
            ],
        ]
    )


def users_list_keyboard(rows, page: int, total: int, mode: str) -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = []

    for row in rows:
        label = format_user_label(row)
        if len(label) > 40:
            label = label[:37] + "..."
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"✉️ {label}",
                    callback_data=f"admin:write:{row['user_id']}",
                )
            ]
        )

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin:{mode}:{page - 1}")
        )
    if (page + 1) * PAGE_SIZE < total:
        nav.append(
            InlineKeyboardButton(text="Вперёд ▶️", callback_data=f"admin:{mode}:{page + 1}")
        )
    if nav:
        keyboard.append(nav)

    keyboard.append([InlineKeyboardButton(text="🏠 В меню", callback_data="admin:menu")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:cancel")]
        ]
    )


async def show_admin_menu(target: Message) -> None:
    await target.answer(
        "🔐 <b>Админ-панель</b>\n\n"
        "Выберите раздел:",
        reply_markup=admin_menu_keyboard(),
    )


@router.message(Command("myid"))
async def cmd_myid(message: Message) -> None:
    user = message.from_user
    if not user:
        return
    await message.answer(str(user.id))


@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    user = message.from_user
    if not user or user.id not in ADMIN_IDS:
        await message.answer("У вас нет доступа к админ-панели")
        return

    await state.clear()
    await show_admin_menu(message)


@router.callback_query(F.data == "admin:menu", AdminFilter())
async def on_admin_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if callback.message:
        await callback.message.edit_text(
            "🔐 <b>Админ-панель</b>\n\nВыберите раздел:",
            reply_markup=admin_menu_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:list:"), AdminFilter())
async def on_downloaders_list(callback: CallbackQuery) -> None:
    page = int(callback.data.split(":")[-1])
    total = count_downloaders()
    rows = get_downloaders(PAGE_SIZE, page * PAGE_SIZE)

    if not rows:
        text = "📥 Пока никто не скачал карту."
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🏠 В меню", callback_data="admin:menu")]
            ]
        )
    else:
        lines = [
            f"• {format_user_label(row)} — {format_datetime(row['map_sent_at'])}"
            for row in rows
        ]
        text = (
            f"📥 <b>Скачали карту</b> ({total})\n"
            f"Страница {page + 1} из {max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)}\n\n"
            + "\n".join(lines)
            + "\n\nНажмите на пользователя, чтобы написать ему:"
        )
        keyboard = users_list_keyboard(rows, page, total, "list")

    if callback.message:
        await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:all:"), AdminFilter())
async def on_all_users_list(callback: CallbackQuery) -> None:
    page = int(callback.data.split(":")[-1])
    total = count_starters()
    rows = get_all_users(PAGE_SIZE, page * PAGE_SIZE)

    if not rows:
        text = "👥 Пользователей пока нет."
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🏠 В меню", callback_data="admin:menu")]
            ]
        )
    else:
        lines = []
        for row in rows:
            status = "✅ скачала" if row["map_sent_at"] else "⏳ не скачала"
            lines.append(f"• {format_user_label(row)} — {status}")
        text = (
            f"👥 <b>Все пользователи</b> ({total})\n"
            f"Страница {page + 1} из {max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)}\n\n"
            + "\n".join(lines)
            + "\n\nНажмите на пользователя, чтобы написать ему:"
        )
        keyboard = users_list_keyboard(rows, page, total, "all")

    if callback.message:
        await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("admin:write:"), AdminFilter())
async def on_write_user(callback: CallbackQuery, state: FSMContext) -> None:
    user_id = int(callback.data.split(":")[-1])
    row = get_user_by_id(user_id)
    if not row:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    await state.set_state(AdminStates.waiting_message)
    await state.update_data(target_user_id=user_id)

    if callback.message:
        await callback.message.edit_text(
            f"✉️ Напишите сообщение для:\n<b>{format_user_label(row)}</b>\n\n"
            "Отправьте текст в этот чат.\n"
            "Для отмены нажмите кнопку ниже или отправьте /cancel.",
            reply_markup=cancel_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data == "admin:cancel", AdminFilter())
async def on_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if callback.message:
        await callback.message.edit_text(
            "🔐 <b>Админ-панель</b>\n\nВыберите раздел:",
            reply_markup=admin_menu_keyboard(),
        )
    await callback.answer("Отменено")


@router.message(Command("cancel"), AdminFilter())
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await show_admin_menu(message)


@router.message(AdminStates.waiting_message, AdminFilter())
async def on_admin_message_text(message: Message, state: FSMContext, bot: Bot) -> None:
    if not message.text:
        await message.answer("Отправьте текстовое сообщение.")
        return

    data = await state.get_data()
    target_user_id = data.get("target_user_id")
    if not target_user_id:
        await state.clear()
        await show_admin_menu(message)
        return

    row = get_user_by_id(target_user_id)
    label = format_user_label(row) if row else str(target_user_id)

    try:
        await bot.send_message(chat_id=target_user_id, text=message.text)
    except TelegramForbiddenError:
        await message.answer(
            f"❌ Не удалось отправить сообщение пользователю {label}.\n"
            "Возможно, он заблокировал бота."
        )
    except TelegramBadRequest as exc:
        await message.answer(f"❌ Ошибка отправки: {exc}")
    else:
        await message.answer(
            f"✅ Сообщение отправлено пользователю:\n<b>{label}</b>",
            reply_markup=admin_menu_keyboard(),
        )
        await state.clear()
