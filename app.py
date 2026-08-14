import os
import json
import pickle
from io import BytesIO
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from scipy.stats import skew
from flask import Flask, request, jsonify, render_template, send_from_directory
from groq import Groq
from dotenv import load_dotenv

from ydata_profiling import ProfileReport
import sweetviz as sv

from pandas.api.types import (
    is_numeric_dtype,
    is_string_dtype,
    is_object_dtype,
    is_datetime64_any_dtype,
    is_bool_dtype
)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

load_dotenv()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)
DF_CACHE = os.path.join(CACHE_DIR, "current.pkl")
KPI_CACHE = os.path.join(CACHE_DIR, "kpis.json")

global_df = None
global_kpis = {}

DARK_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=40, r=40, t=60, b=40),
    font=dict(color="#e2e8f0"),
)


def fig_to_chart(fig):
    fig.update_layout(**DARK_LAYOUT)
    payload = json.loads(fig.to_json())
    return {"data": payload["data"], "layout": payload["layout"]}


def load_cached_state():
    global global_df, global_kpis
    if global_df is None and os.path.exists(DF_CACHE):
        try:
            with open(DF_CACHE, "rb") as f:
                global_df = pickle.load(f)
        except Exception:
            global_df = None
    if not global_kpis and os.path.exists(KPI_CACHE):
        try:
            with open(KPI_CACHE, "r", encoding="utf-8") as f:
                global_kpis = json.load(f)
        except Exception:
            global_kpis = {}


def save_cached_state():
    try:
        with open(DF_CACHE, "wb") as f:
            pickle.dump(global_df, f)
        with open(KPI_CACHE, "w", encoding="utf-8") as f:
            json.dump(global_kpis, f)
    except Exception:
        pass


def looks_like_header_value(val):
    if pd.isna(val):
        return False
    text = str(val).strip()
    if not text or text.lower().startswith("unnamed"):
        return False
    try:
        float(text.replace(",", ""))
        return False
    except ValueError:
        return any(ch.isalpha() for ch in text)


def score_dataframe(df):
    if df is None or df.empty:
        return -10_000
    cols = [str(c) for c in df.columns]
    unnamed = sum(1 for c in cols if c.lower().startswith("unnamed") or c.startswith("col_"))
    nonempty_cols = int(df.dropna(axis=1, how="all").shape[1])
    header_quality = sum(1 for c in cols if looks_like_header_value(c))
    return nonempty_cols * 20 + header_quality * 15 - unnamed * 25 + min(len(df), 500)


def promote_header_row(df, row_idx):
    headers = []
    seen = {}
    for val in df.iloc[row_idx].tolist():
        name = str(val).strip() if pd.notna(val) else "column"
        if not name or name.lower() == "nan":
            name = "column"
        count = seen.get(name, 0)
        seen[name] = count + 1
        headers.append(name if count == 0 else f"{name}_{count}")
    out = df.iloc[row_idx + 1:].copy()
    out.columns = headers
    out.reset_index(drop=True, inplace=True)
    return out


def repair_headers(df):
    cols = [str(c) for c in df.columns]
    unnamed_ratio = sum(c.lower().startswith("unnamed") for c in cols) / max(len(cols), 1)
    if unnamed_ratio < 0.4:
        return df

    best = df
    best_score = score_dataframe(df)
    scan_rows = min(8, len(df))
    for i in range(scan_rows):
        header_hits = sum(looks_like_header_value(v) for v in df.iloc[i].tolist())
        if header_hits < max(2, int(df.shape[1] * 0.4)):
            continue
        candidate = promote_header_row(df, i)
        score = score_dataframe(candidate)
        if score > best_score:
            best = candidate
            best_score = score
    return best


def read_tabular_file(file_storage):
    raw = file_storage.read()
    filename = (file_storage.filename or "").lower()
    candidates = []

    if filename.endswith((".xlsx", ".xls")):
        bio = BytesIO(raw)
        df = pd.read_excel(bio)
        return repair_headers(df)

    for skip in range(0, 6):
        try:
            df = pd.read_csv(BytesIO(raw), skiprows=skip)
            candidates.append(repair_headers(df))
        except Exception:
            continue

    try:
        raw_df = pd.read_csv(BytesIO(raw), header=None)
        candidates.append(repair_headers(raw_df))
    except Exception:
        pass

    if not candidates:
        raise ValueError("Could not parse the uploaded file")

    return max(candidates, key=score_dataframe)


