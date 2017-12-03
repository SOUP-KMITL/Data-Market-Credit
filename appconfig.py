# Example configuration
class DevConfig(object):
    DEBUG = True
    MONGO_DBNAME = "data_market"
    MONGO_HOST = "localhost"
    MONGO_PORT = 27017

API_VER = "/v1"
API_PREFIX = "/api" + API_VER

EXT_API_PORT = 8080
EXT_API_VER = "/v1"
EXT_API_GATEWAY = "http://api.smartcity.kmitl.io:" + str(EXT_API_PORT) + "/api" + EXT_API_VER
