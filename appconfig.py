# Example configuration
class DefaultConfig(object):
    DEBUG = True
    MONGO_DBNAME = "data_market"
    MONGO_HOST = "localhost"
    MONGO_PORT = 27017


API_VER    = 1

EXT_API_PORT    = 8080
#  EXT_API_GATEWAY = "http://api.smartcity.kmitl.io:" + str(EXT_API_PORT) + "/api/v1"
EXT_API_GATEWAY = "http://203.154.59.55:" + str(EXT_API_PORT) + "/api/v1"

#  Production (public server) configuration
#  API_PREFIX     = "/credits"
#  COLLECTION_API = "http://collection-service:" + str(EXT_API_PORT) + "/api/v1/collections"
#  USER_API       = "http://user-service:" + str(EXT_API_PORT) + "/api/v1/users"
#  LOGIN_API      = USER_API + "/login"
#  METER_API      = "http://meter-service:" + str(EXT_API_PORT) + "/api/v1/meters"

#  Development (local) configuration
API_PREFIX     = "/api/v" + str(API_VER) + "/credits"
COLLECTION_API = EXT_API_GATEWAY + "/collections"
USER_API       = EXT_API_GATEWAY + "/users"
LOGIN_API      = USER_API + "/login"
METER_API      = EXT_API_GATEWAY + "/meters"

SECRET = "some secret"
