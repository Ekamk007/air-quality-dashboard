from flask import Flask, render_template, request
import pandas as pd
import os
import warnings

warnings.filterwarnings("ignore")
app = Flask(__name__)

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CITY_DAY_CSV = os.path.join(BASE_DIR, "CITY_DAY.csv")
STATION_DAY_CSV = os.path.join(BASE_DIR, "STATION_DAY.csv")
CITY_HOUR_CSV = os.path.join(BASE_DIR, "CITY_HOUR.csv")
STATION_HOUR_CSV = os.path.join(BASE_DIR, "STATION_HOUR.csv")
RISK_SCORES_CSV = os.path.join(BASE_DIR, "city_risk_scores.csv")

# Load CSVs
def load_csv_safe(path, rename_map=None):
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]
    if rename_map:
        df = df.rename(columns=rename_map)
    return df

city_day = load_csv_safe(CITY_DAY_CSV, rename_map={"City":"city","Date":"date","AQI":"aqi"})
station_day = load_csv_safe(STATION_DAY_CSV, rename_map={"StationId":"station","Date":"date","AQI":"aqi"})
city_hour = load_csv_safe(CITY_HOUR_CSV, rename_map={"City":"city","Datetime":"datetime","AQI":"aqi"})
station_hour = load_csv_safe(STATION_HOUR_CSV, rename_map={"StationId":"station","Datetime":"datetime","AQI":"aqi"})
risk_scores = load_csv_safe(RISK_SCORES_CSV, rename_map={"City":"city","LinearRegression_risk_score":"linearregression_risk_score"})

# Convert dates
city_day['date'] = pd.to_datetime(city_day['date'], errors='coerce')
station_day['date'] = pd.to_datetime(station_day['date'], errors='coerce')
city_hour['datetime'] = pd.to_datetime(city_hour['datetime'], errors='coerce')
station_hour['datetime'] = pd.to_datetime(station_hour['datetime'], errors='coerce')

@app.route("/", methods=["GET","POST"])
def dashboard():
    # Get filter parameters
    selected_city = request.form.get("city", "All")
    start_date = request.form.get("start_date", city_day['date'].min())
    end_date = request.form.get("end_date", city_day['date'].max())

    # Filter datasets
    filtered_city_day = city_day.copy()
    if selected_city != "All":
        filtered_city_day = filtered_city_day[filtered_city_day['city']==selected_city]
    filtered_city_day = filtered_city_day[(filtered_city_day['date']>=pd.to_datetime(start_date)) & 
                                          (filtered_city_day['date']<=pd.to_datetime(end_date))]

    filtered_station_day = station_day.copy()
    filtered_station_day = filtered_station_day[(filtered_station_day['date']>=pd.to_datetime(start_date)) & 
                                                (filtered_station_day['date']<=pd.to_datetime(end_date))]

    # Metrics
    num_cities = filtered_city_day['city'].nunique()
    num_stations = filtered_station_day['station'].nunique()
    avg_aqi = round(filtered_city_day['aqi'].mean(), 2) if not filtered_city_day.empty else 0

    # City trends (top AQI city)
    if not filtered_city_day.empty:
        top_city = filtered_city_day.groupby("city")["aqi"].mean().idxmax()
        trends_df = filtered_city_day[filtered_city_day['city']==top_city].sort_values('date').tail(30)
        trends_df = trends_df.dropna(subset=['aqi'])
        trend_dates = trends_df['date'].dt.strftime('%Y-%m-%d').tolist()
        trend_values = trends_df['aqi'].tolist()
    else:
        trend_dates, trend_values = [], []

    # Heatmap
    heatmap_df = filtered_city_day.groupby("city")["aqi"].mean().reset_index().sort_values("aqi", ascending=False)
    heatmap_cities = heatmap_df['city'].tolist()
    heatmap_values = heatmap_df['aqi'].tolist()
    max_aqi = max(heatmap_values) if heatmap_values else 1
    heatmap_colors = [f"rgba({int((val/max_aqi)*255)}, {int((1-(val/max_aqi))*255)}, 0, 0.8)" for val in heatmap_values]

    # Station performance
    stations_df = filtered_station_day.groupby("station")["aqi"].agg(["count","mean"]).reset_index().rename(columns={"count":"Data Points","mean":"Avg AQI"})
    stations_names = stations_df['station'].tolist()
    stations_avg = stations_df['Avg AQI'].tolist()

    # Risk Scores
    risks_df = risk_scores.copy()
    risks_df['Policy'] = risks_df['linearregression_risk_score'].apply(
        lambda x: "Severe" if x>300 else "High" if x>200 else "Moderate" if x>150 else "Low"
    )
    risks_df = risks_df.sort_values('linearregression_risk_score', ascending=False)
    risks_list = list(zip(risks_df['city'], risks_df['Policy']))  # Pass zipped list to template
    risks_names = risks_df['city'].tolist()
    risks_values = risks_df['linearregression_risk_score'].tolist()

    # Cities list for filter dropdown
    cities_list = ["All"] + sorted(city_day['city'].unique().tolist())

    return render_template("dashboard.html",
        num_cities=num_cities,
        num_stations=num_stations,
        avg_aqi=avg_aqi,
        trend_dates=trend_dates,
        trend_values=trend_values,
        heatmap_cities=heatmap_cities,
        heatmap_values=heatmap_values,
        heatmap_colors=heatmap_colors,
        stations_names=stations_names,
        stations_avg=stations_avg,
        risks_list=risks_list,  # updated
        risks_names=risks_names,
        risks_values=risks_values,
        cities_list=cities_list,
        selected_city=selected_city,
        start_date=start_date,
        end_date=end_date
    )

if __name__=="__main__":
    app.run(debug=True)
