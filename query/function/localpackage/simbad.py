import datetime
from . import dbutils
from astroquery.simbad import Simbad
import requests
from bs4 import BeautifulSoup


def now():
    return datetime.datetime.utcnow()


def get_simbad_from_stellar_catalog(wise_short_name):
    """
    Given a WISE short name (e.g., "WISE-2056-1459"),
    scrape StellarCatalog to find the full SIMBAD identifier.
    """
    # Normalize the URL for StellarCatalog
    wise_name_url = wise_short_name.lower().replace(" ", "-")
    url = f"https://www.stellarcatalog.com/stars/{wise_name_url}"
    print(url)

    # Fetch the page
    response = requests.get(url)
    if response.status_code != 200:
        return f"Error: Could not fetch page, status code {response.status_code}"

    # Parse HTML
    soup = BeautifulSoup(response.text, "html.parser")

    # Look for SIMBAD link (it usually contains 'simbad' in the href)
    simbad_link = soup.find("a", href=lambda x: x and "simbad" in x.lower())

    if simbad_link and "href" in simbad_link.attrs:
        href = simbad_link["href"]
        # The SIMBAD identifier is usually at the end of the URL after 'Ident='
        if "Ident=" in href:
            simbad_id = href.split("Ident=")[-1]
            # Decode URL encoding if any
            simbad_id = simbad_id.replace("%20", " ").replace("%2B", "+")
            return simbad_id
        else:
            return wise_short_name
    else:
        return wise_short_name


def wise_to_simbad(wise_short_name):
    """
    Convert a WISE short name (WISE hhmm±ddmm) into a SIMBAD-style full name.

    Example:
        WISE 0350-5658 -> WISE J035000-565800
    """
    # Remove "WISE " prefix if present
    name = wise_short_name.strip().replace("WISE ", "")

    # Extract RA and Dec parts
    ra_part = name[:4]  # hhmm
    dec_part = name[4:]  # ±ddmm

    # Split RA into hours and minutes
    ra_hh = ra_part[:2]
    ra_mm = ra_part[2:]
    ra_ss = "00.00"  # placeholder for seconds

    # Split Dec into degrees and minutes
    dec_sign = dec_part[0]  # + or -
    dec_dd = dec_part[1:3]
    dec_mm = dec_part[3:]
    dec_ss = "00.0"  # placeholder for arcseconds

    # Combine into SIMBAD-style name
    simbad_name = f"WISE J{ra_hh}{ra_mm}{ra_ss}{dec_sign}{dec_dd}{dec_mm}{dec_ss}"
    return simbad_name


