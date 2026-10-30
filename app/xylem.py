import logging
from datetime import datetime, timedelta
from pathlib import Path

import requests
from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator

from app.security import get_token

from . import util

# Sandbox urls:
# OBSERVATIONS_URL = (
#     "https://cloudfront-gc.xylem-cloud.com/xcloud/data-export/observations"
# )

logger = logging.getLogger(__name__)

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


class Observation(BaseModel):
    # Using a pydantic model for type validation when reading json from API.
    # This class represents a single observation
    model_config = ConfigDict(frozen=True, extra="forbid")

    value: float
    # json field name is phenomenonTime, an epoch time
    timestamp: datetime = Field(alias="phenomenonTime")
    resultTime: int

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


datetime_to_epoch_ms = lambda dt: int(dt.timestamp() * 1000)

epoch_to_datetime = lambda epoch_time_ms: datetime.fromtimestamp(
    epoch_time_ms / 1000, tz=util.utc
)


def get_stream_name(id: str) -> str | None:
    return EXO_DATA_STREAMS.get(id, None) or MET_DATA_STREAMS.get(id, None)


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
    """Fetch observations for the given datastreams and time range."""
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
    obs_dict = normalize_xylem_json(json_content)
    if not is_valid_content(obs_dict) and strict:
        raise util.AppError("Bad data")

    return obs_dict


def is_valid_content(obs_dict: dict[str, list[Observation]]) -> bool:
    expected_streams = len(EXO_DATA_STREAMS) + len(MET_DATA_STREAMS)
    num_streams = len(obs_dict)
    logger.debug(f"pulled data for {num_streams} data streams from xylem")
    valid = True

    if num_streams != expected_streams:
        logger.error(
            f"Expected {expected_streams} streams from Xylem but got {num_streams}"
        )
        valid = False

    for name, obs_list in obs_dict.items():
        if len(obs_list) == 0 or len(obs_list) % 4 != 0:
            logger.error(f"Stream {name} has {len(obs_list)} values")
            valid = False

    return valid


def normalize_xylem_json(json_content: dict) -> dict[str, list[Observation]]:
    obs_dict = StreamObservations.model_validate(json_content, strict=True)
    normal: dict[str, list[StreamObservations]] = {}
    for stream_id, obs_list in obs_dict.root.items():
        name = get_stream_name(stream_id)
        if name is None:
            raise RuntimeError(f"stream {stream_id} is not valid")
        normal[name] = obs_list
    return normal


def to_timestamp_rows(
    stream_names: list[str],
    observations: dict[str, list[StreamObservations]],
    start: datetime,
    end: datetime,
) -> list[list]:
    """Flatten observations into CSV rows, ordered by datastream."""

    # The order of datastreams.values() will match the order
    header = ["datetime-utc"] + stream_names

    # sort the data by datetime, then stream name
    cooked: dict[datetime, list[str]] = {}
    # observations contain both EXO and MET. Only consider the ones with names contained in the header.
    for name in stream_names:
        # restrict it to only EXO or MET datastreams
        stream_obs = observations.get(name, [])
        if len(stream_obs) != 4:
            raise util.AppError(f"{name} has {len(stream_obs)} values, expected 4")

        for obs in stream_obs:
            if start <= obs.timestamp <= end:
                cooked.setdefault(obs.timestamp, [])
                cooked[obs.timestamp].append(obs.value)

    rows = [header]
    for obs_time, data in dict(sorted(cooked.items())).items():
        rows.append([obs_time.isoformat()] + data)
    return rows
