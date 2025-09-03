#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Flask module."""

import os

import re
import math
from pathlib import Path
from textwrap import dedent
from datetime import datetime
import requests
from flask import (
    Flask,
    render_template,
    request,
    flash,
    jsonify,
    url_for,
    redirect,
    session,
)
import bcrypt
from functools import wraps
from dotenv import load_dotenv
from src.utils.register.register import Register
from src.utils.login.login import Login
from src.utils.user.user import User
from src.utils.journal.journal import Journal
from src.utils.data_summary.data_summary import DataSummary
from src.utils.checkup.checkup import Checkup
from src.validator import (
    ValidateRegister,
    ValidateLogin,
    ValidateJournal,
    ValidateCheckup,
    ValidateDoctorKey,
)
import json
from src.utils.emotion.emotion import Emotion

from src.utils.payment.payment import Payment
from src.utils.subscription.subscription import Subscription
from src.utils.db_connection.db_connection import DBConnection


# APP INIT SECTION #
load_dotenv()  # load .env
# Initialize database connection
db_connection = DBConnection() 

if db_connection and db_connection.is_connected():
    print("✅ Database connection successful!")
else:
    print("❌ Database connection failed!")



ROOT_DIR = Path(__file__).parent.parent  # getting root dir path
STATIC_DIR = (ROOT_DIR).joinpath("static")  # generating static dir path
TEMPLATES_DIR = (ROOT_DIR).joinpath(
    "templates"
)  # generating templates dir path

# Initialize payment and subscription objects
payment_processor = Payment()
subscription_manager = Subscription(db_connection)

HF_API_TOKEN = os.getenv("HF_API_TOKEN")
MODEL = os.getenv("HF_MODEL", "j-hartmann/emotion-english-distilroberta-base")

if not HF_API_TOKEN:
    raise RuntimeError("HF_API_TOKEN not set. Put it in .env or your environment.")

API_URL = f"https://router.huggingface.co/hf-inference/models/{MODEL}"

app = Flask(
    __name__, static_folder=STATIC_DIR, template_folder=TEMPLATES_DIR
)  # init flask app
app.url_map.strict_slashes = False  # ignores trailing slash in routes

# assigning secret key for flask app
app.secret_key = os.getenv("APP_SECRET_KEY")


# ROUTES SECTION #


@app.route("/")  # homepage route
def home_page():
    """Route for home page."""
    data = {"doc_title": "Home | Mooda"}
    return render_template("index.html", data=data)

@app.route("/analyze", methods=["GET"])
def analysis_page():
    # Check if user is logged in (optional)
   
    # Serve the analysis page with the model name
    data = {
        "doc_title": "Emotion Analysis | Mooda"
    }
    return render_template("analyze.html", data=data, model=MODEL)

