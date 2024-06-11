from flask import Flask, jsonify, request
from flask_jwt_extended import JWTManager, create_access_token, jwt_required
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, func
from database.models import Trade, AccountInfo, Balance, Position
from flask_cors import CORS
import numpy as np
from scipy.stats import norm
import os

app = Flask("TradingAPI")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://localhost:3000")

# Configure CORS
CORS(app, resources={r"/*": {"origins": DASHBOARD_URL}}, supports_credentials=True)

app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'super-secret')  # Change this!
jwt = JWTManager(app)

USERNAME = os.environ.get('APP_USERNAME', 'admin')
PASSWORD = os.environ.get('APP_PASSWORD', 'password')

def handle_options_request(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method == 'OPTIONS':
            response = make_response('', 200)
            response.headers.add('Access-Control-Allow-Origin', DASHBOARD_URL)
            response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
            response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
            response.headers.add('Access-Control-Allow-Credentials', 'true')
            return response
        return f(*args, **kwargs)
    return decorated_function

@app.route('/', methods=['GET'])
@handle_options_request
def ok():
    return jsonify({"status": "ok"}), 200

@app.route('/login', methods=['POST'])
@handle_options_request
def login():
    if not request.is_json:
        return jsonify({"msg": "Missing JSON in request"}), 400

    username = request.json.get('username', None)
    password = request.json.get('password', None)
    if username != USERNAME or password != PASSWORD:
        return jsonify({"msg": "Bad username or password"}), 401

    access_token = create_access_token(identity=username)
    return jsonify(access_token=access_token), 200

@app.route('/trades_per_strategy', methods=['GET'])
@jwt_required()
@handle_options_request
def trades_per_strategy():
    trades_count = app.session.query(Trade.strategy, Trade.broker, func.count(Trade.id)).group_by(Trade.strategy, Trade.broker).all()
    trades_count_serializable = [{"strategy": strategy, "broker": broker, "count": count} for strategy, broker, count in trades_count]
    return jsonify({"trades_per_strategy": trades_count_serializable})

@app.route('/historic_balance_per_strategy', methods=['GET'])
@jwt_required()
@handle_options_request
def historic_balance_per_strategy():
    try:
        historical_balances = app.session.query(
            Balance.strategy,
            Balance.broker,
            func.strftime('%Y-%m-%d %H', Balance.timestamp).label('hour'),
            Balance.balance,
        ).group_by(
            Balance.strategy, Balance.broker, 'hour'
        ).order_by(
            Balance.strategy, Balance.broker, 'hour'
        ).all()
        historical_balances_serializable = []
        for strategy, broker, hour, balance in historical_balances:
            historical_balances_serializable.append({
                "strategy": strategy,
                "broker": broker,
                "hour": hour,
                "balance": balance
            })
        return jsonify({"historic_balance_per_strategy": historical_balances_serializable})
    finally:
        app.session.close()

@app.route('/account_values', methods=['GET'])
@jwt_required()
@handle_options_request
def account_values():
    accounts = app.session.query(AccountInfo).all()
    accounts_data = {account.broker: account.value for account in accounts}
    return jsonify({"account_values": accounts_data})

@app.route('/trade_success_rate', methods=['GET'])
@jwt_required()
@handle_options_request
def trade_success_rate():
    strategies_and_brokers = app.session.query(Trade.strategy, Trade.broker).distinct().all()
    success_rate_by_strategy_and_broker = []

    for strategy, broker in strategies_and_brokers:
        total_trades = app.session.query(func.count(Trade.id)).filter(Trade.strategy == strategy, Trade.broker == broker).scalar()
        successful_trades = app.session.query(func.count(Trade.id)).filter(Trade.strategy == strategy, Trade.broker == broker, Trade.profit_loss > 0).scalar()
        failed_trades = total_trades - successful_trades

        success_rate_by_strategy_and_broker.append({
            "strategy": strategy,
            "broker": broker,
            "total_trades": total_trades,
            "successful_trades": successful_trades,
            "failed_trades": failed_trades
        })

    return jsonify({"trade_success_rate": success_rate_by_strategy_and_broker})

@app.route('/positions', methods=['GET'])
@jwt_required()
@handle_options_request
def get_positions():
    brokers = request.args.getlist('brokers[]')
    strategies = request.args.getlist('strategies[]')

    query = app.session.query(Position)

    if brokers:
        query = query.filter(Position.broker.in_(brokers))
    if strategies:
        query = query.filter(Position.strategy.in_(strategies))

    positions = query.all()
    positions_data = []
    for position in positions:
        positions_data.append({
            'broker': position.broker,
            'strategy': position.strategy,
            'symbol': position.symbol,
            'quantity': position.quantity,
            'latest_price': position.latest_price,
            'timestamp': position.last_updated,
        })

    return jsonify({'positions': positions_data})

@app.route('/trades', methods=['GET'])
@jwt_required()
@handle_options_request
def get_trades():
    brokers = request.args.getlist('brokers[]')
    strategies = request.args.getlist('strategies[]')

    query = app.session.query(Trade)

    if brokers:
        query = query.filter(Trade.broker.in_(brokers))
    if strategies:
        query = query.filter(Trade.strategy.in_(strategies))

    trades = query.all()
    trades_data = [{
        'id': trade.id,
        'broker': trade.broker,
        'strategy': trade.strategy,
        'symbol': trade.symbol,
        'quantity': trade.quantity,
        'price': trade.price,
        'profit_loss': trade.profit_loss,
        'timestamp': trade.timestamp
    } for trade in trades]

    return jsonify({'trades': trades_data})

@app.route('/trade_stats', methods=['GET'])
@jwt_required()
@handle_options_request
def get_trade_stats():
    brokers = request.args.getlist('brokers[]')
    strategies = request.args.getlist('strategies[]')

    query = app.session.query(Trade)

    if brokers:
        query = query.filter(Trade.broker.in_(brokers))
    if strategies:
        query = query.filter(Trade.strategy.in_(strategies))

    trades = query.all()

    if not trades:
        return jsonify({
            'average_profit_loss': 0,
            'win_loss_rate': 0,
            'number_of_trades': 0,
            'trades_per_day': {}
        })

    total_profit_loss = sum(trade.profit_loss for trade in trades)
    number_of_trades = len(trades)
    wins = sum(1 for trade in trades if trade.profit_loss > 0)
    losses = sum(1 for trade in trades if trade.profit_loss <= 0)
    win_loss_rate = wins / number_of_trades if number_of_trades > 0 else 0

    trades_per_day = {}
    for trade in trades:
        day = trade.timestamp.date().isoformat()  # Convert date to string
        if day not in trades_per_day:
            trades_per_day[day] = 0
        trades_per_day[day] += 1

    average_profit_loss = total_profit_loss / number_of_trades

    return jsonify({
        'average_profit_loss': average_profit_loss,
        'win_loss_rate': win_loss_rate,
        'number_of_trades': number_of_trades,
        'trades_per_day': trades_per_day
    })

@app.route('/var', methods=['GET'])
@jwt_required()
@handle_options_request
def get_var():
    brokers = request.args.getlist('brokers[]')
    strategies = request.args.getlist('strategies[]')

    query = app.session.query(Trade)

    if brokers:
        query = query.filter(Trade.broker.in_(brokers))
    if strategies:
        query = query.filter(Trade.strategy.in_(strategies))

    trades = query.all()

    if not trades:
        return jsonify({'var': 0})

    returns = [trade.profit_loss for trade in trades]
    mean_return = np.mean(returns)
    std_dev_return = np.std(returns)
    var_95 = norm.ppf(0.05, mean_return, std_dev_return)

    return jsonify({'var': var_95})

@app.route('/max_drawdown', methods=['GET'])
@jwt_required()
@handle_options_request
def get_max_drawdown():
    brokers = request.args.getlist('brokers[]')
    strategies = request.args.getlist('strategies[]')

    query = app.session.query(Trade)

    if brokers:
        query = query.filter(Trade.broker.in_(brokers))
    if strategies:
        query = query.filter(Trade.strategy.in_(strategies))

    trades = query.all()

    if not trades:
        return jsonify({'max_drawdown': 0})

    cum_returns = np.cumsum([trade.profit_loss for trade in trades])
    running_max = np.maximum.accumulate(cum_returns)
    drawdowns = (running_max - cum_returns) / running_max
    max_drawdown = np.max(drawdowns)

    return jsonify({'max_drawdown': max_drawdown})

@app.route('/sharpe_ratio', methods=['GET'])
@jwt_required()
@handle_options_request
def get_sharpe_ratio():
    brokers = request.args.getlist('brokers[]')
    strategies = request.args.getlist('strategies[]')

    query = app.session.query(Trade)

    if brokers:
        query = query.filter(Trade.broker.in_(brokers))
    if strategies:
        query = query.filter(Trade.strategy.in_(strategies))

    trades = query.all()

    if not trades:
        return jsonify({'sharpe_ratio': 0})

    returns = [trade.profit_loss for trade in trades]
    mean_return = np.mean(returns)
    std_dev_return = np.std(returns)
    sharpe_ratio = mean_return / std_dev_return if std_dev_return != 0 else 0

    return jsonify({'sharpe_ratio': sharpe_ratio})

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', DASHBOARD_URL)
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

def create_app(engine):
    Session = sessionmaker(bind=engine)
    app.session = Session()
    return app
