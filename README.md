# Noise Complaint Bot & Admin Dashboard

This project is a comprehensive system for reporting and analyzing urban noise complaints. It consists of a **Telegram Bot** for users to easily submit reports and a **Flask Web Dashboard** for administrators to analyze the data, view interactive maps, and get automated audio analysis.
<img width="1512" height="873" alt="image" src="https://github.com/user-attachments/assets/85b3802b-5e1b-433c-a806-e041f48e34bf" />

## Features

* **Telegram Bot (`bot.py`)**: 
  * Easy step-by-step reporting process (Address, Time, Reason, Media evidence).
  * Reverse geocoding: automatically converts GPS coordinates into readable street addresses.
  * Smart Audio Analysis: automatically analyzes uploaded audio/video files to determine average frequency (Hz), volume (dB), and classifies the noise profile (Brown, Pink, or White noise).
  * Recommends masking sounds and even specific indoor plants based on the noise profile.
* **Admin Web Dashboard (`app.py`)**:
  * Built with Flask and SQLAlchemy.
  * Interactive Map (Leaflet.js) highlighting high-frequency complaint locations.
  * Statistical breakdown of peak noise hours and common reasons.
  * Built-in audio player and detailed noise analysis data for every report.
  * Filtering system to track specific users or problem addresses.

## Technologies Used

* **Backend:** Python 3.9+, Aiogram 3.x, Flask, SQLite + SQLAlchemy
* **Audio Analysis:** Librosa, NumPy
* **Frontend:** HTML, Bootstrap 5, Leaflet.js
* **APIs:** OpenStreetMap Nominatim (Geocoding)

## Installation & Setup

### 1. Clone the repository
```bash
git clone [https://github.com/povad1r/impacthon.git](https://github.com/povad1r/impacthon.git)
cd impacthon
```

### 2. Install system dependencies (FFmpeg)
To process audio files, your system needs FFmpeg installed:

```
Mac: brew install ffmpeg

Linux (Ubuntu): sudo apt update && sudo apt install ffmpeg

Windows: Download from gyan.dev and add to PATH.
```

### 3. Set up Python environment
```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
(Note: For Windows use venv\Scripts\activate)
```

### 4. Configuration (.env)
Create a .env file in the root directory and add your secure keys. Do not upload this file to GitHub!

```
BOT_TOKEN=your_telegram_bot_token_here
FLASK_SECRET_KEY=your_random_flask_secret_key
```

### Running the Project
You need to run the bot and the web dashboard simultaneously (in two separate terminal windows).

Start the Telegram Bot:
```
python bot.py
```
Start the Admin Dashboard:
```
python app.py
```
Open your browser and navigate to http://127.0.0.1:5000/admin to access the dashboard.

```
Project Structure
├── bot.py                  # Telegram bot main script
├── app.py                  # Flask web dashboard main script
├── instance/               # SQLite database directory (ignored in git)
├── static/
│   └── uploads/            # User-uploaded media files (ignored in git)
├── templates/              # HTML templates for the web dashboard
│   ├── index.html
│   ├── admin.html
│   └── admin_filtered.html
├── .env                    # Environment variables (ignored in git)
├── .gitignore              # Git ignore rules
└── README.md               # Project documentation
```