@app.route("/analyze", methods=["POST"])
def analysis_post():
    """
    Accepts:
      - JSON: { "text": "I feel..." }
      - form-encoded: text=<...>

    Calls the Hugging Face Inference API for emotion classification and returns
    a richer analytics payload to power the new UI, while preserving
    {labels, scores} for backward compatibility.

    Response:
      {
        labels: string[],
        scores: number[],
        raw: any,
        dominant_emotion: string,
        confidence: number,          # top label probability
        entropy: number,             # 0..1 normalized uncertainty
        valence: number,             # -1..1 weighted affective valence
        positivity: number,          # 0..1 mapped from valence
        arousal: number,             # 0..1 weighted arousal
        keywords: {text: string, score: number}[],
        suggestions: string[],
        prompt: string,
        stats: { word_count: int, unique_ratio: float, reading_time_min: float },
        model: string
      }
    """

    # ---------- helpers ----------
    def _parse_text_from_request():
        data = request.get_json(silent=True)
        if data and isinstance(data, dict) and "text" in data:
            return (data["text"] or "").strip()
        if request.form:
            return (request.form.get("text") or "").strip()
        return None

    def _hf_emotion(_text: str):
        headers = {
            "Authorization": f"Bearer {HF_API_TOKEN}",
            "Content-Type": "application/json",
        }
        try:
            r = requests.post(API_URL, headers=headers, json={"inputs": _text}, timeout=30)
        except requests.exceptions.RequestException as e:
            return (None, (500, {"error": "Network error when calling HF Inference API.", "details": str(e)}))
        if r.status_code == 401:
            return (None, (401, {"error": "Unauthorized — check your HF_API_TOKEN."}))
        if r.status_code == 503:
            return (None, (503, {"error": "Model temporarily unavailable or warming up (503). Try again in a few seconds."}))
        if r.status_code >= 400:
            return (None, (r.status_code, {"error": "HF API error", "status_code": r.status_code, "text": r.text}))
        try:
            return (r.json(), None)
        except ValueError:
            return (None, (500, {"error": "Invalid JSON from HF API", "text": r.text}))

    def _normalize_labels_scores(result):
        labels, scores = [], []
        # List format
        if isinstance(result, list) and len(result) > 0:
            if isinstance(result[0], list):
                result = result[0]
            if all(isinstance(x, dict) and "label" in x and "score" in x for x in result):
                ordered = sorted(result, key=lambda x: x["score"], reverse=True)
                labels = [o["label"] for o in ordered]
                scores = [float(o["score"]) for o in ordered]
            elif all(isinstance(x, dict) and any(k in x for k in ["label", "entity", "token"]) for x in result):
                tmp = []
                for it in result:
                    lbl = it.get("label") or it.get("entity") or it.get("token")
                    sc = float(it.get("score", 0))
                    if lbl is not None:
                        tmp.append((lbl, sc))
                tmp.sort(key=lambda t: t[1], reverse=True)
                if tmp:
                    labels, scores = zip(*tmp)
                    labels, scores = list(labels), list(scores)
        # Dict format
        elif isinstance(result, dict):
            if "label" in result and "score" in result:
                labels = [result["label"]]
                scores = [float(result["score"])]
            else:
                for _, value in result.items():
                    if isinstance(value, list) and all(isinstance(x, dict) for x in value):
                        if all("label" in x and "score" in x for x in value):
                            ordered = sorted(value, key=lambda x: x["score"], reverse=True)
                            labels = [o["label"] for o in ordered]
                            scores = [float(o["score"]) for o in ordered]
                            break
        return labels, scores

    def _entropy(prob):
        prob = [p for p in prob if p is not None]
        total = sum(prob) if prob else 0
        if total <= 0 or len(prob) <= 1:
            return 0.0
        p = [max(1e-12, x / total) for x in prob]
        h = -sum(x * math.log(x) for x in p)
        return float(h / math.log(len(p)))

    def _affect(labels, scores):
        # valence in [-1, 1], arousal in [0, 1]
        valence_map = {
            "joy": 0.95, "happiness": 0.95, "love": 0.9, "optimism": 0.7, "gratitude": 0.8,
            "surprise": 0.2, "neutral": 0.0,
            "sadness": -0.85, "pessimism": -0.6, "fear": -0.9, "anger": -0.9, "disgust": -0.9,
            "annoyance": -0.5, "disappointment": -0.6, "embarrassment": -0.5, "remorse": -0.6,
        }
        arousal_map = {
            "joy": 0.7, "happiness": 0.7, "love": 0.5, "optimism": 0.55, "gratitude": 0.4,
            "surprise": 0.85, "neutral": 0.2,
            "sadness": 0.3, "pessimism": 0.35, "fear": 0.9, "anger": 0.9, "disgust": 0.75,
            "annoyance": 0.6, "disappointment": 0.45, "embarrassment": 0.6, "remorse": 0.5,
        }
        if not labels or not scores:
            return 0.0, 0.0
        total = sum(scores) or 1.0
        v = sum(valence_map.get(lbl.lower(), 0.0) * sc for lbl, sc in zip(labels, scores)) / total
        a = sum(arousal_map.get(lbl.lower(), 0.5) * sc for lbl, sc in zip(labels, scores)) / total
        return float(max(-1.0, min(1.0, v))), float(max(0.0, min(1.0, a)))

    STOPWORDS = set(
        [
            "i","me","my","myself","we","our","ours","ourselves","you","your","yours","yourself","yourselves",
            "he","him","his","himself","she","her","hers","herself","it","its","itself","they","them","their","theirs","themselves",
            "what","which","who","whom","this","that","these","those","am","is","are","was","were","be","been","being",
            "have","has","had","having","do","does","did","doing","a","an","the","and","but","if","or","because","as","until","while",
            "of","at","by","for","with","about","against","between","into","through","during","before","after","above","below","to","from",
            "up","down","in","out","on","off","over","under","again","further","then","once","here","there","when","where","why","how",
            "all","any","both","each","few","more","most","other","some","such","no","nor","not","only","own","same","so","than","too","very",
            "can","will","just","don","should","now"
        ]
    )

    def _tokenize(text):
        return re.findall(r"[A-Za-z']+", text.lower())

    def _offline_emotion(_text: str):
        """Return a local heuristic emotion prediction in HF-like format.
        Produces a list of {label, score} dicts for labels:
        [joy, love, surprise, sadness, fear, anger, disgust, neutral].
        """
        try:
            tokens = _tokenize(_text or "")
            if not tokens:
                return [
                    {"label": "neutral", "score": 1.0},
                    {"label": "joy", "score": 0.0},
                    {"label": "love", "score": 0.0},
                    {"label": "surprise", "score": 0.0},
                    {"label": "sadness", "score": 0.0},
                    {"label": "fear", "score": 0.0},
                    {"label": "anger", "score": 0.0},
                    {"label": "disgust", "score": 0.0},
                ]

            lex = {
                "joy": {"happy","joy","glad","great","good","amazing","excited","cheerful","delighted","smile","grateful","proud","progress"},
                "love": {"love","loving","caring","affection","romance","heart","beloved","dear","gratitude","friend"},
                "surprise": {"surprised","unexpected","shock","shocked","astonished","wow","sudden"},
                "sadness": {"sad","down","depressed","lonely","cry","tears","unhappy","blue","heartbroken","grief","lost","hurt"},
                "fear": {"afraid","anxious","anxiety","worry","worried","scared","nervous","panic","fear","terrified","overwhelm","unsafe"},
                "anger": {"angry","mad","furious","annoyed","frustrated","rage","irritated","pissed","hate","resent"},
                "disgust": {"disgust","gross","nausea","nauseous","sick","ew","repulsed","nasty","filthy"},
            }
            counts = {k: 0 for k in lex.keys()}
            for t in tokens:
                for k, kws in lex.items():
                    if t in kws:
                        counts[k] += 1

            total = sum(counts.values())
            if total == 0:
                # If no keywords matched, default to neutral
                return [
                    {"label": "neutral", "score": 1.0},
                    {"label": "joy", "score": 0.0},
                    {"label": "love", "score": 0.0},
                    {"label": "surprise", "score": 0.0},
                    {"label": "sadness", "score": 0.0},
                    {"label": "fear", "score": 0.0},
                    {"label": "anger", "score": 0.0},
                    {"label": "disgust", "score": 0.0},
                ]

            # Normalize to probabilities
            raw = []
            for k in ["joy","love","surprise","sadness","fear","anger","disgust"]:
                raw.append({"label": k, "score": counts[k] / total})
            # Add a small neutral probability inversely proportional to total matches
            neutral_score = max(0.0, min(0.7, 0.2 if total > 0 else 1.0))
            # Re-normalize including neutral
            sum_non_neutral = sum(x["score"] for x in raw)
            if sum_non_neutral + neutral_score > 0:
                factor = 1.0 / (sum_non_neutral + neutral_score)
            else:
                factor = 1.0
            normalized = [{"label": x["label"], "score": x["score"] * factor} for x in raw]
            normalized.append({"label": "neutral", "score": neutral_score * factor})
            # Sort desc by score to mimic HF output order
            normalized.sort(key=lambda x: x["score"], reverse=True)
            return normalized
        except Exception:
            # On any error, return a neutral prediction
            return [
                {"label": "neutral", "score": 1.0},
                {"label": "joy", "score": 0.0},
                {"label": "love", "score": 0.0},
                {"label": "surprise", "score": 0.0},
                {"label": "sadness", "score": 0.0},
                {"label": "fear", "score": 0.0},
                {"label": "anger", "score": 0.0},
                {"label": "disgust", "score": 0.0},
            ]

    def _keywords(text, topk=8):
        tokens = _tokenize(text)
        if not tokens:
            return [], {"word_count": 0, "unique_ratio": 0.0, "reading_time_min": 0.0}
        words = [t for t in tokens if t not in STOPWORDS and len(t) > 2]
        wc = len(tokens)
        unique_ratio = (len(set(tokens)) / wc) if wc > 0 else 0.0
        rt = wc / 200.0  # ~200 wpm
        freq = {}
        for w in words:
            freq[w] = freq.get(w, 0) + 1
        if not freq:
            return [], {"word_count": wc, "unique_ratio": round(unique_ratio, 3), "reading_time_min": round(rt, 2)}
        total = sum(freq.values())
        scored = [(w, c / total) for w, c in freq.items()]
        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:topk]
        return (
            [{"text": w, "score": round(s, 4)} for w, s in top],
            {"word_count": wc, "unique_ratio": round(unique_ratio, 3), "reading_time_min": round(rt, 2)}
        )

    def _suggestions(emotion: str):
        e = (emotion or "").lower()
        base = [
            "Take three deep breaths",
            "Name what you feel (labeling emotions reduces intensity)",
            "Write a short gratitude note (1-2 sentences)",
        ]
        mapping = {
            "anger": ["Try a 5-minute walk to discharge energy", "Delay response to triggers by 10 minutes"],
            "sadness": ["Reach out to a trusted person", "Do one small self-care action"],
            "fear": ["List what you can control vs. cannot", "Ground yourself with 5-4-3-2-1 technique"],
            "disgust": ["Identify the boundary being crossed", "Practice self-compassion statement"],
            "surprise": ["Write initial reaction and a second interpretation", "Pause before acting"],
            "joy": ["Savor the moment (describe 3 details)", "Share the good news with someone"],
            "love": ["Send a kind message", "Plan a mindful connection activity"],
            "neutral": ["Do a quick body scan", "Set a simple intention for the next hour"],
            "optimism": ["Set a concrete next step", "Visualize success for 60 seconds"],
            "pessimism": ["Challenge one negative prediction", "Note one thing that went okay today"],
        }
        return base + mapping.get(e, [])

    def _prompt(emotion: str):
        e = (emotion or "").lower()
        prompts = {
            "anger": "What boundary felt crossed, and how can you assert it kindly?",
            "sadness": "What loss or unmet need is present right now?",
            "fear": "What outcome do you fear most, and what would help you feel 10% safer?",
            "disgust": "What value of yours feels violated?",
            "surprise": "What expectation was disrupted and what new possibility exists?",
            "joy": "What specifically made this feel good and how can you amplify it?",
            "love": "What connection are you grateful for and why?",
            "neutral": "What small action would make the next hour 1% better?",
            "optimism": "What is one realistic step toward the outcome you hope for?",
            "pessimism": "What evidence challenges your most negative expectation?",
        }
        return prompts.get(e, "What feels most important to acknowledge right now?")

    # ---------- main flow ----------
    text = _parse_text_from_request()
    if text is None:
        return jsonify({"error": "Please send JSON or form data with 'text' field."}), 400
    if not text:
        return jsonify({"error": "Empty text."}), 400

    result, err = _hf_emotion(text)
    source = "hf"
    if err is not None:
        # Attempt offline heuristic fallback to keep the app usable without network
        result = _offline_emotion(text)
        source = "offline"
        if not result:
            status, payload = err
            return jsonify(payload), status

    labels, scores = _normalize_labels_scores(result)
    if not labels or not scores:
        return jsonify({"error": "Could not parse HF API response", "raw": result}), 500

    # derived analytics
    dominant = labels[0]
    confidence = float(scores[0])
    entropy = _entropy(scores)
    valence, arousal = _affect(labels, scores)
    positivity = (valence + 1.0) / 2.0
    kw, stats = _keywords(text)
    suggestions = _suggestions(dominant)
    prompt = _prompt(dominant)

    # Save to database if user is logged in (keep existing behavior)
    if is_loggedin():
        try:
            emotion = Emotion(db_connection)
            emotion_data = {
                "labels": labels,
                "scores": scores,
                "raw": json.dumps(result),
            }
            emotion.save_emotion_analysis(
                session["user_id"]["user_id"],
                text,
                emotion_data,
            )
        except Exception as e:
            app.logger.error(f"Failed to save emotion analysis: {str(e)}")

    # Enhanced experience fields
    emoji_map = {
        "joy": "😊", "happiness": "😊", "love": "💗", "optimism": "🌤️", "gratitude": "🙏",
        "surprise": "🤯", "neutral": "😐",
        "sadness": "😔", "pessimism": "🌧️", "fear": "😟", "anger": "😠", "disgust": "🤢",
        "annoyance": "😒", "disappointment": "🙁", "embarrassment": "😳", "remorse": "😞",
    }
    emoji = emoji_map.get(dominant.lower(), "🌀")

    theme_map = {
        "joy": {"primary": "#22c55e", "gradient": "linear-gradient(135deg,#d1fae5,#a7f3d0,#6ee7b7)"},
        "happiness": {"primary": "#22c55e", "gradient": "linear-gradient(135deg,#d1fae5,#a7f3d0,#6ee7b7)"},
        "love": {"primary": "#f43f5e", "gradient": "linear-gradient(135deg,#ffe4e6,#fecdd3,#fda4af)"},
        "optimism": {"primary": "#06b6d4", "gradient": "linear-gradient(135deg,#e0f2fe,#bae6fd,#7dd3fc)"},
        "gratitude": {"primary": "#a855f7", "gradient": "linear-gradient(135deg,#ede9fe,#ddd6fe,#c4b5fd)"},
        "surprise": {"primary": "#f59e0b", "gradient": "linear-gradient(135deg,#fff7ed,#ffedd5,#fed7aa)"},
        "neutral": {"primary": "#94a3b8", "gradient": "linear-gradient(135deg,#f1f5f9,#e2e8f0,#cbd5e1)"},
        "sadness": {"primary": "#3b82f6", "gradient": "linear-gradient(135deg,#dbeafe,#bfdbfe,#93c5fd)"},
        "pessimism": {"primary": "#64748b", "gradient": "linear-gradient(135deg,#e2e8f0,#cbd5e1,#94a3b8)"},
        "fear": {"primary": "#8b5cf6", "gradient": "linear-gradient(135deg,#ede9fe,#ddd6fe,#c4b5fd)"},
        "anger": {"primary": "#ef4444", "gradient": "linear-gradient(135deg,#fee2e2,#fecaca,#fca5a5)"},
        "disgust": {"primary": "#84cc16", "gradient": "linear-gradient(135deg,#ecfccb,#d9f99d,#bef264)"},
        "annoyance": {"primary": "#f97316", "gradient": "linear-gradient(135deg,#ffedd5,#fed7aa,#fdba74)"},
        "disappointment": {"primary": "#64748b", "gradient": "linear-gradient(135deg,#e2e8f0,#cbd5e1,#94a3b8)"},
        "embarrassment": {"primary": "#f472b6", "gradient": "linear-gradient(135deg,#fdf2f8,#fce7f3,#fbcfe8)"},
        "remorse": {"primary": "#475569", "gradient": "linear-gradient(135deg,#e2e8f0,#cbd5e1,#94a3b8)"},
        "default": {"primary": "#6366f1", "gradient": "linear-gradient(135deg,#e0e7ff,#c7d2fe,#a5b4fc)"},
    }
    theme = theme_map.get(dominant.lower(), theme_map["default"])

    # Breathing cadence based on arousal
    if arousal >= 0.7:
        inhale_ms, exhale_ms = 3000, 4500
    elif arousal >= 0.4:
        inhale_ms, exhale_ms = 3000, 3500
    else:
        inhale_ms, exhale_ms = 3500, 3500

    # Music suggestion
    music = {"url": url_for('static', filename='audio/1.mp3')}

    micro_actions_map = {
        "anger": ["Box-breath for 2 minutes", "Write a kind boundary statement", "Walk for 3 minutes"],
        "sadness": ["Send a message to someone you trust", "Drink water and sit by a window", "Name one need"],
        "fear": ["List 3 things you control", "Do the 5-4-3-2-1 grounding", "Plan one safe step"],
        "disgust": ["Note the value being crossed", "Gently tidy one thing", "Say a self-compassion phrase"],
        "surprise": ["Write an alternate interpretation", "Pause 60 seconds before acting"],
        "joy": ["Savor 3 details", "Share good news", "Schedule a repeat"]
    }
    micro_actions = micro_actions_map.get(dominant.lower(), suggestions[:3])

    # Lightweight streak/progress tracking in session
    try:
        today = datetime.today().date()
        today_str = today.isoformat()
        last_date = session.get('analyze_last_date')
        streak = int(session.get('analyze_streak_days', 0))
        from datetime import timedelta
        if last_date:
            try:
                last = datetime.fromisoformat(last_date).date()
                if today == last:
                    pass
                elif today - last == timedelta(days=1):
                    streak += 1
                else:
                    streak = 1
            except Exception:
                streak = 1
        else:
            streak = 1
        session['analyze_last_date'] = today_str
        session['analyze_streak_days'] = streak
        session['analyze_today_count'] = int(session.get('analyze_today_count', 0)) + (1 if last_date == today_str else 1)
        session['analyze_total_count'] = int(session.get('analyze_total_count', 0)) + 1
    except Exception:
        streak = 1

    return jsonify(
        {
            "labels": labels,
            "scores": scores,
            "raw": result,
            "dominant_emotion": dominant,
            "confidence": confidence,
            "entropy": round(entropy, 4),
            "valence": round(valence, 4),
            "positivity": round(positivity, 4),
            "arousal": round(arousal, 4),
            "keywords": kw,
            "suggestions": suggestions,
            "prompt": prompt,
            "stats": stats,
            "model": MODEL,
            "source": source,
            "emoji": emoji,
            "theme": theme,
            "breathing": {"inhale_ms": inhale_ms, "exhale_ms": exhale_ms},
            "music": music,
            "micro_actions": micro_actions,
            "progress": {
                "today_entries": int(session.get('analyze_today_count', 1)),
                "total_entries": int(session.get('analyze_total_count', 1)),
                "streak_days": int(session.get('analyze_streak_days', 1)),
            },
        }
    )


