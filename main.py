import telebot
from telebot import types
import random
import time
import threading
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

TOKEN = os.environ['BOT_TOKEN']

bot = telebot.TeleBot(TOKEN)

active_raffle = {
    'message_id': None,
    'chat_id': None,
    'participants': set(),
    'winner_count': 1,
    'prize': 'Arrow Çekilişi',
    'block_winners': True
}

blocked_users = {}
raffle_history = []
stats = {
    'total_participants': set(),
    'total_raffles': 0,
    'total_winners': 0
}

def cleanup_blocked():
    while True:
        time.sleep(60)
        current_time = time.time()
        to_remove = [uid for uid, end_time in blocked_users.items() if current_time > end_time]
        for uid in to_remove:
            del blocked_users[uid]

threading.Thread(target=cleanup_blocked, daemon=True).start()

def is_admin(chat_id, user_id):
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ['administrator', 'creator']
    except:
        return False

def get_user_mention(user):
    if user.username:
        return f"@{user.username}"
    else:
        return f"[{user.first_name}](tg://user?id={user.id})"

# YENİ: Fotoğraflı çekiliş
@bot.message_handler(content_types=['photo'])
def handle_photo_raffle(message):
    if not is_admin(message.chat.id, message.from_user.id):
        return

    if active_raffle['message_id'] is not None:
        bot.reply_to(message, "⚠️ Zaten aktif çekiliş var! Önce /iptal veya /cek kullan.")
        return

    caption = message.caption or ""
    if not caption:
        bot.reply_to(message, "❌ Fotoğrafın altına /cekilis veya /cekilisall + ödül metni yazmalısın.")
        return

    if caption.startswith('/cekilis '):
        block_winners = True
        prize_text = caption[len('/cekilis '):].strip()
    elif caption.startswith('/cekilisall '):
        block_winners = False
        prize_text = caption[len('/cekilisall '):].strip()
    else:
        bot.reply_to(message, "❌ Caption /cekilis veya /cekilisall ile başlamalı.")
        return

    prize = prize_text if prize_text else "Arrow Çekilişi 🎉"

    active_raffle['prize'] = prize
    active_raffle['winner_count'] = 1
    active_raffle['participants'] = set()
    active_raffle['chat_id'] = message.chat.id
    active_raffle['block_winners'] = block_winners

    block_text = "" if block_winners else "\n⚠️ Bu çekilişte kazananlara 24 saat blok uygulanmayacak!"

    markup = types.InlineKeyboardMarkup()
    button = types.InlineKeyboardButton("🎉 Katıl", callback_data="join_raffle")
    markup.add(button)

    photo = message.photo[-1].file_id
    sent = bot.send_photo(
        message.chat.id,
        photo,
        caption=f"🎯 **ARROW ÇEKİLİŞ BAŞLADI!**{block_text}\n\n"
                f"🎁 **Ödül:** {prize}\n\n"
                "Katılmak için butona bas!\n\n"
                f"👥 Katılan: 0 kişi\n"
                f"🏆 Kazanan sayısı: 1 kişi",
        reply_markup=markup,
        parse_mode='Markdown'
    )

    active_raffle['message_id'] = sent.message_id

# Metinle çekiliş (eski komutlar)
@bot.message_handler(commands=['cekilis'])
def start_normal(message):
    start_text_raffle(message, block_winners=True)

@bot.message_handler(commands=['cekilisall'])
def start_no_block(message):
    start_text_raffle(message, block_winners=False)

def start_text_raffle(message, block_winners):
    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "❌ Sadece yöneticiler çekiliş başlatabilir!")
        return

    if active_raffle['message_id'] is not None:
        bot.reply_to(message, "⚠️ Zaten aktif çekiliş var! /iptal veya /cek kullan.")
        return

    text = ' '.join(message.text.split()[1:]).strip()
    prize = text if text else "Arrow Çekilişi 🎉"

    active_raffle['prize'] = prize
    active_raffle['winner_count'] = 1
    active_raffle['participants'] = set()
    active_raffle['chat_id'] = message.chat.id
    active_raffle['block_winners'] = block_winners

    block_text = "" if block_winners else "\n⚠️ Bu çekilişte kazananlara 24 saat blok uygulanmayacak!"

    markup = types.InlineKeyboardMarkup()
    button = types.InlineKeyboardButton("🎉 Katıl", callback_data="join_raffle")
    markup.add(button)

    sent = bot.send_message(
        message.chat.id,
        f"🎯 **ARROW ÇEKİLİŞ BAŞLADI!**{block_text}\n\n"
        f"🎁 **Ödül:** {prize}\n\n"
        "Katılmak için butona bas!\n\n"
        f"👥 Katılan: 0 kişi\n"
        f"🏆 Kazanan sayısı: 1 kişi",
        reply_markup=markup,
        parse_mode='Markdown'
    )

    active_raffle['message_id'] = sent.message_id

# Diğer komutlar (kazanan, duzenle, katilanlar, iptal, blokekaldir, bloklistesi, gecmis, istatistik, cek, join_raffle, update_raffle_message, finalize_raffle_end aynı kalıyor, önceki tam koddan al)

print("Arrow Çekiliş Botu başlatılıyor... 🎯")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))

    def run_polling():
        while True:
            try:
                bot.infinity_polling(none_stop=True, interval=0, timeout=20)
            except Exception as e:
                print(f"Polling hatası: {e}")
                time.sleep(5)

    threading.Thread(target=run_polling, daemon=True).start()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Arrow Cekilis Botu calisiyor!")

    HTTPServer(('', port), Handler).serve_forever()
