import os

env    = os.environ.get("FLASK_ENV", "DEV")
dbhost = os.environ.get("DB_HOST", "mongodb")


# Example configuration
class DefaultConfig(object):
    MONGO_DBNAME = "data_market"
    MONGO_HOST   = dbhost
    MONGO_PORT   = 27017
    DEBUG        = False if env == "PROD" else True


API_VER = 1
EXT_API_PORT = 443
INT_API_PORT = 8080

if env == "PROD":
    #  Production (public server) configuration
    API_PREFIX     = "/credits"
    COLLECTION_API = "http://collection-service:" + str(INT_API_PORT) + "/api/v1/collections"
    USER_API       = "http://user-service:" + str(INT_API_PORT) + "/api/v1/users"
    LOGIN_API      = USER_API + "/login"
    METER_API      = "http://meter-service:" + str(INT_API_PORT) + "/api/v1/meters"
else:
    #  Development (local) configuration
    EXT_API_GATEWAY = "https://api.smartcity.kmitl.io:" + str(EXT_API_PORT) + "/api/v1"
    #  EXT_API_GATEWAY = "https://203.154.59.55:" + str(EXT_API_PORT) + "/api/v1"
    API_PREFIX     = "/api/v" + str(API_VER) + "/credits"
    COLLECTION_API = EXT_API_GATEWAY + "/collections"
    USER_API       = EXT_API_GATEWAY + "/users"
    LOGIN_API      = USER_API + "/login"
    METER_API      = EXT_API_GATEWAY + "/meters"
