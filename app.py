from flask import (
    Flask,
    jsonify,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for
)
from datetime import datetime
from functools import wraps
from kiteconnect import KiteConnect
import threading
import time
import requests
import os
import mysqlconnection

class User: 
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password

    def __repr__(self):
        return f'<User: {self.username}>'

app = Flask(__name__)
app.secret_key = 'fnyhwrbc1fyfulg3opt6pkj25nagxphi'

# Replace with your actual API key and access token
api_key = "nou76gvyfsugbu6q"
access_token = "vUNA5Rax5fZf8patweFpahXnJKGzUo3x"
BASE_URL = 'https://kite.zerodha.com/'
position_details = []  # Replace with your actual symbols      

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = mysqlconnection.get_user_credentials(username)
        if user and user[1] == password:
            session['username'] = username
            return redirect(url_for('profile'))
        else:
            return render_template('login.html', message='Invalid username or password')
    return render_template('login.html', message='')

# Breathing page
@app.route('/breathing1')
@login_required
def breathing1():
 return render_template('breathing.html')

# Feedback page
@app.route('/feedback')
@login_required
def feedback():
    return render_template('feedback.html')

@app.route('/trade')
def profile():
    if 'username' in session:
        return render_template('trade.html')
    return render_template('login.html')

@app.route('/')
def home():
    if 'username' in session:
        return render_template('trade.html')
    return redirect(url_for('login'))

def get_actual_executed_price(order_id):
    endpoint = f'{BASE_URL}oms/orders/trades?order_id={order_id}'
    headers = {'Authorization': f'Bearer {access_token}'}
    response = requests.get(endpoint, headers=headers)

    if response.status_code == 200:
        order_data = response.json()
        return order_data['data']['average_price']
    else:
        raise Exception(response)

def get_last_traded_price(stock_symbol):
    # Replace with the actual API endpoint provided by Zerodha for last traded price
    api_url = f"https://api.kite.trade/quote/ltp?i=NSE:{stock_symbol}"
    
    # Include your API key in the headers
    headers = {
        "X-Kite-Version": "3",
        "Authorization": f"token {api_key}:{access_token}"
    }
    # Make an API request
    response = requests.get(api_url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        last_traded_price = data["data"]["NSE:" + stock_symbol]["last_price"]
        return last_traded_price
    else:
        return None

@app.route('/get_last_traded_price_and_profit_loss')
@login_required
def get_last_traded_price_and_profit_loss():
    stock_symbol = request.args.get('symbol')
    last_traded_price = get_last_traded_price(stock_symbol)
    profit_loss = p_n_l
    quantity = quantity

    # Fetch the average price from the position details
    position = next((p for p in position_details if p['symbol'] == stock_symbol), None)
    if position:
        average_price = position['average_price']
        #quantity = position['quantity']

        # Calculate profit/loss and change percentage
        if position['type'] == 'Buy':
            profit_loss = (last_traded_price - average_price) * quantity
        elif position['type'] == 'Sell':
            profit_loss = (average_price - last_traded_price) * quantity
        else:
            profit_loss = (average_price - last_traded_price) * quantity

        # Calculate change percentage
        if average_price != 0:
            change_percentage = ((last_traded_price - average_price) / average_price) * 100
        else:
            change_percentage = 0.0

        # Update the position details with profit/loss and change percentage
        #position['profit_loss'] = profit_loss
        position['change_percentage'] = change_percentage

        data = {
            "last_traded_price": last_traded_price,
            "profit_loss": profit_loss,
            "quantity": quantity,
            "change_percentage": change_percentage
        }
        return jsonify(data)
    else:
        return ('', 404)

@app.route('/place_buy_order', methods=['POST'])
@login_required
def place_buy_order():
    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)

    stock_symbol = request.form['stockSymbolBuy']
    quantity = int(request.form['quantity'])

    # Define order details for a market sell order
    order_details = {
        "tradingsymbol": stock_symbol,
        "exchange": "NSE",
        "transaction_type": "BUY",
        "quantity": quantity,
        "order_type": "MARKET",
        "product": "MIS"
    }

    try:
        last_traded_price = get_last_traded_price(stock_symbol)
        order_id = kite.place_order(variety=kite.VARIETY_REGULAR, **order_details)
        trade_details = kite.order_trades(order_id)  # Fetch trade details
        average_price = trade_details[0]['average_price']
        average_cost = average_price * quantity
        data = [
        ( session['username'], stock_symbol, quantity, average_price, 'buy', average_cost, order_id),
        ]
        mysqlconnection.updatedb(data)
        return render_template('trade.html', order_confirmation=f"buy order placed successfully. Order ID: {order_id}")
    except Exception as e:
        result = f"Error placing sell order: {e}"
        data = [
        ( session['username'], stock_symbol, quantity, 0, 'buy', 0, "order Failed"),
        ]
        mysqlconnection.updatedb(data)
        return render_template('trade.html', error_message=result)

@app.route('/place_sell_order', methods=['POST'])
@login_required
def place_sell_order():
    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)

    stock_symbol = request.form['stockSymbolSell']
    quantity = int(request.form['quantity'])

    # Define order details for a market sell order
    order_details = {
        "tradingsymbol": stock_symbol,
        "exchange": "NSE",
        "transaction_type": "SELL",
        "quantity": quantity,
        "order_type": "MARKET",
        "product": "MIS"
    }

    try:
        last_traded_price = get_last_traded_price(stock_symbol)
        order_id = kite.place_order(variety=kite.VARIETY_REGULAR, **order_details)
        trade_details = kite.order_trades(order_id)  # Fetch trade details
        average_price = trade_details[0]['average_price']
        average_cost = average_price * quantity
        data = [
        ( session['username'], stock_symbol, quantity, average_price, 'sell', average_cost, order_id),
        ]
        mysqlconnection.updatedb(data)
        return render_template('trade.html', order_confirmation=f"Sell order placed successfully. Order ID: {order_id}")
    except Exception as e:
        result = f"Error placing sell order: {e}"
        data = [
        ( session['username'], stock_symbol, quantity, 0, 'buy', 0, "order Failed"),
        ]
        mysqlconnection.updatedb(data)
        return render_template('trade.html', error_message=result)

@app.route('/position_details')
@login_required
def position_details_page():
    return render_template('position_details.html', positions=position_details)

@app.route('/dashboard')
@login_required
def dashboard_page():
    return render_template('dashboard.html')

@app.route('/executed_orders')
@login_required
def executed_orders_page():
    return render_template('executed_orders.html', orders=mysqlconnection.get_executed_orders(session['username']))

@app.route('/logout')
def logout():
     session.pop('username',None)
     return redirect(url_for('login'))

def run_app(port):
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)

if __name__ == "__main__":
    run_app(9000)
