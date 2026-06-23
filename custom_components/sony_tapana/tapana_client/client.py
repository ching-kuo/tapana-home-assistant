"""Sony LGTG-200 Tapana Cloud API client.

Authentication flow:
  1. Cognito SRP auth  -> id_token, access_token, refresh_token
  2. Identity Pool     -> temporary AWS credentials (AccessKeyId/SecretKey/SessionToken)
  3. AppSync call      -> SigV4 signed + x-reach-auth: <id_token>
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import logging
import time
import urllib.request
from urllib.parse import urlparse

import boto3
from pycognito import Cognito

from .const import (
    ACTION_LIGHT,
    ACTION_TOGGLE,
    APPSYNC_MAIN,
    APPSYNC_SERVICE,
    CLIENT_ID,
    CMD_BRIGHTNESS,
    CMD_COLOR_TEMP,
    CMD_NIGHTLIGHT,
    CMD_POWER,
    CMD_SCENE_CALL,
    CMD_SCENE_RESET,
    CMD_SCENE_SAVE,
    IDENTITY_POOL_ID,
    LOGINS_KEY,
    REGION,
    SENSOR_CONNECTED,
    SENSOR_HUMIDITY,
    SENSOR_ILLUMINANCE_AMB,
    SENSOR_MOTION,
    SENSOR_TEMPERATURE,
    SIG_ABSOLUTE,
    SIG_POWER,
    SIG_SET,
    SLOT_BRIGHTNESS,
    SLOT_COLOR_TEMP,
    SLOT_LIGHT_POWER,
    TOKEN_REFRESH_BUFFER_S,
    USER_POOL_ID,
)
from .exceptions import (
    ApiError,
    AuthenticationError,
    CommandError,
    InvalidParamsError,
)
from .models import ActionResult, LightState, Node, NodeData, SensorData

_LOGGER = logging.getLogger(__name__)

_POST_ACTIONS_MUTATION = """
mutation postActions(
  $actionMode: String
  $ActionHandleRequestModel: ActionHandleRequestArrayModelInput!
) {
  postActions(
    actionMode: $actionMode
    ActionHandleRequestModel: $ActionHandleRequestModel
  ) {
    notificationId
    nodeActionType
    timestamp
    recipeId
    errorCode
  }
}
"""

_GET_NODE_QUERY = """
query getNodesNodeId($nodeId: String!, $extraNodeData: String) {
  getNodesNodeId(nodeId: $nodeId, extraNodeData: $extraNodeData) {
    id
    edgeId
    name
    uuid
    version
    subversion
    userGroupId
    areaLabel
    isFirmwareUpdating
    nodeDataList {
      compositeId persistent time value label nodeDataTypeId nodeId alertLevel
    }
  }
}
"""

_GET_NODES_QUERY = """
query getNodes($placeId: String, $extraNodeData: String) {
  getNodes(placeId: $placeId, extraNodeData: $extraNodeData) {
    id
    edgeId
    name
    uuid
    version
    subversion
    userGroupId
    areaLabel
    isFirmwareUpdating
    nodeDataList {
      compositeId persistent time value label nodeDataTypeId nodeId alertLevel
    }
  }
}
"""


def _hmac_digest(key: bytes, msg: str | bytes) -> bytes:
    """Return HMAC-SHA256 digest."""
    return hmac.new(
        key,
        msg.encode() if isinstance(msg, str) else msg,
        hashlib.sha256,
    ).digest()


def _sigv4_signing_key(secret_key: str, date_stamp: str, region: str, service: str) -> bytes:
    """Derive the AWS SigV4 signing key."""
    k_date = _hmac_digest(f"AWS4{secret_key}".encode(), date_stamp)
    k_region = _hmac_digest(k_date, region)
    k_service = _hmac_digest(k_region, service)
    return _hmac_digest(k_service, "aws4_request")


def _slot_of(composite_id: str) -> int | None:
    """Return the slot index from a compositeId like "<nodeId>:<slot>"."""
    if composite_id and ":" in composite_id:
        try:
            return int(composite_id.rsplit(":", 1)[1])
        except ValueError:
            return None
    return None


def _parse_light_state(node: Node) -> LightState:
    """Extract LightState from a Node's data list (keyed by slot)."""
    by_slot: dict[int, str] = {}
    for nd in node.node_data_list:
        slot = _slot_of(nd.composite_id)
        if slot is not None:
            by_slot[slot] = nd.value

    state = LightState()

    power = by_slot.get(SLOT_LIGHT_POWER)
    if power is not None:
        low = str(power).lower()
        if low in ("on", "true", "1"):
            state.is_on = True
        elif low in ("off", "false", "0"):
            state.is_on = False

    raw_brightness = by_slot.get(SLOT_BRIGHTNESS)
    if raw_brightness is not None:
        try:
            state.brightness_pct = int(float(raw_brightness))
        except (ValueError, TypeError):
            pass

    raw_color_temp = by_slot.get(SLOT_COLOR_TEMP)
    if raw_color_temp is not None:
        try:
            # The phone app can set values >100 on a different scale; clamp so
            # the kelvin conversion stays within the advertised range.
            state.color_temp_pct = max(0, min(100, int(float(raw_color_temp))))
        except (ValueError, TypeError):
            pass

    return state