def is_index_like(series):
    if not is_numeric_dtype(series):
        return False
    vals = pd.to_numeric(series, errors="coerce").dropna()
    if len(vals) < 3:
        return False
    if series.nunique(dropna=True) == len(series) and vals.min() in (0, 1):
        diffs = np.diff(np.sort(vals.unique()))
        return len(diffs) and np.all(diffs == diffs[0])
    return False


def classify_columns(df):
    datetime_cols, numeric_cols, categorical_cols = [], [], []
    for col in df.columns:
        series = df[col]
        name = str(col).lower()
        if name.startswith("unnamed") or is_index_like(series):
            continue
        if is_datetime64_any_dtype(series):
            datetime_cols.append(col)
        elif is_bool_dtype(series):
            categorical_cols.append(col)
        elif is_numeric_dtype(series):
            nunique = series.nunique(dropna=True)
            if 1 < nunique <= 8 and nunique / max(len(series), 1) < 0.3:
                categorical_cols.append(col)
            else:
                numeric_cols.append(col)
        else:
            categorical_cols.append(col)
    return datetime_cols, numeric_cols, categorical_cols


def clean_data(df):
    df = df.copy()
    df.replace(r"^\s*$", np.nan, regex=True, inplace=True)
    df.dropna(axis=0, how="all", inplace=True)
    df.dropna(axis=1, how="all", inplace=True)

    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.replace(r"[^\w\s]", "", regex=True)
        .str.replace(r"\s+", "_", regex=True)
        .str.lower()
    )
    df.columns = [c if c and c != "nan" else f"column_{i}" for i, c in enumerate(df.columns)]

    keep = []
    for col in df.columns:
        if str(col).startswith("unnamed") and (df[col].dropna().empty or is_index_like(df[col])):
            continue
        keep.append(col)
    if keep:
        df = df[keep]

    df.drop_duplicates(inplace=True)
    df.reset_index(drop=True, inplace=True)

    for col in df.columns:
        if is_object_dtype(df[col]) or is_string_dtype(df[col]):
            as_num = pd.to_numeric(df[col].astype(str).str.replace(",", "", regex=False), errors="coerce")
            if as_num.notna().mean() > 0.7:
                df[col] = as_num
                continue
            sample = df[col].dropna().astype(str).head(20)
            date_like = sample.str.contains(r"\d{4}|\d{1,2}[-/]\d{1,2}", regex=True).mean() if len(sample) else 0
            if date_like > 0.5:
                converted = pd.to_datetime(df[col], errors="coerce")
                if converted.notna().mean() > 0.6:
                    df[col] = converted
                    continue
            df[col] = df[col].astype("string")

    for col in df.columns:
        if is_numeric_dtype(df[col]):
            median = df[col].median()
            df[col] = df[col].fillna(0 if pd.isna(median) else median)
        elif is_datetime64_any_dtype(df[col]):
            df[col] = df[col].ffill().bfill()
        elif is_bool_dtype(df[col]):
            df[col] = df[col].fillna(False)
        else:
            mode = df[col].mode(dropna=True)
            fill_val = mode.iloc[0] if not mode.empty else "Unknown"
            df[col] = df[col].fillna(fill_val)

    return df


def generate_dynamic_kpis(df):
    datetime_cols, numeric_cols, categorical_cols = classify_columns(df)
    kpis = {}
    kpis["Total Records"] = int(df.shape[0])
    kpis["Total Columns"] = int(df.shape[1])
    missing = int(df.isnull().sum().sum())
    kpis["Missing Values"] = missing
    kpis["Completeness %"] = round(100 * (1 - missing / max(df.size, 1)), 1)
    kpis["Duplicate Records"] = int(df.duplicated().sum())

    for col in numeric_cols[:4]:
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        if series.empty:
            continue
        label = str(col).replace("_", " ").title()
        kpis[f"{label} Mean"] = round(float(series.mean()), 2)
        kpis[f"{label} Median"] = round(float(series.median()), 2)
        kpis[f"{label} Max"] = round(float(series.max()), 2)

    for col in categorical_cols[:3]:
        vc = df[col].astype(str).value_counts()
        if vc.empty:
            continue
        label = str(col).replace("_", " ").title()
        kpis[f"Top {label}"] = str(vc.index[0])[:40]
        kpis[f"{label} Unique"] = int(vc.size)

    return kpis


