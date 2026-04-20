from ..models.payment import Payment
from .. import db

def create_payment(data):
    payment = Payment(
        amount=data.get("amount"),
        transactionID=data.get("transactionID"),
        vnpTxnRef=data.get("vnpTxnRef"),
        vnpPayDate=data.get("vnpPayDate"),
        status=data.get("status"),
        bookingId=data.get("bookingId")
    )

    db.session.add(payment)
    db.session.commit()

    return payment