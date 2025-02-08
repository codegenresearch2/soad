from sqlalchemy import Column, Integer, String, Float, DateTime, create_engine, ForeignKey\\nfrom sqlalchemy.ext.declarative import declarative_base\nfrom sqlalchemy.orm import sessionmaker, relationship\nfrom datetime import datetime\n\\\nBase = declarative_base()\n\\\nclass Trade(Base):\n    __tablename__ = 'trades'\n    \\nid = Column(Integer, primary_key=True)\n    symbol = Column(String, nullable=False)\n    quantity = Column(Integer, nullable=False)\n    price = Column(Float, nullable=False)\n    executed_price = Column(Float, nullable=True)\n    order_type = Column(String, nullable=False)\n    status = Column(String, nullable=False)\n    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)\n    broker = Column(String, nullable=False)\n    strategy = Column(String, nullable=False)\n    profit_loss = Column(Float, nullable=True)\n    success = Column(String, nullable=True)\n    balance_id = Column(Integer, ForeignKey('balances.id'))\n\nclass AccountInfo(Base):\n    __tablename__ = 'account_info'\n    id = Column(Integer, primary_key=True, autoincrement=True)\n    broker = Column(String, unique=True)\n    value = Column(Float)\n\nclass Balance(Base):\n    __tablename__ = 'balances'\n    id = Column(Integer, primary_key=True, autoincrement=True)\n    broker = Column(String)\n    strategy = Column(String)\n    initial_balance = Column(Float, default=0.0)\n    total_balance = Column(Float, default=0.0)\n    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)\n    trades = relationship('Trade', backref='balance')\n    positions = relationship('Position', back_populates='balance')\n\nclass Position(Base):\n    __tablename__ = 'positions'\n\nid = Column(Integer, primary_key=True, autoincrement=True)\nbalance_id = Column(Integer, ForeignKey('balances.id'), nullable=False)\nsymbol = Column(String, nullable=False)\nquantity = Column(Float, nullable=False)\nlatest_price = Column(Float, nullable=False)\ndefault_updated = Column(DateTime, default=datetime.utcnow)\n\nbalance = relationship('Balance', back_populates='positions')\n\ndef drop_then_init_db(engine):\n    """Drops existing tables and creates new tables."""\n    Base.metadata.drop_all(engine)\n    Base.metadata.create_all(engine)\n\ndef init_db(engine):\n    """Creates new tables."""\n    Base.metadata.create_all(engine)\n