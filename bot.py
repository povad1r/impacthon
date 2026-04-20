import os
import sqlite3
import asyncio
import aiohttp
import numpy as np
import librosa
from datetime import datetime, timedelta, timezone
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("No BOT_TOKEN found! Please add it to your .env file.")
DB_PATH = 'instance/complaints.db'
UPLOAD_FOLDER = 'static/uploads'

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


class ReportForm(StatesGroup):
    address = State()
    time = State()
    reason = State()
    custom_reason = State()
    media = State()


reasons_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Bus"), KeyboardButton(text="Train")],
        [KeyboardButton(text="Drunk people"), KeyboardButton(text="Other")]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS complaint (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email VARCHAR(120) NOT NULL,
                address VARCHAR(200) NOT NULL,
                time VARCHAR(50) NOT NULL,
                reason VARCHAR(50) NOT NULL,
                custom_reason VARCHAR(200),
                media_file VARCHAR(255) NOT NULL,
                device_info VARCHAR(255),
                avg_frequency FLOAT,
                avg_volume_db FLOAT,
                noise_profile VARCHAR(50),
                created_at DATETIME
            )
        """)
        conn.commit()

def analyze_audio(filepath):
    try:
        y, sr = librosa.load(filepath, sr=None)

        rms = librosa.feature.rms(y=y)
        volume_db = librosa.amplitude_to_db(rms, ref=np.max)
        avg_volume_2 = float(np.mean(volume_db))
        avg_volume = -avg_volume_2
        cent = librosa.feature.spectral_centroid(y=y, sr=sr)
        avg_freq = float(np.mean(cent))

        if avg_freq < 500:
            profile = "Brown Noise (Rumble/Bass)"
        elif avg_freq < 2000:
            profile = "Pink Noise (Balanced/Wind)"
        else:
            profile = "White Noise (Hiss/Screech)"

        return round(avg_freq, 2), round(avg_volume, 2), profile
    except Exception as e:
        print(f"Could not analyze audio: {e}")
        return None, None, None


async def get_address_from_coords(lat, lon):
    url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&accept-language=en"
    headers = {"User-Agent": "NoiseComplaintBot/1.0 (yaroslavrohovets@gmail.com)"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, ssl=False) as response:
                if response.status == 200:
                    data = await response.json()
                    address_details = data.get("address", {})
                    road = address_details.get("road", "")
                    house_number = address_details.get("house_number", "")
                    city = address_details.get("city", address_details.get("town", address_details.get("village", "")))
                    parts = []
                    if house_number and road:
                        parts.append(f"{house_number} {road}")
                    elif road:
                        parts.append(road)
                    if city:
                        parts.append(city)
                    return ", ".join(parts) if parts else data.get("display_name")
    except Exception as e:
        print(f"Geocoding API error: {e}")
    return None


def check_rate_limit(tg_email):
    one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM complaint WHERE email = ? AND created_at >= ?", (tg_email, one_hour_ago))
        return cursor.fetchone() is not None


@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    tg_email = f"tg_{message.from_user.id}"
    if check_rate_limit(tg_email):
        await message.answer("🚫 You can only submit one report per hour. Please wait.")
        return
    await message.answer(
        "👋 Welcome to the Noise Complaint Bot.\n\n"
        "Please enter the **Address** where the noise is happening "
        "(or send your location via paperclip 📎):",
        parse_mode="Markdown"
    )
    await state.set_state(ReportForm.address)


@dp.message(ReportForm.address)
async def process_address(message: Message, state: FSMContext):
    if message.location:
        lat = message.location.latitude
        lon = message.location.longitude
        processing_msg = await message.answer("🔍 Converting GPS to street address...")
        address = await get_address_from_coords(lat, lon)
        if not address:
            address = f"Lat: {lat}, Lon: {lon}"
        await processing_msg.delete()
    else:
        address = message.text

    await state.update_data(address=address)
    current_time = datetime.now().strftime("%H:%M")
    time_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=f"🕒 Now ({current_time})")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await message.answer(
        f"📍 Address saved: **{address}**\n\n"
        f"When did the noise happen?",
        reply_markup=time_kb,
        parse_mode="Markdown"
    )
    await state.set_state(ReportForm.time)


@dp.message(ReportForm.time, F.text)
async def process_time(message: Message, state: FSMContext):
    text = message.text
    if text.startswith("🕒 Now"):
        text = text.replace("🕒 Now (", "").replace(")", "").strip()

    await state.update_data(time=text)
    await message.answer(
        "🕒 Time saved. What is the reason for the noise?",
        reply_markup=reasons_kb
    )
    await state.set_state(ReportForm.reason)


@dp.message(ReportForm.reason, F.text)
async def process_reason(message: Message, state: FSMContext):
    reason = message.text
    if reason not in ["Bus", "Train", "Drunk people", "Other"]:
        await message.answer("Please choose an option from the keyboard.", reply_markup=reasons_kb)
        return
    await state.update_data(reason=reason)
    if reason == "Other":
        await message.answer("Please type the specific reason:", reply_markup=ReplyKeyboardRemove())
        await state.set_state(ReportForm.custom_reason)
    else:
        await state.update_data(custom_reason=None)
        await message.answer(
            "Almost done! 📹 Please send an **audio message**, **video**, or **file** as evidence.",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="Markdown"
        )
        await state.set_state(ReportForm.media)


@dp.message(ReportForm.custom_reason, F.text)
async def process_custom_reason(message: Message, state: FSMContext):
    await state.update_data(custom_reason=message.text)
    await message.answer("Got it! 📹 Please send an **audio message**, **video**, or **file** as evidence.")
    await state.set_state(ReportForm.media)


@dp.message(ReportForm.media)
async def process_media(message: Message, state: FSMContext):
    if message.voice:
        file_id = message.voice.file_id
        ext = "ogg"
    elif message.video:
        file_id = message.video.file_id
        ext = "mp4"
    elif message.audio:
        file_id = message.audio.file_id
        ext = "mp3"
    elif message.video_note:
        file_id = message.video_note.file_id
        ext = "mp4"
    else:
        await message.answer("Please send a valid media format (Voice, Video, Audio, or Video Note).")
        return

    file_info = await bot.get_file(file_id)
    timestamp = str(datetime.now().timestamp()).replace('.', '')
    filename = f"tg_{timestamp}.{ext}"
    destination = os.path.join(UPLOAD_FOLDER, filename)
    await bot.download_file(file_info.file_path, destination)

    analyzing_msg = await message.answer("🔬 Analyzing audio...")
    avg_frequency, avg_volume_db, noise_profile = analyze_audio(destination)
    await analyzing_msg.delete()

    if noise_profile:
        masking_map = {
            "Brown Noise (Rumble/Bass)": {
                "emoji": "🟤",
                "mask": "Brown noise",
                "plants": [],
                "iot": "Bass-heavy Smart Speaker",
            },
            "Pink Noise (Balanced/Wind)": {
                "emoji": "🌸",
                "mask": "Pink noise",
                "plants": ["Nordmann fir", "Mountain pine", "Scots pine"],
                "iot": "Standard IoT Speaker",
            },
            "White Noise (Hiss/Screech)": {
                "emoji": "⚪",
                "mask": "White noise",
                "plants": ["Cherry laurel", "Common Holly"],
                "iot": "White Noise Generator",
            },
        }

        rec = masking_map[noise_profile]
        plants_text = f"\n• Plants: _{', '.join(rec['plants'])}_" if rec['plants'] else ""
        iot_text = f"\n• IoT device: `{rec['iot']}`" if rec['iot'] else ""

        analysis_text = (
            f"\n\n📊 *Audio Analysis:*\n"
            f"• Type: `{noise_profile}`\n"
            f"• Avg frequency: `{avg_frequency} Hz`\n"
            f"• Avg volume: `{avg_volume_db} dB`\n"
            f"• Recommended masking: *{rec['emoji']} {rec['mask']}*"
            f"{plants_text}"
            f"{iot_text}"
        )
    else:
        analysis_text = ""

    data = await state.get_data()
    tg_email = f"tg_{message.from_user.id}"
    current_utc_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO complaint
                (email, address, time, reason, custom_reason, media_file, device_info,
                 avg_frequency, avg_volume_db, noise_profile, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tg_email,
                data['address'],
                data['time'],
                data['reason'],
                data.get('custom_reason'),
                filename,
                "Telegram Bot",
                avg_frequency,    # новое
                avg_volume_db,    # новое
                noise_profile,    # новое
                current_utc_str
            ))
            conn.commit()

        await message.answer(
            f"✅ *Thank you!* Your report has been submitted successfully. {analysis_text}",
            parse_mode="Markdown"
        )
    except Exception as e:
        await message.answer("❌ Something went wrong while saving to the database.")
        print(f"DB Error: {e}")

    await state.clear()


async def main():
    init_db()
    print("User Report Bot is running...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())