def intelligent_chart_generator(df):
    charts = []
    datetime_cols, numeric_cols, categorical_cols = classify_columns(df)
    usable_numeric = numeric_cols[:]
    if not usable_numeric:
        usable_numeric = [c for c in df.columns if is_numeric_dtype(df[c]) and not is_index_like(df[c])]

    def add(fig):
        try:
            charts.append(fig_to_chart(fig))
        except Exception:
            pass

    for num_col in usable_numeric[:4]:
        try:
            vals = pd.to_numeric(df[num_col], errors="coerce").dropna()
            if len(vals) < 3:
                continue
            try:
                sk = abs(float(skew(vals))) if len(vals) > 10 else 0
            except Exception:
                sk = 0
            if sk > 1.2:
                add(px.box(df, y=num_col, title=f"Outliers in {num_col}"))
            else:
                add(px.histogram(df, x=num_col, nbins=20, title=f"Distribution of {num_col}"))
        except Exception:
            continue

    for cat_col in categorical_cols[:4]:
        try:
            counts = df[cat_col].astype(str).value_counts().head(12)
            if counts.empty or counts.size < 2:
                continue
            title = f"Breakdown of {cat_col}"
            if counts.size <= 6:
                add(px.pie(names=counts.index, values=counts.values, hole=0.4, title=title))
            else:
                fig = px.bar(x=counts.values, y=counts.index.astype(str), orientation="h", title=title)
                fig.update_layout(yaxis={"categoryorder": "total ascending"})
                add(fig)
        except Exception:
            continue

    if categorical_cols and usable_numeric:
        try:
            cat_c, num_c = categorical_cols[0], usable_numeric[0]
            if df[cat_c].nunique(dropna=True) <= 20:
                tmp = df[[cat_c, num_c]].copy()
                tmp[cat_c] = tmp[cat_c].astype(str)
                agg = tmp.groupby(cat_c, as_index=False)[num_c].mean()
                agg = agg.sort_values(num_c, ascending=False).head(12)
                add(px.bar(agg, x=cat_c, y=num_c, title=f"Average {num_c} by {cat_c}"))
        except Exception:
            pass

    if len(usable_numeric) >= 2:
        try:
            n1, n2 = usable_numeric[0], usable_numeric[1]
            color = categorical_cols[0] if categorical_cols and df[categorical_cols[0]].nunique() <= 12 else None
            add(px.scatter(df, x=n1, y=n2, color=color, title=f"{n1} vs {n2}", opacity=0.7))
        except Exception:
            pass

    if len(usable_numeric) >= 3:
        try:
            corr = df[usable_numeric[:8]].corr()
            add(px.imshow(corr, text_auto=True, aspect="auto", color_continuous_scale="RdBu_r",
                          title="Feature Correlation Heatmap"))
        except Exception:
            pass

    if datetime_cols and usable_numeric:
        try:
            dt_c = datetime_cols[0]
            sorted_df = df.sort_values(dt_c)
            add(px.line(sorted_df, x=dt_c, y=usable_numeric[0], title=f"Trend of {usable_numeric[0]} over time"))
        except Exception:
            pass

    if not charts:
        first = df.columns[0]
        counts = df[first].astype(str).value_counts().head(15)
        add(px.bar(x=counts.index.astype(str), y=counts.values, title=f"Top values in {first}"))

    return charts[:12]