@app.route('/analyze/history', methods=['GET'])
def analyze_history_api():
    """Return recent emotion analyses for the logged-in user."""
    if not is_loggedin():
        return jsonify([])
    try:
        emotion = Emotion(db_connection)
        rows = emotion.get_user_emotions(session["user_id"]["user_id"], limit=50)
        out = []
        for r in rows or []:
            try:
                data = json.loads(r.get('emotion_data')) if isinstance(r.get('emotion_data'), str) else r.get('emotion_data')
            except Exception:
                data = r.get('emotion_data')
            created = r.get('created_at')
            created_str = created.isoformat() if hasattr(created, 'isoformat') else str(created)
            out.append({
                "text": r.get("input_text"),
                "data": data,
                "created_at": created_str,
            })
        return jsonify(out)
    except Exception as e:
        app.logger.error(f"Failed to fetch analyze history: {e}")
        return jsonify([])


@app.route('/analyze/save-journal', methods=['POST'])
def analyze_save_journal():
    """Quick-save the latest analysis input as a journal entry."""
    if not is_loggedin():
        return jsonify({"status": False, "message": "Not authenticated"}), 401
    payload = request.get_json(silent=True) or {}
    text = (payload.get('text') or '').strip()
    title = (payload.get('title') or 'Emotion Reflection')
    if not text:
        return jsonify({"status": False, "message": "Text is required"}), 400
    try:
        journal = Journal()
        today = datetime.today().date()
        res = journal.create_journal(journal_content=text, journal_date=today, journal_title=title, user_id=session["user_id"]["user_id"])
        ok = bool(res.get("journal_created"))
        return jsonify({"status": ok})
    except Exception as e:
        app.logger.error(f"Failed to save journal from analysis: {e}")
        return jsonify({"status": False, "message": "Server error"}), 500


