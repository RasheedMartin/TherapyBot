"""
Find licensed mental-health providers near a ZIP code.

Provider data comes from the CMS NPI Registry (public, no key) and addresses are
geocoded with the US Census Bureau batch geocoder (public, no key). Neither source
says whether someone is accepting new clients or takes a given insurance, so the UI
tells users to confirm by phone.
"""

import csv
import hashlib
import io
import logging
import statistics
from concurrent.futures import ThreadPoolExecutor

import requests
from django.core.cache import cache

logger = logging.getLogger(__name__)

NPI_URL = "https://npiregistry.cms.hhs.gov/api/"
GEOCODE_URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
TIMEOUT = 20
CACHE_SECONDS = 60 * 60 * 24

# key -> (label, NPI taxonomy search term, accepted primary taxonomies; a trailing * matches a prefix)
PROVIDER_TYPES = {
    "psychologist": ("Psychologist", "Psycholog*", ("Psychologist*",)),
    "counselor": ("Counselor", "Counselor", ("Counselor", "Counselor, Mental Health", "Counselor, Professional")),
    "social_worker": ("Clinical social worker", "Social Worker", ("Social Worker, Clinical",)),
    "marriage_family": ("Marriage & family therapist", "Marriage", ("Marriage & Family Therapist",)),
    "psychiatrist": (
        "Psychiatrist",
        "Psychiatry",
        ("Psychiatry & Neurology, Psychiatry", "Psychiatry & Neurology, Child & Adolescent Psychiatry"),
    ),
    "substance_use": ("Substance use counselor", "Counselor", ("Counselor, Addiction (Substance Use Disorder)",)),
}
DEFAULT_TYPES = ["psychologist", "counselor", "social_worker", "marriage_family"]
WIDEN_BELOW = 15  # if an exact ZIP finds fewer providers than this, search the surrounding area


class ProviderSearchError(Exception):
    pass


def _name_case(text: str) -> str:
    return (text or "").strip().title()


def _address_case(text: str) -> str:
    # "224 W 35TH ST STE 500" -> "224 W 35th St Ste 500"
    return " ".join(w.capitalize() for w in (text or "").split())


def _accepts(type_key: str, desc: str) -> bool:
    return any(
        desc.startswith(a[:-1]) if a.endswith("*") else desc == a for a in PROVIDER_TYPES[type_key][2]
    )


def _format_phone(raw: str) -> str:
    digits = "".join(c for c in raw or "" if c.isdigit())
    return f"({digits[:3]}) {digits[3:6]}-{digits[6:10]}" if len(digits) == 10 else (raw or "")


def _normalize(record: dict, type_key: str) -> dict | None:
    primary = next((t for t in record.get("taxonomies", []) if t.get("primary")), None)
    if not primary or not _accepts(type_key, primary.get("desc", "")):
        return None
    location = next((a for a in record.get("addresses", []) if a.get("address_purpose") == "LOCATION"), None)
    if not location or location.get("country_code") != "US":
        return None

    basic = record.get("basic", {})
    is_org = record.get("enumeration_type") == "NPI-2"
    if is_org:
        name = _name_case(basic.get("organization_name", ""))
    else:
        name = _name_case(" ".join(filter(None, [basic.get("first_name"), basic.get("last_name")])))
    if not name:
        return None

    street = " ".join(filter(None, [location.get("address_1"), location.get("address_2")]))
    return {
        "npi": record["number"],
        "name": name,
        "credential": "" if is_org else (basic.get("credential") or "").replace(".", "").upper(),
        "is_organization": is_org,
        "type": type_key,
        "type_label": PROVIDER_TYPES[type_key][0],
        "specialty": primary["desc"],
        "license_state": primary.get("state") or "",
        "street": _address_case(street),
        "geocode_street": location.get("address_1", ""),
        "city": _name_case(location.get("city", "")),
        "state": location.get("state", ""),
        "zip": (location.get("postal_code") or "")[:5],
        "phone": _format_phone(location.get("telephone_number", "")),
        "lat": None,
        "lng": None,
    }


