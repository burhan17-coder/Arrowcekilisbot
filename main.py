import telebot
from telebot import types
import random
import time
import threading
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

TOKEN = os.environ['BOT_TOKEN']

bot = telebot.TeleBot(TOKEN)

# Aktif çekiliş - her zaman temiz başlangıç
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

def reset_active_raffle():
    global active_raffle
    active_raffle = {
        'message_id': None,
        'chat_id': None,
        'participants': set(),
        'winner_count': 1,
        'prize': 'Arrow Çekilişi',
        'block_winners': True
    }

@bot.message_handler(commands=['cekilis'])
def start_normal(message):
    start_raffle(message, block_winners=True)

@bot.message_handler(commands=['cekilisall'])
def start_no_block(message):
    start_raffle(message, block_winners=False)

def start_raffle(message, block_winners):
    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "❌ Sadece yöneticiler çekiliş başlatabilir!")
        return

    if active_raffle['message_id'] is not None:
        bot.reply_to(message, "⚠️ Zaten aktif çekiliş var! Önce /iptal veya /cek kullan.")
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

@bot.message_handler(commands=['kazanan'])
def set_winner_count(message):
    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "❌ Sadece yöneticiler ayar yapabilir!")
        return

    if active_raffle['message_id'] is None:
        bot.reply_to(message, "⚠️ Aktif çekiliş yok!")
        return

    try:
        count = int(message.text.split()[1])
        if not 1 <= count <= 100:
            bot.reply_to(message, "❌ Kazanan sayısı 1-100 arası olmalı!")
            return
        active_raffle['winner_count'] = count
        update_raffle_message()
        bot.reply_to(message, f"✅ Kazanan sayısı {count} olarak ayarlandı!")
    except:
        bot.reply_to(message, "❌ Kullanım: /kazanan 50")

@bot.message_handler(commands=['iptal'])
def cancel_raffle(message):
    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "❌ Sadece yöneticiler iptal edebilir!")
        return

    if active_raffle['message_id'] is None:
        bot.reply_to(message, "⚠️ İptal edilecek çekiliş yok.")
        return

    try:
        bot.edit_message_text(
            chat_id=active_raffle['chat_id'],
            message_id=active_raffle['message_id'],
            text="❌ **Çekiliş iptal edildi!**",
            parse_mode='Markdown'
        )
    except:
        pass

    reset_active_raffle()
    bot.reply_to(message, "✅ Çekiliş iptal edildi! Yeni çekiliş başlatabilirsin.")

@bot.message_handler(commands=['cek'])
def end_raffle(message):
    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "❌ Sadece yöneticiler bitirebilir!")
        return

    if active_raffle['message_id'] is None:
        bot.reply_to(message, "⚠️ Aktif çekiliş yok!")
        return

    participants = list(active_raffle['participants'])

    if len(participants) == 0:
        bot.reply_to(message, "😢 Kimse katılmadı, çekiliş otomatik sonlandırıldı.")
        reset_active_raffle()
        return

    if len(participants) < active_raffle['winner_count']:
        bot.reply_to(message, f"😔 Yeterli katılım yok, çekiliş sonlandırıldı.")
        reset_active_raffle()
        return

    winners = random.sample(participants, active_raffle['winner_count'])

    winner_text = ""
    for i, winner_id in enumerate(winners, 1):
        try:
            member = bot.get_chat_member(active_raffle['chat_id'], winner_id)
            user = member.user
            mention = get_user_mention(user)
        except:
            mention = f"Kullanıcı {winner_id}"
        winner_text += f"{i}. 🎉 {mention}\n"

        if active_raffle['block_winners']:
            blocked_users[winner_id] = time.time() + 24 * 3600

    block_warning = "\n\nKazananlar 24 saat yeni çekilişe katılamaz ⏳" if active_raffle['block_winners'] else "\n\nBu çekilişte 24 saat blok uygulanmadı ⚠️"

    result_text = (
        f"🏆 **ARROW ÇEKİLİŞ SONUÇLARI!**\n\n"
        f"🎁 **Ödül:** {active_raffle['prize']}\n\n"
        f"**Kazananlar ({len(winners)} kişi):**\n\n"
        f"{winner_text}\n"
        f"Tebrikler! 🎊{block_warning}"
    )

    bot.send_message(active_raffle['chat_id'], result_text, parse_mode='Markdown')

    raffle_history.insert(0, {
        'prize': active_raffle['prize'],
        'winners': winners,
        'winner_count': active_raffle['winner_count'],
        'date': time.time(),
        'block_applied': active_raffle['block_winners']
    })
    if len(raffle_history) > 10:
        raffle_history.pop()

    reset_active_raffle()

def update_raffle_message():
    if active_raffle['message_id'] is None:
        return

    participant_count = len(active_raffle['participants'])
    markup = types.InlineKeyboardMarkup()
    button = types.InlineKeyboardButton("🎉 Katıl", callback_data="join_raffle")
    markup.add(button)

    block_text = "" if active_raffle['block_winners'] else "\n⚠️ Bu çekilişte blok uygulanmıyor!"

    text = (
        f"🎯 **ARROW ÇEKİLİŞ DEVAM EDİYOR!**{block_text}\n\n"
        f"🎁 **Ödül:** {active_raffle['prize']}\n\n"
        f"👥 Katılan: {participant_count} kişi\n"
        f"🏆 Kazanan sayısı: {active_raffle['winner_count']} kişi"
    )

    try:
        bot.edit_message_text(
            chat_id=active_raffle['chat_id'],
            message_id=active_raffle['message_id'],
            text=text,
            reply_markup=markup,
            parse_mode='Markdown'
        )
    except:
        pass

@bot.callback_query_handler(func=lambda call: call.data == "join_raffle")
def join_raffle(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if active_raffle['chat_id'] != chat_id or active_raffle['message_id'] != call.message.message_id:
        bot.answer_callback_query(call.id, "Bu çekiliş bitmiş.", show_alert=True)
        return

    if user_id in blocked_users and active_raffle['block_winners']:
        remaining = int(blocked_users[user_id] - time.time())
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        bot.answer_callback_query(call.id, f"⛔ 24 saat bloklusun! Kalan: {hours}h {minutes}dk", show_alert=True)
        return

    if user_id in active_raffle['participants']:
        bot.answer_callback_query(call.id, "Zaten katıldın! 🎯")
        return

    active_raffle['participants'].add(user_id)
    bot.answer_callback_query(call.id, "Başarıyla katıldın! 🎉")
    update_raffle_message()

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
            self.wfile.write(b"Bot calisiyor!")

    HTTPServer(('', port), Handler).serve_forever()
