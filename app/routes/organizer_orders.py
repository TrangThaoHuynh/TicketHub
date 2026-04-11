from flask import Blueprint, render_template

organizer_bp = Blueprint('organizer', __name__)

@organizer_bp.route('/organizer/orders')
def organizer_orders():
    # demo data (tạm)
    orders = [
        {
            "id": "DH001",
            "customer_name": "Nguyễn Văn A",
            "customer_phone": "0934719411",
            "customer_email": "a@gmail.com",
            "ticket_count": 2,
            "total_amount": 2000000,
            "status": "paid"
        },
        {
            "id": "DH002",
            "customer_name": "Nguyễn Văn B",
            "customer_phone": "0123456789",
            "customer_email": "b@gmail.com",
            "ticket_count": 3,
            "total_amount": 3000000,
            "status": "unpaid"
        }
    ]

    return render_template("organizer_orders.html", orders=orders)

@organizer_bp.route('/organizer/orders/<order_id>')
def organizer_order_detail(order_id):
    # demo data (tạm)
    order = {
        "id": order_id,
        "customer_name": "Nguyễn Văn A",
        "customer_phone": "0934719411",
        "customer_email": "a@gmail.com",
        "ticket_count": 2,
        "total_amount": 2000000,
        "status": "paid"
    }

    return render_template("organizer_order_detail.html", order=order)