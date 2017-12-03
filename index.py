from flask import Flask, request, render_template, url_for, redirect, abort, jsonify
from flask_pymongo import PyMongo
from pymongo import ReturnDocument
import requests

# Custom modules and packages
import appconfig

app = Flask(__name__)
app.config.from_object("appconfig.DevConfig")

mongo = PyMongo(app)
ticketRate = 100


@app.route(appconfig.API_PREFIX + "/credits/<userId>")
def getUserCredits(userId):
    userCredits = mongo.db.user_credits.find_one({"userId": userId}, {"_id": False})

    if userCredits is not None:
        credits, ts = calCredits(userId, userCredits.get("timestamp", 0))

        if ts != 0:
            userCredits = mongo.db.user_credits.find_one_and_update(
                    {"userId": userId},
                    {"$inc": {"credits": credits}, "$set": {"timestamp": ts}},
                    {"_id": False},
                    return_document=ReturnDocument.AFTER)

        return jsonify(userCredits), 200

    return syncUserCredits(userId)


@app.route(appconfig.API_PREFIX + "/credits/transactions/", methods=['POST'])
def transfer():
    if request.is_json:
        incomData = request.get_json()
        amount = incomData.get("amount", 0)
        src = mongo.db.user_credits.find_one({"userId": incomData.get("from", "")}, {"_id": False})

        # couldn't find "from"
        if src is None:
            return jsonify({
                "status": "failed",
                "message": "couldn't find user " + incomData.get("from", "<blank userId>"),
                "is_transfered": False}), 400

        if (not (amount > 0)) or (src.get("credits", 0) < amount):
            return jsonify({
                "status": "failed",
                "message": "invalid transaction",
                "is_transfered": False}), 400

        # add amount
        result = mongo.db.user_credits.update_one(
            {"userId": incomData.get("to", "")},
            {"$inc": {"credits": amount}})

        # @TODO add to log file
        if result.modified_count != 1:
            return jsonify({
                "status": "failed",
                "message": "couldn't add the amount to " + incomData.get("to", "<blank userId>"),
                "is_transfered": False}), 400

        #subtract amount
        result = mongo.db.user_credits.update_one(
            {"userId": incomData.get("from", "")},
            {"$inc": {"credits": - amount}})

        # @TODO add to log file
        if result.modified_count != 1:
            return jsonify({
                "status": "failed",
                "message": "couldn't subtract the amount from " + incomData.get("from", "<blank userId>"),
                "is_transfered": False}), 400

        return jsonify({
            "status": "successful",
            "message": "transaction completed",
            "is_transfered": True}), 200


def syncUserCredits(userId):
    query = {"userId": userId}
    resp = requests.get(appconfig.EXT_API_GATEWAY + "/users", params=query)
    users = resp.json()

    if len(users) == 1:
        credits, ts = calCredits(userId, 0)
        user = {"userId": users[0].get("userId", ""), "credits": credits, "timestamp": ts}
        mongo.db.user_credits.insert_one(user)
        userCredits = mongo.db.user_credits.find_one({"userId": userId}, {"_id": False})

        return jsonify(userCredits), 200

    return jsonify({"status": "failed", "message": "no userId found", "userId": 0}), 400


def calCredits(userId, timestamp):
    query = {"userId": userId}

    if timestamp != 0:
        query["timestamp"] = timestamp

    resp = requests.get(appconfig.EXT_API_GATEWAY + "/meters", params=query)
    meters = resp.json()

    if len(meters) >= 1:
        return sumCredits(meters)

    return 0, 0


def sumCredits(meters):
    accum = 0
    ts = 0

    for meter in meters:
        accum += meter.get("size", 0) * (2 if meter.get("open", False) else 1)
        ts = (meter.get("timestamp", 0) if meter.get("timestamp", 0) > ts else ts)

    return accum, ts