def get_simbad_object(system_address, name):

    dbutils.setup_sql_conn()
    cur = dbutils.get_cursor()
    try:
        dbutils.setup_sql_conn()
        cur = dbutils.get_cursor()
        # Normalize name for SIMBAD query
        norm_prefixes = "KOI"
        norm_name = name
        for prefix in norm_prefixes:
            if norm_name.startswith(prefix + " "):
                norm_name = prefix + "-" + norm_name[len(prefix) + 1 :]
                break

        # Try to get from DB
        cur.execute(
            "SELECT * FROM system_simbad_data WHERE system_address=%s AND name=%s",
            (system_address, name),
        )
        record = cur.fetchone()
        if record:
            return record  # cache hit

        # Handle WISE names specially
        if name.startswith("WISE "):
            norm_name = get_simbad_from_stellar_catalog(name)
            print(f"WISE name converted: {name} -> {norm_name}")

        # cache miss → query SIMBAD
        result = None
        successful_mirror = None
        mirrors = [
            ("simbad.u-strasbg.fr", 1),
            ("simbad.harvard.edu", 5),
            ("simbad.cds.unistra.fr", 10),
        ]

        for mirror_url, timeout in mirrors:
            try:
                simbad = Simbad()
                simbad.TIMEOUT = timeout
                simbad.server = mirror_url
                simbad.add_votable_fields("ids", "plx", "oid")
                result = simbad.query_object(norm_name)
                if result is not None:
                    successful_mirror = mirror_url
                    break  # Success, exit the loop
            except Exception as query_error:
                if mirror_url == mirrors[-1]:  # Last mirror failed
                    pass
                continue  # Try next mirror

        # Cache the result even if not found (to avoid repeated queries)
        if result is None or len(result) == 0:
            # Cache "not found" result with null fields
            record_data = {
                "system_address": system_address,
                "name": name,
                "simbad_name": None,
                "simbad_ident": None,
                "other_names": None,
                "ra_j2000": None,
                "dec_j2000": None,
                "parallax": None,
                "epoch_error_j2000b1950": False,
                "created_at": now(),
                "updated_at": now(),
            }
        else:
            # Extract data from successful result
            simbad_name = result["main_id"][0] if "main_id" in result.colnames else None
            simbad_ident = result["oid"][0] if "oid" in result.colnames else None
            other_names = result["ids"][0] if "ids" in result.colnames else None
            ra_j2000 = result["ra"][0] if "ra" in result.colnames else None
            dec_j2000 = result["dec"][0] if "dec" in result.colnames else None
            parallax = (
                result["plx_value"][0] if "plx_value" in result.colnames else None
            )
            # Convert masked or non-float parallax to float or None
            try:
                if parallax is not None and parallax != "" and parallax is not ...:
                    parallax = float(parallax)
                else:
                    parallax = None
            except Exception:
                parallax = None
            # Calculate epoch_error_j2000b1950 from coo_err_maj and coo_err_min
            epoch_error_j2000b1950 = False
            if "coo_err_maj" in result.colnames and "coo_err_min" in result.colnames:
                epoch_error_j2000b1950 = any(
                    v is not None and v > 0
                    for v in (result["coo_err_maj"][0], result["coo_err_min"][0])
                )

            record_data = {
                "system_address": system_address,
                "name": name,
                "simbad_name": simbad_name,
                "simbad_ident": simbad_ident,
                "other_names": other_names,
                "ra_j2000": ra_j2000,
                "dec_j2000": dec_j2000,
                "parallax": parallax,
                "epoch_error_j2000b1950": epoch_error_j2000b1950,
                "created_at": now(),
                "updated_at": now(),
            }
        cur.execute(
            """
            INSERT INTO system_simbad_data (system_address, name, simbad_name, simbad_ident,other_names, ra_j2000, dec_j2000, parallax, epoch_error_j2000b1950, created_at, updated_at)
            VALUES (%(system_address)s, %(name)s, %(simbad_name)s, %(simbad_ident)s,%(other_names)s,    %(ra_j2000)s, %(dec_j2000)s, %(parallax)s, %(epoch_error_j2000b1950)s, %(created_at)s, %(updated_at)s)
            ON DUPLICATE KEY UPDATE
                simbad_name=VALUES(simbad_name),
                simbad_ident=VALUES(simbad_ident),
                ra_j2000=VALUES(ra_j2000),
                dec_j2000=VALUES(dec_j2000),
                parallax=VALUES(parallax),
                epoch_error_j2000b1950=VALUES(epoch_error_j2000b1950),
                updated_at=VALUES(updated_at)
            """,
            record_data,
        )
        dbutils.mysql_conn.commit()
        # Return the new/updated row
        cur.execute(
            "SELECT * FROM system_simbad_data WHERE system_address=%s AND name=%s",
            (system_address, name),
        )
        record = cur.fetchone()
        # Add the successful mirror to the output (not stored in DB)
        if record and successful_mirror:
            # Convert to dict if needed and add mirror info
            if isinstance(record, dict):
                record["simbad_mirror"] = successful_mirror
            else:
                # If it's a tuple/other type, convert to dict
                record = dict(record) if hasattr(record, "keys") else record
                if isinstance(record, dict):
                    record["simbad_mirror"] = successful_mirror
        return record
    except Exception as e:
        import logging

        logging.error(f"SIMBAD/DB error: {e}")
        return None
