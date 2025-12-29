import random
import time
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# Global veriler
active_draws = {}  # Çekilişler ve katılımcılar
blocked_users = {}  # Bloklanan kullanıcılar
draw_history = {}  # Kazananlar ve kazandıkları tarih
no_block_draws = []  # Blokesiz çekilişler
draws_messages = {}  # Çekiliş ödül mesajları
past_winners = []  # Geçmiş kazananlar

# Çekiliş başlatma komutu (24 saat blokeli)
def start_draw(update: Update, context: CallbackContext) -> None:
    if len(context.args) < 2:
        update.message.reply_text("Çekiliş başlatmak için doğru formatı kullanmalısınız: /Çekilis <çekiliş_ismi> <çekiliş_süresi>")
        return

    draw_name = context.args[0]
    draw_duration = int(context.args[1])  # Çekiliş süresi dakika cinsinden

    if draw_name in active_draws:
        update.message.reply_text(f"Bu çekiliş zaten aktif! Çekiliş ismi: {draw_name}")
        return

    active_draws[draw_name] = {
        'participants': [],
        'end_time': datetime.now() + timedelta(minutes=draw_duration),
        'messages_count': 0
    }

    update.message.reply_text(f"{draw_name} çekilişi başlatıldı! {draw_duration} dakika sürecek. Katılmak için yazın!")

# Blokesiz çekiliş başlatma komutu
def start_no_block_draw(update: Update, context: CallbackContext) -> None:
    if len(context.args) < 2:
        update.message.reply_text("Blokesiz çekiliş başlatmak için doğru formatı kullanmalısınız: /Cekilisall <çekiliş_ismi> <çekiliş_süresi>")
        return

    draw_name = context.args[0]
    draw_duration = int(context.args[1])  # Çekiliş süresi dakika cinsinden

    if draw_name in no_block_draws:
        update.message.reply_text(f"Bu çekiliş zaten aktif! Çekiliş ismi: {draw_name}")
        return

    no_block_draws.append(draw_name)
    update.message.reply_text(f"{draw_name} blokesiz çekilişi başlatıldı! {draw_duration} dakika sürecek. Katılmak için yazın!")

# Çekilişe katılma komutu
def join_draw(update: Update, context: CallbackContext) -> None:
    draw_name = context.args[0] if context.args else None
    if not draw_name or draw_name not in active_draws and draw_name not in no_block_draws:
        update.message.reply_text("Lütfen geçerli bir çekiliş ismi girin!")
        return

    user_id = update.message.from_user.id
    if user_id in blocked_users:
        update.message.reply_text("Bu çekilişe katılamazsınız, çünkü daha önce kazandınız!")
        return

    # Blokesiz çekilişe katılma
    if draw_name in no_block_draws and user_id not in active_draws.get(draw_name, {}).get('participants', []):
        active_draws.setdefault(draw_name, {'participants': []})['participants'].append(user_id)
        update.message.reply_text(f"{update.message.from_user.first_name} {draw_name} blokesiz çekilişine katıldı!")
        return

    # 24 saat blokeli çekilişe katılma
    if draw_name in active_draws:
        draw = active_draws[draw_name]
        if user_id in draw['participants']:
            update.message.reply_text("Zaten bu çekilişe katıldınız!")
            return

        # Mesaj sayısı kontrolü
        draw['messages_count'] += 1
        if draw['messages_count'] < 10:
            remaining_messages = 10 - draw['messages_count']
            update.message.reply_text(f"Bu çekilişe katılmak için en az 10 mesaj atmalısınız. {remaining_messages} mesaj eksik.")
            return
        
        draw['participants'].append(user_id)
        update.message.reply_text(f"{update.message.from_user.first_name} {draw_name} çekilişine katıldı!")

# Çekiliş ödül mesajını ekleme komutu
def add_draw_message(update: Update, context: CallbackContext) -> None:
    draw_name = context.args[0] if context.args else None
    if not draw_name or draw_name not in active_draws:
        update.message.reply_text("Geçerli bir çekiliş ismi girin!")
        return

    draw_message = " ".join(context.args[1:])
    if not draw_message:
        update.message.reply_text("Lütfen ödül mesajını girin!")
        return

    draws_messages[draw_name] = draw_message
    update.message.reply_text(f"{draw_name} çekilişi için ödül mesajı belirlendi: {draw_message}")

# Ödül mesajını düzenleme komutu
def edit_draw_message(update: Update, context: CallbackContext) -> None:
    draw_name = context.args[0] if context.args else None
    if not draw_name or draw_name not in draws_messages:
        update.message.reply_text("Bu çekiliş için ödül mesajı belirlenmemiş!")
        return

    new_message = " ".join(context.args[1:])
    if not new_message:
        update.message.reply_text("Lütfen yeni ödül mesajını girin!")
        return

    draws_messages[draw_name] = new_message
    update.message.reply_text(f"{draw_name} çekilişinin ödül mesajı güncellendi: {new_message}")

