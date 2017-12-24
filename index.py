from flask import Flask, request, jsonify
from flask_pymongo import PyMongo
from pymongo import ReturnDocument
import requests
#  import json

# Custom modules and packages
import appconfig

app = Flask(__name__)
app.config.from_object("appconfig.DefaultConfig")
mongo = PyMongo(app)
ticketRate = 100


@app.route(appconfig.API_PREFIX + "/<userId>/")
def getViewCredits(userId):
    retResp, httpCode = getCredits(userId)
    return jsonify(retResp), httpCode


@app.route(appconfig.API_PREFIX + "/transactions/", methods=['POST'])
def createTranscation():
    retResp = {"status": "failed", "message": "", "is_transfered": False}
    httpCode = 400

    if request.is_json:
        incomData = request.get_json()
        buyer = incomData.get("buyer", "")
        seller = incomData.get("seller", "")
        collectionId = incomData.get("collectionId", "")
        amount = getPrice(collectionId)

        if amount is not None:
            retResp, httpCode = transfer(buyer, seller, amount)
        else:
            retResp["message"] = "couldn't find collection " + collectionId
    else:
        retResp["message"] = "invalid request body type, expected JSON"

    return jsonify(retResp), httpCode


def transfer(srcUserId, dstUserId, amount):
    retResp = {"status": "failed", "message": "", "is_transfered": False}
    httpCode = 400

    if srcUserId == dstUserId:
        retResp["status"] = "successful"
        retResp["is_transfered"] = True
        httpCode = 200
    else:
        src, srcStatus = getCredits(srcUserId)
        dst, dstStatus = getCredits(dstUserId)

        if srcStatus != 200:
            retResp["message"] = "couldn't find src user " + getRtrnUserId(srcUserId)
            httpCode = 404
        elif dstStatus != 200:
            retResp["message"] = "couldn't find dst user " + getRtrnUserId(dstUserId)
            httpCode = 404
        elif (not (amount > 0)) or (src.get("credits", 0) < amount):
            retResp["message"] = "invalid transaction"
        else:
            mongo.db.user_credits.update_one(
                {"userId": dstUserId},
                {"$inc": {"credits": amount}})

            mongo.db.user_credits.update_one(
                {"userId": srcUserId},
                {"$inc": {"credits": - amount}})

            retResp["status"] = "successful"
            retResp["message"] = "transaction completed"
            retResp["is_transfered"] = True
            httpCode = 200

    return retResp, httpCode


# @TODO
# This function should sync the price of collections
# in the DB and return the correct price to the caller.
# Since for now, we're gonna fix the price, so just return smth.
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
        resp = requests.get(appconfig.COLLECTION_API + "/" + collectionId + "/meta")
    except requests.ConnectionError:
        # TODO log error
        print("syncCollectionPrice: couldn't connect to external service")
    except requests.ConnectTimeout:
        # TODO log error
        print("syncCollectionPrice: connection to external service timeout")
    else:
        print("syncCollectionPrice: " + getRtrnMsg(resp.status_code))

        if resp.status_code == 200:
            collections = resp.json()

            if len(collections) == 1:
                collectionPrice = {"collectionId": collections[0].get("collectionId", "")}
                mongo.db.collection_price.insert_one(collectionPrice)

                price = ticketRate
            else:
                # TODO log error
                print("syncCollectionPrice: couldn't find collection " + collectionId)
    finally:
        return price


def getCredits(userId):
    userCredits = mongo.db.user_credits.find_one(
            {"userId": userId},
            {"_id": False})
    retResp = {"status": "failed", "message": "", "credits": None}

    if userCredits is not None:
        retResp["status"] = "successful"
        retResp["credits"] = userCredits.get("credits", 0)
        credits, ts = calCredits(userId, userCredits.get("timestamp", 0))

        if ts != 0:
            userCredits = mongo.db.user_credits.find_one_and_update(
                    {"userId": userId},
                    {"$inc": {"credits": credits}, "$set": {"timestamp": ts}},
                    {"_id": False},
                    return_document=ReturnDocument.AFTER)
            retResp["credits"] += credits

        return retResp, 200
    else:
        return syncUserCredits(userId)


def syncUserCredits(userId):
    query = {"userId": userId}
    retResp = {"status": "failed", "message": "", "credits": None}
    httpCode = 400

    try:
        resp = requests.get(appconfig.USER_API, params=query)
    except requests.ConnectionError:
        retResp["message"] = "couldn't connect to external service"
    except requests.ConnectTimeout:
        retResp["message"] = "connection to external service timeout"
    else:
        retResp["message"] = getRtrnMsg(resp.status_code)

        if resp.status_code == 200:
            users = resp.json()

            if len(users) == 1:
                credits, ts = calCredits(userId, 0)
                user = {
                        "userId": users[0].get("userId", ""),
                        "credits": credits,
                        "timestamp": ts}
                mongo.db.user_credits.insert_one(user)

                retResp["status"] = "successful"
                retResp["credits"] = credits
                httpCode = 200
            else:
                retResp["message"] = "couldn't find user " + userId
                httpCode = 404
    finally:
        return retResp, httpCode


def calCredits(userId, timestamp):
    credits = 0
    ts = 0
    query = {"userId": userId}

    if timestamp != 0:
        query["timestamp"] = timestamp

    try:
        resp = requests.get(appconfig.METER_API, params=query)
    except requests.ConnectionError:
        # TODO log error
        print("calCredits: couldn't connect to external service")
    except requests.ConnectTimeout:
        # TODO log error
        print("calCredits: connection to external service timeout")
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
        ts = (meter.get("timestamp", 0) if meter.get("timestamp", 0) > ts else ts)

    return accum, ts


def getRtrnMsg(code):
    return {
            400: "Bad request",
            500: "external service error",
            200: ""}.get(code, "Unknown external service error: " + str(code))


def getRtrnUserId(userId):
    return "<blank userId>" if not userId else userId
