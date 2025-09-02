#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Flask module."""

import os
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

API_URL = f"https://api-inference.huggingface.co/models/{MODEL}"

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
    Sends the text to Hugging Face Inference API and returns JSON:
      { labels: [...], scores: [...], raw: {...} }
    """
    # Try JSON first, then form fallback
    data = request.get_json(silent=True)
    text = None
    if data and "text" in data:
        text = data["text"]
    else:
        # fallback to form data (e.g. normal form submit)
        text = request.form.get("text") if request.form else None

    if text is None:
        return jsonify({"error": "Please send JSON or form data with 'text' field."}), 400

    text = text.strip()
    if not text:
        return jsonify({"error": "Empty text."}), 400

    headers = {
        "Authorization": f"Bearer {HF_API_TOKEN}",
        "Content-Type": "application/json",
    }

    # call Hugging Face Inference API
    try:
        resp = requests.post(API_URL, headers=headers, json={"inputs": text}, timeout=30)
    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Network error when calling HF Inference API.", "details": str(e)}), 500

    if resp.status_code == 401:
        return jsonify({"error": "Unauthorized — check your HF_API_TOKEN."}), 401
    if resp.status_code == 503:
        return jsonify({"error": "Model temporarily unavailable or warming up (503). Try again in a few seconds."}), 503
    if resp.status_code >= 400:
        return jsonify({"error": "HF API error", "status_code": resp.status_code, "text": resp.text}), resp.status_code

    try:
        result = resp.json()
    except ValueError:
        return jsonify({"error": "Invalid JSON from HF API", "text": resp.text}), 500

    # Handle different response formats from HF API
    labels = []
    scores = []
    
    # Format 1: List of dictionaries with label and score
    if isinstance(result, list) and len(result) > 0:
        if isinstance(result[0], list):
            # Handle nested list format
            result = result[0]
            
        if all(isinstance(x, dict) and "label" in x and "score" in x for x in result):
            result_sorted = sorted(result, key=lambda x: x["score"], reverse=True)
            labels = [r["label"] for r in result_sorted]
            scores = [r["score"] for r in result_sorted]
        elif all(isinstance(x, dict) and any(k in x for k in ["label", "entity", "token"]) for x in result):
            # Handle different key names that might be used
            for item in result:
                if "label" in item:
                    labels.append(item["label"])
                    scores.append(item.get("score", 0))
                elif "entity" in item:
                    labels.append(item["entity"])
                    scores.append(item.get("score", 0))
    
    # Format 2: Single dictionary with label and score
    elif isinstance(result, dict):
        if "label" in result and "score" in result:
            labels = [result["label"]]
            scores = [result["score"]]
        # Try to find any keys that might contain the predictions
        else:
            for key, value in result.items():
                if isinstance(value, list) and all(isinstance(x, dict) for x in value):
                    if all("label" in x and "score" in x for x in value):
                        result_sorted = sorted(value, key=lambda x: x["score"], reverse=True)
                        labels = [r["label"] for r in result_sorted]
                        scores = [r["score"] for r in result_sorted]
                        break
    
    # If we still haven't extracted any labels/scores, return the raw response
    if not labels or not scores:
        return jsonify({"error": "Could not parse HF API response", "raw": result}), 500

    # Save to database if user is logged in
    if is_loggedin():
        try:
            emotion = Emotion(db_connection)  # Initialize your emotion DB class
            emotion_data = {
                "labels": labels,
                "scores": scores,
                "raw": json.dumps(result)  # Ensure raw result is JSON-serializable
            }
            emotion.save_emotion_analysis(
                session["user_id"]["user_id"], 
                text, 
                emotion_data
            )
        except Exception as e:
            # Log the error but don't fail the request
            app.logger.error(f"Failed to save emotion analysis: {str(e)}")

    return jsonify({"labels": labels, "scores": scores, "raw": result})


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
    emotion = Emotion()
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
    # Verify webhook signature
    signature = request.headers.get('x-paystack-signature')
    payload = request.get_data()
    
    if not payment_processor.verify_webhook_signature(payload, signature):
        return jsonify({"status": "error"}), 401
    
    event = request.json
    event_type = event.get('event')
    data = event.get('data')
    
    if event_type == 'charge.success':
        # Handle successful charge
        reference = data.get('reference')
        # Update subscription status in database
        subscription_manager.update_subscription_status(reference, 'active')
    
    elif event_type in ['subscription.disable', 'charge.failed']:
        # Handle failed payments or disabled subscriptions
        reference = data.get('reference')
        subscription_manager.update_subscription_status(reference, 'inactive')
    
    return jsonify({"status": "success"})

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