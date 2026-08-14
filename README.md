# 🤖 Gen AI Data Analyzer

An intelligent web-based data analysis application that allows users to upload **CSV or Excel files**, automatically clean and analyze the data, generate dynamic KPIs and visualizations, and produce AI-powered business insights.

The application is built using **Python, Flask, Pandas, Plotly, Groq API, YData Profiling, and Sweetviz**.

---

## 🚀 Features

* 📂 Upload CSV and Excel datasets
* 🧹 Automatic data cleaning
* 🔍 Automatic column type detection
* 📊 Dynamic KPI generation
* 📈 Automatic chart generation based on dataset structure
* 📉 Distribution and outlier analysis
* 🔗 Correlation heatmap generation
* 📅 Time-series trend visualization when date columns are available
* 🧠 AI-powered data insights using Groq
* 📋 Executive summaries and business recommendations
* 📑 Automated YData Profiling reports
* 📊 Automated Sweetviz reports
* 💾 Dataset and KPI caching
* 🌐 Flask-based web interface

---

## 🛠️ Technologies Used

### Backend

* Python
* Flask
* Pandas
* NumPy
* SciPy

### Data Visualization

* Plotly
* Plotly Express

### Generative AI

* Groq API
* Llama 3.3 70B Versatile

### Automated Data Profiling

* YData Profiling
* Sweetviz

### Frontend

* HTML
* CSS
* JavaScript

---

## 🏗️ Project Structure

```text
GEN_AI_DATA_ANALYSIS/
│
├── app.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
│
├── templates/
│   └── index.html
│
└── static/
    ├── script.js
    └── style.css
```

---

## ⚙️ Installation

### 1. Clone the repository

```bash
git clone https://github.com/ganesh065/GEN_AI_DATA_ANALYSIS.git
```

### 2. Navigate to the project

```bash
cd GEN_AI_DATA_ANALYSIS
```

### 3. Create a virtual environment

Windows:

```bash
python -m venv venv
```

Activate it:

```bash
venv\Scripts\activate
```

Linux/macOS:

```bash
python3 -m venv venv
source venv/bin/activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

---

## 🔑 Configure Groq API

The application uses the Groq API to generate AI-powered insights.

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key_here
```

You can use `.env.example` as a template.

**Never commit your actual `.env` file or API key to GitHub.**

---

## ▶️ Run the Application

Start the Flask application:

```bash
python app.py
```

The application runs on:

```text
http://127.0.0.1:8080
```

Open the URL in your browser.

---

## 🔄 How It Works

```text
Upload CSV / Excel
        ↓
Read Dataset
        ↓
Automatic Data Cleaning
        ↓
Column Classification
        ↓
Dynamic KPI Generation
        ↓
Automatic Chart Generation
        ↓
Data Profiling
        ↓
AI-Powered Insights
        ↓
Business Recommendations
```

---

## 📊 Automatic Data Analysis

The application automatically identifies:

* Numeric columns
* Categorical columns
* Boolean columns
* Date/time columns
* Index-like columns

Based on the dataset, it dynamically generates visualizations such as:

* Histograms
* Box plots
* Bar charts
* Pie charts
* Scatter plots
* Correlation heatmaps
* Time-series line charts

This means the visualization logic is **data-driven rather than hardcoded to a specific dataset**.

---

## 🧠 AI-Powered Insights

The application sends a summarized representation of the uploaded dataset and generated KPIs to the Groq API.

The AI generates:

1. Executive Summary
2. Key Insights
3. Trends
4. Anomalies
5. Business Recommendations

If the AI service is unavailable, the application uses a rule-based insight generation system as a fallback.

---

## 📋 Automated Reports

After uploading a dataset, the application can generate:

### YData Profiling Report

Provides automated statistical and data-quality analysis.

### Sweetviz Report

Provides an automated visual exploration of the dataset.

Generated reports are stored locally and are excluded from Git tracking.

---

## 🔌 API Endpoints

| Endpoint        | Method | Description                     |
| --------------- | ------ | ------------------------------- |
| `/`             | GET    | Main application page           |
| `/api/upload`   | POST   | Upload and analyze a dataset    |
| `/api/charts`   | GET    | Generate dataset visualizations |
| `/api/insights` | POST   | Generate AI-powered insights    |

---

## 🔒 Security

Sensitive files are excluded from version control.

The `.gitignore` file prevents files such as:

```text
.env
cache/
__pycache__/
*.pkl
```

from being uploaded to GitHub.

---

## 🎯 Future Enhancements

* Natural-language chat with uploaded datasets
* SQL-based dataset querying
* More advanced AI agents
* Automated anomaly detection
* Predictive analytics
* Machine learning model recommendations
* PDF report generation
* PowerPoint report generation
* Docker deployment
* Cloud deployment
* User authentication
* Multiple dataset support

---

## 👨‍💻 Author

M SAI GANESH REDDY

GitHub:
https://github.com/ganesh065

---

## ⭐ Support

If you find this project useful, consider giving the repository a ⭐ on GitHub.
