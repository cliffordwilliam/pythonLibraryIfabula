from flask import Flask, jsonify, request
import os
from dotenv import load_dotenv
from pymongo import MongoClient
import certifi  # https://stackoverflow.com/questions/54484890/ssl-handshake-issue-with-pymongo-on-python3

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

app = Flask(__name__)


@app.route("/register", methods=["POST"])
def register():
    try:
        db = get_db(os.getenv("MONGODB_DB_NAME"))
        # get body - FOR NOW USE POSTMAN (otherwise use request.json)
        body = {
            "name": request.form.get("name")
        }
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


# listen 5000
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)
