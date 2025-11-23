# extras.py
"""
Extra helper functions for network_tree.py:
- Device type detection
- MAC randomization detection
- Dynamic L2/L3 zone tagging
- Normalized vendor + MAC handling
"""

import re


#  MAC NORMALIZATION


def normalize_mac(mac: str) -> str:
    """
    Normalizes MAC to lowercase colon-separated format.
    Accepts formats like:
        AA-BB-CC-DD-EE-FF
        aabbccddeeff
        Aa:Bb:Cc:Dd:Ee:Ff
    Returns "aa:bb:cc:dd:ee:ff" or "unknown".
    """
    if not mac or mac.lower() == "unknown":
        return "unknown"

    mac = mac.strip().lower()

    # remove all non-hex characters
    hex_only = re.sub(r"[^0-9a-f]", "", mac)

    if len(hex_only) != 12:
        return "unknown"

    # colon-inserted normalized MAC
    return ":".join(hex_only[i : i + 2] for i in range(0, 12, 2))


#  MAC RANDOMIZATION DETECTION


def is_random_mac(mac: str) -> bool:
    """
    Detects if a MAC is locally-administered (randomized).
    Fully normalized + validated.
    """
    mac = normalize_mac(mac)
    if mac == "unknown":
        return False

    try:
        first_octet = int(mac.split(":")[0], 16)
    except ValueError:
        return False

    # U/L bit = 1 → Locally Administered = Random
    return (first_octet & 0b10) != 0


#  DEVICE TYPE CLASSIFICATION


def classify_device_type(mac: str, vendor: str, random: bool) -> str:
    """
    Classifies device into:
    - Phone
    - Apple Device
    - Laptop/PC
    - Network Device
    - IoT Device
    - Random Device
    - Device (fallback)
    Uses cleaned vendor tokens for accurate matching.
    """

    if random:
        return "Random Device"

    vendor = (vendor or "").lower().strip()

    # Tokenize vendor for more reliable matching
    tokens = vendor.replace(",", " ").replace("-", " ").split()

    def match_any(keyword_list):
        return any(kw in vendor for kw in keyword_list) or any(
            kw in tokens for kw in keyword_list
        )

    # Phones
    if match_any(
        [
            "samsung",
            "xiaomi",
            "redmi",
            "oneplus",
            "oppo",
            "vivo",
            "realme",
            "motorola",
            "google",
            "hmd",
            "lenovo",
            "lg electronics",
            "sony mobile",
        ]
    ):
        return "Phone"

    # Apple detection
    if "apple" in vendor or "apple" in tokens:
        return "Apple Device"

    # Laptops / PCs
    if match_any(
        [
            "intel",
            "cloud network technology",
            "azurewave",
            "lite-on",
            "compal",
            "quanta",
            "pegatron",
            "hon hai",
            "lenovo",
            "hp",
            "dell",
        ]
    ):
        return "Laptop/PC"

    # Network Gear
    if match_any(
        [
            "aruba",
            "cisco",
            "tp-link",
            "mikrotik",
            "ubiquiti",
            "juniper",
            "netgear",
            "d-link",
            "hewlett",
        ]
    ):
        return "Network Device"

    # IoT Devices
    if match_any(
        [
            "espressif",
            "tuya",
            "sonos",
            "hikvision",
            "bosch",
            "murata",
            "wyze",
            "amazon",
            "ecobee",
            "bose",
        ]
    ):
        return "IoT Device"

    return "Device"


#  ZONE DETECTION


def detect_zone(dev_list) -> str:
    """
    Determines network zone based on MAC visibility.
    - L2-LOCAL: Most hosts reveal MACs (same physical LAN)
    - L2-NEARBY: Some MACs visible, but not many (WiFi w/ isolation)
    - L3-REMOTE: No MACs (beyond ARP reach or routed)
    """

    if not dev_list:
        return "L3-REMOTE"

    # Count valid normalized MACs
    macs = [normalize_mac(d.get("mac", "")) for d in dev_list]
    mac_count = sum(1 for m in macs if m != "unknown")

    ratio = mac_count / len(dev_list)

    # Pure heuristic, but improved:
    if mac_count == 0:
        return "L3-REMOTE"
    elif ratio < 0.5:
        return "L2-NEARBY"
    else:
        return "L2-LOCAL"


#  SINGLE CALL INTERFACE


def classify_device(mac: str, vendor: str, random_flag: bool) -> str:
    """
    Exposed unified classifier.
    """
    return classify_device_type(normalize_mac(mac), vendor, random_flag)
