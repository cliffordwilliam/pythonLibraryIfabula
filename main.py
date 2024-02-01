from flask import Flask, jsonify, request
from flask_cors import CORS
import os
from dotenv import load_dotenv
from pymongo import MongoClient
import certifi  # https://stackoverflow.com/questions/54484890/ssl-handshake-issue-with-pymongo-on-python3
import re
import jwt

ca = certifi.where()
load_dotenv()

connection_string = os.getenv("MONGODB_CONNECTION_STRING")

if not connection_string:
    raise ValueError("MONGODB_CONNECTION_STRING is not defined")

client = None


def get_client():
    global client
    if not client:
        client = MongoClient(connection_string, tlsCAFile=ca)
    return client


def get_db(name):
    mongo_client = get_client()
    db = mongo_client[name]
    return db


# CONST
USER_COLLECTION = "users"
BOOK_COLLECTION = "books"

app = Flask(__name__)
CORS(app)


@app.route("/register", methods=["POST"])
def register():
    try:
        # get db
        db = get_db(os.getenv("MONGODB_DB_NAME"))
        # get body - FOR NOW USE POSTMAN (otherwise use request.json)
        body = {
            "email": request.form.get("email"),
            "password": request.form.get("password"),
            "book": "",
            "status": "Regular"
        }
        # email harus merupakan domain email yang benar (contoh: @gmail.com, @hotmail.com etc).
        if not re.match(r"[^@]+@[^@]+\.[^@]+", body["email"]):
            return jsonify({"error": "Invalid email format"}), 400
        # password harus terdiri dari 8 Karakter Alphanumeric dan harus mengandung setidaknya 1 huruf kapital, tidak boleh mengandung special karakter.
        if not (len(body["password"]) >= 8 and any(char.isupper() for char in body["password"]) and body["password"].isalnum()):
            return jsonify({"error": "Invalid password format"}), 400
        # tidak dapat register dengan email yang sama.
        existing_user = db[USER_COLLECTION].find_one({"email": body["email"]})
        if existing_user:
            # 409 Conflict
            return jsonify({"error": "Email already exists"}), 409
        # POST
        result = db[USER_COLLECTION].insert_one(body)
        # ok?
        if result.inserted_id:
            return jsonify({"msg": "User registered successfully"}), 201
        # bad?
        else:
            return jsonify({"error": "Failed to register user"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/login", methods=["POST"])
def login():
    try:
        # get db
        db = get_db(os.getenv("MONGODB_DB_NAME"))
        # get body
        body = {
            "email": request.form.get("email"),
            "password": request.form.get("password"),
        }
        # email harus merupakan domain email yang benar (contoh: @gmail.com, @hotmail.com etc).
        if not re.match(r"[^@]+@[^@]+\.[^@]+", body["email"]):
            return jsonify({"error": "Invalid email format"}), 400
        # password harus terdiri dari 8 Karakter Alphanumeric dan harus mengandung setidaknya 1 huruf kapital, tidak boleh mengandung special karakter.
        if not (len(body["password"]) >= 8 and any(char.isupper() for char in body["password"]) and body["password"].isalnum()):
            return jsonify({"error": "Invalid password format"}), 400
        # tidak dapat register dengan email yang sama.
        existing_user = db[USER_COLLECTION].find_one({"email": body["email"]})
        if not existing_user:
            # 409 Conflict
            return jsonify({"error": "User not found"}), 404
        # bad password?
        if str(body["password"]) != str(existing_user["password"]):
            return jsonify({"error": "Incorrect password"}), 401
        # payload -> token
        token = jwt.encode({"email": existing_user["email"]}, os.getenv(
            "JWT_SECRET"), algorithm="HS256")
        # return existing user + token here
        return jsonify({
            "msg": "Login successful",
            "user": {
                "email": existing_user["email"],
                "book": existing_user["book"],
                "status": existing_user["status"],
            },
            "token": token
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/books", methods=["GET"])
def books():
    try:
        # get db
        db = get_db(os.getenv("MONGODB_DB_NAME"))
        # GET
        books = [{"_id": str(book["_id"]),
                  "title": book["title"],
                  "author": book["author"],
                  "image": book["image"],
                  "status": book["status"], } for book in db[BOOK_COLLECTION].find()]
        # return
        return jsonify({
            "msg": "Books retrieved successfully",
            "books": books,
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/borrow/<book_title>", methods=["PATCH"])
def borrow(book_title):
    try:
        # get auth header
        auth_header = request.headers.get("Authorization")
        # no auth header?
        if not auth_header:
            return jsonify({"error": "Unauthorized"}), 401
        # get token
        token = auth_header.split(
            "Bearer ")[1] if "Bearer " in auth_header else auth_header
        # token -> payload
        try:
            decoded_token = jwt.decode(token, os.getenv(
                "JWT_SECRET"), algorithms=["HS256"])
            loggedin_user_email = decoded_token.get("email")
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
        # get db
        db = get_db(os.getenv("MONGODB_DB_NAME"))
        # GET
        book = db[BOOK_COLLECTION].find_one({"title": book_title})
        # no book?
        if not book:
            return jsonify({"error": "Book not found"}), 404
        # borrowed alr?
        if book["status"] == "borrowed":
            return jsonify({"error": "Book is already borrowed"}), 400
        # (book) not borrowed -> borrowed
        db[BOOK_COLLECTION].update_one(
            {"title": book_title}, {"$set": {"status": "borrowed"}})
        # (user) book -> book title
        db[USER_COLLECTION].update_one({"email": loggedin_user_email}, {
                                       "$set": {"book": book_title}})
        # return
        return jsonify({
            "msg": "Book borrowed successfully",
            "book": book_title,
            "borrower": loggedin_user_email
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/returnBook/<book_title>", methods=["PATCH"])
def returnBook(book_title):
    try:
        # get auth header
        auth_header = request.headers.get("Authorization")
        # no auth header?
        if not auth_header:
            return jsonify({"error": "Unauthorized"}), 401
        # get token
        token = auth_header.split(
            "Bearer ")[1] if "Bearer " in auth_header else auth_header
        # token -> payload
        try:
            decoded_token = jwt.decode(token, os.getenv(
                "JWT_SECRET"), algorithms=["HS256"])
            loggedin_user_email = decoded_token.get("email")
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
        # get db
        db = get_db(os.getenv("MONGODB_DB_NAME"))
        # GET
        book = db[BOOK_COLLECTION].find_one({"title": book_title})
        # no book?
        if not book:
            return jsonify({"error": "Book not found"}), 404
        # returned alr?
        if book["status"] == "not borrowed":
            return jsonify({"error": "Book is already returned"}), 400
        # (book) borrowed -> not borrowed
        db[BOOK_COLLECTION].update_one(
            {"title": book_title}, {"$set": {"status": "not borrowed"}})
        # (user) book -> ""
        db[USER_COLLECTION].update_one({"email": loggedin_user_email}, {
                                       "$set": {"book": ""}})
        # return
        return jsonify({
            "msg": "Book returned successfully",
            "book": book_title,
            "borrower": loggedin_user_email
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# listen 8080
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)
