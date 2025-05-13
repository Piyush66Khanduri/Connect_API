from flask import Flask, jsonify, request
import firebase_admin
from firebase_admin import credentials, firestore
import random
import smtplib
import json
import os
from email.mime.text import MIMEText

cred_dict = json.loads(os.environ['GOOGLE_APPLICATION_CREDENTIALS_JSON'])
cred = credentials.Certificate(cred_dict)
firebase_admin.initialize_app(cred)

db = firestore.client()
app = Flask(__name__)

@app.route('/register', methods=['POST'])
def register_user():
    try:
        name = request.json.get("name")
        gmail = request.json.get("gmail")

        if not name or not gmail:
            return jsonify({"error": "Name and Gmail are required"}), 400
        
        user_ref = db.collection("Connect_user").document(name)
        user_doc = user_ref.get()


        if user_doc.exists:
            return jsonify({"error": "User exists use a different Name"}), 400

        otp = generate_otp()
        user_ref.set({
            "name": name,
            "gmail": gmail,
            "otp": otp,
            "verified": False
        })

        send_email(gmail, otp)

        return jsonify({"message": "OTP sent to Gmail"}), 200
        

    except Exception as e:
        print(f"Error occurred: {e}")
        return jsonify({"error": "Internal server error", "message": str(e)}), 500
def generate_otp():
    return str(random.randint(100000, 999999))


def send_email(receiver_email, otp):
    sender_email = "mansinner666@gmail.com"  
    sender_password = "jfuaihaslyggigsl"      

    subject = "Verification OTP Code"
    body = f"Your OTP is: {otp}"

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = receiver_email

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)
    except Exception as e:
        print("Email send failed:", str(e))



@app.route('/verify', methods=['POST'])
def verify_otp():
    try:
        name = request.json.get("name")
        gmail = request.json.get("gmail")
        otp = request.json.get("otp")

        temp_ref = db.collection("Connect_user").document(name)
        temp_doc = temp_ref.get()

        if not temp_doc.exists:
            return jsonify({"error": "No such user pending verification"}), 404

        data = temp_doc.to_dict()

        if data["otp"] != otp or data["gmail"] != gmail:
            return jsonify({"error": "Invalid OTP or email"}), 400

        user_ref = db.collection("Connect_user").document(name)
        user_ref.set({
            "name": name,
            "gmail": gmail,
            "status": 1
        })


       

       

        return jsonify({"message": "User verified and registered"}), 200

    except Exception as e:
        print("Error in verify:", str(e))
        return jsonify({"error": "Internal server error", "message": str(e)}), 500

@app.route('/send_friend_request', methods=['POST'])
def send_friend_request():
    data = request.get_json()
    sender = data['sender']
    receiver = data['receiver']

    receiver_docs = list(db.collection(receiver).limit(1).stream())
    if not receiver_docs:
        return jsonify({"error": "User not found"}), 404

    db.collection(sender).document(receiver).set({
        "sender": sender,
        "receiver": receiver,
        "status": -1
    })

    db.collection(receiver).document(sender).set({
        "sender": sender,
        "receiver": receiver,
        "status": 0
    })

    return jsonify({"message": "Friend request sent"}), 200


@app.route('/respond_request', methods=['POST'])
def respond_request():
    data = request.get_json()
    sender = data['sender']
    receiver = data['receiver']
    status = data['status']  

    if status == 1:
        db.collection(receiver).document(sender).update({"status": 1})
        db.collection(sender).document(receiver).update({"status": 1})
        return jsonify({"message": "Friend request accepted"}), 200
    else:
        db.collection(receiver).document(sender).delete()
        db.collection(sender).document(receiver).delete()
        return jsonify({"message": "Friend request denied"}), 200


@app.route('/get_requests', methods=['GET'])
def get_requests():
    user = request.args.get("name")
    query = db.collection(user).where("status", "==", 0)
    docs = query.stream()
    result = [doc.to_dict()["sender"] for doc in docs]
    return jsonify(result), 200

@app.route('/get_friends', methods=['GET'])
def get_friends():
    user = request.args.get("name")
    
    query = db.collection(user).where("status", "==", 1)
    docs = query.stream()
    result = []
    for doc in docs:
        data = doc.to_dict()
        sender = data.get("sender")
        receiver = data.get("receiver")
        if sender == user:
            result.append(receiver)
        else:
            result.append(sender)
    return jsonify(result), 200

@app.route('/send_message', methods=['POST'])
def send_message():
    data = request.json
    sender = data.get("sender")
    receiver = data.get("receiver")
    message = data.get("message")

    if not sender or not receiver or not message:
        return jsonify({"error": "Invalid data"}), 400

  
    message_data = {
        "sender": sender,
        "message": message,
        "timestamp": firestore.SERVER_TIMESTAMP
    }

    db.collection(receiver).document(sender).collection("messages").add(message_data)

    db.collection(sender).document(receiver).collection("messages").add(message_data)
    return jsonify(), 200



@app.route('/get_messages', methods=['GET'])
def get_messages():
    user = request.args.get("name")
    friend = request.args.get("from")

    if not user or not friend:
        return jsonify({"error": "Missing user or friend"}), 400

    messages_ref = db.collection(user).document(friend).collection("messages")
    messages = messages_ref.order_by("timestamp").stream()

    result = []
    for msg in messages:
        data = msg.to_dict()
        sender = data.get("sender") or user  
        message = data.get("message", "")
        result.append({
            "sender": sender,
            "message": message
        })

    return jsonify(result), 200
@app.route('/')
def index():
    return 'Welcome to Piyush API'

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
