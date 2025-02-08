from flask import Flask, jsonify, render_template, request
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from database.models import Trade, AccountInfo, Balance, Position
import os

app = Flask('TradingAPI', template_folder='ui/templates')

DATABASE_URL = 'sqlite:///trading.db'
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
app.session = Session()

@app.route('/position_page')
def positions():
    try:
        return render_template('positions.html')
    except Exception as e:
        app.logger.error(f'Error rendering positions.html: {str(e)}')
        return 'Internal Server Error', 500

@app.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        app.logger.error(f'Error rendering index.html: {str(e)}')
        return 'Internal Server Error', 500

@app.route('/trades_per_strategy')
def trades_per_strategy():
    trades_count = app.session.query(Trade.strategy, Trade.broker, func.count(Trade.id)).group_by(Trade.strategy, Trade.broker).all()
    trades_count_serializable = [{'strategy': strategy, 'broker': broker, 'count': count} for strategy, broker, count in trades_count]
    return jsonify({'trades_per_strategy': trades_count_serializable})

@app.route('/historic_balance_per_strategy', methods=['GET'])
def historic_balance_per_strategy():
    with app.session() as session:
        try:
            historical_balances = session.query(
                Balance.strategy,
                Balance.broker,
                func.strftime('%Y-%m-%d %H', Balance.timestamp).label('hour'),
                Balance.total_balance,
            ).group_by(
                Balance.strategy, Balance.broker, 'hour'
            ).order_by(
                Balance.strategy, Balance.broker, 'hour'
            ).all()
            historical_balances_serializable = []
            for strategy, broker, hour, total_balance in historical_balances:
                historical_balances_serializable.append({
                    "strategy": strategy,
                    "broker": broker,
                    "hour": hour,
                    "total_balance": total_balance
                })
            return jsonify({'historic_balance_per_strategy': historical_balances_serializable})
        finally:
            session.close()

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
            "strategy": strategy,
            "broker": broker,
            "total_trades": total_trades,
            "successful_trades": successful_trades,
            "failed_trades": failed_trades
        })

    return jsonify({'trade_success_rate': success_rate_by_strategy_and_broker})

@app.route('/positions', methods=['GET'])
def get_positions():
    brokers = request.args.getlist('brokers[]')
    strategies = request.args.getlist('strategies[]')

    query = app.session.query(Position, Balance).join(Balance, Position.balance_id == Balance.id)

    if brokers:
        query = query.filter(Balance.broker.in_(brokers))
    if strategies:
        query = query.filter(Balance.strategy.in_(strategies))

    positions = query.all()
    positions_data = []
    for position, balance in positions:
        positions_data.append({
            "broker": balance.broker,
            "strategy": balance.strategy,
            "symbol": position.symbol,
            "quantity": position.quantity,
            "latest_price": position.latest_price,
            "timestamp": balance.timestamp
        })

    return jsonify({'positions': positions_data})

# Static files are served automatically from the 'static' folder

def create_app(engine):
    Session = sessionmaker(bind=engine)
    app.session = Session()
    return app