from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()

# SQLAlchemy 모델 예시
class ItemMaster(db.Model):
    __tablename__ = 'itemmaster'
    itemcode = db.Column(db.String(50), primary_key=True)
    itemname = db.Column(db.String(100))
    spec = db.Column(db.String(100))
    unit = db.Column(db.String(20))
    purchaseprice = db.Column(db.Float)
    salesprice = db.Column(db.Float)
    usage = db.Column(db.String(1))
    remarks = db.Column(db.String(200))
