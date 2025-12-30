import telebot
from telebot import types
import random
import time
import threading
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

TOKEN = os.environ['BOT_TOKEN']

bot = telebot.TeleBot(TOKEN)

# Aktif çekiliş - güvenli erişim için .get() kullanacağız
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

# FOTOĞRAFLI ÇEKİLİŞ
@bot.message_handler(content_types=['photo'])
def handle_photo_raffle(message):
    if not is_admin(message.chat.id, message.from_user.id):
        return

    if active_raffle.get('message_id') is not None:
        bot.reply_to(message, "⚠️ Zaten aktif çekiliş var! Önce /iptal veya /cek kullan.")
        return

    caption = message.caption or ""
    if not caption:
        bot.reply_to(message, "❌ Fotoğrafın altına /cekilis veya /cekilisall + ödül metni yazmalısın.")
        return

    if caption.startswith('/cekilis '):
        block_winners = True   # Normal çekiliş → blok koyacak
        prize_text = caption[len('/cekilis '):].strip()
    elif caption.startswith('/cekilisall '):
        block_winners = False  # All → blok koymayacak
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

# METİNLE ÇEKİLİŞ
# METİNLE ÇEKİLİŞ
@bot.message_handler(commands=['cekilis', 'cekilisall'])
def handle_text_raffle(message):
    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "❌ Sadece yöneticiler çekiliş başlatabilir!")
        return

    if active_raffle.get('message_id') is not None:
        bot.reply_to(message, "⚠️ Zaten aktif çekiliş var! /iptal veya /cek kullan.")
        return

    # Blok mantığı: cekilisall varsa blok koyma, yoksa koy
    block_winners = not 'cekilisall' in message.text.lower()

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

# KAZANAN AYARLA
@bot.message_handler(commands=['kazanan'])
def set_winner_count(message):
    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "❌ Sadece yöneticiler ayar yapabilir!")
        return

    if active_raffle.get('message_id') is None:
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

# DÜZENLE
@bot.message_handler(commands=['duzenle'])
def edit_prize(message):
    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "❌ Sadece yöneticiler düzenleyebilir!")
        return

    if active_raffle.get('message_id') is None:
        bot.reply_to(message, "⚠️ Aktif çekiliş yok!")
        return

    new_prize = ' '.join(message.text.split()[1:]).strip()
    if not new_prize:
        bot.reply_to(message, "❌ Yeni ödül metnini yazın.")
        return

    active_raffle['prize'] = new_prize
    update_raffle_message()
    bot.reply_to(message, f"✅ Ödül değiştirildi: {new_prize}")

# KATILANLAR
@bot.message_handler(commands=['katilanlar'])
def list_participants(message):
    if active_raffle.get('message_id') is None:
        bot.reply_to(message, "⚠️ Aktif çekiliş yok!")
        return

    participants = list(active_raffle.get('participants', set()))
    if not participants:
        bot.reply_to(message, "😔 Henüz kimse katılmadı.")
        return

    text = f"👥 **Katılanlar ({len(participants)} kişi)**:\n\n"
    for i, user_id in enumerate(participants, 1):
        try:
            member = bot.get_chat_member(active_raffle.get('chat_id'), user_id)
            user = member.user
            mention = get_user_mention(user)
        except:
            mention = f"Kullanıcı {user_id}"
        text += f"{i}. {mention}\n"

    bot.reply_to(message, text, parse_mode='Markdown', disable_web_page_preview=True)

# İPTAL
@bot.message_handler(commands=['iptal'])
def cancel_raffle(message):
    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "❌ Sadece yöneticiler iptal edebilir!")
        return

    if active_raffle.get('message_id') is None:
        bot.reply_to(message, "⚠️ İptal edilecek çekiliş yok.")
        return

    try:
        bot.edit_message_text(
            chat_id=active_raffle.get('chat_id'),
            message_id=active_raffle.get('message_id'),
            text="❌ **Çekiliş iptal edildi!**",
            parse_mode='Markdown'
        )
    except:
        pass

    active_raffle.clear()
    active_raffle['prize'] = 'Arrow Çekilişi'
    active_raffle['winner_count'] = 1
    active_raffle['block_winners'] = True

    bot.reply_to(message, "✅ Çekiliş iptal edildi! Yeni çekiliş başlatabilirsin.")

