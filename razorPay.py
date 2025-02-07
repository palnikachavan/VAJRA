from flask import Flask, render_template, request, jsonify
import razorpay
import hashlib
import hmac
import json
from config import RAZORPAY_API_KEY, RAZORPAY_API_SECRET

app = Flask(__name__, static_folder="static", static_url_path="")

razorpay_client = razorpay.Client(auth=(RAZORPAY_API_KEY, RAZORPAY_API_SECRET))


@app.route('/')
def app_create():
    return render_template('app.html', key_id=RAZORPAY_API_KEY)


@app.route('/create_order', methods=['POST'])
def create_order():
    try:
        amount = 5100  
        order_data = {
            "amount": amount,
            "currency": "USD",
            "payment_capture": "1"
        }
        order = razorpay_client.order.create(data=order_data)
        return jsonify(order)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route('/verify_payment', methods=['POST'])
def verify_payment():
    try:
        data = request.form
        order_id = data.get("razorpay_order_id")
        payment_id = data.get("razorpay_payment_id")
        signature = data.get("razorpay_signature")

        if not order_id or not payment_id or not signature:
            return jsonify({"status": "error", "message": "Missing parameters"}), 400

        generated_signature = hmac.new(
            bytes(RAZORPAY_API_SECRET, 'utf-8'),
            bytes(f"{order_id}|{payment_id}", 'utf-8'),
            hashlib.sha256
        ).hexdigest()

        if generated_signature == signature:
            return render_template("success.html", payment_id=payment_id, order_id=order_id)
        else:
            return jsonify({"status": "failure", "message": "Signature mismatch!"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


if __name__ == '__main__':
    app.run(debug=True)