# Kazananı seçme komutu
def draw_winner(update: Update, context: CallbackContext) -> None:
    draw_name = context.args[0] if context.args else None
    if not draw_name or draw_name not in active_draws:
        update.message.reply_text("Geçerli bir çekiliş ismi girin!")
        return

    draw = active_draws[draw_name]
    if datetime.now() < draw['end_time']:
        update.message.reply_text(f"{draw_name} çekilişi henüz bitmedi!")
        return

    if len(draw['participants']) < 1:
        update.message.reply_text(f"{draw_name} çekilişine katılan kimse yok!")
        return

    winner = random.choice(draw['participants'])
    winner_name = update.message.bot.get_chat_member(update.message.chat.id, winner).user.first_name
    past_winners.append(winner_name)

    # Kazananı 24 saat bloke et
    blocked_users[winner] = datetime.now() + timedelta(hours=24)

    # Çekilişi sona erdir
    del active_draws[draw_name]

    update.message.reply_text(f"{draw_name} çekilişinin kazananı: {winner_name}!\nÖdül: {draws_messages.get(draw_name, 'Ödül henüz belirlenmemiş.')}")
    
# Geçmiş kazananlar
def show_past_winners(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(f"Son 10 kazanan: {', '.join(past_winners[-10:])}")

# Çekilişi iptal etme komutu
def cancel_draw(update: Update, context: CallbackContext) -> None:
    draw_name = context.args[0] if context.args else None
    if not draw_name or draw_name not in active_draws:
        update.message.reply_text("Geçerli bir çekiliş ismi girin!")
        return

    del active_draws[draw_name]
    update.message.reply_text(f"{draw_name} çekilişi iptal edildi.")

# Blokeli kullanıcıları gösterme
def show_blocked_users(update: Update, context: CallbackContext) -> None:
    blocked_list = [f"{user_id}: {blocked_users[user_id]}" for user_id in blocked_users]
    if blocked_list:
        update.message.reply_text("\n".join(blocked_list))
    else:
        update.message.reply_text("Blokeli kullanıcı bulunmamaktadır.")

# Kullanıcı özel blokeyi gösterme
def show_user_block(update: Update, context: CallbackContext) -> None:
    username = context.args[0] if context.args else None
    if not username:
        update.message.reply_text("Lütfen geçerli bir kullanıcı adı girin!")
        return

    user_id = get_user_id_from_username(update, username)
    if user_id in blocked_users:
        update.message.reply_text(f"User @{username} blokesi: {blocked_users[user_id]}")
    else:
        update.message.reply_text(f"User @{username} blokesiz.")

# Kullanıcı adından kullanıcı ID'sini alma
def get_user_id_from_username(update: Update, username: str) -> int:
    try:
        user = update.message.chat.get_member(username)
        return user.user.id
    except:
        return None

# Bloke kaldırma
def remove_block(update: Update, context: CallbackContext) -> None:
    username = context.args[0] if context.args else None
    if not username:
        update.message.reply_text("Lütfen geçerli bir kullanıcı adı girin!")
        return

    user_id = get_user_id_from_username(update, username)
    if user_id in blocked_users:
        del blocked_users[user_id]
        update.message.reply_text(f"User @{username} için blok kaldırıldı.")
    else:
        update.message.reply_text(f"User @{username} zaten blokesiz.")

# Bloke kaldırma (tüm kullanıcılar)
def remove_all_blocks(update: Update, context: CallbackContext) -> None:
    blocked_users.clear()
    update.message.reply_text("Tüm kullanıcıların blokesi kaldırıldı.")

# Kullanıcıya bloke verme
def block_user(update: Update, context: CallbackContext) -> None:
    username = context.args[0] if context.args else None
    block_duration = context.args[1] if len(context.args) > 1 else None
    if not username or not block_duration:
        update.message.reply_text("Lütfen geçerli bir kullanıcı adı ve bloke süresi girin!")
        return

    user_id = get_user_id_from_username(update, username)
    block_time = convert_to_timedelta(block_duration)
    if not block_time:
        update.message.reply_text("Geçerli bir süre girin! Örnek: 1h, 20m")
        return

    blocked_users[user_id] = datetime.now() + block_time
    update.message.reply_text(f"User @{username} için {block_duration} kadar blok verildi.")

# Zaman formatı dönüşümü
def convert_to_timedelta(time_str):
    time_mapping = {
        'm': 'minutes',
        'h': 'hours',
        'd': 'days'
    }
    try:
        time_unit = time_str[-1]
        time_value = int(time_str[:-1])
        if time_unit in time_mapping:
            return timedelta(**{time_mapping[time_unit]: time_value})
        return None
    except ValueError:
        return None

# Botu başlatacak ana fonksiyon
def main() -> None:
    token = 'YOUR_BOT_TOKEN'  # Buraya bot tokeninizi ekleyin

    updater = Updater(token)
    dispatcher = updater.dispatcher

    # Komutlar
    dispatcher.add_handler(CommandHandler('Çekilis', start_draw))
    dispatcher.add_handler(CommandHandler('Cekilisall', start_no_block_draw))
    dispatcher.add_handler(CommandHandler('Cekilis', join_draw))
    dispatcher.add_handler(CommandHandler('Edit', edit_draw_message))
    dispatcher.add_handler(CommandHandler('Kazanan', draw_winner))
    dispatcher.add_handler(CommandHandler('Cek', draw_winner))
    dispatcher.add_handler(CommandHandler('İptal', cancel_draw))
    dispatcher.add_handler(CommandHandler('Gecmis', show_past_winners))
    dispatcher.add_handler(CommandHandler('Bloklistall', show_blocked_users))
    dispatcher.add_handler(CommandHandler('Bloklist', show_user_block))
    dispatcher.add_handler(CommandHandler('Blokkaldir', remove_block))
    dispatcher.add_handler(CommandHandler('Blokkaldirall', remove_all_blocks))
    dispatcher.add_handler(CommandHandler('Blok', block_user))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
