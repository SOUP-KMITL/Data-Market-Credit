from flask import Flask, request, jsonify
from flask_pymongo import PyMongo
import requests
#  import json

# Custom modules and packages
import appconfig

app = Flask(__name__)
app.config.from_object("appconfig.DefaultConfig")
mongo = PyMongo(app)
ticketRate = 100


@app.route(appconfig.API_PREFIX + "/<userId>/")
def getUserCredits(userId):
    retResp = {"status": "failed", "message": "", "credits": -1}
    httpCode = 400

    try:
        credits = getCredits(userId)
    except (requests.ConnectionError, requests.ConnectTimeout, Exception) as e:
        retResp["message"] = e.__str__()
    else:
        retResp["status"] = "successful"
        retResp["credits"] = credits
        httpCode = 200

    return jsonify(retResp), httpCode


@app.route(appconfig.API_PREFIX + "/transactions/", methods=['POST'])
def createTranscation():
    retResp = {"status": "failed", "message": "", "isTransferred": False}
    httpCode = 400

    if request.is_json:
        incomData = request.get_json()
        buyer = incomData.get("buyer", "")
        seller = incomData.get("seller", "")
        collectionId = incomData.get("collectionId", "")
        amount = getPrice(collectionId)

        if amount is not None:
            try:
                retResp["isTransferred"] = transfer(buyer, seller, amount)
            except (requests.ConnectionError, requests.ConnectTimeout, Exception) as e:
                retResp["message"] = e.__str__()
            else:
                if retResp.get("isTransferred", False):
                    retResp["message"] = "transaction completed"
                    retResp["status"] = "successful"
                    httpCode = 200
                else:
                    retResp["message"] = "invalid amount of credits"
        else:
            retResp["message"] = "couldn't find collection " + collectionId
    else:
        retResp["message"] = "invalid request body type, expected JSON"

    return jsonify(retResp), httpCode


#  @app.route(appconfig.API_PREFIX + "/test/")
#  def test():
#      userCredits = mongo.db.user_credits.find({}, {"_id": False, "timestamp": False})
#      return jsonify(list(userCredits)), 200


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
    credits = 0
    userCredits = mongo.db.user_credits.find_one(
            {"userId": userId},
            {"_id": False})

    if userCredits is not None:
        ts = 0
        marginCredits = 0
        credits = userCredits.get("credits", 0)

        try:
            marginCredits, ts = calCredits(userId, userCredits.get("timestamp", 0))
        except (requests.ConnectionError, requests.ConnectTimeout):
            raise

        if ts != 0:
            mongo.db.user_credits.update_one(
                    {"userId": userId},
                    {"$inc": {"credits": marginCredits}, "$set": {"timestamp": ts}})

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
            raise Exception("couldn't find user " + userId)
    else:
        print("syncUserCredits: external service returned with unexpected value")
        raise Exception("external service returned with unexpected value")

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
        ts = (meter.get("timestamp", 0) if meter.get("timestamp", 0) > ts else ts)

    return accum, ts


def getRtrnMsg(code):
    return {
            400: "Bad request",
            500: "external service error",
            200: ""}.get(code, "Unknown external service error: " + str(code))


def getRtrnUserId(userId):
    return "<blank userId>" if not userId else userId
