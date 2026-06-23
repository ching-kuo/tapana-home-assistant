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

# Sensor data type IDs
SENSOR_PRESENCE = 100          # Motion detected (Boolean)
SENSOR_ILLUMINANCE_AMB = 102   # Ambient illuminance (Float, lumen 0-100)
SENSOR_CONNECTED = 104         # Device online (Boolean)
SENSOR_BRIGHTNESS = 106        # Current brightness (String)
SENSOR_ILLUMINANCE = 107       # Illuminance setting (Long)
SENSOR_COLOR_TEMP = 108        # Color temperature setting (Long)
SENSOR_TEMPERATURE = 400       # Temperature (Float, -30 to 50 C)
SENSOR_HUMIDITY = 401          # Humidity (Float, 0-100 %)
SENSOR_FAN_SPEED = 402         # Aircon fan speed (String)
SENSOR_TEMP_SETTING = 403      # Aircon target temperature (String)
SENSOR_STATUS = 704            # Various status fields
SENSOR_MODE = 705              # Operating mode (String)
SENSOR_SECURE = 902            # Security mode
SENSOR_SECURE_NODE = 954       # Node secure mode (Boolean)
SENSOR_OP_ACCEPT = 963         # Device accepts commands (Boolean)

# Error codes returned in postActions response
ERROR_OK = None          # null -> success
ERROR_BAD_REQUEST = 40000
ERROR_NOT_FOUND = 40400

# Token lifetime in seconds (conservative buffer)
TOKEN_REFRESH_BUFFER_S = 300   # refresh 5 min before expiry
