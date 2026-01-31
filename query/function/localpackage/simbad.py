import datetime
from . import dbutils
from astroquery.simbad import Simbad


def now():
    return datetime.datetime.utcnow()


def get_simbad_object(system_address, name):

    dbutils.setup_sql_conn()
    cur = dbutils.get_cursor()
    try:
        dbutils.setup_sql_conn()
        cur = dbutils.get_cursor()
        # Normalize name for SIMBAD query
        norm_prefixes = ("KOI", "HD", "HIP", "CPC")
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

        # cache miss → query SIMBAD
        simbad = Simbad()
        simbad.add_votable_fields("ids", "plx", "oid")
        result = simbad.query_object(norm_name)
        print(f"SIMBAD query_object({norm_name}) result: {result}")
        if result is not None:
            print(f"SIMBAD columns: {result.colnames}")
            if len(result) > 0:
                for col in result.colnames:
                    print(f"{col}: {result[col][0]}")
            else:
                print("SIMBAD returned a table with no rows.")
        if result is None:
            return None
        # Only extract fields if there is at least one row
        if len(result) == 0:
            return None

        simbad_name = result["main_id"][0] if "main_id" in result.colnames else None
        simbad_ident = result["oid"][0] if "oid" in result.colnames else None
        other_names = result["ids"][0] if "ids" in result.colnames else None
        ra_j2000 = result["ra"][0] if "ra" in result.colnames else None
        dec_j2000 = result["dec"][0] if "dec" in result.colnames else None
        parallax = result["plx_value"][0] if "plx_value" in result.colnames else None
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
        return cur.fetchone()
    except Exception as e:
        import logging

        logging.error(f"SIMBAD/DB error: {e}")
        return None
