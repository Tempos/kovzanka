import contextlib
import logging
import os
from datetime import datetime, timezone

import requests
from telegram import Bot, KeyboardButton, ReplyKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes, filters, MessageHandler

from app.db import SessionLocal
from app.models import QueueItem, QueueStatus

logger = logging.getLogger(__name__)

_application = None


def normalize_phone(phone: str) -> str:
    if phone:
        digits = "".join(filter(str.isdigit, phone))
        return digits[-9:] if len(digits) >= 9 else digits
    return ""


async def send_telegram_notification(chat_id: str, text: str):
    if not (token := os.getenv("TELEGRAM_BOT_TOKEN")):
        logger.error("TELEGRAM_BOT_TOKEN is missing in environment variables!")
        return
    if not chat_id:
        logger.warning("Skipped Telegram notification: chat_id is empty or None.")
        return

    try:
        async with Bot(token=token) as bot:
            await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
        logger.info(f"Successfully sent Telegram notification to chat_id: {chat_id}")
    except Exception as e:
        logger.error(f"Failed to send Telegram notification to {chat_id}: {e}", exc_info=True)


def get_main_menu_keyboard():
    keyboard = [
        [KeyboardButton("🎟️ Мої талони"), KeyboardButton("⏱️ Час на льоду")],
        [KeyboardButton("📱 Оновити номер телефону")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Received /start from user: {update.effective_user.id}")
    button = KeyboardButton("📱 Поділитися номером телефону", request_contact=True)
    reply_markup = ReplyKeyboardMarkup([[button]], resize_keyboard=True, one_time_keyboard=True)
    text = "Вітаємо у ковзанці «Акула Мама»! ⛸️ Натисніть кнопку нижче, щоб зв'язати свій номер телефону з ботом."
    await update.message.reply_text(text, reply_markup=reply_markup)


async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    logger.info(f"Received contact from user {update.effective_user.id}: {contact.phone_number if contact else 'None'}")

    if not contact or not contact.phone_number:
        return

    chat_id = str(update.effective_chat.id)
    norm_phone = normalize_phone(contact.phone_number)
    logger.info(f"Normalized phone from Telegram: {norm_phone}, Chat ID: {chat_id}")

    db = SessionLocal()
    try:
        active_items = db.query(QueueItem).filter(
            QueueItem.status.in_([QueueStatus.WAITING, QueueStatus.CALLING, QueueStatus.SERVED])
        ).all()

        matched_tickets = []
        for item in active_items:
            db_norm_phone = normalize_phone(item.phone)
            logger.info(f"Checking ticket #{item.ticket_number} with phone {item.phone} (norm: {db_norm_phone})")
            if db_norm_phone == norm_phone:
                item.telegram_chat_id = chat_id
                matched_tickets.append(str(item.ticket_number))

        db.commit()
        logger.info(f"Successfully matched and linked tickets: {matched_tickets}")

        if matched_tickets:
            text = f"✅ Успішно! Ваш номер зв'язано з талоном(ами): #{', '.join(matched_tickets)}."
        else:
            text = "✅ Номер збережено! Щойно ви зареєструєтесь на касі, сповіщення надходитимуть сюди."
        await update.message.reply_text(text, reply_markup=get_main_menu_keyboard())
    except Exception as e:
        logger.error(f"Error in contact_handler: {e}", exc_info=True)
    finally:
        db.close()


def _get_friendly_status(status) -> str:
    raw_status = status.name if hasattr(status, "name") else str(status)
    if "." in raw_status:
        raw_status = raw_status.split(".")[-1]

    return {
        "ЧЕКАЄ": "⏳ Чекає",
        "ВИКЛИКАЄТЬСЯ": "🔔 Викликається",
        "ОБСЛУГОВУЄТЬСЯ": "⛸️ На льоду",
        "WAITING": "⏳ Чекає",
        "CALLING": "🔔 Викликається",
        "SERVED": "⛸️ На льоду"
    }.get(raw_status.upper(), raw_status)


async def _handle_my_tickets(update: Update, chat_id: str, db):
    items = db.query(QueueItem).filter(
        QueueItem.telegram_chat_id == chat_id,
        QueueItem.status.in_([
            QueueStatus.WAITING, QueueStatus.CALLING, QueueStatus.SERVED,
            "ЧЕКАЄ", "ВИКЛИКАЄТЬСЯ", "ОБСЛУГОВУЄТЬСЯ"
        ])
    ).all()

    if not items:
        text = "📭 У вас немає активних талонів на даний момент."
        await update.message.reply_text(text, reply_markup=get_main_menu_keyboard())
        return

    base_url = get_dynamic_base_url()
    response_lines = ["🎟️ *Ваші активні талони:*"]
    for item in items:
        status_emoji = _get_friendly_status(item.status)
        ticket_url = f"{base_url}/status?ticket={item.ticket_number}"
        response_lines.append(
            f"• [Талон #{item.ticket_number}]({ticket_url}) — Статус: {status_emoji} (Людей: {item.people_count})")

    await update.message.reply_text("\n".join(response_lines), "Markdown", reply_markup=get_main_menu_keyboard())


def get_dynamic_base_url() -> str:
    if env_url := os.getenv("BASE_URL"):  # BASE_URL (Apache)
        return env_url.rstrip("/")

    with contextlib.suppress(Exception):  # ngrok
        response = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=1)
        data = response.json()
        for tunnel in data.get("tunnels", []):
            if tunnel.get("proto") == "https":
                return tunnel.get("public_url").rstrip("/")
    return "http://127.0.0.1:8000"


async def _handle_ice_time(update: Update, chat_id: str, db):
    items = db.query(QueueItem).filter(
        QueueItem.telegram_chat_id == chat_id,
        QueueItem.status.in_([QueueStatus.SERVED, "SERVED", "ОБСЛУГОВУЄТЬСЯ"])
    ).all()

    if not items:
        text = "⛸️ Зараз у вас немає активних сеансів на льоду."
        await update.message.reply_text(text, reply_markup=get_main_menu_keyboard())
        return

    base_url = get_dynamic_base_url()
    now = datetime.now(timezone.utc)
    response_lines = ["⏱️ *Залишок часу на льоду:*"]

    for item in items:
        ticket_url = f"{base_url}/status?ticket={item.ticket_number}"

        if item.session_end:
            end_time = item.session_end
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=timezone.utc)

            remaining_sec = int((end_time - now).total_seconds())
            if remaining_sec > 0:
                mins, secs = divmod(remaining_sec, 60)
                time_str = f"{mins} хв {secs:02d} с"
                response_lines.append(f"• [Талон #{item.ticket_number}]({ticket_url}) — залишилося *{time_str}*")
            else:
                response_lines.append(f"• [Талон #{item.ticket_number}]({ticket_url}) — ⏱️ Час сеансу вичерпано!")
        else:
            response_lines.append(f"• [Талон #{item.ticket_number}]({ticket_url}) — час сеансу ще не запущено касиром.")

    await update.message.reply_text("\n".join(response_lines), "Markdown", reply_markup=get_main_menu_keyboard())