def _parse_sensor_data(node: Node) -> SensorData:
    """Extract SensorData from a Node's data list (keyed by typeId)."""
    by_type: dict[int, str] = {
        nd.node_data_type_id: nd.value for nd in node.node_data_list
    }

    def _float(key: int) -> float | None:
        raw = by_type.get(key)
        if raw is None:
            return None
        try:
            return float(raw)
        except (ValueError, TypeError):
            return None

    def _bool(key: int) -> bool | None:
        raw = by_type.get(key)
        if raw is None:
            return None
        return raw.lower() in ("true", "1", "yes")

    motion = _float(SENSOR_MOTION)
    return SensorData(
        temperature=_float(SENSOR_TEMPERATURE),
        humidity=_float(SENSOR_HUMIDITY),
        illuminance=_float(SENSOR_ILLUMINANCE_AMB),
        presence=(motion > 0) if motion is not None else None,
        connected=_bool(SENSOR_CONNECTED),
    )


class TapanaClient:
    """Client for the Sony LGTG-200 Tapana cloud API.

    Usage::

        client = TapanaClient(
            email="user@example.com",
            password="secret",
            node_id=1415902,
        )
        client.authenticate()
        client.turn_on()
        client.set_brightness(80)
        state = client.get_light_state()
    """

    def __init__(self, email: str, password: str, node_id: int) -> None:
        self._email = email
        self._password = password
        self._node_id = node_id

        # Cognito state
        self._cog: Cognito | None = None
        self._id_token: str | None = None
        self._refresh_token: str | None = None
        self._token_expiry: float = 0.0

        # AWS temporary credentials
        self._aws_access_key: str | None = None
        self._aws_secret_key: str | None = None
        self._aws_session_token: str | None = None
        self._aws_creds_expiry: float = 0.0

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def authenticate(self) -> None:
        """Perform initial Cognito SRP authentication and fetch AWS credentials."""
        _LOGGER.debug("Authenticating with Cognito user pool %s", USER_POOL_ID)
        try:
            cog = Cognito(
                USER_POOL_ID,
                CLIENT_ID,
                username=self._email,
                user_pool_region=REGION,
            )
            cog.authenticate(password=self._password)
        except Exception as exc:
            raise AuthenticationError(
                f"Cognito authentication failed: {exc}"
            ) from exc

        self._cog = cog
        self._id_token = cog.id_token
        self._refresh_token = cog.refresh_token
        self._token_expiry = time.time() + 3600 - TOKEN_REFRESH_BUFFER_S

        self._refresh_aws_credentials()

    def _refresh_tokens(self) -> None:
        """Refresh Cognito tokens; falls back to full re-auth on failure."""
        _LOGGER.debug("Refreshing Cognito tokens")
        if self._cog is None or self._refresh_token is None:
            self.authenticate()
            return
        try:
            self._cog.renew_access_token()
            self._id_token = self._cog.id_token
            self._token_expiry = time.time() + 3600 - TOKEN_REFRESH_BUFFER_S
        except Exception:
            _LOGGER.warning("Token refresh failed, re-authenticating")
            self.authenticate()

    def _refresh_aws_credentials(self) -> None:
        """Exchange the Cognito id_token for temporary AWS credentials."""
        _LOGGER.debug("Fetching AWS credentials from Identity Pool")
        # Anonymous boto3 client -- get_id and get_credentials_for_identity
        # do not require AWS request signing; auth comes from the Cognito JWT.
        id_client = boto3.client(
            "cognito-identity",
            region_name=REGION,
            aws_access_key_id="",
            aws_secret_access_key="",
        )
        logins = {LOGINS_KEY: self._id_token}
        try:
            identity_id = id_client.get_id(
                IdentityPoolId=IDENTITY_POOL_ID,
                Logins=logins,
            )["IdentityId"]
            creds_resp = id_client.get_credentials_for_identity(
                IdentityId=identity_id,
                Logins=logins,
            )
        except Exception as exc:
            raise AuthenticationError(
                f"Failed to obtain AWS credentials: {exc}"
            ) from exc

        creds = creds_resp["Credentials"]
        self._aws_access_key = creds["AccessKeyId"]
        self._aws_secret_key = creds["SecretKey"]
        self._aws_session_token = creds["SessionToken"]

        expiry = creds.get("Expiration")
        if expiry:
            self._aws_creds_expiry = expiry.timestamp() - TOKEN_REFRESH_BUFFER_S
        else:
            self._aws_creds_expiry = time.time() + 3600 - TOKEN_REFRESH_BUFFER_S

    def _ensure_valid_credentials(self) -> None:
        """Ensure tokens and AWS credentials are current."""
        if self._id_token is None:
            self.authenticate()
            return

        now = time.time()
        if now >= self._token_expiry:
            self._refresh_tokens()
        if now >= self._aws_creds_expiry:
            self._refresh_aws_credentials()

    # ------------------------------------------------------------------
    # SigV4 signing
    # ------------------------------------------------------------------

    def _sign_request(self, url: str, body: str) -> dict[str, str]:
        """Return HTTP headers signed with AWS Signature Version 4."""
        parsed = urlparse(url)
        host: str = parsed.hostname  # type: ignore[assignment]
        path: str = parsed.path

        t = datetime.datetime.now(datetime.timezone.utc)
        amz_date = t.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = t.strftime("%Y%m%d")

        # Canonical headers (must be sorted alphabetically by key)
        header_map = {
            "content-type": "application/json",
            "host": host,
            "x-amz-date": amz_date,
            "x-amz-security-token": self._aws_session_token,
        }
        sorted_keys = sorted(header_map)
        canonical_headers = "".join(f"{k}:{header_map[k]}\n" for k in sorted_keys)
        signed_headers_str = ";".join(sorted_keys)

        payload_hash = hashlib.sha256(body.encode()).hexdigest()
        canonical_request = "\n".join([
            "POST",
            path,
            "",  # query string (empty)
            canonical_headers,
            signed_headers_str,
            payload_hash,
        ])

        scope = f"{date_stamp}/{REGION}/{APPSYNC_SERVICE}/aws4_request"
        string_to_sign = "\n".join([
            "AWS4-HMAC-SHA256",
            amz_date,
            scope,
            hashlib.sha256(canonical_request.encode()).hexdigest(),
        ])

        signing_key = _sigv4_signing_key(
            self._aws_secret_key,  # type: ignore[arg-type]
            date_stamp,
            REGION,
            APPSYNC_SERVICE,
        )
        signature = hmac.new(
            signing_key, string_to_sign.encode(), hashlib.sha256
        ).hexdigest()

        authorization = (
            f"AWS4-HMAC-SHA256 Credential={self._aws_access_key}/{scope}, "
            f"SignedHeaders={signed_headers_str}, Signature={signature}"
        )

        return {
            "Content-Type": "application/json",
            "Host": host,
            "X-Amz-Date": amz_date,
            "X-Amz-Security-Token": self._aws_session_token,  # type: ignore[return-value]
            "Authorization": authorization,
            "x-reach-auth": self._id_token,  # type: ignore[return-value]
        }

    # ------------------------------------------------------------------
    # GraphQL execution
    # ------------------------------------------------------------------

    def _call(
        self,
        query: str,
        variables: dict | None = None,
        endpoint: str = APPSYNC_MAIN,
    ) -> dict:
        """Execute a GraphQL operation against an AppSync endpoint."""
        self._ensure_valid_credentials()

        payload: dict = {"query": query}
        if variables:
            payload["variables"] = variables
        body = json.dumps(payload)

        headers = self._sign_request(endpoint, body)
        req = urllib.request.Request(
            endpoint,
            data=body.encode(),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            raise ApiError(f"HTTP {exc.code} from AppSync: {exc.reason}") from exc
        except Exception as exc:
            raise ApiError(f"Request to AppSync failed: {exc}") from exc

        if "errors" in data:
            errors = data["errors"]
            msg = "; ".join(e.get("message", str(e)) for e in errors)
            raise ApiError(f"GraphQL error: {msg}")

        return data.get("data", {})

    # ------------------------------------------------------------------
    # Device queries
    # ------------------------------------------------------------------

    def get_node(self) -> Node:
        """Fetch the current node state from the cloud API."""
        data = self._call(
            _GET_NODE_QUERY,
            # extraNodeData="true" is required for nodeDataList (light/sensor
            # state) to be populated; without it the list comes back empty.
            variables={"nodeId": str(self._node_id), "extraNodeData": "true"},
        )
        raw = data.get("getNodesNodeId")
        if not raw:
            raise ApiError("getNodesNodeId returned empty data")
        return Node.from_api(raw)

    def get_nodes(self) -> list[Node]:
        """Fetch all nodes (devices) registered to the account."""
        data = self._call(_GET_NODES_QUERY, variables={})
        raw = data.get("getNodes") or []
        return [Node.from_api(n) for n in raw if n]

    def get_light_state(self) -> LightState:
        """Return the current light state."""
        return _parse_light_state(self.get_node())

    def get_sensor_data(self) -> SensorData:
        """Return environmental sensor readings."""
        return _parse_sensor_data(self.get_node())

    # ------------------------------------------------------------------
    # Internal: send a device command
    # ------------------------------------------------------------------

    def _light_action(
        self,
        action_type_id: int,
        params: dict | str,
        endpoint: str = APPSYNC_MAIN,
    ) -> ActionResult:
        """Send a postActions mutation and return the parsed result."""
        params_str = (
            json.dumps(params) if isinstance(params, dict) else str(params)
        )
        variables = {
            "actionMode": "manual",
            "ActionHandleRequestModel": {
                "requests": [
                    {
                        "actionTypeId": action_type_id,
                        "nodeId": self._node_id,
                        "params": params_str,
                        "recipeFiredId": int(time.time() * 1000),
                    }
                ]
            },
        }
        data = self._call(_POST_ACTIONS_MUTATION, variables=variables, endpoint=endpoint)
        raw = data.get("postActions")
        if not raw:
            raise ApiError("postActions returned empty data")
        # postActions mirrors the requests array, returning a list of results.
        if isinstance(raw, list):
            raw = raw[0]
        result = ActionResult.from_api(raw)
        if not result.success:
            raise CommandError(
                f"Command rejected (errorCode={result.error_code})",
                error_code=result.error_code,
            )
        return result

    # ------------------------------------------------------------------
    # Light control
    # ------------------------------------------------------------------

    def toggle(self) -> ActionResult:
        """Toggle the main light on/off."""
        return self._light_action(ACTION_TOGGLE, "{}")

    def turn_on(self) -> ActionResult:
        """Turn the main light on."""
        return self._light_action(
            ACTION_LIGHT,
            {
                "target": "light",
                "commandType": CMD_POWER,
                "signalType": SIG_POWER,
                "signal": "true",
            },
        )

    def turn_off(self) -> ActionResult:
        """Turn the main light off."""
        return self._light_action(
            ACTION_LIGHT,
            {
                "target": "light",
                "commandType": CMD_POWER,
                "signalType": SIG_POWER,
                "signal": "false",
            },
        )

    def set_brightness(self, brightness_pct: int) -> ActionResult:
        """Set brightness level (0-100)."""
        if not 0 <= brightness_pct <= 100:
            raise InvalidParamsError(
                f"Brightness must be 0-100, got {brightness_pct}"
            )
        return self._light_action(
            ACTION_LIGHT,
            {
                "target": "light",
                "commandType": CMD_BRIGHTNESS,
                "signalType": SIG_ABSOLUTE,
                "signal": str(brightness_pct),
            },
        )

    def set_color_temperature(self, color_temp_pct: int) -> ActionResult:
        """Set color temperature (0=warmest/2700K, 100=coolest/6500K)."""
        if not 0 <= color_temp_pct <= 100:
            raise InvalidParamsError(
                f"Color temperature must be 0-100, got {color_temp_pct}"
            )
        return self._light_action(
            ACTION_LIGHT,
            {
                "target": "light",
                "commandType": CMD_COLOR_TEMP,
                "signalType": SIG_SET,
                "signal": str(color_temp_pct),
            },
        )

    def set_nightlight(self, on: bool) -> ActionResult:
        """Turn the night light on or off."""
        return self._light_action(
            ACTION_LIGHT,
            {
                "target": "light",
                "commandType": CMD_NIGHTLIGHT,
                "signalType": SIG_POWER,
                "signal": "true" if on else "false",
            },
        )

    def recall_scene(self, scene_number: int) -> ActionResult:
        """Recall a saved scene (1-4)."""
        if not 1 <= scene_number <= 4:
            raise InvalidParamsError(
                f"Scene number must be 1-4, got {scene_number}"
            )
        return self._light_action(
            ACTION_LIGHT,
            {
                "target": "light",
                "commandType": CMD_SCENE_CALL,
                "signalType": SIG_SET,
                "signal": str(scene_number),
            },
        )

    def save_scene(self, scene_number: int) -> ActionResult:
        """Save the current state as scene 1-4."""
        if not 1 <= scene_number <= 4:
            raise InvalidParamsError(
                f"Scene number must be 1-4, got {scene_number}"
            )
        return self._light_action(
            ACTION_LIGHT,
            {
                "target": "light",
                "commandType": CMD_SCENE_SAVE,
                "signalType": SIG_SET,
                "signal": str(scene_number),
            },
        )

    def reset_scene(self, scene_number: int) -> ActionResult:
        """Reset scene 1-4 back to factory default."""
        if not 1 <= scene_number <= 4:
            raise InvalidParamsError(
                f"Scene number must be 1-4, got {scene_number}"
            )
        return self._light_action(
            ACTION_LIGHT,
            {
                "target": "light",
                "commandType": CMD_SCENE_RESET,
                "signalType": SIG_SET,
                "signal": str(scene_number),
            },
        )
