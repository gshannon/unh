from datetime import datetime, timedelta

import requests
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    field_validator,
)

from app.security import get_token
from app.util import datetime_to_epoch_ms, epoch_to_datetime

# Sandbox urls:
# OBSERVATIONS_URL = (
#     "https://cloudfront-gc.xylem-cloud.com/xcloud/data-export/observations"
# )

OBSERVATIONS_URL = "https://cloud.xylem.com/xcloud/data-export/observations"

MAX_OBSERVATION_WINDOW = timedelta(days=14)
CUNDY_HARBOR_REG_ID = "D1frRlqlLf4JIcSO64PW"

EXO_DATA_STREAMS = {
    "2282793": "Chlorophyll_ug/L",
    "2282801": "Phycoerythrin_ug/L",
    "2282796": "DO_Sat",
    "2282804": "SpCond_uS/cm",
    "2282797": "DO_mg/L",
    "2282799": "pH",
    "2282798": "ExoSamplesCounter",
    "2282794": "Date",
    "2282806": "Time",
    "2282802": "Salinity_PSU",
    "2282803": "Sonde_Battery_Power_V",
    "2282795": "Depth_m",
    "2282805": "Temp_DegC",
    "2282807": "Turbidity_NTU",
    "2282800": "pH_mV",
}

MET_DATA_STREAMS = {
    "2282821": "Strikes",
    "2282810": "CompassHd_deg",
    "2282816": "NorthWSpd_ms",
    "2282820": "SlrFD_W",
    "2282808": "AirT_C",
    "2282814": "MaxWSpd_ms",
    "2282809": "BP_kPa",
    "2282813": "MaxWS_ms",
    "2282811": "Dist_km",
    "2282822": "TiltNS_deg",
    "2282812": "EastWSpd_ms",
    "2282818": "RH",
    "2282815": "METSamplesCounter",
    "2282817": "Rain_mm",
    "2282819": "RHT_C",
    "2282823": "TiltWE_deg",
    "2282826": "WS_ms",
    "2282825": "WindDir",
    "2282824": "VP_kPa",
}

EXO_HEADER = ["datetime-utc"] + list(EXO_DATA_STREAMS.values())
MET_HEADER = ["datetime-utc"] + list(MET_DATA_STREAMS.values())


class Observation(BaseModel):
    # Using a pydantic model for type validation when reading json from API.
    # This class represents a single observation
    model_config = ConfigDict(frozen=True, extra="forbid")

    value: float
    # json field name is phenomenonTime, an epoch time
    timestamp: datetime = Field(alias="phenomenonTime")
    resultTime: int = Field(exclude=True)

    @field_validator("timestamp", mode="before")
    @classmethod
    def convert_epoch(cls, ptime: int) -> datetime:
        return epoch_to_datetime(ptime)


class StreamObservations(RootModel[dict[str, list[Observation]]]):
    model_config = ConfigDict(frozen=True)


class XylemApiError(Exception):
    """An error response from the Xylem API (400, 401, 403, 404, 500, ...).

    error_code and message come from the documented ErrorResponse body
    (e.g. UNAUTHORIZED_ERROR) and are None if the body isn't in that format.
    """

    def __init__(self, status_code: int, error_code: str | None, message: str | None):
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        super().__init__(f"{status_code} {error_code or ''}: {message or ''}".strip())


def _raise_for_error(resp: requests.Response) -> None:
    if resp.ok:
        return
    try:
        body = resp.json()
    except ValueError:
        body = None
    if not isinstance(body, dict):
        body = {}
    raise XylemApiError(
        resp.status_code,
        body.get("errorCode"),
        body.get("message") or resp.text or resp.reason,
    )


def _get(url: str, token: str, params: dict | None = None):
    resp = requests.get(
        url,
        headers={"Authorization": f"bearer {token}"},
        params=params,
        timeout=30,
    )
    _raise_for_error(resp)
    return resp.json()


def get_observations(
    datastream_ids: list[str],
    start_time: datetime,
    end_time: datetime,
    strict: bool = False,
) -> dict[str, list[StreamObservations]]:
    """Fetch observations for the given datastreams and time range.

    Returns a dict keyed by datastream id; each value is a list of
    observations with phenomenonTime (epoch ms) and value.
    Raises ValueError if the range is longer than the API's limit,
    or XylemApiError on an error response.
    """
    if end_time - start_time > MAX_OBSERVATION_WINDOW:
        raise ValueError(
            f"Time window of {end_time - start_time} exceeds the "
            f"{MAX_OBSERVATION_WINDOW.days}-day limit"
        )
    params = {
        "datastreamIds": ",".join(datastream_ids),
        "from": datetime_to_epoch_ms(start_time),
        "until": datetime_to_epoch_ms(end_time),
    }
    json_content = _get(OBSERVATIONS_URL, get_token(), params=params)
    obs_dict = StreamObservations.model_validate(json_content, strict=True)
    data = obs_dict.root

    expected_streams = len(EXO_DATA_STREAMS) + len(MET_DATA_STREAMS)
    num_streams = len(data)
    fail = False
    if num_streams != expected_streams:
        print(f"Expected {expected_streams} keys from Xylem but got {num_streams}")
        if strict:
            fail = True
    for stream_id, obs_dict in data.items():
        if len(obs_dict) == 0 or len(obs_dict) % 4 != 0:
            if strict:
                fail = True
            print(f"Xylem {stream_id} has {len(obs_dict)} values)")
    if fail:
        raise Exception("Bad Data")  # noQA
    return data


def dump_xylem(data: dict[str, list[dict]]) -> None:
    # {"2282793": [{"phenomenonTime": 99999999, "value": "123.45"}, ...]}
    min_key = min(data)
    print(f"First parameter: {min_key}")
    obs1 = data[min_key]
    ptime = obs1[0]["phenomenonTime"]
    obs_time = epoch_to_datetime(ptime)
    print(f"  {ptime:<18} ({obs_time}): [...]")
