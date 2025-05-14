import datetime
import logging
import os
import requests
import asyncio
from aiogram import Bot
import datetime as dt
import locale
import urllib.parse
import re

# Modify the links and data below:
DEADLINES_URL = "https://m3104.nawinds.dev/DEADLINES.json"
ADD_DEADLINE_LINK = "https://m3104.nawinds.dev/deadlines-editing-instructions/"
BOT_NAME = "Дединсайдер M3104"
BOT_USERNAME = "m3104_deadliner_bot"

# Environment variables that should be available:
TOKEN: str = os.getenv("TOKEN") # type: ignore
MAIN_GROUP_ID = int(os.getenv("MAIN_GROUP_ID")) # type: ignore

logging.basicConfig(level=logging.INFO)

bot = Bot(TOKEN)

NUMBER_EMOJIS = ['0.', '1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']

def get_current_time() -> str:
    current_time = dt.datetime.now()
    current_time_hour = current_time.hour if current_time.hour >= 10 else "0" + str(current_time.hour)
    current_time_minute = current_time.minute if current_time.minute >= 10 else "0" + str(current_time.minute)
    return f"{current_time_hour}:{current_time_minute}"

def get_dt_obj_from_string(time: str) -> dt.datetime:
    time = time.replace('GMT+3', '+0300')
    locale.setlocale(locale.LC_TIME, 'en_US.UTF-8')
    return dt.datetime.strptime(time, "%d %b %Y %H:%M:%S %z")

def generate_link(event_name: str, event_time: str) -> str:
    dt_obj = get_dt_obj_from_string(event_time)
    formatted_time = dt_obj.strftime("%Y%m%d T%H%M%S%z")
    description = f"Дедлайн добавлен ботом {BOT_NAME} (https://t.me/{BOT_USERNAME})"
    link = f"https://calendar.google.com/calendar/u/0/r/eventedit?" \
           f"text={urllib.parse.quote(event_name)}&" \
           f"dates={formatted_time}/{formatted_time}&details={urllib.parse.quote(description)}&" \
           f"color=6"
    return link

def get_human_timedelta(time: str) -> str:
    dt_obj = get_dt_obj_from_string(time)
    dt_now = dt.datetime.now(dt_obj.tzinfo)  # Ensure timezones are consistent
    delta = dt_obj - dt_now

    total_seconds = int(delta.total_seconds())
    days = total_seconds // (24 * 3600)
    hours = (total_seconds % (24 * 3600)) // 3600
    minutes = (total_seconds % 3600) // 60

    if days >= 5:
        return f"{days} дней"
    elif days >= 2:
        return f"{days} дня"
    elif days == 1:
        return f"1 день {hours}ч {minutes}м"
    else:
        return f"{hours}ч {minutes}м"

def get_human_time(time: str) -> str:
    dt_obj = get_dt_obj_from_string(time)
    locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')
    formatted_date = dt_obj.strftime("%a, %d %B в %H:%M")
    return formatted_date

def timestamp_func(a: dict) -> float:
    time = a["time"].replace('GMT+3', '+0300')
    locale.setlocale(locale.LC_TIME, 'en_US.UTF-8')
    a_timestamp = dt.datetime.strptime(time, "%d %b %Y %H:%M:%S %z").timestamp()
    return a_timestamp  # 29 Oct 2024 23:59:59 GMT+3

def relevant_filter_func(d: dict) -> bool:
    dt_obj = get_dt_obj_from_string(d["time"])
    return not dt_obj < dt.datetime.now(dt_obj.tzinfo)

def deadline_type_filter_func(d: dict, dtype: str = '') -> bool:
    if not dtype:
        return not re.match(r'^\[.*\]', d['name'])

    return f"[{dtype.lower()}]" in d["name"].lower()

def get_message_text() -> str:
    try:
        response = requests.get(DEADLINES_URL).json()
    except Exception as e:
        print(f"{datetime.datetime.now()} Failed to fetch deadlines: {e}")
        return ""
    all_deadlines = response["deadlines"]

    types = [
        ('', ''), # deadlines
        ('🧑‍💻 Тесты', 'тест'),
        ('🎓 Лекции', 'лекция'),
        ('🛡 Защиты', 'защита')
    ]

    assignments = [(sorted(filter(lambda t: deadline_type_filter_func(t, x[1]) and relevant_filter_func(t), all_deadlines),
                           key=lambda z: timestamp_func(z)), x[0], x[1]) for x in types]

    text = f"🔥️️ <b>Дедлайны</b> (<i>Обновлено в {get_current_time()} 🔄</i>):\n\n"

    if len(assignments[0]) == 0:
        text += "Дедлайнов нет)\n\n"

    def add_items(items: list, category_name: str = '', replace_name: str = ''):
        if len(items) == 0:
            return

        nonlocal text
        REPLACE_PATTERN = re.compile(rf'^\[{replace_name}\]', flags=re.IGNORECASE)

        if category_name:
            text += f"\n<b>{category_name}</b>:\n\n"

        for i, item in enumerate(items):
            no = i + 1
            if no <= 10:
                no = NUMBER_EMOJIS[no] + " "
            else:
                no = str(no) + ". "

            text += no + "<b>"

            name = re.sub(REPLACE_PATTERN, '', item['name'])
            url = item.get('url')

            if url:
                text += f"<a href='{url}'>{name}</a>"
            else:
                text += name

            text += "</b> — "
            text += get_human_timedelta(item["time"])
            text += f"\n(<a href='{generate_link(name, item['time'])}'>"
            text += get_human_time(item["time"]) + "</a>)\n\n"

    for assignment_type in assignments:
        add_items(*assignment_type)

    text += f"\n🆕 <a href='{ADD_DEADLINE_LINK}'>" \
            f"Добавить дедлайн</a>"
    return text

async def send_deadlines(chat_id: int) -> None:
    text = get_message_text()
    if text == "Дедлайнов нет)\n\n":
        return

    msg = await bot.send_message(chat_id, text, parse_mode="HTML", disable_web_page_preview=True)
    started_updating = dt.datetime.now()
    print(datetime.datetime.now(), "Message sent. Msg id:", msg.message_id)

    while dt.datetime.now() - started_updating < dt.timedelta(days=1):
        await asyncio.sleep(60)
        try:
            new_text = get_message_text()
            if text != new_text and new_text != "":
                await msg.edit_text(new_text, parse_mode="HTML", disable_web_page_preview=True)
                text = new_text
                print(datetime.datetime.now(), "Message updated. Msg id:", msg.message_id)
            else:
                print(datetime.datetime.now(), "Message update skipped. Msg id:", msg.message_id)

        except Exception as e:
            logging.warning(datetime.datetime.now(),f"{datetime.datetime.now()} Error updating message: {e}")
            continue
    await msg.delete()


async def main():
    await send_deadlines(MAIN_GROUP_ID)
    await bot.session.close()


if __name__ == '__main__':
    asyncio.run(main())
