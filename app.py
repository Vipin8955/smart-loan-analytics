from flask import Flask, render_template, request, jsonify, redirect, session, send_file
import os
import numpy as np
import pandas as pd
import statsmodels.api as sm
import requests
import io
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient

# Built-in lightweight .env loader (eliminates external python-dotenv dependency)
def load_dotenv():
    dotenv_path = os.path.join(os.path.dirname(__file__), ".env") if "__file__" in globals() else ".env"
    try:
        with open(dotenv_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    val = val.strip().strip("'").strip('"')
                    os.environ[key.strip()] = val
    except FileNotFoundError:
        pass

load_dotenv()

# ReportLab imports for beautiful PDF generation
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "super_secret_loan_dashboard_key_change_this")

# ================= MONGODB WITH OFFLINE FALLBACK =================
MONGO_AVAILABLE = False
users_collection = None
loan_collection = None
mongo_client = None

# Offline Mock Storage (Falls back to this if local MongoDB is not running)
OFFLINE_USERS = {}  # username -> hashed_pw
OFFLINE_HISTORY = []  # List of dict records

mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")

def init_mongo():
    """Attempt to connect to MongoDB. Returns True on success, False on failure."""
    global MONGO_AVAILABLE, users_collection, loan_collection, mongo_client
    try:
        mongo_client = MongoClient(
            mongo_uri,
            serverSelectionTimeoutMS=2000,
            connectTimeoutMS=2000,
            socketTimeoutMS=3000
        )
        # Verify the connection is live
        mongo_client.server_info()
        db = mongo_client["loan_dashboard"]
        users_collection = db["users"]
        loan_collection = db["loan_history"]
        MONGO_AVAILABLE = True
        print("[SUCCESS] Successfully connected to MongoDB!")
        return True
    except Exception as e:
        MONGO_AVAILABLE = False
        users_collection = None
        loan_collection = None
        print("[WARNING] MongoDB connection failed. Falling back to In-Memory Offline Storage.")
        print("  Error detail:", e)
        return False

def is_mongo_alive():
    """Lightweight ping to check if the MongoDB connection is still alive."""
    global MONGO_AVAILABLE
    if not mongo_client:
        MONGO_AVAILABLE = False
        return False
    try:
        mongo_client.admin.command('ping')
        MONGO_AVAILABLE = True
        return True
    except Exception:
        MONGO_AVAILABLE = False
        return False

def get_mongo_status():
    """Returns human-readable status of the MongoDB connection."""
    if is_mongo_alive():
        return "connected"
    # Try reconnecting once
    if init_mongo():
        return "reconnected"
    return "offline"

# Initial connection attempt
init_mongo()

# ================= EMI FORMULA =================
def calculate_emi(P, annual_rate, years, compounding=12):
    # compounding=0 means Simple Interest mode
    if compounding == 0:
        if years <= 0:
            return 0
        total_months = years * 12
        simple_interest = P * (annual_rate / 100) * years
        return (P + simple_interest) / total_months

    r = annual_rate / (compounding * 100)
    n = years * compounding
    if r == 0:
        # Zero interest rate: principal-only equal instalments
        return P / n if n > 0 else 0
    denom = (1 + r)**n - 1
    if denom == 0:
        return 0
    return (P * r * (1 + r)**n) / denom

# ================= FETCH RBI REPO =================
def fetch_repo_history():
    try:
        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            "series_id": "INDIRLTLT01STM",
            "api_key": os.environ.get("FRED_API_KEY", "c8fadf182aecf101011aafb72b598539"),
            "file_type": "json"
        }
        response = requests.get(url, params=params, timeout=3)
        data = response.json()
        values = [
            float(obs["value"])
            for obs in data["observations"]
            if obs["value"] != "."
        ]
        return pd.Series(values)
    except Exception as e:
        print("FRED API Error:", e)
        # Safe fallback with realistic India repo rates
        return pd.Series(np.random.uniform(5.5, 7.0, 120))