# BLOK KALDIR
@bot.message_handler(commands=['blokekaldir'])
def unblock_user(message):
    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "❌ Sadece yöneticiler blok kaldırabilir!")
        return

    text = message.text[len('/blokekaldir'):].strip().lower()

    if text == 'all':
        blocked_users.clear()
        bot.reply_to(message, "✅ Tüm blokeler kaldırıldı!")
        return

    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        if user_id in blocked_users:
            del blocked_users[user_id]
            bot.reply_to(message, f"✅ {message.reply_to_message.from_user.first_name} blokesi kaldırıldı!")
        else:
            bot.reply_to(message, "❌ Bu kullanıcı bloklu değil.")
        return

    bot.reply_to(message, "❌ 'all' yazın veya bir kullanıcıya cevap vererek blok kaldırın.")

# BLOK LİSTESİ
@bot.message_handler(commands=['bloklistesi'])
def block_list(message):
    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "❌ Sadece yöneticiler blok listesini görebilir!")
        return

    if not blocked_users:
        bot.reply_to(message, "✅ Şu an kimse bloklu değil.")
        return

    current_time = time.time()
    text = "⛔ **Bloklu Kullanıcılar**\n\n"

    for user_id, end_time in blocked_users.items():
        remaining = int(end_time - current_time)
        if remaining <= 0:
            continue

        hours = remaining // 3600
        minutes = (remaining % 3600) // 60

        try:
            member = bot.get_chat_member(message.chat.id, user_id)
            user = member.user
            mention = get_user_mention(user)
        except:
            mention = f"Kullanıcı {user_id} (grupta değil)"

        text += f"• {mention} — Kalan: {hours}h {minutes}dk\n"

    bot.reply_to(message, text, parse_mode='Markdown', disable_web_page_preview=True)

# GEÇMİŞ
@bot.message_handler(commands=['gecmis'])
def show_history(message):
    if not raffle_history:
        bot.reply_to(message, "📜 Henüz biten çekiliş yok.")
        return

    text = "📜 **SON 10 ÇEKİLİŞ GEÇMİŞİ**\n\n"
    for idx, raffle in enumerate(raffle_history[:10], 1):
        date_str = time.strftime('%d.%m.%Y %H:%M', time.localtime(raffle['date']))
        text += f"**{idx}.** {date_str}\n"
        text += f"🎁 Ödül: {raffle['prize']}\n"
        text += f"🏆 Kazanan: {raffle['winner_count']} kişi\n"
        text += "**Kazananlar:**\n"
        for i, winner_id in enumerate(raffle['winners'], 1):
            try:
                member = bot.get_chat_member(message.chat.id, winner_id)
                user = member.user
                mention = get_user_mention(user)
            except:
                mention = f"Kullanıcı {winner_id} (grupta değil)"
            text += f"{i}. {mention}\n"
        text += "\n"

    bot.reply_to(message, text, parse_mode='Markdown', disable_web_page_preview=True)

# İSTATİSTİK
@bot.message_handler(commands=['istatistik'])
def show_stats(message):
    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "❌ Sadece yöneticiler istatistikleri görebilir!")
        return

    total_unique = len(stats['total_participants'])
    total_raffles = stats['total_raffles']
    total_winners = stats['total_winners']
    current_blocked = len(blocked_users)

    avg_participation = 0
    if total_raffles > 0:
        total_participation_all = sum(len(r['participants']) for r in raffle_history) if raffle_history else 0
        avg_participation = round(total_participation_all / total_raffles, 1)

    text = (
        "📊 **ARROW ÇEKİLİŞ İSTATİSTİKLERİ**\n\n"
        f"👥 Toplam benzersiz katılımcı: {total_unique} kişi\n"
        f"🏆 Yapılan çekiliş sayısı: {total_raffles}\n"
        f"🎉 Toplam kazanan kişi: {total_winners}\n"
        f"⛔ Şu an bloklu kişi: {current_blocked}\n"
        f"📈 Ortalama katılım: {avg_participation} kişi"
    )

    bot.reply_to(message, text, parse_mode='Markdown')

