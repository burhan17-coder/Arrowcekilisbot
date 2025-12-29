#!/usr/bin/env python3
import os
import random
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# Optional: load .env in local dev (do NOT commit .env)
load_dotenv()

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Config
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    logger.warning("BOT_TOKEN environment variable not set. The bot will fail to start without a token.")

REQUIRED_MESSAGES = 10  # Mesaj sayısı (24 saat bloklu çekilişler için)

# Data structures
# active_draws: draw_name -> {
#    chat_id, participants [user_id...], end_time (datetime),
#    message_counts {user_id: int}, prize_message (str|None), no_block (bool)
# }
active_draws = {}
blocked_users = {}  # user_id -> unblock_datetime (None means permanent)
past_winners = []   # isim listesi

def clean_expired_blocks():
    """Remove expired timed blocks."""
    now = datetime.now()
    expired = [uid for uid, t in blocked_users.items() if t is not None and t <= now]
    for uid in expired:
        del blocked_users[uid]

def is_blocked(user_id: int) -> bool:
    clean_expired_blocks()
    return user_id in blocked_users

# --- Command handlers ---

def start_draw(update: Update, context: CallbackContext) -> None:
    if len(context.args) < 2:
        update.message.reply_text("Kullanım: /cekilis <çekiliş_ismi> <süre_dakika>")
        return
    draw_name = context.args[0]
    try:
        minutes = int(context.args[1])
    except ValueError:
        update.message.reply_text("Süre bir sayı olmalı (dakika). Örnek: /cekilis mydraw 60")
        return
    chat_id = update.effective_chat.id
    if draw_name in active_draws:
        update.message.reply_text(f"\"{draw_name}\" zaten aktif.")
        return
    active_draws[draw_name] = {
        'chat_id': chat_id,
        'participants': [],
        'end_time': datetime.now() + timedelta(minutes=minutes),
        'message_counts': {},
        'prize_message': None,
        'no_block': False
    }
    update.message.reply_text(f"\"{draw_name}\" çekilişi başladı ({minutes} dakika). /katil <çekiliş_ismi> ile katıl.")

def start_no_block_draw(update: Update, context: CallbackContext) -> None:
    if len(context.args) < 2:
        update.message.reply_text("Kullanım: /cekilisall <çekiliş_ismi> <süre_dakika>")
        return
    draw_name = context.args[0]
    try:
        minutes = int(context.args[1])
    except ValueError:
        update.message.reply_text("Süre bir sayı olmalı (dakika). Örnek: /cekilisall mydraw 60")
        return
    chat_id = update.effective_chat.id
    if draw_name in active_draws:
        update.message.reply_text(f"\"{draw_name}\" zaten aktif.")
        return
    active_draws[draw_name] = {
        'chat_id': chat_id,
        'participants': [],
        'end_time': datetime.now() + timedelta(minutes=minutes),
        'message_counts': {},
        'prize_message': None,
        'no_block': True
    }
    update.message.reply_text(f"\"{draw_name}\" blokesiz çekilişi başladı ({minutes} dakika). /katil <çekiliş_ismi> ile katıl.")

def on_message(update: Update, context: CallbackContext) -> None:
    """Count non-command text messages per-user for active draws in this chat."""
    if update.effective_user is None:
        return
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    # For each active draw in this chat, increment message count
    for draw in active_draws.values():
        if draw['chat_id'] != chat_id:
            continue
        counts = draw.setdefault('message_counts', {})
        counts[user_id] = counts.get(user_id, 0) + 1

def join_draw(update: Update, context: CallbackContext) -> None:
    if not context.args:
        update.message.reply_text("Kullanım: /katil <çekiliş_ismi>")
        return
    draw_name = context.args[0]
    user = update.effective_user
    if user is None:
        return
    user_id = user.id
    if draw_name not in active_draws:
        update.message.reply_text("Geçerli bir çekiliş ismi girin.")
        return
    draw = active_draws[draw_name]
    if draw['chat_id'] != update.effective_chat.id:
        update.message.reply_text("Bu çekiliş başka bir sohbette başlatılmış.")
        return
    if is_blocked(user_id):
        update.message.reply_text("Bu kullanıcı şu an bloklu olduğu için katılamaz.")
        return
    if user_id in draw['participants']:
        update.message.reply_text("Zaten katıldınız!")
        return
    if draw.get('no_block'):
        draw['participants'].append(user_id)
        update.message.reply_text(f"{user.first_name} blokesiz çekilişe katıldı.")
        return
    msg_count = draw.get('message_counts', {}).get(user_id, 0)
    if msg_count < REQUIRED_MESSAGES:
        remaining = REQUIRED_MESSAGES - msg_count
        update.message.reply_text(f"Katılmak için en az {REQUIRED_MESSAGES} mesaj atmalısınız. {remaining} mesaj eksik.")
        return
    draw['participants'].append(user_id)
    update.message.reply_text(f"{user.first_name} çekilişe katıldı!")

def add_draw_message(update: Update, context: CallbackContext) -> None:
    if len(context.args) < 2:
        update.message.reply_text("Kullanım: /odul_ekle <çekiliş_ismi> <ödül_metni>")
        return
    draw_name = context.args[0]
    if draw_name not in active_draws:
        update.message.reply_text("Geçerli bir çekiliş ismi girin.")
        return
    prize = " ".join(context.args[1:])
    active_draws[draw_name]['prize_message'] = prize
    update.message.reply_text(f"\"{draw_name}\" için ödül mesajı kaydedildi.")

