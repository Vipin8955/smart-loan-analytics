# 📊 Smart Loan EMI Analytics Dashboard

A full-stack **Flask web application** for intelligent loan EMI calculation, risk profiling, and econometric regression analysis — powered by real RBI benchmark rates and statistical modelling.

![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python)
![Flask](https://img.shields.io/badge/Flask-3.0%2B-black?logo=flask)
![MongoDB](https://img.shields.io/badge/MongoDB-Optional-green?logo=mongodb)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## 🚀 Features

- 🔐 **User Authentication** — Signup/Login with hashed passwords (Werkzeug)
- 🏦 **Multi-Loan Support** — Home, Personal, Car, and Other loan types
- 📈 **Live RBI Repo Rate** — Fetches real benchmark rates via FRED API
- 🧮 **EMI Calculator** — Supports Monthly, Quarterly, Semi-Annual, and Yearly compounding
- 📉 **OLS Regression Engine** — Fits 3 econometric models (Simple, Multiple, Polynomial) using `statsmodels`
- ⚠️ **Risk Profiler** — Debt-to-Income ratio with Safe / Moderate / High classification
- 🔮 **Scenario Simulation** — EMI impact of ±0.5% interest rate shifts
- 📊 **Interactive Charts** — R² comparison via Chart.js
- 🧾 **PDF Report Generator** — Downloadable analytics report via ReportLab
- 🗃️ **Calculation History** — Filterable and sortable loan log
- 🌙 **Dark Mode** — One-click theme toggle
- 🔄 **Offline Fallback** — Works without MongoDB using in-memory storage

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, Flask |
| Database | MongoDB (via PyMongo) — optional |
| Statistics | statsmodels, NumPy, Pandas |
| PDF Generation | ReportLab |
| Frontend | HTML5, Bootstrap 5, Chart.js, Vanilla JS |
| Auth | Werkzeug password hashing |
| Rate Data | FRED API (St. Louis Fed) |

---

## 📁 Project Structure

```
loan_project/
│
├── app.py                  # Main Flask application
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template (copy to .env)
├── .gitignore
│
├── templates/
│   ├── index.html          # Main dashboard
│   ├── login.html          # Login page
│   └── signup.html         # Signup page
│
├── static/
│   ├── style.css           # Dashboard styles
│   ├── login.css           # Login page styles
│   ├── signup.css          # Signup page styles
│   ├── script.js           # Dashboard logic & API calls
│   ├── login.js            # Login form validation
│   └── signup.js           # Signup form validation
│
├── repo_test.py            # Standalone FRED API test
├── dataset_test.py         # Standalone dataset generation test
└── regression_test.py      # Standalone OLS regression test
```

---

## ⚙️ Setup & Installation

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/loan_project.git
cd loan_project
```

### 2. Create a Virtual Environment

```bash
python -m venv myvenv

# Windows
myvenv\Scripts\activate

# macOS / Linux
source myvenv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

```bash
# Copy the template
copy .env.example .env       # Windows
cp .env.example .env         # macOS/Linux

# Edit .env and fill in your values
```

Your `.env` file should look like:

```env
FLASK_SECRET_KEY=your_long_random_secret_key_here
MONGO_URI=mongodb://localhost:27017/
FRED_API_KEY=your_fred_api_key_here
```

> **Get a free FRED API key:** [https://fred.stlouisfed.org/docs/api/api_key.html](https://fred.stlouisfed.org/docs/api/api_key.html)

### 5. Run the Application

```bash
python app.py
```

Open your browser at: **http://127.0.0.1:5000**

---

## 🗄️ MongoDB Setup (Optional)

MongoDB is **optional**. The app works fully without it using in-memory storage.

### Local MongoDB
1. [Download MongoDB Community](https://www.mongodb.com/try/download/community)
2. Start MongoDB: `mongod`
3. Set `MONGO_URI=mongodb://localhost:27017/` in your `.env`

### MongoDB Atlas (Cloud)
1. Create a free cluster at [mongodb.com/atlas](https://www.mongodb.com/atlas)
2. Get your connection string and set:
   ```env
   MONGO_URI=mongodb+srv://<user>:<password>@cluster.mongodb.net/
   ```

> ⚠️ **Offline Mode:** If MongoDB is not available, the app automatically falls back to in-memory storage. A warning banner will appear in the UI. Note that in-memory data is lost when the server restarts.

---

## 🧪 Running Tests

```bash
# Test FRED API connection
python repo_test.py

# Test dataset generation
python dataset_test.py

# Test OLS regression
python regression_test.py
```

---

## 🔑 Environment Variables Reference

| Variable | Description | Default |
|---|---|---|
| `FLASK_SECRET_KEY` | Flask session encryption key | Insecure default (change this!) |
| `MONGO_URI` | MongoDB connection string | `mongodb://localhost:27017/` |
| `FRED_API_KEY` | FRED API key for repo rate data | Built-in fallback key |

> **Security Note:** Never commit your real `.env` file to GitHub. Only `.env.example` should be committed.

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Main dashboard (requires login) |
| `GET/POST` | `/login` | User login |
| `GET/POST` | `/signup` | User registration |
| `GET` | `/logout` | Logout |
| `POST` | `/calculate` | Run EMI + regression analysis |
| `GET` | `/history` | Fetch user's calculation history |
| `GET` | `/download-report` | Download PDF analytics report |
| `GET` | `/health` | App health check |
| `GET` | `/db-status` | MongoDB connection status |

---

## 📸 Screenshots

> _Dashboard with EMI Summary, Risk Analysis, Regression Charts, and History_

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m "Add your feature"`
4. Push to the branch: `git push origin feature/your-feature`
5. Open a Pull Request

---

> **Disclaimer:** This application is for educational and analytical purposes only. EMI calculations and risk assessments are based on simulated econometric models and should not be used as formal financial advice.
