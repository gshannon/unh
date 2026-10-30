import logging
import xml.etree.ElementTree as ElTree
from datetime import date, datetime, timedelta

from dotenv import load_dotenv

from . import util
from .soap import SoapClient

load_dotenv()

logger = logging.getLogger(__name__)

WATER_STATION = "welinwq"
WATER_PARAMS = ["Temp", "DO_MgL", "SpCond", "cLevel", "Sal", "pH", "DO_pct", "Turb"]
MAX_CDMO_WINDOW = 10  # 10 days max


def get_water_data(
    start_time: datetime, end_time: datetime, strict: bool = False
) -> dict[datetime, dict[str, str]]:
    xml: bytes = get_cdmo_xml(WATER_STATION, start_time, end_time, WATER_PARAMS)
    data: dict[datetime, dict[str, str]] = parse_cdmo_xml(
        start_time, end_time, WATER_PARAMS, xml
    )

    # Before returning it, do some quality control.  First,
    # ensure we have a multiple of 4 timestamps, so we have full days only.
    num_timestamps = len(data)
    if num_timestamps == 0 or num_timestamps % 4 != 0:
        logger.warning(f"Got {num_timestamps} datetimes from CDMO")
        if strict:
            raise util.AppError("Bad data")

    # Now check for the correct number of values for each time.
    expected_values = len(WATER_PARAMS)
    for dt, values in data.items():
        if len(values) != expected_values:
            logger.warning(
                f"CDMO {dt} has {len(values)} values, expected {expected_values}"
            )
            if strict:
                raise util.AppError("Bad data")

    return data


def get_cdmo_xml(
    station_id: str, start_time: datetime, end_time: datetime, params: list[str]
) -> bytes:
    # Because CDMO returns units of entire days using LST, we may need to adjust the dates we request.
    req_start_date, req_end_date = compute_cdmo_request_dates(start_time, end_time)
    logger.debug(f"requesting from cdmo: {req_start_date} - {req_end_date}")
    param_str = ",".join(params)
    xml: bytes = SoapClient.get_client().service.exportAllParamsDateRangeXMLNew(
        station_id, req_start_date, req_end_date, param_str
    )
    return xml


def parse_cdmo_xml(
    start_time: datetime, end_time: datetime, params: list[str], xml: bytes
) -> dict[datetime, dict[str, str]]:
    data: dict[datetime, dict[str, str]] = {}

    if xml is None or len(xml) == 0:
        return data

    root = ElTree.fromstring(xml)
    ensure_no_text(root)
    read_cnt = keep_cnt = 0
    for record in root.findall(".//data"):  # use XPATH to dig out our data points
        # we use <utcStamp>, not <DateTimeStamp> because the latter is in LST, not sensitive to DST.
        date_str = record.findtext("./utcStamp")
        dt_in_utc = datetime.strptime(date_str or "", "%m/%d/%Y %H:%M").replace(
            tzinfo=util.utc
        )
        read_cnt += 1

        if dt_in_utc < start_time or dt_in_utc > end_time:
            continue

        keep_cnt += 1
        for param in params:
            val = record.findtext(f"./{param}")
            if val and val.strip():
                data.setdefault(dt_in_utc, {})
                data[dt_in_utc][param] = val

    logger.debug(f"read {read_cnt} records, using {keep_cnt}")
    return data


def sort_values_by_param(data: dict[str, str]) -> list[str]:
    cooked: list[str] = []
    for key in WATER_PARAMS:
        val = data.get(key, "")
        if len(val) == 0:
            logger.warning(f"No data returned for {key}")
        cooked.append(val)
    return cooked


def to_cdmo_rows(
    water: dict[datetime, dict[str, str]],
    start: datetime,
    end: datetime,
) -> list[list[str]]:
    rows: list[list] = [["datetime-utc"] + WATER_PARAMS]

    for obs_time, data in dict(sorted(water.items())).items():
        if start <= obs_time <= end:
            rows.append([obs_time.isoformat()] + sort_values_by_param(data))
    return rows


def ensure_no_text(rootElement: ElTree.Element) -> None:
    """The root node is not supposed to have text, so if it does, we assume it's an error message since
    that's how CDMO does it. e.g., "Invalid IP address"
    """
    text: str | None = rootElement.findtext(".//data")
    try:
        message = text.strip() if text else ""
        if len(message) > 0:
            raise util.AppError(f"CDMO returned: {message}")
    except AttributeError:
        pass  # Not every payload has text in their data node


def compute_cdmo_request_dates(
    start_time: datetime, end_time: datetime
) -> tuple[date, date]:
    requested_start_date = start_time.date()
    requested_end_date = end_time.date()

    if util.is_dst(start_time) and start_time.hour < 1:
        requested_start_date -= timedelta(days=1)

    if util.is_dst(end_time) and end_time.hour < 1:
        requested_end_date -= timedelta(days=1)

    return requested_start_date, requested_end_date