async def _handle_phone_update(update: Update):
    button = KeyboardButton("📱 Поділитися новим номером", request_contact=True)
    reply_markup = ReplyKeyboardMarkup([[button]], resize_keyboard=True, one_time_keyboard=True)
    text = "Натисніть кнопку нижче, щоб оновити свій контактний номер телефону:"
    await update.message.reply_text(text, reply_markup=reply_markup)


async def menu_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip().lower()
    chat_id = str(update.effective_chat.id)

    db = SessionLocal()
    try:
        if "талон" in text:
            await _handle_my_tickets(update, chat_id, db)
        elif "час" in text or "льоду" in text:
            await _handle_ice_time(update, chat_id, db)
        elif "номер" in text or "оновити" in text:
            await _handle_phone_update(update)
        else:
            text = "Будь ласка, скористайтеся кнопками меню нижче:"
            await update.message.reply_text(text, reply_markup=get_main_menu_keyboard())
    finally:
        db.close()


async def init_telegram_bot():
    global _application
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not found, bot initialization skipped.")
        return

    _application = Application.builder().token(token).build()
    _application.add_handler(CommandHandler("start", start_command))
    _application.add_handler(MessageHandler(filters.CONTACT, contact_handler))
    _application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_text_handler))

    await _application.initialize()
    await _application.start()
    await _application.updater.start_polling()
    logger.info("Telegram bot initialized and polling started.")


async def stop_telegram_bot():
    global _application
    if _application:
        try:
            if _application.updater and _application.updater.running:
                await _application.updater.stop()
            if _application.running:
                await _application.stop()
            await _application.shutdown()
            logger.info("Telegram bot stopped successfully.")
        except Exception as e:
            logger.error(f"Error stopping Telegram bot: {e}", exc_info=True)
