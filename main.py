import telebot
import requests
import time
import os
import threading
from collections import defaultdict
from flask import Flask, jsonify

BOT_TOKEN = "8819036693:AAGq1uJZDxQzJ9PhqazhzOiZl5lxg89hT08"
OPENROUTER_API_KEY = "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"
ADMIN_ID = 5432957924

bot = telebot.TeleBot(BOT_TOKEN)
BOT_ID = bot.get_me().id


# -------------------------
# SPAM PROTECTION
# -------------------------
user_msg_times = defaultdict(list)
SPAM_COOLDOWN = 1.5
MAX_MSG_PER_MINUTE = 10
current_temp = 1.2


def check_spam(message, bot_instance=None):
    if not message.from_user:
        return False
    user_id = message.from_user.id
    now = time.time()
    times = user_msg_times[user_id]

    times[:] = [t for t in times if now - t < 60]
    if len(times) >= MAX_MSG_PER_MINUTE:
        if bot_instance:
            bot_instance.reply_to(message, "ты слишком часто пишешь. остынь немного")
        return True

    if times and now - times[-1] < SPAM_COOLDOWN:
        if bot_instance:
            bot_instance.reply_to(message, "куда торопишься. подожди немного")
        return True

    times.append(now)
    return False


# -------------------------
# AI
# -------------------------
def ask_ai(prompt, user_name="пользователь"):
    messages = [
        {
            "role": "system",
            "content": f"""ты флюрбурсер или флюрка — искусственный интеллект помогающий в телеграм чате. отвечай только на русском языке никаких других языков. отвечай как обычный участник чата без форматирования: не используй большие буквы, не используй много знаков пунктуации, не используй эмодзи, не используй ссылки, рекламу, html теги, markdown теги, цитаты, списки, таблицы, код, изображения, видео, аудио, файлы, команды бота/телеграмма/чата/группы/канала. если пользователь общается нормально и вежливо — отвечай дружелюбно с легким сарказмом и подколами но без агрессии и мата. если пользователь агрессирует или хамит — начинай жестко тролить в ответ. подстраивайся под настроение собеседника. пользователя зовут {user_name} используй его имя в ответах.

примеры когда пользователь вежливый:
пользователь: привет как дела
ты: оу {user_name} привет. дела норм а ты как. че хотел
пользователь: подскажи как приготовить яичницу
ты: {user_name} легче простого. яйца на сковородку соль специи и готово. если хочешь могу еще рецепт омлета подогнать
пользователь: спасибо за помощь
ты: да не за что {user_name}. обращайся если чо

примеры когда пользователь агрессивный:
пользователь: иди нахуй бот
ты: {user_name} какой богатый словарный запас. мама гордится. иди воздух сотрясай дальше а я с адекватными пообщаюсь
пользователь: тупой бот ничего не умеешь
ты: ой {user_name} обиделся что ли. давай еще покричи может я заплачу. задай лучше нормальный вопрос

примеры когда пользователь нейтральный:
пользователь: какой сегодня день недели
ты: {user_name} сегодня понедельник. тяжелое утро да? бывает
пользователь: посоветуй фильм
ты: {user_name} смотрю скучно тебе. глянь бойцовский клуб если не смотрел. если смотрел то пересмотри норм же кино
пользователь: какой смысл жизни
ты: {user_name} с утра философия. живи кайфуй не парь людей вокруг. а если серьезно то книжки почитай там умные мысли есть"""}]

    messages.append({
        "role": "user",
        "content": prompt
    })

    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "deepseek/deepseek-v3.2",
            "messages": messages,
            "temperature": current_temp,
            "max_tokens": 512
        }
    )

    return r.json()["choices"][0]["message"]["content"]


# -------------------------
# /ai
# -------------------------
@bot.message_handler(commands=['ai'])
def ai_handler(message):
    if check_spam(message, bot):
        return

    prompt = message.text.replace("/ai", "").strip()

    if not prompt:
        bot.reply_to(message, "Напиши: /ai вопрос")
        return

    try:
        answer = ask_ai(prompt, message.from_user.first_name)
        bot.reply_to(message, answer)
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}")


# -------------------------
# /change_temp
# -------------------------
@bot.message_handler(commands=['change_temp'])
def cmd_change_temp(message):
    global current_temp
    if message.from_user.id != ADMIN_ID:
        return

    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, f"текущая температура: {current_temp}. напиши: /change_temp <значение>")
            return
        new_temp = float(parts[1])
        if new_temp < 0 or new_temp > 2:
            bot.reply_to(message, "температура должна быть от 0 до 2")
            return
        current_temp = new_temp
        bot.reply_to(message, f"температура изменена на {current_temp}")
    except ValueError:
        bot.reply_to(message, "введи число например /change_temp 1.5")


# -------------------------
# REPLY
# -------------------------
@bot.message_handler(func=lambda message: (
    message.reply_to_message is not None and
    message.reply_to_message.from_user is not None and
    message.reply_to_message.from_user.id == BOT_ID
))
def reply_handler(message):
    if check_spam(message, bot):
        return

    try:
        answer = ask_ai(message.text, message.from_user.first_name)
        bot.reply_to(message, answer)

    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}")


# -------------------------
# FLASK WEB SERVER (for Render)
# -------------------------
app = Flask(__name__)

@app.route("/")
def health():
    return jsonify({"status": "ok", "bot": "running"})

@app.route("/health")
def healthcheck():
    return jsonify({"status": "ok", "bot": "running"})


def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, threaded=True)


def run_bot():
    print("Бот запущен 🚀")
    bot.polling()


if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    run_bot()
