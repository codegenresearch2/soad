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

@app.route('/trade_success_rate')
def trade_success_rate():
    strategies_and_brokers = app.session.query(Trade.strategy, Trade.broker).distinct().all()
    success_rate_by_strategy_and_broker = []

    for strategy, broker in strategies_and_brokers:
        total_trades = app.session.query(func.count(Trade.id)).filter(Trade.strategy == strategy, Trade.broker == broker).scalar()
        successful_trades = app.session.query(func.count(Trade.id)).filter(Trade.strategy == strategy, Trade.broker == broker, Trade.profit_loss > 0).scalar()
        failed_trades = total_trades - successful_trades

        success_rate_by_strategy_and_broker.append({
            'strategy': strategy,
            'broker': broker,
            'total_trades': total_trades,
            'successful_trades': successful_trades,
            'failed_trades': failed_trades
        })

    return jsonify({'trade_success_rate': success_rate_by_strategy_and_broker})

# Additional routes and functions...

# Function to create the Flask app with SQLAlchemy session
def create_app(engine):
    Session = sessionmaker(bind=engine)
    app.session = Session()
    return app