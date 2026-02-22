import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

LOGGER = logging.getLogger(__name__)

# EDP binary header is 23 bytes; text payload follows.
EDP_HEADER_SIZE = 23

# The broken-bar character used as sub-delimiter in field 4.
SUB_DELIM = "\xa6"  # ¦


@dataclass
class EdpEvent:
    system_id: int
    timestamp: datetime
    event_class: str
    device_id: int
    device_name: str
    area_id: int | None = None
    area_name: str | None = None


def _to_utf8(data: bytes) -> str:
    """Decode ISO-8859-1 bytes to a Python str (effectively Latin-1 → UTF-8)."""
    return data.decode("iso-8859-1")


def _parse_timestamp(ts: str) -> datetime:
    """Parse EDP timestamp format HHMMSSDDMMYYYYr → datetime (UTC)."""
    # Example: "21155703112020" → 2020-11-03 21:15:57
    try:
        return datetime.strptime(ts[:14], "%H%M%S%d%m%Y").replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)


def _parse_name_field(raw: str) -> tuple[str, int | None, str | None]:
    """Parse the sub-delimited name field.

    Returns (device_name, area_id, area_name).

    Formats:
      Zone events:  "DeviceName¦ZONE¦AreaID¦AreaName"
      Area events:  "AreaName¦UserName¦AreaID"
      System events: "Description¦ID"
    """
    parts = raw.split(SUB_DELIM)

    if len(parts) >= 4 and parts[1] == "ZONE":
        # Zone event: DeviceName ¦ ZONE ¦ AreaID ¦ AreaName
        device_name = parts[0].strip()
        try:
            area_id = int(parts[2])
        except ValueError:
            area_id = None
        area_name = parts[3].strip() if len(parts) > 3 else None
        return device_name, area_id, area_name

    if len(parts) >= 3:
        # Area/user event: AreaName ¦ UserName ¦ AreaID
        area_name = parts[0].strip()
        device_name = parts[1].strip()
        try:
            area_id = int(parts[2])
        except ValueError:
            area_id = None
        return device_name, area_id, area_name

    if len(parts) == 2:
        # System event: Description ¦ ID
        return parts[0].strip(), None, None

    return raw.strip(), None, None


def parse_edp_message(data: bytes) -> EdpEvent:
    """Parse a raw EDP UDP packet into an EdpEvent.

    Raises ValueError if the packet cannot be parsed.
    """
    if len(data) < EDP_HEADER_SIZE + 5:
        raise ValueError(f"EDP packet too short: {len(data)} bytes")

    text = _to_utf8(data[EDP_HEADER_SIZE:])

    # Strip leading '[' and trailing ']'
    text = text.strip()
    if text.startswith("["):
        text = text[1:]
    if text.endswith("]"):
        text = text[:-1]

    fields = text.split("|")
    if len(fields) < 5:
        raise ValueError(f"EDP message has too few fields: {text!r}")

    # Field 0: "#SYSTEMID"
    system_id_str = fields[0]
    if system_id_str.startswith("#"):
        system_id_str = system_id_str[1:]
    try:
        system_id = int(system_id_str)
    except ValueError:
        raise ValueError(f"EDP invalid system ID: {fields[0]!r}")

    timestamp = _parse_timestamp(fields[1])
    event_class = fields[2].strip().upper()

    try:
        device_id = int(fields[3])
    except ValueError:
        raise ValueError(f"EDP invalid device ID: {fields[3]!r}")

    device_name, area_id, area_name = _parse_name_field(fields[4])

    return EdpEvent(
        system_id=system_id,
        timestamp=timestamp,
        event_class=event_class,
        device_id=device_id,
        device_name=device_name,
        area_id=area_id,
        area_name=area_name,
    )


class _EdpProtocol(asyncio.DatagramProtocol):
    """asyncio UDP protocol that parses EDP packets."""

    def __init__(self, system_id: int, callback):
        self._system_id = system_id
        self._callback = callback

    def datagram_received(self, data: bytes, addr: tuple):
        try:
            event = parse_edp_message(data)
        except ValueError as e:
            LOGGER.warning("EDP parse error from %s: %s", addr, e)
            return

        if self._system_id and event.system_id != self._system_id:
            LOGGER.debug(
                "EDP ignoring system %d (expecting %d)",
                event.system_id, self._system_id,
            )
            return

        LOGGER.debug(
            "EDP event: class=%s device=%d (%s) area=%s",
            event.event_class, event.device_id, event.device_name,
            event.area_id,
        )
        self._callback(event)

    def error_received(self, exc):
        LOGGER.warning("EDP socket error: %s", exc)

    def connection_lost(self, exc):
        if exc:
            LOGGER.warning("EDP connection lost: %s", exc)


class EdpListener:
    """Manages a UDP socket that receives EDP events from the SPC panel."""

    def __init__(self, port: int, system_id: int, callback):
        self._port = port
        self._system_id = system_id
        self._callback = callback
        self._transport = None

    async def start(self):
        """Bind the UDP socket and start receiving."""
        loop = asyncio.get_running_loop()
        self._transport, _ = await loop.create_datagram_endpoint(
            lambda: _EdpProtocol(self._system_id, self._callback),
            local_addr=("0.0.0.0", self._port),
        )
        LOGGER.info("EDP listener started on UDP port %d", self._port)

    async def stop(self):
        """Close the UDP socket."""
        if self._transport:
            self._transport.close()
            self._transport = None
            LOGGER.info("EDP listener stopped")
