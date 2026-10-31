import logging
import xml.etree.ElementTree as ElTree
from datetime import date, datetime, timedelta

from dotenv import load_dotenv

from . import util
from .soap import SoapClient

load_dotenv()

logger = logging.getLogger(__name__)

CLEVEL = "cLevel"
WATER_STATION = "welinwq"
WATER_PARAMS = ["Temp", "DO_MgL", "SpCond", CLEVEL, "Sal", "pH", "DO_pct", "Turb"]
MAX_CDMO_WINDOW = 10  # 10 days max


def get_water_data(
    start_time: datetime, end_time: datetime, strict: bool = False
) -> dict[datetime, dict[str, str]]:

    xml: bytes = get_cdmo_xml(WATER_STATION, start_time, end_time, WATER_PARAMS)
    return parse_cdmo_xml(start_time, end_time, xml, strict)


def get_cdmo_xml(
    station_id: str, start_time: datetime, end_time: datetime, params: list[str]
) -> bytes:
    # Because CDMO returns units of entire days using LST, we may need to adjust the dates we request.
    req_start_date, req_end_date = compute_cdmo_request_dates(start_time, end_time)
    logger.debug(f"requesting from cdmo: {req_start_date} to {req_end_date}")
    param_str = ",".join(params)
    xml: bytes = SoapClient.get_client().service.exportAllParamsDateRangeXMLNew(
        station_id, req_start_date, req_end_date, param_str
    )
    # util.dump_xml(Path("cdmo.xml"), xml)
    return xml


def parse_cdmo_xml(
    start_time: datetime,
    end_time: datetime,
    xml: bytes,
    strict: bool,
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
        for param in WATER_PARAMS:
            val = record.findtext(f"./{param}")
            if val and val.strip():
                data.setdefault(dt_in_utc, {})
                data[dt_in_utc][param] = val

    logger.debug(f"read {read_cnt} records, considering {keep_cnt}")

    # Check for the correct number of values for each time.  Remove all *trailing* records with
    # missing cLevel.  If cLevel is missing in the middle, it is allowed nd will be converted to NaN later.
    # Here we depend on the fact that the data keys are in reverse chronological order.
    expected_values = len(WATER_PARAMS)
    clevel_found = False
    for dt in list(data.keys()):  # don't use items() b/c we might mutate the dict
        values = data[dt]
        num_values = len(values)
        if num_values == expected_values:
            clevel_found = True
        elif num_values == expected_values - 1 and not CLEVEL in values:
            # It's only missing cLevel.
            if not clevel_found:
                # It's missing at the end of the data.
                # This is an expected case and we can just delete it.
                logger.warning(f"{dt} is missing {CLEVEL}, on end, deleting")
                del data[dt]
            else:
                logger.warning(f"{dt} is missing {CLEVEL}, will return {util.NAN}")
        else:
            logger.error(f"{dt} has {num_values} values, expected {expected_values}")
            if strict:
                raise util.AppError("Bad data")

    # Finally sort it by datetime ascending
    return dict(sorted(data.items()))


def sort_values_by_param(data: dict[str, str]) -> list[str]:
    cooked: list[str] = []
    for key in WATER_PARAMS:
        val = data.get(key, util.NAN)
        if len(val) == util.NAN:
            logger.warning(f"No data returned for {key}")
        cooked.append(val)
    return cooked


def to_cdmo_rows(water: dict[datetime, dict[str, str]]) -> list[list[str]]:
    rows: list[list] = [["datetime-utc"] + WATER_PARAMS]

    for obs_time, data in dict(sorted(water.items())).items():
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