@app.route('/admin/db-config', methods=['GET', 'POST'])
def run_db_config():
    """Run database configuration directly"""
    try:
        # Capture output
        import io 
        import sys
        from contextlib import redirect_stdout, redirect_stderr
        
        # Capture stdout and stderr
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        # Run the configuration
        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            try:
                # Import and run your db_config function
                from db_config import db_config 
                success = db_config()
            except Exception as e:
                success = False
                print(f"Error: {e}", file=sys.stderr)
        
        # Get the captured output
        output = stdout_capture.getvalue()
        error_output = stderr_capture.getvalue()
        
        return f"""
        <html>
        <head><title>Database Configuration</title></head>
        <body style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
            <h1>📊 Database Configuration Results</h1>
            <div style="background: #f5f5f5; padding: 15px; border-radius: 5px; margin: 10px 0;">
                <h3>✅ Output:</h3>
                <pre style="background: white; padding: 10px; border: 1px solid #ddd; overflow: auto;">{output or 'No output'}</pre>
            </div>
            
            <div style="background: #fff3f3; padding: 15px; border-radius: 5px; margin: 10px 0;">
                <h3>❌ Errors:</h3>
                <pre style="background: white; padding: 10px; border: 1px solid #ffdddd; overflow: auto;">{error_output or 'No errors'}</pre>
            </div>
            
            <div style="background: #e8f4ff; padding: 15px; border-radius: 5px; margin: 10px 0;">
                <h3>📋 Status:</h3>
                <p><strong>Success:</strong> {success if 'success' in locals() else 'Unknown'}</p>
            </div>
            
            <div style="margin-top: 20px;">
                <a href="/" style="background: #007bff; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px;">← Back to Home</a>
                <a href="/admin/db-config" style="background: #28a745; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px; margin-left: 10px;">🔄 Run Again</a>
            </div>
        </body>
        </html>
        """
        
    except Exception as e:
        return f"Error running database configuration: {str(e)}", 500
    
