from datetime import datetime, timedelta
from urllib.parse import quote

import requests

from app.security import get_token
from app.util import datetime_to_epoch_ms

# Sandbox urls:
# SITES_URL = "https://cloudfront-gc.xylem-cloud.com/xcloud/data-export/sites"
# SITES_V2_URL = "https://cloudfront-gc.xylem-cloud.com/xcloud/data-export/v2/sites"
# DATASTREAMS_URL = "https://cloudfront-gc.xylem-cloud.com/xcloud/data-export/site/{site_id}/datastreams"
# OBSERVATIONS_URL = (
#     "https://cloudfront-gc.xylem-cloud.com/xcloud/data-export/observations"
# )

SITES_URL = "https://cloud.xylem.com/xcloud/data-export/sites"
SITES_V2_URL = "https://cloud.xylem.com/xcloud/data-export/v2/sites"
DATASTREAMS_URL = (
    "https://cloud.xylem.com/xcloud/data-export/site/{site_id}/datastreams"
)
OBSERVATIONS_URL = "https://cloud.xylem.com/xcloud/data-export/observations"

MAX_OBSERVATION_WINDOW = timedelta(days=14)
CUNDY_HARBOR_REG_ID = "D1frRlqlLf4JIcSO64PW"
CUNDY_HARBOR_ID = "68ae13a5f9101a3a0812f688"

DATA_STREAMS = {
    "2282793": "Exo1Data:Chlorophyll_ug/L",
    "2282801": "Exo1Data:Phycoerythrin_ug/L",
    "2282796": "Exo1Data:DO_Sat",
    "2282804": "Exo1Data:SpCond_uS/cm",
    "2282797": "Exo1Data:DO_mg/L",
    "2282799": "Exo1Data:pH",
    "2282798": "Exo1Data:ExoSamplesCounter",
    "2282794": "Exo1Data:Date",
    "2282806": "Exo1Data:Time",
    "2282802": "Exo1Data:Salinity_PSU",
    "2282803": "Exo1Data:Sonde_Battery_Power_V",
    "2282795": "Exo1Data:Depth_m",
    "2282805": "Exo1Data:Temp_DegC",
    "2282807": "Exo1Data:Turbidity_NTU",
    "2282800": "Exo1Data:pH_mV",
    "2282821": "METData:Strikes",
    "2282810": "METData:CompassHd_deg",
    "2282816": "METData:NorthWSpd_ms",
    "2282820": "METData:SlrFD_W",
    "2282808": "METData:AirT_C",
    "2282814": "METData:MaxWSpd_ms",
    "2282809": "METData:BP_kPa",
    "2282813": "METData:MaxWS_ms",
    "2282811": "METData:Dist_km",
    "2282822": "METData:TiltNS_deg",
    "2282812": "METData:EastWSpd_ms",
    "2282818": "METData:RH",
    "2282815": "METData:METSamplesCounter",
    "2282817": "METData:Rain_mm",
    "2282819": "METData:RHT_C",
    "2282823": "METData:TiltWE_deg",
    "2282826": "METData:WS_ms",
    "2282825": "METData:WindDir",
    "2282824": "METData:VP_kPa",
}


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


def get_sites() -> list[dict]:
    """Fetch the list of sites from the Xylem data-export API.

    Raises XylemApiError on an error response. Note this endpoint returns at
    most 1000 sites; use get_sites_v2() for more.
    """
    return _get(SITES_URL, get_token())


def get_sites_v2(page_size: int = 500, max_records: int | None = None) -> list[dict]:
    """Fetch all sites from the paginated /v2/sites endpoint.

    Requests pages of page_size sites until the last page and returns them
    as a single list. If max_records is given, stops once that many sites have
    been fetched and returns at most that many. Raises XylemApiError on an
    error response.
    """
    if max_records is not None:
        page_size = min(page_size, max_records)
    token = get_token()
    sites: list[dict] = []
    page = 0
    while True:
        body = _get(SITES_V2_URL, token, {"page": page, "size": page_size})
        content = body.get("content") or []
        sites.extend(content)
        if max_records is not None and len(sites) >= max_records:
            return sites[:max_records]
        total_pages = body.get("totalPages")
        if total_pages is not None:
            if page + 1 >= total_pages:
                break
        elif len(content) < page_size:  # totalPages is nullable in the spec
            break
        page += 1
    return sites


def get_datastreams(site_id: str) -> list[dict]:
    """Fetch the datastreams (sensors) for a site.

    Each datastream has id, name, description, parameterReference and
    unitOfMeasurement. Raises XylemApiError on an error response (404 if the
    site doesn't exist).
    """
    url = DATASTREAMS_URL.format(site_id=quote(site_id, safe=""))
    return _get(url, get_token())


def get_observations(
    datastream_ids: list[str],
    start_time: datetime,
    end_time: datetime,
    strict: bool = False,
) -> dict[str, list[dict]]:
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
    data = _get(OBSERVATIONS_URL, get_token(), params=params)
    expected_keys = len(DATA_STREAMS)
    num_keys = len(data)
    fail = False
    if num_keys != expected_keys:
        print(f"Expected {expected_keys} keys from Xylem but got {num_keys}")
        if strict:
            fail = True
    for key, val in data.items():
        if len(val) == 0 or len(val) % 4 != 0:
            if strict:
                fail = True
            print(
                f"Xylem {key} has {len(val)} values ({DATA_STREAMS.get(key, 'unknown')})"
            )
    if fail:
        raise Exception("Bad Data")  # noQA
    return data