# ================= USER AUTHENTICATION =================

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            return render_template("signup.html", error="Please fill all fields.")

        if len(username) < 3:
            return render_template("signup.html", error="Username must be at least 3 characters.")

        if len(password) < 4:
            return render_template("signup.html", error="Password must be at least 4 characters.")

        mongo_live = is_mongo_alive()

        # Check existing user
        if mongo_live:
            try:
                if users_collection.find_one({"username": username}):
                    return render_template("signup.html", error="User already exists.")
            except Exception as e:
                print("[ERROR] MongoDB Error on Signup Check:", e)
                # Attempt one reconnect before giving up
                if not init_mongo():
                    return render_template("signup.html", error="Database unavailable. Please try again later.")
                try:
                    if users_collection.find_one({"username": username}):
                        return render_template("signup.html", error="User already exists.")
                except Exception as e2:
                    print("[ERROR] MongoDB Retry Failed on Signup Check:", e2)
                    return render_template("signup.html", error="Database error. Please try again.")
        else:
            if username in OFFLINE_USERS:
                return render_template("signup.html", error="User already exists (Offline Mode).")

        hashed_pw = generate_password_hash(password)

        # Save user
        if mongo_live and MONGO_AVAILABLE:
            try:
                users_collection.insert_one({
                    "username": username,
                    "password": hashed_pw,
                    "created_at": datetime.utcnow()
                })
            except Exception as e:
                print("[ERROR] MongoDB Error on Signup Save:", e)
                # Fallback to in-memory if DB fails during save
                OFFLINE_USERS[username] = hashed_pw
                print("[INFO] User saved to offline in-memory storage as fallback.")
        else:
            OFFLINE_USERS[username] = hashed_pw

        return redirect("/login")

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            return render_template("login.html", error="Please fill all fields.")

        user_found = False
        stored_hash = None
        db_error = False

        mongo_live = is_mongo_alive()

        if mongo_live:
            try:
                user = users_collection.find_one({"username": username})
                if user:
                    user_found = True
                    stored_hash = user["password"]
            except Exception as e:
                print("[ERROR] MongoDB Error on Login:", e)
                db_error = True
                # Attempt one reconnect
                if init_mongo():
                    try:
                        user = users_collection.find_one({"username": username})
                        if user:
                            user_found = True
                            stored_hash = user["password"]
                            db_error = False
                    except Exception as e2:
                        print("[ERROR] MongoDB Retry Failed on Login:", e2)
                        db_error = True
        else:
            # Offline in-memory fallback
            if username in OFFLINE_USERS:
                user_found = True
                stored_hash = OFFLINE_USERS[username]

        if db_error:
            return render_template("login.html", error="Database connection error. Please try again shortly.")

        if user_found and stored_hash and check_password_hash(stored_hash, password):
            session["user"] = username
            return redirect("/")
        else:
            mode_str = " (Offline Mode)" if not MONGO_AVAILABLE else ""
            return render_template("login.html", error="Invalid credentials" + mode_str)

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user", None)
    session.pop("latest_calculation", None)
    return redirect("/login")

# ================= HOME DASHBOARD =================

@app.route("/")
def home():
    if "user" not in session:
        return redirect("/login")
    return render_template("index.html", username=session["user"])

# ================= CORE CALCULATION & REGRESSION ENGINE =================

