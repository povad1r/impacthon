import os
import random
import librosa
import numpy as np
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import requests
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback_dev_key")

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///complaints.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    time = db.Column(db.String(50), nullable=False)
    reason = db.Column(db.String(50), nullable=False)
    custom_reason = db.Column(db.String(200), nullable=True)
    media_file = db.Column(db.String(255), nullable=False)
    device_info = db.Column(db.String(255), nullable=True)

    avg_frequency = db.Column(db.Float, nullable=True)
    avg_volume_db = db.Column(db.Float, nullable=True)
    noise_profile = db.Column(db.String(50), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


with app.app_context():
    db.create_all()


@app.template_filter('to_local')
def to_local(dt):
    if dt is None:
        return ''
    return (dt + timedelta(hours=2)).strftime('%Y-%m-%d %H:%M')

@app.template_filter('noise_rec')
def noise_rec(noise_profile):
    return get_noise_recommendation(noise_profile)

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

def get_noise_recommendation(noise_profile):
    recommendations = {
        "Brown Noise (Rumble/Bass)": {
            "mask_with": "Brown noise",
            "plants": [],
            "iot": "Bass-heavy Smart Speaker",
            "emoji": "🟤",
        },
        "Pink Noise (Balanced/Wind)": {
            "mask_with": "Pink noise",
            "plants": ["Nordmann fir", "Mountain pine", "Scots pine"],
            "iot": "Standard IoT Speaker",
            "emoji": "🌸",
        },
        "White Noise (Hiss/Screech)": {
            "mask_with": "White noise",
            "plants": ["Cherry laurel", "Common Holly"],
            "iot": "White Noise Generator",
            "emoji": "⚪",
        },
    }
    return recommendations.get(noise_profile)


def geocode_address(address):
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": address, "format": "json", "limit": 1}
        headers = {"User-Agent": "NoiseComplaintBot/1.0"}
        response = requests.get(url, params=params, headers=headers, timeout=5)
        data = response.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as e:
        print(f"Geocode error for '{address}': {e}")
    return None, None
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        email = request.form.get('email').lower()

        user_captcha = request.form.get('captcha')
        if int(user_captcha) != session.get('captcha_answer'):
            flash("Wrong CAPTCHA answer. Are you a robot?", "danger")
            return redirect(url_for('index'))

        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        last_report = Complaint.query.filter(
            Complaint.email == email,
            Complaint.created_at >= one_hour_ago
        ).first()

        if last_report:
            flash("You can only submit one report per hour.", "warning")
            return redirect(url_for('index'))

        file = request.files.get('media')
        if not file or file.filename == '':
            flash("Media file is required as evidence!", "danger")
            return redirect(url_for('index'))

        filename = secure_filename(f"{datetime.now().timestamp()}_{file.filename}")
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        frequency, volume, noise_profile = analyze_audio(file_path)

        new_complaint = Complaint(
            email=email,
            address=request.form.get('address'),
            time=request.form.get('time'),
            reason=request.form.get('reason'),
            custom_reason=request.form.get('custom_reason'),
            media_file=filename,
            device_info=request.headers.get('User-Agent'),
            avg_frequency=frequency,  # Добавлено
            avg_volume_db=volume,  # Добавлено
            noise_profile=noise_profile  # Добавлено
        )
        db.session.add(new_complaint)
        db.session.commit()

        flash("Thank you! Your report has been submitted.", "success")
        return redirect(url_for('index'))

    num1 = random.randint(1, 10)
    num2 = random.randint(1, 10)
    session['captcha_answer'] = num1 + num2
    captcha_question = f"What is {num1} + {num2}?"

    return render_template('index.html', captcha_question=captcha_question)


@app.route('/admin')
def admin():
    last_24_hours = datetime.utcnow() - timedelta(days=1)
    recent = Complaint.query.filter(Complaint.created_at >= last_24_hours).all()
    all_complaints = Complaint.query.order_by(Complaint.created_at.desc()).all()

    address_counts = {}
    for c in recent:
        address_counts[c.address] = address_counts.get(c.address, 0) + 1
    red_flags = [addr for addr, count in address_counts.items() if count >= 10]

    reason_stats = {}
    for c in all_complaints:
        r = f"Other: {c.custom_reason}" if c.reason == 'Other' and c.custom_reason else c.reason
        reason_stats[r] = reason_stats.get(r, 0) + 1
    top_reasons = sorted(reason_stats.items(), key=lambda x: x[1], reverse=True)[:3]

    time_stats = {}
    for c in all_complaints:
        hour = c.time.split(':')[0] + ":00"
        time_stats[hour] = time_stats.get(hour, 0) + 1
    top_times = sorted(time_stats.items(), key=lambda x: x[1], reverse=True)[:3]

    map_markers = []
    for address, count in address_counts.items():
        lat, lon = geocode_address(address)
        if lat and lon:
            map_markers.append({
                "address": address,
                "count": count,
                "lat": lat,
                "lon": lon,
                "is_red": address in red_flags
            })

    return render_template('admin.html',
                           complaints=all_complaints,
                           red_flags=red_flags,
                           top_reasons=top_reasons,
                           top_times=top_times,
                           map_markers=map_markers)


@app.route('/admin/email/<email>')
def admin_by_email(email):
    user_complaints = Complaint.query.filter_by(email=email).order_by(Complaint.created_at.desc()).all()
    return render_template('admin_filtered.html', complaints=user_complaints, filter_type="User",
                           filter_val=email)


@app.route('/admin/address/<path:address>')
def admin_by_address(address):
    location_complaints = Complaint.query.filter_by(address=address).order_by(Complaint.created_at.desc()).all()
    return render_template('admin_filtered.html', complaints=location_complaints, filter_type="Address",
                           filter_val=address)


if __name__ == '__main__':
    app.run(debug=True)