# KATIL BUTONU
@bot.callback_query_handler(func=lambda call: call.data == "join_raffle")
def join_raffle(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if active_raffle.get('chat_id') != chat_id or active_raffle.get('message_id') != call.message.message_id:
        bot.answer_callback_query(call.id, "Bu çekiliş bitmiş.", show_alert=True)
        return

    if user_id in blocked_users and active_raffle.get('block_winners'):
        remaining = int(blocked_users[user_id] - time.time())
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        bot.answer_callback_query(call.id, f"⛔ 24 saat bloklusun! Kalan: {hours}h {minutes}dk", show_alert=True)
        return

    if user_id in active_raffle.get('participants', set()):
        bot.answer_callback_query(call.id, "Zaten katıldın! 🎯")
        return

    active_raffle['participants'].add(user_id)
    stats['total_participants'].add(user_id)
    bot.answer_callback_query(call.id, "Başarıyla katıldın! 🎉")
    update_raffle_message()

def update_raffle_message():
    if active_raffle.get('message_id') is None:
        return

    participant_count = len(active_raffle.get('participants', set()))
    markup = types.InlineKeyboardMarkup()
    button = types.InlineKeyboardButton("🎉 Katıl", callback_data="join_raffle")
    markup.add(button)

    block_text = "" if active_raffle.get('block_winners') else "\n⚠️ Bu çekilişte blok uygulanmıyor!"

    text = (
        f"🎯 **ARROW ÇEKİLİŞ DEVAM EDİYOR!**{block_text}\n\n"
        f"🎁 **Ödül:** {active_raffle.get('prize', 'Arrow Çekilişi')}\n\n"
        f"👥 Katılan: {participant_count} kişi\n"
        f"🏆 Kazanan sayısı: {active_raffle.get('winner_count', 1)} kişi"
    )

    try:
        bot.edit_message_text(
            chat_id=active_raffle.get('chat_id'),
            message_id=active_raffle.get('message_id'),
            text=text,
            reply_markup=markup,
            parse_mode='Markdown'
        )
    except:
        pass

# ÇEK
@bot.message_handler(commands=['cek'])
def end_raffle(message):
    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "❌ Sadece yöneticiler bitirebilir!")
        return

    if active_raffle.get('message_id') is None:
        bot.reply_to(message, "⚠️ Aktif çekiliş yok!")
        return

    participants = list(active_raffle.get('participants', set()))

    if len(participants) == 0:
        bot.reply_to(message, "😢 Kimse katılmadı, çekiliş otomatik sonlandırıldı.")
        active_raffle.clear()
        active_raffle['prize'] = 'Arrow Çekilişi'
        active_raffle['winner_count'] = 1
        active_raffle['block_winners'] = True
        return

    if len(participants) < active_raffle.get('winner_count', 1):
        bot.reply_to(message, f"😔 Yeterli katılım yok ({len(participants)} / {active_raffle.get('winner_count', 1)}), çekiliş sonlandırıldı.")
        active_raffle.clear()
        active_raffle['prize'] = 'Arrow Çekilişi'
        active_raffle['winner_count'] = 1
        active_raffle['block_winners'] = True
        return

    winners = random.sample(participants, active_raffle.get('winner_count', 1))

    winner_text = ""
    for i, winner_id in enumerate(winners, 1):
        try:
            member = bot.get_chat_member(active_raffle.get('chat_id'), winner_id)
            user = member.user
            mention = get_user_mention(user)
        except:
            mention = f"Kullanıcı {winner_id}"
        winner_text += f"{i}. 🎉 {mention}\n"

        if active_raffle.get('block_winners'):
            blocked_users[winner_id] = time.time() + 24 * 3600

    block_warning = "\n\nKazananlar 24 saat yeni çekilişe katılamaz ⏳" if active_raffle.get('block_winners') else "\n\nBu çekilişte 24 saat blok uygulanmadı ⚠️"

    result_text = (
        f"🏆 **ARROW ÇEKİLİŞ SONUÇLARI!**\n\n"
        f"🎁 **Ödül:** {active_raffle.get('prize', 'Arrow Çekilişi')}\n\n"
        f"**Kazananlar ({len(winners)} kişi):**\n\n"
        f"{winner_text}\n"
        f"Tebrikler! 🎊{block_warning}"
    )

    bot.send_message(active_raffle.get('chat_id'), result_text, parse_mode='Markdown', disable_web_page_preview=True)

    raffle_history.insert(0, {
        'prize': active_raffle.get('prize', 'Arrow Çekilişi'),
        'winners': winners,
        'winner_count': active_raffle.get('winner_count', 1),
        'date': time.time(),
        'block_applied': active_raffle.get('block_winners')
    })
    if len(raffle_history) > 10:
        raffle_history.pop()

    stats['total_raffles'] += 1
    stats['total_winners'] += len(winners)

    active_raffle.clear()
    active_raffle['prize'] = 'Arrow Çekilişi'
    active_raffle['winner_count'] = 1
    active_raffle['block_winners'] = True

print("Arrow Çekiliş Botu başlatılıyor... 🎯")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))

    def run_polling():
        while True:
            try:
                bot.polling(none_stop=True, interval=0, timeout=20)
            except Exception as e:
                print(f"Polling hatası: {e}. 5 saniye sonra yeniden başlıyor...")
                time.sleep(5)

    threading.Thread(target=run_polling, daemon=True).start()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Arrow Cekilis Botu calisiyor!")

    HTTPServer(('', port), Handler).serve_forever()