@app.route("/register", methods=["POST", "GET"])  # register route
def register():
    """Route for account registration page."""
    if is_loggedin():
        return redirect(url_for("myspace"))

    form = ValidateRegister(request.form)  # init register form
    if request.method == "POST" and form.validate():
        hashed_pwd = encrypt_password(str.encode(form.password.data))

        user_data = {
            "first_name": form.first_name.data,
            "last_name": form.last_name.data,
            "email": form.email.data,
            "password": hashed_pwd,
            "birth": form.birth.data,
            "gender": form.gender.data,
        }  # data fetched from register form

        try_register(user_data)  # attempt to register user

    data = {"doc_title": "Register | Mooda", "register_form": form}
    return render_template("register.html", data=data)


@app.route("/login", methods=["GET", "POST"])  # login route
def login():
    """Route for login page."""
    if is_loggedin():
        return redirect(url_for("myspace"))

    form = ValidateLogin(request.form)  # init login form
    if request.method == "POST" and form.validate():
        user_data = {
            "email": form.email.data,
            "password": form.password.data,
        }  # data fetched from login form

        return try_login(user_data)  # attempt to login & return result

    data = {"doc_title": "Login | Mooda", "login_form": form}
    return render_template("login.html", data=data)


@app.route("/logout")  # logout route
def logout():
    """Route to logout a user."""
    session.clear()  # clear all session keys

    flash("You have been successfully logged out", "success")
    return redirect(url_for("login"))


