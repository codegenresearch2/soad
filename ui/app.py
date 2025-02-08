from flask import Flask, jsonify, request
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, func
from database.models import Trade, AccountInfo, Balance, Position
from flask_cors import CORS
import numpy as np
from scipy.stats import norm
import os

app = Flask('TradingAPI')
CORS(app, origins=['http://localhost:3000'], supports_credentials=True)

@app.route('/trades_per_strategy')
def trades_per_strategy():
    trades_count = app.session.query(Trade.strategy, Trade.broker, func.count(Trade.id)).group_by(Trade.strategy, Trade.broker).all()
    trades_count_serializable = [{'strategy': strategy, 'broker': broker, 'count': count} for strategy, broker, count in trades_count]
    return jsonify({'trades_per_strategy': trades_count_serializable})

@app.route('/historic_balance_per_strategy', methods=['GET'])
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
                'strategy': strategy,
                'broker': broker,
                'hour': hour,
                'balance': balance
            })
        return jsonify({'historic_balance_per_strategy': historical_balances_serializable})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/account_values')
def account_values():
    accounts = app.session.query(AccountInfo).all()
    accounts_data = {account.broker: account.value for account in accounts}
    return jsonify({'account_values': accounts_data})

# Additional routes
@app.route('/positions')
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
def get_trades():
    brokers = request.args.getlist('brokers[]')
    strategies = request.args.getlist('strategies[]')

    query = app.session.query(Trade)

    if brokers:
        query = query.filter(Trade.broker.in_(brokers))
    if strategies:
        query = query.filter(Trade.strategy.in_(strategies))

    trades = query.all()
    trades_data = [{'id': trade.id, 'broker': trade.broker, 'strategy': trade.strategy, 'symbol': trade.symbol, 'quantity': trade.quantity, 'price': trade.price, 'profit_loss': trade.profit_loss, 'timestamp': trade.timestamp} for trade in trades]

    return jsonify({'trades': trades_data})

@app.route('/trade_stats', methods=['GET'])
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

# Function to create the Flask app with SQLAlchemy session
def create_app(engine):
    Session = sessionmaker(bind=engine)
    app.session = Session()
    return app