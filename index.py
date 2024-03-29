from flask import Flask, request, jsonify
from flask_pymongo import PyMongo
import requests
import time
import uuid

# Custom modules and packages
import appconfig

app = Flask(__name__)
app.config.from_object("appconfig.DefaultConfig")
mongo = PyMongo(app)
ticketRate = 100


@app.route(appconfig.API_PREFIX + "/")
def getAllUserCredits():
    userCredits = mongo.db.user_credits.find(
            {},
            {"_id": False, "timestamp": False})
    return jsonify(list(userCredits)), 200


@app.route(appconfig.API_PREFIX + "/<userId>/")
def getUserCredits(userId):
    retResp = {"success": False, "message": ""}
    httpCode = 400

    try:
        credits = getCredits(userId)
    except (requests.ConnectionError, requests.ConnectTimeout) as e:
        retResp["message"] = e.__str__()
        httpCode = 500
    except Exception as e:
        retResp["message"] = e.args[1]
        httpCode = e.args[0]
    else:
        retResp = {"userId": userId, "credits": credits}
        httpCode = 200

    return jsonify(retResp), httpCode


@app.route(appconfig.API_PREFIX + "/transactions/", methods=['POST'])
def createTranscation():
    retResp = {"success": False, "message": ""}
    isTransferred = False
    httpCode = 400

    if not request.is_json:
        retResp["message"] = "invalid request body type, expected JSON"
        return jsonify(retResp), httpCode

    incomData = request.get_json()
    ttype = incomData.get("type", "")

    if not isValidTransactionType(ttype):
        retResp["message"] = "invalid transaction type"
        return jsonify(retResp), httpCode

    buyer = incomData.get("from", "")
    seller = incomData.get("to", "")
    collectionId = incomData.get("collectionId", "")
    amount = getPrice(collectionId) if ttype == "TCKT" else incomData.get("amount", 0)

    if amount is None:
        retResp["message"] = "couldn't find collection " + collectionId
        return jsonify(retResp), httpCode

    try:
        isTransferred = transfer(buyer, seller, amount)
    except (requests.ConnectionError, requests.ConnectTimeout) as e:
        retResp["message"] = e.__str__()
        httpCode = 503
    except Exception as e:
        retResp["message"] = e.args[1]
        httpCode = e.args[0]
    else:
        if not isTransferred:
            retResp["message"] = "invalid amount of credits"
            return jsonify(retResp), httpCode

        transaction = {
                "id": str(uuid.uuid1()),
                "from": buyer,
                "to": seller,
                "amount": amount,
                "type": ttype,
                "created_at": int(time.time())}

        mongo.db.transaction.insert_one(transaction)

        retResp["message"] = "transaction completed"
        retResp["success"] = True
        httpCode = 201

    return jsonify(retResp), httpCode


def transfer(srcUserId, dstUserId, amount):
    if srcUserId == dstUserId:
        return True

    try:
        srcCredits = getCredits(srcUserId)

        # Just to sync the credits
        getCredits(dstUserId)
    except (requests.ConnectionError, requests.ConnectTimeout, Exception):
        raise

    if (not (amount > 0)) or (srcCredits < amount):
        return False

    mongo.db.user_credits.update_one(
        {"userId": dstUserId},
        {"$inc": {"credits": amount}})

    mongo.db.user_credits.update_one(
        {"userId": srcUserId},
        {"$inc": {"credits": - amount}})

    return True


# @TODO
# This function should sync the price of collections
# in the DB and return the correct price to the caller.
# Since for now, we're gonna use a fixed the price,
# so just return smth.
def getPrice(collectionId):
    collectionPrice = mongo.db.collection_price.find_one(
            {"collectionId": collectionId},
            {"_id": False})
    price = None

    if collectionPrice is not None:
        price = ticketRate
    else:
        price = syncCollectionPrice(collectionId)

    return price


def syncCollectionPrice(collectionId):
    #  query = {"collectionId": collectionId}
    price = None

    try:
        resp = requests.get(
                appconfig.COLLECTION_API +
                "/" +
                collectionId +
                "/meta")
    except requests.ConnectionError:
        print("syncCollectionPrice: couldn't connect to external service")
        raise
    except requests.ConnectTimeout:
        print("syncCollectionPrice: connection to external service timeout")
        raise
    else:
        if resp.status_code != 200:
            print("syncCollectionPrice: Unknown external service error " +
                  str(resp.status_code))
            raise Exception(resp.status_code, "Unknown external service error")

        collections = resp.json()

        if len(collections) != 1:
            print("syncCollectionPrice: couldn't find collection " +
                  collectionId)
            raise Exception(400, "couldn't find collection " + collectionId)

        collectionPrice = {
                "collectionId": collections[0].get("collectionId", "")}
        mongo.db.collection_price.insert_one(collectionPrice)
        price = ticketRate
    finally:
        return price


def getCredits(userId):
    credits = 0
    userCredits = mongo.db.user_credits.find_one(
            {"userId": userId},
            {"_id": False})

    if userCredits is not None:
        ts = 0
        marginCredits = 0
        credits = userCredits.get("credits", 0)

        try:
            marginCredits, ts = calCredits(
                    userId,
                    userCredits.get("timestamp", 0))
        except (requests.ConnectionError, requests.ConnectTimeout):
            raise

        if ts != 0:
            mongo.db.user_credits.update_one(
                    {"userId": userId},
                    {"$inc": {
                        "credits": marginCredits},
                        "$set": {"timestamp": ts}})

            credits += marginCredits
    else:
        try:
            credits = syncUserCredits(userId)
        except (requests.ConnectionError, requests.ConnectTimeout, Exception):
            raise

    return credits


def syncUserCredits(userId):
    query = {"userId": userId}
    credits = 0
    resp = None

    try:
        resp = requests.get(appconfig.USER_API, params=query)
    except requests.ConnectionError:
        print("syncUserCredits: couldn't connect to external service")
        raise
    except requests.ConnectTimeout:
        print("syncUserCredits: connection to external service timeout")
        raise

    if resp.status_code == 200:
        users = resp.json()

        if len(users) == 1:
            credits, ts = calCredits(userId, 0)
            user = {
                    "userId": users[0].get("userId", ""),
                    "credits": credits,
                    "timestamp": ts}
            mongo.db.user_credits.insert_one(user)
        else:
            print("syncUserCredits: couldn't find user " + userId)
            raise Exception(400, "couldn't find user " + userId)
    else:
        print("syncUserCredits: Unknown external service error " +
              str(resp.status_code))
        raise Exception(resp.status_code, "Unknown external service error")

    return credits


def calCredits(userId, timestamp):
    credits = 0
    ts = 0
    query = {"userId": userId}

    if timestamp != 0:
        query["timestamp"] = timestamp

    try:
        resp = requests.get(appconfig.METER_API, params=query)
    except requests.ConnectionError:
        print("calCredits: couldn't connect to external service")
        raise
    except requests.ConnectTimeout:
        print("calCredits: connection to external service timeout")
        raise
    else:
        if resp.status_code == 200:
            meters = resp.json()

            if len(meters) >= 1:
                credits, ts = sumCredits(meters)
    finally:
        return credits, ts


def sumCredits(meters):
    accum = 0
    ts = 0

    for meter in meters:
        accum += meter.get("size", 0) * (2 if meter.get("open", False) else 1)
        ts = meter.get("timestamp", 0) if meter.get("timestamp", 0) > ts else ts

    return accum, ts


def isValidTransactionType(t):
    return t in ["TCKT", "NORM"]
