import telebot
import random
import sqlite3
import time
from telebot import types
from datetime import datetime

# ========== КОНФИГУРАЦИЯ ==========
BOT_TOKEN = "8747603493:AAELFPMJwQNpfo8ycaQCxipULq2fAWJJQuM"
ADMIN_ID = 7921743592
CHANNEL_ID = -1003842490996
MIN_BET = 0.1
MAX_BET = 10

bot = telebot.TeleBot(BOT_TOKEN)

# ========== БАЗА ДАННЫХ ==========
conn = sqlite3.connect('casino.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS casino_balance (
        id INTEGER PRIMARY KEY,
        balance REAL DEFAULT 0
    )
''')
cursor.execute('SELECT * FROM casino_balance WHERE id = 1')
if not cursor.fetchone():
    cursor.execute('INSERT INTO casino_balance (id, balance) VALUES (1, 1000)')
conn.commit()

# ========== КОМАНДЫ ==========
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add('🪙 Орёл/Решка', '🎲 Куб (1-6)')
    markup.add('🎯 Дартс', '🏀 Баскетбол', '⚽ Футбол')
    markup.add('💰 Ставка', '📊 Статистика')
    
    bot.send_message(message.chat.id, 
        f"🎰 Добро пожаловать в Casino Bot!\n\n"
        f"💰 Минимальная ставка: ${MIN_BET}\n"
        f"💰 Максимальная ставка: ${MAX_BET}\n\n"
        f"Выберите игру:", reply_markup=markup)

# ========== ИГРЫ ==========
@bot.message_handler(func=lambda message: message.text in ['🪙 Орёл/Решка', '🎲 Куб (1-6)', '🎯 Дартс', '🏀 Баскетбол', '⚽ Футбол'])
def choose_game(message):
    game = message.text
    msg = bot.send_message(message.chat.id, f"Введите сумму ставки от ${MIN_BET} до ${MAX_BET}:")
    bot.register_next_step_handler(msg, process_bet, game)

def process_bet(message, game):
    try:
        bet = float(message.text)
        if bet < MIN_BET or bet > MAX_BET:
            bot.send_message(message.chat.id, f"❌ Ставка должна быть от ${MIN_BET} до ${MAX_BET}")
            return
        
        # Создаем счет в CryptoBot
        check_data = create_crypto_check(bet, message.from_user.id)
        if not check_data:
            bot.send_message(message.chat.id, "❌ Ошибка создания счета. Попробуйте позже.")
            return
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💳 Оплатить", url=check_data['pay_url']))
        markup.add(types.InlineKeyboardButton("✅ Проверить оплату", callback_data=f"check_{check_data['check_id']}_{game}_{bet}"))
        
        bot.send_message(message.chat.id, 
            f"💳 Счет создан!\n\n"
            f"Сумма: ${bet}\n"
            f"Игра: {game}\n\n"
            f"Нажмите 'Оплатить' и затем 'Проверить оплату'", 
            reply_markup=markup)
            
    except ValueError:
        bot.send_message(message.chat.id, "❌ Введите корректное число")

@bot.callback_query_handler(func=lambda call: call.data.startswith('check_'))
def check_payment(call):
    data = call.data.split('_')
    check_id = data[1]
    game = data[2]
    bet = float(data[3])
    user_id = call.from_user.id
    
    # Проверяем оплату (в реальном API нужно проверять через CryptoBot)
    # Для примера считаем что оплата прошла
    payment_success = True
    
    if payment_success:
        # Играем
        result, win_amount = play_game(game, bet)
        
        if win_amount > 0:
            # Создаем чек на выигрыш
            payout_check = create_payout_check(win_amount, user_id)
            
            # Отправляем в канал
            channel_msg = (
                f"🎰 НОВАЯ ИГРА\n\n"
                f"👤 Игрок: @{call.from_user.username or 'Аноним'}\n"
                f"🎮 Игра: {game}\n"
                f"💰 Ставка: ${bet}\n"
                f"🏆 Выигрыш: ${win_amount}\n"
                f"✅ Результат: {result}"
            )
            bot.send_message(CHANNEL_ID, channel_msg)
            
            # Отправляем игроку
            bot.send_message(call.message.chat.id, 
                f"🎉 ВЫ ВЫИГРАЛИ!\n\n"
                f"💰 Сумма: ${win_amount}\n"
                f"🎮 Игра: {game}\n"
                f"✅ Результат: {result}\n\n"
                f"💳 Чек на выплату отправлен в личные сообщения")
            
            # Отправляем чек игроку
            bot.send_message(user_id, f"🎫 Ваш чек на ${win_amount}:\n{payout_check}")
            
            # Обновляем баланс казино
            update_casino_balance(-win_amount)
        else:
            bot.send_message(call.message.chat.id, f"😢 Вы проиграли. {result}")
            bot.send_message(CHANNEL_ID, 
                f"😢 Проигрыш\n👤 @{call.from_user.username or 'Аноним'}\n🎮 {game}\n💰 Ставка: ${bet}\n❌ Результат: {result}")
            
            update_casino_balance(bet)
    else:
        bot.send_message(call.message.chat.id, "❌ Платеж не найден")

def play_game(game, bet):
    if game == '🪙 Орёл/Решка':
        result = random.choice(['Орёл', 'Решка'])
        win = random.random() < 0.45  # 45% шанс
        if win:
            return f"Выпал: {result}", bet * 2
        return f"Выпал: {result}", 0
    
    elif game == '🎲 Куб (1-6)':
        player = random.randint(1, 6)
        casino = random.randint(1, 6)
        if player > casino:
            return f"Вы: {player} | Казино: {casino}", bet * 2
        elif player == casino:
            return f"Вы: {player} | Казино: {casino} - Ничья", bet
        else:
            return f"Вы: {player} | Казино: {casino}", 0
    
    elif game == '🎯 Дартс':
        score = random.randint(0, 100)
        if score > 70:
            return f"Очки: {score} - Попадание!", bet * 3
        return f"Очки: {score} - Мимо", 0
    
    elif game == '🏀 Баскетбол':
        made = random.random() < 0.4  # 40% попаданий
        if made:
            return "🏀 Гол!", bet * 2.5
        return "❌ Промах", 0
    
    elif game == '⚽ Футбол':
        goals = random.randint(0, 3)
        if goals >= 2:
            return f"⚽ Голов: {goals} - Победа!", bet * 3
        return f"⚽ Голов: {goals} - Поражение", 0

# ========== КРИПТО ФУНКЦИИ ==========
def create_crypto_check(amount, user_id):
    """Создание чека на оплату через CryptoBot"""
    # Здесь должна быть интеграция с API CryptoBot
    # Для примера возвращаем тестовые данные
    return {
        'check_id': f"check_{int(time.time())}",
        'pay_url': f"https://t.me/send?start={amount}USD"
    }

def create_payout_check(amount, user_id):
    """Создание чека на выплату"""
    # Здесь должна быть интеграция с API CryptoBot для создания чека
    return f"https://t.me/CryptoBot?start={amount}USD_{user_id}"

# ========== АДМИНКА ==========
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add('💰 Баланс казино', '💳 Пополнить казну')
    markup.add('📊 Статистика', '🔙 Назад')
    
    bot.send_message(message.chat.id, "🔐 Админ панель:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == '💰 Баланс казино' and message.from_user.id == ADMIN_ID)
def show_balance(message):
    balance = get_casino_balance()
    bot.send_message(message.chat.id, f"💰 Баланс казино: ${balance}")

@bot.message_handler(func=lambda message: message.text == '💳 Пополнить казну' and message.from_user.id == ADMIN_ID)
def deposit_casino(message):
    msg = bot.send_message(message.chat.id, "Введите сумму пополнения:")
    bot.register_next_step_handler(msg, process_deposit)

def process_deposit(message):
    try:
        amount = float(message.text)
        # Создаем счет для админа
        check = create_crypto_check(amount, ADMIN_ID)
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💳 Оплатить", url=check['pay_url']))
        markup.add(types.InlineKeyboardButton("✅ Подтвердить", callback_data=f"deposit_{amount}"))
        
        bot.send_message(message.chat.id, 
            f"Счет на ${amount} создан. После оплаты нажмите подтвердить",
            reply_markup=markup)
    except:
        bot.send_message(message.chat.id, "❌ Ошибка")

@bot.callback_query_handler(func=lambda call: call.data.startswith('deposit_'))
def confirm_deposit(call):
    if call.from_user.id != ADMIN_ID:
        return
    
    amount = float(call.data.split('_')[1])
    new_balance = update_casino_balance(amount)
    bot.send_message(call.message.chat.id, f"✅ Казна пополнена на ${amount}\nНовый баланс: ${new_balance}")
    bot.send_message(CHANNEL_ID, f"💰 Казна пополнена на ${amount}")

# ========== СТАТИСТИКА ==========
@bot.message_handler(func=lambda message: message.text == '📊 Статистика')
def stats(message):
    cursor.execute('SELECT COUNT(*), SUM(bet_amount), SUM(win_amount) FROM transactions')
    result = cursor.fetchone()
    
    games_played = result[0] or 0
    total_bets = result[1] or 0
    total_wins = result[2] or 0
    
    bot.send_message(message.chat.id, 
        f"📊 Статистика:\n\n"
        f"🎮 Игр сыграно: {games_played}\n"
        f"💰 Всего ставок: ${total_bets}\n"
        f"🏆 Всего выигрышей: ${total_wins}")

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def get_casino_balance():
    cursor.execute('SELECT balance FROM casino_balance WHERE id = 1')
    return cursor.fetchone()[0]

def update_casino_balance(amount):
    current = get_casino_balance()
    new = current + amount
    cursor.execute('UPDATE casino_balance SET balance = ? WHERE id = 1', (new,))
    conn.commit()
    return new

# ========== ЗАПУСК ==========
if __name__ == '__main__':
    print("Бот запущен...")
    bot.infinity_polling()