def draw_winner(update: Update, context: CallbackContext) -> None:
    if not context.args:
        update.message.reply_text("Kullanım: /kazanan <çekiliş_ismi>")
        return
    draw_name = context.args[0]
    if draw_name not in active_draws:
        update.message.reply_text("Geçerli bir çekiliş ismi girin.")
        return
    draw = active_draws[draw_name]
    if datetime.now() < draw['end_time']:
        remaining = draw['end_time'] - datetime.now()
        mins = int(remaining.total_seconds() // 60) + 1
        update.message.reply_text(f"Çekiliş henüz bitmedi. Kalan ~{mins} dakika.")
        return
    if not draw['participants']:
        update.message.reply_text("Çekilişe katılan yok. Çekiliş iptal ediliyor.")
        del active_draws[draw_name]
        return
    winner_id = random.choice(draw['participants'])
    try:
        winner_member = context.bot.get_chat_member(draw['chat_id'], winner_id)
        winner_name = winner_member.user.full_name or winner_member.user.first_name
    except Exception:
        winner_name = str(winner_id)
    past_winners.append(winner_name)
    blocked_users[winner_id] = datetime.now() + timedelta(hours=24)
    prize = draw.get('prize_message') or "Ödül belirlenmemiş."
    del active_draws[draw_name]
    update.message.reply_text(f"Çekiliş kazananı: {winner_name}\nÖdül: {prize}")

def show_past_winners(update: Update, context: CallbackContext) -> None:
    if not past_winners:
        update.message.reply_text("Henüz kazanan yok.")
        return
    update.message.reply_text("Son 10 kazanan: " + ", ".join(past_winners[-10:]))

def cancel_draw(update: Update, context: CallbackContext) -> None:
    if not context.args:
        update.message.reply_text("Kullanım: /iptal <çekiliş_ismi>")
        return
    draw_name = context.args[0]
    if draw_name in active_draws:
        del active_draws[draw_name]
        update.message.reply_text(f"\"{draw_name}\" iptal edildi.")
    else:
        update.message.reply_text("Böyle bir aktif çekiliş yok.")

def show_blocked_users(update: Update, context: CallbackContext) -> None:
    clean_expired_blocks()
    if not blocked_users:
        update.message.reply_text("Bloklu kullanıcı yok.")
        return
    lines = []
    for uid, dt in blocked_users.items():
        lines.append(f"{uid}: {'kalıcı' if dt is None else dt.isoformat()}")
    update.message.reply_text("\n".join(lines))

def parse_user_id_from_arg(update: Update, context: CallbackContext, idx=0):
    """Try to obtain user id via reply or numeric arg. Username->id generally not available."""
    if update.message.reply_to_message:
        return update.message.reply_to_message.from_user.id
    if len(context.args) <= idx:
        return None
    raw = context.args[idx]
    try:
        return int(raw)
    except ValueError:
        return None

def block_user(update: Update, context: CallbackContext) -> None:
    user_id = parse_user_id_from_arg(update, context, 0)
    if user_id is None:
        update.message.reply_text("Kullanıcı ID girin veya kullanıcının mesajına reply yapın.")
        return
    duration = context.args[1] if len(context.args) > 1 else None
    if duration:
        td = convert_to_timedelta(duration)
        if not td:
            update.message.reply_text("Geçerli süre girin. Örnek: 1h, 20m, 2d")
            return
        blocked_users[user_id] = datetime.now() + td
        update.message.reply_text(f"{user_id} {duration} süreyle bloklandı.")
    else:
        blocked_users[user_id] = None
        update.message.reply_text(f"{user_id} için kalıcı blok verildi.")

def remove_block(update: Update, context: CallbackContext) -> None:
    user_id = parse_user_id_from_arg(update, context, 0)
    if user_id is None:
        update.message.reply_text("Kullanıcı ID girin veya kullanıcının mesajına reply yapın.")
        return
    if user_id in blocked_users:
        del blocked_users[user_id]
        update.message.reply_text("Blok kaldırıldı.")
    else:
        update.message.reply_text("Kullanıcı bloklu değil.")

def remove_all_blocks(update: Update, context: CallbackContext) -> None:
    blocked_users.clear()
    update.message.reply_text("Tüm bloklar kaldırıldı.")

def convert_to_timedelta(time_str):
    if not time_str:
        return None
    mapping = {'m': 'minutes', 'h': 'hours', 'd': 'days'}
    unit = time_str[-1]
    try:
        value = int(time_str[:-1])
    except ValueError:
        return None
    if unit not in mapping:
        return None
    return timedelta(**{mapping[unit]: value})

# --- Main ---
def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable not set. Set it and restart.")
    updater = Updater(BOT_TOKEN)
    dispatcher = updater.dispatcher

    # Command handlers
    dispatcher.add_handler(CommandHandler('cekilis', start_draw))
    dispatcher.add_handler(CommandHandler('cekilisall', start_no_block_draw))
    dispatcher.add_handler(CommandHandler('katil', join_draw))
    dispatcher.add_handler(CommandHandler('odul_ekle', add_draw_message))
    dispatcher.add_handler(CommandHandler('kazanan', draw_winner))
    dispatcher.add_handler(CommandHandler('iptal', cancel_draw))
    dispatcher.add_handler(CommandHandler('gecmis', show_past_winners))
    dispatcher.add_handler(CommandHandler('bloklist', show_blocked_users))
    dispatcher.add_handler(CommandHandler('blokla', block_user))
    dispatcher.add_handler(CommandHandler('blokkaldir', remove_block))
    dispatcher.add_handler(CommandHandler('blokkaldirall', remove_all_blocks))

    # Count messages (non-command texts)
    dispatcher.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