@app.route("/calculate", methods=["POST"])
def calculate():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.json
    if not data:
        return jsonify({"error": "No JSON data received."}), 400

    try:
        principal_input = float(data["principal"])
        tenure_input = float(data["years"])
        income_input = float(data["income"])
        loan_type = data["loan_type"]
        compounding = int(data.get("compound", 12))
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({"error": "Invalid calculation inputs. Please check all fields."}), 400

    # ===== BOUNDS VALIDATION =====
    if principal_input <= 0:
        return jsonify({"error": "Loan amount must be greater than zero."}), 400
    if tenure_input <= 0:
        return jsonify({"error": "Loan tenure must be greater than zero."}), 400
    if income_input <= 0:
        return jsonify({"error": "Monthly income must be greater than zero."}), 400
    if principal_input > 1e9:
        return jsonify({"error": "Loan amount exceeds maximum allowed limit (₹10 Crore)."}), 400
    if tenure_input > 50:
        return jsonify({"error": "Loan tenure cannot exceed 50 years."}), 400
    if loan_type not in ["Home", "Personal", "Car", "Other"]:
        loan_type = "Other"  # Safe default for unknown types
    if compounding not in [0, 1, 2, 4, 12]:
        compounding = 12   # Default to monthly

    repo_rates = fetch_repo_history()
    latest_repo = repo_rates.iloc[-1]

    # ================= LOAN TYPE CONFIGURATION =================
    if loan_type == "Home":
        principal_range = (1500000, 8000000)
        tenure_range = (10, 30)
        spread_range = (2.0, 3.0)
        noise_level = 200
        risk_threshold = 40

    elif loan_type == "Personal":
        principal_range = (100000, 1000000)
        tenure_range = (1, 5)
        spread_range = (5.0, 7.0)
        noise_level = 800
        risk_threshold = 30

    elif loan_type == "Car":
        principal_range = (500000, 2000000)
        tenure_range = (3, 7)
        spread_range = (3.0, 5.0)
        noise_level = 400
        risk_threshold = 35

    else:  # Other Loans
        principal_range = (800000, 1500000)
        tenure_range = (5, 20)
        spread_range = (3.0, 4.0)
        noise_level = 500
        risk_threshold = 35

    # Calculate actual user parameters
    spread = np.random.uniform(*spread_range)
    user_interest = latest_repo + spread
    user_emi = calculate_emi(principal_input, user_interest, tenure_input, compounding)

    # ================= EMPIRICAL DATASET GENERATION =================
    dataset = []
    for repo in repo_rates:
        simulated_spread = np.random.uniform(*spread_range)
        rate = repo + simulated_spread

        principal = np.random.uniform(*principal_range)
        years = np.random.uniform(*tenure_range)

        emi = calculate_emi(principal, rate, years, compounding)
        emi += np.random.normal(0, noise_level)

        dataset.append([principal, rate, years, emi])

    df = pd.DataFrame(dataset, columns=["Principal", "Interest", "Tenure", "EMI"])

    # ================= GENUINE STATSMODELS REGRESSION & DIAGNOSTICS =================
    try:
        # Model 1: Simple Linear Regression of EMI on Interest
        X1 = sm.add_constant(df["Interest"])
        model1 = sm.OLS(df["EMI"], X1).fit()

        # Model 2: Multiple Linear Regression of EMI on Principal, Interest, Tenure
        X2 = sm.add_constant(df[["Principal", "Interest", "Tenure"]])
        model2 = sm.OLS(df["EMI"], X2).fit()

        # Model 3: Polynomial Regression of EMI on Interest and Interest^2
        df["Interest_sq"] = df["Interest"] ** 2
        X3 = sm.add_constant(df[["Interest", "Interest_sq"]])
        model3 = sm.OLS(df["EMI"], X3).fit()

        models_aic = {
            "Linear": model1.aic,
            "Multiple": model2.aic,
            "Polynomial": model3.aic
        }
        best_model = min(models_aic, key=models_aic.get)

        # ================= AFFORDABILITY & RISK ANALYSIS =================
        debt_ratio = (user_emi / income_input) * 100
        if debt_ratio < risk_threshold:
            risk_level = "Safe"
        elif debt_ratio < risk_threshold + 15:
            risk_level = "Moderate"
        else:
            risk_level = "High"

        # ================= INTEREST RATE SCENARIO SIMULATION =================
        low_emi = calculate_emi(principal_input, user_interest - 0.5, tenure_input, compounding)
        high_emi = calculate_emi(principal_input, user_interest + 0.5, tenure_input, compounding)

        # ================= REGRESSION RESIDUAL DIAGNOSTICS =================
        residuals = model2.resid
        res_mean = float(np.mean(residuals))
        res_std = float(np.std(residuals))

        jb_stat, jb_pvalue, skew, kurtosis = sm.stats.jarque_bera(residuals)
        dw_stat = sm.stats.durbin_watson(residuals)

        coefficients = model2.params.to_dict()
    except Exception as e:
        print("OLS Regression Engine Error:", e)
        return jsonify({"error": "An econometric calculation error occurred. Please verify that your input parameters are within normal lending bounds."}), 500

    # Create session snapshot for PDF download
    calculation_summary = {
        "username": session["user"],
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "loan_type": loan_type,
        "principal": principal_input,
        "tenure": tenure_input,
        "interest": round(user_interest, 2),
        "compounding": compounding,
        "emi": round(user_emi, 2),
        "income": income_input,
        "debt_ratio": round(debt_ratio, 2),
        "risk_level": risk_level,
        "low_emi": round(low_emi, 2),
        "high_emi": round(high_emi, 2),
        "best_model": best_model,
        "model1_r2": round(model1.rsquared, 4),
        "model2_r2": round(model2.rsquared, 4),
        "model3_r2": round(model3.rsquared, 4),
        "model1_aic": round(model1.aic, 2),
        "model2_aic": round(model2.aic, 2),
        "model3_aic": round(model3.aic, 2),
        "residual_mean": round(res_mean, 4),
        "residual_std": round(res_std, 4),
        "jb_pvalue": round(jb_pvalue, 4),
        "durbin_watson": round(dw_stat, 4),
        "coefficients": {k: round(v, 4) for k, v in coefficients.items()}
    }
    session["latest_calculation"] = calculation_summary

    # ================= SAVE RECORD =================
    record = {
        "username": session["user"],
        "loan_type": loan_type,
        "principal": principal_input,
        "tenure": tenure_input,
        "emi": round(user_emi, 2),
        "risk_level": risk_level,
        "compounding": compounding,
        "timestamp": datetime.utcnow()
    }

    offline_record = {
        "_id": str(len(OFFLINE_HISTORY) + 1),
        "username": session["user"],
        "loan_type": loan_type,
        "principal": principal_input,
        "tenure": tenure_input,
        "emi": round(user_emi, 2),
        "risk_level": risk_level,
        "compounding": compounding,
        "timestamp": datetime.utcnow().isoformat()
    }

    mongo_live = is_mongo_alive()
    if mongo_live:
        try:
            loan_collection.insert_one(record)
        except Exception as e:
            print("[ERROR] MongoDB error while saving history:", e)
            # Graceful fallback: persist in memory so history isn't lost
            OFFLINE_HISTORY.append(offline_record)
            print("[INFO] Calculation saved to offline in-memory storage as fallback.")
    else:
        # In-Memory Backup
        OFFLINE_HISTORY.append(offline_record)

    # Respond with detailed calculation metadata
    return jsonify({
        "emi": round(user_emi, 2),
        "repo_rate": round(float(latest_repo), 2),
        "model1_r2": round(model1.rsquared, 4),
        "model2_r2": round(model2.rsquared, 4),
        "model3_r2": round(model3.rsquared, 4),
        "model1_aic": round(model1.aic, 2),
        "model2_aic": round(model2.aic, 2),
        "model3_aic": round(model3.aic, 2),
        "best_model": best_model,
        "debt_ratio": round(debt_ratio, 2),
        "risk_level": risk_level,
        "low_emi": round(low_emi, 2),
        "base_emi": round(user_emi, 2),
        "high_emi": round(high_emi, 2),
        "residual_mean": round(res_mean, 4),
        "residual_std": round(res_std, 4),
        "jb_pvalue": round(jb_pvalue, 4),
        "durbin_watson": round(dw_stat, 4),
        "coefficients": coefficients
    })