@app.route("/checkup", methods=["GET", "POST"])  # checkup route
def checkup():
    """Route for user space."""
    if not is_loggedin():  # check if user is authenticated
        flash("You are not authenticated", "error")
        return redirect("/login")

    if not control_checkup():  # control if new checkup is required
        return redirect(url_for("myspace"))

    form = ValidateCheckup(request.form)
    if request.method == "POST" and form.validate():
        try_checkup(
            "register", data=form.checkup_range.data
        )  # register todays checkup data
        return redirect(url_for("myspace"))

    todays_checkup = try_checkup("display", data=None)  # fetch todays checkup

    data = {
        "doc_title": "Checkup | Mooda",
        "checkup_form": form,
        "checkup": todays_checkup,
    }
    return render_template("checkup.html", data=data)


@app.route("/myspace")  # myspace route
def myspace():
    """Route for user space."""
    if not is_loggedin():  # check if user is authenticated
        flash("You are not authenticated", "error")
        return redirect("/login")

    # if control_checkup():  # control if new checkup is required
    #     return redirect(url_for("checkup"))

    doctor_key = fetch_doctor_key()  # fetch user doctor key
    assertion = get_assertion()  # fetch assertion from external API

    data = {
        "doc_title": "My Space | Mooda",
        "assertion": assertion,
        "doctor_key": doctor_key,
    }
    return render_template("space-main.html", data=data)

@app.route("/myspace/emotions", methods=["GET"])
def emotion_history():
    """Route for user emotion history."""
    if not is_loggedin():  # check if user is authenticated
        flash("You are not authenticated", "error")
        return redirect("/login")
    
    # Get emotion history
    emotion = Emotion(db_connection)
    emotion_history = emotion.get_user_emotions(session["user_id"]["user_id"])
    
    # Parse the emotion data
    parsed_emotions = []
    for record in emotion_history:
        parsed_emotions.append({
            "text": record["input_text"],
            "data": json.loads(record["emotion_data"]),
            "date": record["created_at"]
        })
    
    data = {
        "doc_title": "My Space - Emotion History | Mooda",
        "emotion_history": parsed_emotions
    }
    return render_template("space-emotions.html", data=data)

# myspace/journals route
@app.route("/myspace/journals", methods=["GET", "POST"])
def journals():
    """Route for user journals."""
    if not is_loggedin():  # check if user is authenticated
        flash("You are not authenticated", "error")
        return redirect("/login")

    form = ValidateJournal(request.form)
    if request.method == "POST" and form.validate():
        journal_data = {
            "title": form.title.data,
            "content": form.content.data,
            "date": form.date_submitted.data,
            "user_id": session["user_id"]["user_id"],
        }

        try_journal(
            "register", journal_data, None
        )  # attempt to save a journal

    fetched_journals = try_journal(
        "display", None, request
    )  # attempt to fetch journals

    data = {
        "doc_title": "My Space - Journals | Mooda",
        "journal_form": form,
        "user_journals": fetched_journals,
    }
    return render_template("space-journals.html", data=data)


