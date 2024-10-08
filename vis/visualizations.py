import pickle
import pandas as pd
import dash
from dash import dcc, html
import plotly.graph_objs as go
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
import logging

def predict_cancellation_probability(model, airport_code, current_weather_data, flight_data):
    """
    Predict the probability of cancellation based on the airport code and current weather data.
    
    Args:
        model (sklearn.pipeline.Pipeline): The trained model.
        airport_code (str): The airport code to predict for.
        current_weather_data (pd.DataFrame): DataFrame with current weather data.
        flight_data (pd.DataFrame): DataFrame with historical flight data.
    
    Returns:
        pd.DataFrame: DataFrame with airlines and their cancellation probabilities.
    """
    try:

        # Rename columns in current_weather_data if needed
        current_weather_data.rename(columns={
            'Temperature (°C)': 'temperature',
            'Humidity (%)': 'humidity',
            'Wind Speed (km/h)': 'wind_speed'
        }, inplace=True)
        
        # Filter flight data for the given airport code
        flight_info = flight_data[flight_data['airport'] == airport_code]
        
        if flight_info.empty:
            raise ValueError("Airport code not found in the flight data.")
        
        # Use the first row of current weather data (since all rows are the same)
        weather_info = current_weather_data.iloc[0]
        
        # Prepare the feature vector for prediction
        features = ['arr_flights', 'arr_del15', 'carrier_ct', 'weather_ct', 'nas_ct', 'security_ct', 'late_aircraft_ct',
                    'arr_delay', 'carrier_delay', 'weather_delay', 'nas_delay', 'security_delay', 'late_aircraft_delay',
                    'temperature', 'humidity', 'wind_speed']
        
        # Create an empty list to store results
        results = []
        
        for _, row in flight_info.iterrows():
            # Extract flight-related features
            flight_features = row[features[:-3]].values.tolist()
            
            # Extract current weather features
            weather_features = weather_info[['temperature', 'humidity', 'wind_speed']].values.tolist()
            
            # Combine flight and weather features
            feature_vector = flight_features + weather_features
            
            # Predict the probability
            probability = model.predict_proba([feature_vector])[0][1]
            
            # Append the result with airline info and probability
            results.append({
                'carrier': row['carrier'],
                'carrier_name': row['carrier_name'],
                'probability_of_cancellation': probability
            })
        
        # Convert results to DataFrame
        results_df = pd.DataFrame(results)
        
        print(f"Cancellation probabilities for airlines at airport {airport_code}:")
        print(results_df)
        # Print out the airport column to verify available codes
        print("Dash is running on http://127.0.0.1:8050/")
        return results_df
    
    except Exception as e:
        logging.basicConfig(filename='data_pipeline.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        logger = logging.getLogger(__name__)
        logger.error(f"Prediction failed: {str(e)}")
        raise

def load_current_weather():
    """
    Load and preprocess the current weather data for Maryland.
    
    Returns:
        pd.DataFrame: Processed DataFrame with current weather data.
    """
    current_weather_path = 'data/processed/weather_data.csv'

    # Load current weather data with encoding handling
    try:
        current_weather_data = pd.read_csv(current_weather_path, encoding='utf-8')
    except UnicodeDecodeError:
        current_weather_data = pd.read_csv(current_weather_path, encoding='ISO-8859-1')
    
    # Ensure relevant columns are present
    if not {'Location', 'Temperature (°C)', 'Conditions', 'Humidity (%)', 'Wind Speed (km/h)'}.issubset(current_weather_data.columns):
        raise ValueError("The current weather data CSV file does not contain the required columns.")
    
    # Preprocess weather data
    current_weather_data.rename(columns={'Location': 'airport', 'Temperature (°C)': 'temperature', 
                                         'Humidity (%)': 'humidity', 'Wind Speed (km/h)': 'wind_speed'}, inplace=True)
    
    return current_weather_data

# Load your flight data to extract unique airport codes
def get_airport_codes():
    # Define the path to your flight data CSV file
    flight_data_path = 'data/outputs/csv_data.csv'
    flight_data = pd.read_csv(flight_data_path)
    return flight_data['airport'].unique().tolist()

airport_codes = get_airport_codes()  # Get the list of airport codes from your flight data


def create_dash_dashboard(initial_airport_code):
    """
    Create and run a Dash dashboard to visualize the probability of cancellation for different airlines and display current weather stats.
    
    Args:
        initial_airport_code (str): Initial airport code for which the data is displayed.
    """
    # Initialize Dash app with a Bootstrap theme for improved styling
    app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])

    # Layout of the app
    app.layout = dbc.Container([
        dbc.Row([
            dbc.Col(html.H1('Airline Cancellation Probability Dashboard'), width=12)
        ], justify='center', className='mb-4'),

        # Row for the dropdown menu with search and input box
        dbc.Row([
            dbc.Col([
                html.Label('Select or Type Airport Code:', className='form-label'),
                dcc.Dropdown(
                    id='airport-dropdown',
                    options=[{'label': code, 'value': code} for code in airport_codes],
                    value=initial_airport_code,
                    clearable=False,
                    searchable=True,  # Enable searching in dropdown
                    style={'width': '100%'}  # Make the dropdown full-width
                ),
            ], width=6, className='mb-3'),
            dbc.Col([
                html.Button('Submit', id='submit-button', n_clicks=0, className='btn btn-primary'),
            ], width=2),
        ], justify='center', className='mb-4'),

        # Display current weather information
        dbc.Row([
            dbc.Col([
                html.Div(id='weather-info', className='mb-4')
            ], width=12)
        ]),

        # Display the airport code
        dbc.Row([
            dbc.Col(html.H3(id='airport-code-display', children=f"Data for Airport Code: {initial_airport_code}"), width=12)
        ], justify='center', className='mb-4'),

        # Display the bar chart
        dbc.Row([
            dbc.Col(dcc.Graph(id='cancellation-probability-chart'), width=12)
        ]),
    ], fluid=True)

    # Callback to update the data, chart, and weather stats when the airport code is submitted
    @app.callback(
        [Output('cancellation-probability-chart', 'figure'),
         Output('airport-code-display', 'children'),
         Output('weather-info', 'children')],
        [Input('submit-button', 'n_clicks')],
        [State('airport-dropdown', 'value')]
    )
    def update_dashboard(n_clicks, airport_code):
        model_path = 'data/outputs/model.pkl'
        model = pickle.load(open(model_path, 'rb'))

        # Define the path to your flight data CSV file
        flight_data_path = 'data/outputs/csv_data.csv'
        flight_data = pd.read_csv(flight_data_path)

        # Fetch the updated data
        current_weather_data = load_current_weather()
        results_df = predict_cancellation_probability(model, airport_code, current_weather_data, flight_data)
        results_df['probability_of_cancellation'] = pd.to_numeric(results_df['probability_of_cancellation'], errors='coerce')

        # Create the bar chart
        figure = {
            'data': [
                go.Bar(
                    x=results_df['carrier_name'],
                    y=results_df['probability_of_cancellation'],
                    text=results_df['probability_of_cancellation'].apply(lambda x: f'{x:.2f}'),
                    textposition='auto',
                    marker=dict(color='orange')
                )
            ],
            'layout': go.Layout(
                title = "Airline Cancellation Probabilities - 1.0 Is the Max but Not 100%",
                xaxis={'title': 'Airline'},
                yaxis={'title': 'Probability of Cancellation 1.0 is chance of high cancellation'},
                template='plotly_dark'
            )
        }

        # Update the display of the airport code
        airport_code_display = f"Data for Airport Code: {airport_code}"

        # Display current weather info
        # Assuming current_weather_data is a DataFrame
        most_recent_weather = current_weather_data.iloc[-1]  # Select the most recent row

        weather_info = html.Div([
           html.H4("Current Weather Stats in MD (flying out of MD)"),
           html.H4(most_recent_weather.to_string())
        ], className='bg-dark text-light p-3 rounded')

        return figure, airport_code_display, weather_info

    # Run the app
    app.run_server(debug=True)