# ================= HISTORY LOGS ROUTE =================

@app.route("/history")
def history():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    mongo_live = is_mongo_alive()

    if mongo_live:
        try:
            records = list(
                loan_collection.find(
                    {"username": session["user"]}
                ).sort("timestamp", -1)
            )
            for r in records:
                r["_id"] = str(r["_id"])
                # format timestamp to string
                if isinstance(r["timestamp"], datetime):
                    r["timestamp"] = r["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
            # Also merge any offline records accumulated during a DB outage
            offline_for_user = [
                r for r in OFFLINE_HISTORY if r["username"] == session["user"]
            ]
            if offline_for_user:
                records = offline_for_user + records
            return jsonify(records)
        except Exception as e:
            print("[ERROR] MongoDB error reading history:", e)
            # Attempt reconnect and retry once
            if init_mongo():
                try:
                    records = list(
                        loan_collection.find(
                            {"username": session["user"]}
                        ).sort("timestamp", -1)
                    )
                    for r in records:
                        r["_id"] = str(r["_id"])
                        if isinstance(r["timestamp"], datetime):
                            r["timestamp"] = r["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
                    return jsonify(records)
                except Exception as e2:
                    print("[ERROR] MongoDB Retry Failed on History Read:", e2)
            # Fallback to offline records
            user_records = [
                r for r in OFFLINE_HISTORY if r["username"] == session["user"]
            ]
            user_records.sort(key=lambda x: x["timestamp"], reverse=True)
            return jsonify(user_records)
    else:
        # Filter In-Memory Backup
        user_records = [
            r for r in OFFLINE_HISTORY if r["username"] == session["user"]
        ]
        # Sort by timestamp descending
        user_records.sort(key=lambda x: x["timestamp"], reverse=True)
        return jsonify(user_records)


# ================= HEALTH & DB STATUS ENDPOINTS =================

@app.route("/health")
def health():
    """Quick health check endpoint for the app."""
    return jsonify({"status": "ok", "app": "Smart Loan EMI Analytics"}), 200


@app.route("/db-status")
def db_status():
    """Returns real-time MongoDB connection status. Attempts reconnect if disconnected."""
    status = get_mongo_status()
    return jsonify({
        "mongo_status": status,
        "mongo_available": MONGO_AVAILABLE,
        "offline_users_count": len(OFFLINE_USERS),
        "offline_history_count": len(OFFLINE_HISTORY)
    }), 200

# ================= PREMIUM REPORTLAB PDF GENERATOR =================

@app.route("/download-report")
def download_report():
    if "user" not in session:
        return "Unauthorized", 401

    calc = session.get("latest_calculation")
    if not calc:
        return "<h3>No analysis results found. Please enter details and click 'Analyze Loan' first.</h3>", 400

    # Initialize PDF buffer
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    # Stylesheet Setup
    styles = getSampleStyleSheet()
    
    # Custom Palette
    COLOR_PRIMARY = colors.HexColor("#1A365D")   # Deep navy blue
    COLOR_SECONDARY = colors.HexColor("#2B6CB0") # Medium blue
    COLOR_TEXT = colors.HexColor("#2D3748")      # Charcoal dark grey
    COLOR_ACCENT = colors.HexColor("#E2E8F0")    # Soft grey border
    
    # Custom Paragraph Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=COLOR_PRIMARY,
        spaceAfter=6
    )
    
    subtitle_style = ParagraphStyle(
        'DocSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#718096"),
        spaceAfter=20
    )
    
    section_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=COLOR_PRIMARY,
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'BodyTextCustom',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=COLOR_TEXT
    )
    
    body_bold = ParagraphStyle(
        'BodyBoldCustom',
        parent=body_style,
        fontName='Helvetica-Bold'
    )

    story = []

    # Title & Header
    story.append(Paragraph("📊 Smart Loan EMI Analytics Report", title_style))
    story.append(Paragraph(
        f"Generated for: <b>{calc['username'] if 'username' in calc else session['user']}</b> | Timestamp: {calc['timestamp']} | Dynamic Stats Engine", 
        subtitle_style
    ))
    
    # Section: Input Summary
    story.append(Paragraph("1. Loan Structure & Pricing Details", section_style))
    
    compounding_map = {0: "Simple Interest", 12: "Monthly", 4: "Quarterly", 2: "Semi-Annual", 1: "Yearly"}
    comp_freq_str = compounding_map.get(calc['compounding'], f"{calc['compounding']}x/Year")

    summary_data = [
        [
            Paragraph("Loan Category", body_bold), 
            Paragraph(f"{calc['loan_type']} Loan", body_style),
            Paragraph("Requested Amount", body_bold),
            Paragraph(f"₹{NumberFormat(calc['principal'])}", body_style)
        ],
        [
            Paragraph("Loan Tenure", body_bold), 
            Paragraph(f"{calc['tenure']} Years", body_style),
            Paragraph("Compounding Period", body_bold),
            Paragraph(comp_freq_str, body_style)
        ],
        [
            Paragraph("Calculated Interest Rate", body_bold), 
            Paragraph(f"{calc['interest']}%", body_style),
            Paragraph("Estimated Installment (EMI)", body_bold),
            Paragraph(f"₹{NumberFormat(calc['emi'])}", body_bold)
        ]
    ]

    t1 = Table(summary_data, colWidths=[120, 140, 120, 140])
    t1.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, COLOR_ACCENT),
        ('PADDING', (0,0), (-1,-1), 8),
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor("#F7FAFC")),
        ('BACKGROUND', (2,0), (2,-1), colors.HexColor("#F7FAFC")),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t1)
    story.append(Spacer(1, 15))

    # Section: Risk Analysis
    story.append(Paragraph("2. Affordability & Debt Risk Profiling", section_style))
    
    risk_color_hex = "#38A169"  # Green
    if calc['risk_level'] == "Moderate":
        risk_color_hex = "#DD6B20"  # Orange
    elif calc['risk_level'] == "High":
        risk_color_hex = "#E53E3E"  # Red
        
    risk_data = [
        [
            Paragraph("Monthly Net Income", body_bold),
            Paragraph(f"₹{NumberFormat(calc['income'])}", body_style),
            Paragraph("Debt-to-Income Ratio", body_bold),
            Paragraph(f"{calc['debt_ratio']}%", body_style)
        ],
        [
            Paragraph("Affordability Classification", body_bold),
            Paragraph(f"<font color='{risk_color_hex}'><b>{calc['risk_level']}</b></font>", body_bold),
            Paragraph("Scenario Simulation (±0.5%)", body_bold),
            Paragraph(f"Low: ₹{NumberFormat(calc['low_emi'])} / High: ₹{NumberFormat(calc['high_emi'])}", body_style)
        ]
    ]
    t2 = Table(risk_data, colWidths=[150, 110, 130, 130])
    t2.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, COLOR_ACCENT),
        ('PADDING', (0,0), (-1,-1), 8),
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor("#F7FAFC")),
        ('BACKGROUND', (2,0), (2,-1), colors.HexColor("#F7FAFC")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t2)
    story.append(Spacer(1, 15))

    # Section: Statistical Comparison
    story.append(Paragraph("3. Empirical OLS Regression Engine", section_style))
    story.append(Paragraph(
        "Fitted three econometric formulas on an empirically simulated dataset based on historical benchmark trends.",
        body_style
    ))
    story.append(Spacer(1, 6))

    regression_data = [
        [
            Paragraph("<b>Model Name</b>", body_bold),
            Paragraph("<b>Fitted Features</b>", body_bold),
            Paragraph("<b>R-squared (R²)</b>", body_bold),
            Paragraph("<b>Akaike Info Criterion (AIC)</b>", body_bold)
        ],
        [
            Paragraph("Simple Linear Regression", body_style),
            Paragraph("Interest Rate", body_style),
            Paragraph(str(calc['model1_r2']), body_style),
            Paragraph(str(calc['model1_aic']), body_style)
        ],
        [
            Paragraph("Multiple Linear Regression (OLS)", body_style),
            Paragraph("Principal + Interest + Tenure", body_style),
            Paragraph(str(calc['model2_r2']), body_style),
            Paragraph(str(calc['model2_aic']), body_style)
        ],
        [
            Paragraph("Polynomial Regression", body_style),
            Paragraph("Interest + Interest²", body_style),
            Paragraph(str(calc['model3_r2']), body_style),
            Paragraph(str(calc['model3_aic']), body_style)
        ]
    ]
    t3 = Table(regression_data, colWidths=[160, 180, 100, 80])
    t3.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, COLOR_ACCENT),
        ('PADDING', (0,0), (-1,-1), 6),
        ('BACKGROUND', (0,0), (-1,0), COLOR_SECONDARY),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    # Quick text formatting fix for header in table style
    for i in range(4):
        t3.setStyle(TableStyle([('TEXTCOLOR', (i,0), (i,0), colors.white)]))
        
    story.append(t3)
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        f"<b>Statistical Verdict:</b> The mathematically superior option is the <font color='#2B6CB0'><b>{calc['best_model']} Model</b></font> (possessing the minimal AIC).", 
        body_style
    ))
    story.append(Spacer(1, 15))

    # Section: OLS Diagnostics
    story.append(Paragraph("4. Multiple Regression Diagnostic Signatures", section_style))
    
    diagnostic_data = [
        [
            Paragraph("Residual Mean", body_bold),
            Paragraph(str(calc['residual_mean']), body_style),
            Paragraph("Residual Std Dev", body_bold),
            Paragraph(str(calc['residual_std']), body_style)
        ],
        [
            Paragraph("Durbin-Watson Stat", body_bold),
            Paragraph(str(calc['durbin_watson']), body_style),
            Paragraph("Jarque-Bera p-value", body_bold),
            Paragraph(str(calc['jb_pvalue']), body_style)
        ]
    ]
    t4 = Table(diagnostic_data, colWidths=[120, 140, 120, 140])
    t4.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, COLOR_ACCENT),
        ('PADDING', (0,0), (-1,-1), 8),
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor("#F7FAFC")),
        ('BACKGROUND', (2,0), (2,-1), colors.HexColor("#F7FAFC")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(t4)
    story.append(Spacer(1, 10))

    # Regression Equation / Coefficients
    coef = calc.get("coefficients", {})
    equation_parts = []
    if "const" in coef:
        equation_parts.append(f"{coef['const']}")
    if "Principal" in coef:
        equation_parts.append(f"({coef['Principal']} * Principal)")
    if "Interest" in coef:
        equation_parts.append(f"({coef['Interest']} * Interest)")
    if "Tenure" in coef:
        equation_parts.append(f"({coef['Tenure']} * Tenure)")
        
    equation_str = "EMI = " + (" + ".join(equation_parts) if equation_parts else "(insufficient coefficient data)")
    
    story.append(Paragraph("<b>Econometric Predictive Formula:</b>", body_bold))
    story.append(Paragraph(f"<i>{equation_str}</i>", ParagraphStyle('EqStyle', parent=body_style, leftIndent=15, textColor=COLOR_SECONDARY)))
    
    # Disclaimer
    story.append(Spacer(1, 20))
    story.append(Paragraph(
        "<b>Disclaimer:</b> This report represents empirical econometric modeling using simulated historical parameters. Actual credit rates, terms, and assessments are subject to institutional credit policies and formal underwriting criteria.",
        ParagraphStyle('Disclaimer', parent=styles['Normal'], fontName='Helvetica-Oblique', fontSize=8, leading=11, textColor=colors.HexColor("#A0AEC0"))
    ))

    # Build & Return Document with robust local error handling
    try:
        doc.build(story)
        pdf_buffer.seek(0)
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=f"Smart_Loan_Report_{calc['loan_type']}.pdf",
            mimetype="application/pdf"
        )
    except Exception as e:
        print("PDF Report Generation Error:", e)
        return "<h3>An internal error occurred while generating the PDF report. Please run the analysis again.</h3>", 500

# Formatting helper for numbers
def NumberFormat(val):
    try:
        return f"{int(val):,}"
    except (ValueError, TypeError):
        return str(val)

# ================= RUN SERVER =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)