def generate_rule_recommendations(df, kpis):
    datetime_cols, numeric_cols, categorical_cols = classify_columns(df)
    lines = ["## Executive Summary", "Automated analysis of the uploaded dataset.", "", "## Key Insights"]
    lines.append(f"- The dataset has **{kpis.get('Total Records', len(df))} records** across **{kpis.get('Total Columns', df.shape[1])} columns**.")
    lines.append(f"- Missing values: **{kpis.get('Missing Values', 0)}** (completeness {kpis.get('Completeness %', 'n/a')}%).")
    if numeric_cols:
        top = numeric_cols[0]
        series = pd.to_numeric(df[top], errors="coerce")
        lines.append(f"- Leading numeric metric **{top}** averages **{series.mean():.2f}** (max {series.max():.2f}).")
    if categorical_cols:
        cat = categorical_cols[0]
        mode = df[cat].astype(str).mode()
        if not mode.empty:
            lines.append(f"- Most common **{cat}** value is **{mode.iloc[0]}**.")
    lines.extend(["", "## Recommendations"])
    if kpis.get("Missing Values", 0) > 0:
        lines.append("- Investigate remaining missing fields before using this data for forecasting.")
    if numeric_cols:
        lines.append(f"- Track **{numeric_cols[0]}** as a primary KPI and review outliers in the charts below.")
    if categorical_cols:
        lines.append(f"- Segment performance by **{categorical_cols[0]}** to find high- and low-performing groups.")
    lines.append("- Use the correlation and distribution charts to validate drivers before acting on them.")
    return "\n".join(lines)


def generate_ai_insights():
    load_cached_state()
    if global_df is None:
        raise ValueError("No data uploaded yet")

    fallback = generate_rule_recommendations(global_df, global_kpis or generate_dynamic_kpis(global_df))
    try:
        client = Groq(api_key=GROQ_API_KEY)
        summary = global_df.describe(include="all").fillna("").to_string()[:4000]
        kpi_text = "\n".join([f"{k}: {v}" for k, v in list((global_kpis or {}).items())[:50]])
        prompt = f"""
        You are a senior data analyst.
        Dataset Summary:
        {summary}
        KPIs:
        {kpi_text}

        Provide:
        1. Executive Summary
        2. Key Insights
        3. Trends
        4. Anomalies
        5. Business Recommendations

        CRITICAL RULE: DO NOT include any programming code, Python scripts, matplotlib/seaborn examples, or implementation code. Only provide textual business and mathematical analysis.
        """
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are an expert data analyst. Format output in valid Markdown."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1024
        )
        text = (response.choices[0].message.content or "").strip()
        return text or fallback
    except Exception:
        return fallback


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/static/reports/<path:filename>")
def custom_static(filename):
    return send_from_directory("static/reports", filename)


@app.route("/api/upload", methods=["POST"])
def upload_file():
    global global_df, global_kpis
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    try:
        df = read_tabular_file(file)
        global_df = clean_data(df)
        global_kpis = generate_dynamic_kpis(global_df)
        charts_json = intelligent_chart_generator(global_df)
        save_cached_state()

        reports_dir = os.path.join(app.root_path, "static", "reports")
        os.makedirs(reports_dir, exist_ok=True)
        try:
            profile = ProfileReport(global_df, explorative=True, title="YData Profiling Report", minimal=True)
            profile.to_file(os.path.join(reports_dir, "ydata_profile.html"))
            sweet_report = sv.analyze(global_df)
            sweet_report.show_html(
                filepath=os.path.join(reports_dir, "sweetviz_report.html"),
                open_browser=False,
                layout="vertical",
                scale=1.0,
            )
            reports = {
                "ydata": "/static/reports/ydata_profile.html",
                "sweetviz": "/static/reports/sweetviz_report.html",
            }
        except Exception:
            reports = None

        insights = generate_ai_insights()

        return jsonify({
            "message": "File uploaded and cleaned successfully",
            "kpis": global_kpis,
            "charts": charts_json,
            "insights": insights,
            "reports": reports,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/charts", methods=["GET"])
def get_charts():
    load_cached_state()
    if global_df is None:
        return jsonify({"error": "No data uploaded yet"}), 400
    try:
        return jsonify({"charts": intelligent_chart_generator(global_df)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/insights", methods=["POST"])
def get_insights():
    load_cached_state()
    if global_df is None:
        return jsonify({"error": "No data uploaded yet"}), 400
    try:
        return jsonify({"insights": generate_ai_insights()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    load_cached_state()
    app.run(debug=True, port=8080, use_reloader=False)
