"""Sony LGTG-200 cloud API constants."""

# AWS region
REGION = "ap-northeast-1"

# Cognito User Pool
USER_POOL_ID = "ap-northeast-1_gviHAAjjj"
CLIENT_ID = "6ohtpjrih0i9gikh0torp8f94d"

# Cognito Identity Pool
IDENTITY_POOL_ID = "ap-northeast-1:22fb561a-0645-4de7-a66d-4b09e9a2f1cc"

# Logins key for the User Pool
LOGINS_KEY = f"cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}"

# AppSync endpoints
APPSYNC_MAIN = (
    "https://trdhqne2rjafxkq3u6ukkp2eoq"
    ".appsync-api.ap-northeast-1.amazonaws.com/graphql"
)
APPSYNC_DEVICE = (
    "https://tqrdnhu5tbdotet3d6qqe4asii"
    ".appsync-api.ap-northeast-1.amazonaws.com/graphql"
)

# AWS service name for SigV4 signing
APPSYNC_SERVICE = "appsync"

# Action type IDs
ACTION_TOGGLE = 700          # Toggle on/off
ACTION_LIGHT = 630           # Lighting control (power/brightness/color temp/scene)
ACTION_IR_STORE = 602        # Store IR signal
ACTION_IR_SEND = 603         # Send IR command
ACTION_MUSIC = 640           # Music control
ACTION_SOUND = 200           # Sound playback
ACTION_SECURE = 902          # Secure mode

# Lighting commandType values
CMD_POWER = "powerControl"
CMD_BRIGHTNESS = "brightnessControl"
CMD_COLOR_TEMP = "colorTemperatureControl"
CMD_NIGHTLIGHT = "nightlightControl"
CMD_SCENE_CALL = "sceneCall"
CMD_SCENE_SAVE = "sceneSave"
CMD_SCENE_RESET = "sceneReset"

# signalType values
SIG_POWER = "power"
SIG_ABSOLUTE = "absolute"
SIG_SET = "set"

# Node-data slots for the light's own channels.
# The live API populates nodeDataList only when getNodes/getNodesNodeId is called
# with extraNodeData="true". Within that list, typeIds 107 and 704 repeat across
# several channels (brightness vs nightlight; light vs TV/AC), so the light is
# keyed by its slot index from compositeId "<nodeId>:<slot>" rather than typeId.
# These slots are fixed by the LGTG-200 device template.
SLOT_LIGHT_POWER = 5    # type 704, value "on"/"off"
SLOT_BRIGHTNESS = 10    # type 107, 0-100
SLOT_COLOR_TEMP = 11    # type 108, 0-100 (0=warm, 100=cool)

# Sensor data type IDs (unique within the node, so keyed by typeId)
SENSOR_ILLUMINANCE_AMB = 102   # Ambient illuminance (lux)
SENSOR_CONNECTED = 104         # Device online (Boolean)
SENSOR_TEMPERATURE = 400       # Temperature (Float, -30 to 50 C)
SENSOR_HUMIDITY = 401          # Humidity (Float, 0-100 %)
SENSOR_MOTION = 611            # Motion detection count (0 = no motion)

# Error codes returned in postActions response
ERROR_OK = None          # null -> success
ERROR_BAD_REQUEST = 40000
ERROR_NOT_FOUND = 40400

# Token lifetime in seconds (conservative buffer)
TOKEN_REFRESH_BUFFER_S = 300   # refresh 5 min before expiry
