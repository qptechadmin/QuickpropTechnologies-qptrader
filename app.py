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
import logging
from decimal import Decimal

# Configure logging
logging.basicConfig(filename='trading.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
    #last_traded_price = get_last_traded_price(stock_symbol)
    last_traded_price = 10
    # Calculate net PNL and M2M for each stock
    net_pnl = {}
    m2m = {}
    for trade in trades:
        stock = trade[2]
        quantity = trade[3]
        avg_price = trade[4]
        pnl = (avg_price - last_traded_price) * quantity
        if trade[5] == 'sell':
            pnl *= -1  # Reverse PNL sign for sell trades
        net_pnl[stock] = net_pnl.get(stock, 0) + pnl
        m2m[stock] = m2m.get(stock, 0) + (avg_price - last_traded_price) * quantity

    return render_template('index.html', trades=trades, net_pnl=net_pnl, m2m=m2m)

    # Fetch the average price from the position details
    position = next((p for p in position_details if p['symbol'] == stock_symbol), None)
    if position:
        average_price = position['average_price']

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
        ( session['username'], stock_symbol, quantity, 10, 'buy', 100, "1001"),
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
        ( session['username'], stock_symbol, quantity, 10, 'sell', 100, "11100"),
        ]
        mysqlconnection.updatedb(data)
        return render_template('trade.html', error_message=result)

@app.route('/position_details')
@login_required
def position_details_page():
    data = mysqlconnection.get_executed_orders(session['username'])
    # Assuming the last traded prices for each stock
    last_traded_prices = {'SUNPHARMA': Decimal('10.50'), 'WIPRO': Decimal('11.00'), 'TCS': Decimal('12.00'), 'INFY': Decimal('13.00')}

    net_pnl = {}
    m2m = {'total': {'quantity': 0, 'm2m': 0, 'pnl': 0}}  # Initialize total values

    for trade in data:
        stock = trade['Stock']
        quantity = trade['quantity']
        avg_price = trade['AVG_price']

        # Calculate PNL
        if trade['type'] == 'buy':
            pnl = (last_traded_prices[stock] - avg_price) * quantity
        else:  # Assuming the type can be 'sell' or 'buy' only
            pnl = (avg_price - last_traded_prices[stock]) * quantity

        # Calculate M2M
        m2m[stock] = {
            'quantity': m2m.get(stock, {'quantity': 0, 'm2m': 0, 'pnl': 0})['quantity'] + quantity,
            'm2m': m2m.get(stock, {'quantity': 0, 'm2m': 0, 'pnl': 0})['m2m'] + (last_traded_prices[stock] - avg_price) * quantity,
            'pnl': net_pnl.get(stock, 0) + pnl
        }

        # Update total values
        m2m['total']['quantity'] += quantity
        m2m['total']['m2m'] += (last_traded_prices[stock] - avg_price) * quantity
        m2m['total']['pnl'] += pnl

    return render_template('position_details.html', m2m=m2m)

@app.route('/dashboard')
@login_required
def dashboard_page():
    return render_template('dashboard.html')

@app.route('/executed_orders')
@login_required
def executed_orders_page():
    return render_template('executed_orders.html', orders=mysqlconnection.get_orders(session['username']))

@app.route('/logout')
def logout():
     session.pop('username',None)
     return redirect(url_for('login'))

def run_app(port):
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)

if __name__ == "__main__":
    run_app(9001)