@app.route("/aboutus")  # about us route
def aboutus():
    """Route for about us page."""
    data = {"doc_title": "About Us | Mooda"}
    return render_template("aboutus.html", data=data)


@app.route("/analysis", methods=["GET", "POST"])  # analysis (doctorform) route
def doctor_form():
    """Route for psychologist portal (doctor form)."""
    form = ValidateDoctorKey(request.form)
    if request.method == "POST" and form.validate():
        session["doctor_key"] = form.doctor_key.data
        return redirect(url_for("doctor_view"))

    data = {"doc_title": "Psychologist Portal | Mooda", "doctor_form": form}
    return render_template("doctorform.html", data=data)


@app.route("/analysis/data", methods=["GET", "POST"])  # analysis/data route
def doctor_view():
    """Fetch patient records to be viewed by the doctor."""
    if (
        session.get("doctor_key") is None
    ):  # check if theres a valid doctor key in session
        return redirect(url_for("doctor_form"))

    doctor_key = session["doctor_key"]

    user = User()
    user_id = user.get_user_id(
        None, doctor_key=doctor_key
    )  # fetch user_id based on doctor_key

    user_email = user.get_email(
        user_id["user_id"]
    )  # fetch user email based on user_id

    curr_month_year = datetime.today().strftime("%Y-%m")

    journal = Journal()
    fetched_journals = journal.search_journals(
        user_id["user_id"], curr_month_year
    )  # fetch all journals based on "curr_month_year" variable
    data_summary = DataSummary()

    data_summary_result = data_summary.get_data_summary(
        user_email["email"]
    )  # fetch user data

    user.update_doctor_key(doctor_key)  # generate new doctor key to user
    session.pop("doctor_key", None)  # force doctor key session to expire

    data = {
        "doc_title": "Psychologist View | Mooda",
        "journals": fetched_journals,
        "data_summary_result": data_summary_result,
    }

    return render_template("doctor-view.html", data=data)

@app.route('/premium')
def premium():
    """Premium subscription page"""
    if not is_loggedin():
        flash("Please log in to view premium features", "error")
        return redirect(url_for("login"))
    
    user_has_premium = subscription_manager.is_premium_user(session["user_id"]["user_id"])
    subscription = subscription_manager.get_user_subscription(session["user_id"]["user_id"])
    
    data = {
        "doc_title": "Premium | Mooda",
        "user_has_premium": user_has_premium,
        "subscription_end_date": subscription["end_date"].strftime("%Y-%m-%d") if subscription else None,
        "paystack_public_key": os.getenv("PAYSTACK_PUBLIC_KEY")
    }
    return render_template("premium.html", data=data)

@app.route('/payment/initialize', methods=['POST'])
def initialize_payment():
    """Initialize a payment transaction"""
    if not is_loggedin():
        return jsonify({"status": False, "message": "Not authenticated"}), 401
    
    data = request.get_json()
    email = data.get('email')
    amount = data.get('amount')
    
    if not email or not amount:
        return jsonify({"status": False, "message": "Email and amount are required"}), 400
    
    # Add user metadata
    metadata = {
        "user_id": session["user_id"]["user_id"],
        "custom_fields": [
            {
                "display_name": "User ID",
                "variable_name": "user_id",
                "value": session["user_id"]["user_id"]
            }
        ]
    }
    
    # Initialize transaction
    result = payment_processor.initialize_transaction(email, amount, metadata=metadata)
    
    if result and result.get('status'):
        return jsonify({"status": True, "message": "Payment initialized", "data": result['data']})
    else:
        return jsonify({"status": False, "message": "Failed to initialize payment"}), 500

@app.route('/payment/verify')
def verify_payment():
    """Verify a payment transaction"""
    if not is_loggedin():
        flash("Please log in to complete payment", "error")
        return redirect(url_for("login"))
    
    reference = request.args.get('reference')
    if not reference:
        flash("Invalid payment reference", "error")
        return redirect(url_for("premium"))
    
    # Verify transaction
    result = payment_processor.verify_transaction(reference)
    
    if result and result.get('status') and result['data']['status'] == 'success':
        # Payment successful
        user_id = session["user_id"]["user_id"]
        amount = result['data']['amount'] / 100  # Convert back from kobo
        customer_code = result['data']['customer']['customer_code']
        
        # Create subscription
        subscription_manager.create_user_subscription(
            user_id, "Premium", amount, reference, customer_code
        )
        
        flash("Payment successful! Your premium features are now active.", "success")
        return redirect(url_for("myspace"))
    else:
        flash("Payment verification failed. Please try again.", "error")
        return redirect(url_for("premium"))

@app.route('/payment/webhook', methods=['POST'])
def payment_webhook():
    """Handle Paystack webhook for payment events"""
    
    # Skip verification in development if secret is not set
    if os.getenv('FLASK_ENV') == 'development' and not os.getenv('PAYSTACK_WEBHOOK_SECRET'):
        # Process webhook without verification
        event = request.json
        # ... your existing webhook processing code
        return jsonify({"status": "success"})
    
    # Normal verification for production
    signature = request.headers.get('x-paystack-signature')
    payload = request.get_data()
    
    if not payment_processor.verify_webhook_signature(payload, signature):
        return jsonify({"status": "error"}), 401
    

