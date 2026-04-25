from dataclasses import dataclass
from .utils import hex_canid_to_int

@dataclass(frozen=True)
class AscFrame:
    bus_number: str
    can_id: int

def parse_asc_frame(line: str) -> AscFrame | None:
    parts = line.strip().split()
    if not parts or len(parts) < 7:
        return None
    
    try:
        # Currently, CANXL frames are not supported
        if parts[1] == "CANFD":
            # CANFD
            bus_number = parts[2]
            canid = parts[4]
        else:
            # Classic CAN
            bus_number = parts[1]
            canid = parts[2]
        return AscFrame(
            bus_number = bus_number,
            can_id = hex_canid_to_int(canid)
        )
    except IndexError:
        return None