def _search_npi(type_key: str, postal_code: str) -> list[dict]:
    params = {
        "version": "2.1",
        "taxonomy_description": PROVIDER_TYPES[type_key][1],
        "postal_code": postal_code,
        "address_purpose": "LOCATION",
        "limit": 200,
    }
    res = requests.get(NPI_URL, params=params, timeout=TIMEOUT)
    res.raise_for_status()
    data = res.json()
    if data.get("Errors"):
        logger.warning("NPI search error for %s %s: %s", type_key, postal_code, data["Errors"])
        return []
    return [p for p in (_normalize(r, type_key) for r in data.get("results", [])) if p]


def _geocode(providers: list[dict]) -> None:
    """Fill in lat/lng in place, one batch request for all uncached addresses."""
    pending = {}
    for p in providers:
        address = f"{p['geocode_street']}|{p['city']}|{p['state']}|{p['zip']}".lower()
        key = "geo:" + hashlib.sha1(address.encode()).hexdigest()
        hit = cache.get(key)
        if hit:
            p["lat"], p["lng"] = hit
        elif hit is None:
            pending.setdefault(key, []).append(p)
    if not pending:
        return

    keys = list(pending)
    buf = io.StringIO()
    writer = csv.writer(buf)
    for i, key in enumerate(keys):
        p = pending[key][0]
        writer.writerow([i, p["geocode_street"], p["city"], p["state"], p["zip"]])
    try:
        res = requests.post(
            GEOCODE_URL,
            files={"addressFile": ("addresses.csv", buf.getvalue(), "text/csv")},
            data={"benchmark": "Public_AR_Current"},
            timeout=60,
        )
        res.raise_for_status()
    except requests.RequestException:
        logger.warning("Census geocoding failed; providers will be listed without map pins", exc_info=True)
        return

    for row in csv.reader(io.StringIO(res.text)):
        if len(row) < 6 or not row[0].isdigit():
            continue
        key = keys[int(row[0])]
        coords = None
        if row[2] == "Match" and "," in row[5]:
            lng, lat = (float(v) for v in row[5].split(","))
            coords = (round(lat, 6), round(lng, 6))
            for p in pending[key]:
                p["lat"], p["lng"] = coords
        cache.set(key, coords or False, CACHE_SECONDS)  # False = known miss, don't retry


def search_providers(zip_code: str, types: list[str]) -> dict:
    types = [t for t in types if t in PROVIDER_TYPES] or DEFAULT_TYPES
    cache_key = f"providers:{zip_code}:{','.join(sorted(types))}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    def run(postal_code):
        with ThreadPoolExecutor(max_workers=len(types)) as pool:
            batches = list(pool.map(lambda t: _search_npi(t, postal_code), types))
        seen, merged = set(), []
        for batch in batches:
            for p in batch:
                if p["npi"] not in seen:
                    seen.add(p["npi"])
                    merged.append(p)
        return merged

    try:
        providers = run(zip_code)
        widened = len(providers) < WIDEN_BELOW
        if widened:
            providers = run(zip_code[:3] + "*")
    except requests.RequestException as e:
        raise ProviderSearchError("The provider directory is unavailable right now.") from e

    # Individuals first, then organizations; same ZIP first
    providers.sort(key=lambda p: (p["is_organization"], p["zip"] != zip_code, p["name"]))
    providers = providers[:150]
    _geocode(providers)
    for p in providers:
        p.pop("geocode_street", None)

    pinned = [p for p in providers if p["lat"] is not None]
    center = (
        {"lat": statistics.median(p["lat"] for p in pinned), "lng": statistics.median(p["lng"] for p in pinned)}
        if pinned
        else None
    )
    result = {"zip": zip_code, "widened": widened, "center": center, "providers": providers}
    cache.set(cache_key, result, CACHE_SECONDS)
    return result