def premium_required(f):
    """Decorator to ensure user has premium subscription"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_loggedin():
            flash("Please log in to access this feature", "error")
            return redirect(url_for("login"))
        
        if not subscription_manager.is_premium_user(session["user_id"]["user_id"]):
            flash("This feature requires a premium subscription", "error")
            return redirect(url_for("premium"))
        
        return f(*args, **kwargs)
    return decorated_function

# Use it to protect premium routes
@app.route('/premium/feature')
@premium_required
def premium_feature():
    # Your premium feature code here
    pass
@app.errorhandler(404)
def page_not_found(err):
    """Handle 404 errors, custom page."""
    data = {"doc_title": "Page not found | Mooda", "e": err}
    return render_template("404.html", data=data), 404


# UTILS FUNCTIONS SECTION #


def load_user(email):
    """Load user id from database based on user's email."""
    user = User()

    return user.get_user_id(email, doctor_key=None)


def encrypt_password(password):
    """Encrypt/hash registration password."""
    hashed_pwd = bcrypt.hashpw(password, bcrypt.gensalt(rounds=15))
    return hashed_pwd


def get_assertion():
    """Fetch an assertion from an external api."""
    url = "https://www.affirmations.dev"

    response = requests.get(url, timeout=3)  # get req
    result = response.json()  # convert to json

    return result["affirmation"]


def is_loggedin():
    """Check wether a user is logged in or not."""
    if session.get("user_id") is None:
        return False
    return True


def fetch_doctor_key():
    """Fetch doctor key for a specific user."""
    init_user = User()
    doctor_key = init_user.get_doctor_key(session["user_id"]["user_id"])
    return doctor_key


def fetch_data_summary(email):
    """Fetch data summary for a specific user."""
    user_id = load_user(email)

    session["user_id"] = user_id
    session["user_email"] = email

    data_summary = DataSummary().get_data_summary(session.get("user_email"))

    session["data_summary"] = data_summary


def control_checkup():
    """Check if a new checkup is required."""
    init_checkup = Checkup().check_answer(session["user_id"]["user_id"])

    new_checkup = init_checkup["new_checkup"]

    if not new_checkup:
        return False
    return True


def try_journal(action, journal_data, j_request):
    """Attempt to display or register journals."""
    journal = Journal()  # init journal object

    match action:  # logic based on action type
        case "register":
            result = journal.create_journal(
                journal_title=journal_data["title"],
                journal_content=journal_data["content"],
                journal_date=journal_data["date"],
                user_id=journal_data["user_id"],
            )  # saves journal to db

            if result["journal_created"]:  # flash msg based on status
                return flash("Journal has been saved", "success")
            return flash("An error occured: Journal not saved", "error")

        case "display":
            if not j_request.args.get("q"):  # if it's NOT a search
                fetched_journals = journal.get_all_journals(
                    session["user_id"]["user_id"]
                )
                return fetched_journals

            search_query = j_request.args.get("q")  # if it's a search
            fetched_journals = journal.search_journals(
                session["user_id"]["user_id"], search_query
            )
            return fetched_journals


def try_checkup(action, data):
    """Attempt to display or register new checkup."""
    init_checkup = Checkup()  # init checkup object

    match action:  # logic based on action type
        case "register":
            checkup_data = {
                "u_id": session["user_id"]["user_id"],
                "c_id": session["t_checkup"],
                "answer": data,
                "answer_date": datetime.today().date(),
            }

            init_checkup.register_checkup(
                checkup_data["c_id"],
                checkup_data["u_id"],
                checkup_data["answer"],
                checkup_data["answer_date"],
            )  # saves checkup to db

            session.pop(
                "t_checkup", None
            )  # remove current checkup from session

        case "display":
            t_checkup = init_checkup.fetch_checkup(
                session["user_id"]["user_id"]
            )  # fetches new checkup
            session["t_checkup"] = t_checkup["todays_checkup"]["id"]
            return t_checkup


def try_login(user_data):
    """Attempt to login user."""
    init_login = Login()  # init login object
    result = init_login.login(
        user_data["email"], user_data["password"]
    )  # attempt login

    match result["login_succeeded"]:  # logic based on login status
        case True:  # if success
            fetch_data_summary(user_data["email"])

            # if control_checkup():  # control if new checkup is required
            #     return redirect(url_for("checkup"))

            return redirect(url_for("myspace"))

        case False | None:  # if fail
            try:  # invalid password
                result["invalid_password"]  # pylint: disable=W0104

                flash("Password is incorrect", "error")
                return redirect(url_for("login"))

            except KeyError:  # invalid email
                flash("This email does not exist", "error")
                return redirect(url_for("login"))


def try_register(user_data):
    """Try to register a user."""
    init_register = Register(user_data)  # init register object w user data
    result = init_register.register_user()  # register user

    match result[
        "registration_succeeded"
    ]:  # flash msg based on register result
        case True:  # if success
            return flash(
                dedent(
                    """\
                    Successfully registered.
                    To continue, please login."""
                ),
                "success",
            )
        case False | None:  # if fail
            return flash("Email already exists", "error")