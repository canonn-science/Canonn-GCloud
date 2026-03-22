import datetime
import logging
from . import dbutils
from astroquery.simbad import Simbad
from astropy import units as u
from astropy.coordinates import (
    SkyCoord,
    CartesianRepresentation,
    SphericalRepresentation,
    Galactic,
    ICRS,
)
from astropy.table import QTable


def now():
    return datetime.datetime.utcnow()


def search_simbad_by_coordinates(x, y, z, name=None, maxdist_ly=0.1):
    """
    Search SIMBAD for the nearest star, pulsar, or black hole within maxdist_ly
    of the given Elite Dangerous coordinates (x, y, z in light years).
    If name starts with 'WISE', prefer returning a WISE object if found.
    Returns the main_id if found, None otherwise.
    """
    print(
        f"[SIMBAD] Starting coordinate search at ({x}, {y}, {z}) with max distance {maxdist_ly} ly, name hint: '{name}'"
    )
    try:
        # Convert Elite Dangerous coordinates to galactic coordinates
        cart = CartesianRepresentation(z, -x, y, unit=u.lightyear)
        coord = SphericalRepresentation.from_cartesian(cart)
        icrs = SkyCoord(coord.lon, coord.lat, coord.distance, frame=Galactic).icrs

        # Calculate search radius in degrees
        maxdist = maxdist_ly * u.lightyear
        radius = (maxdist * u.radian / coord.distance) << u.deg
        print(
            f"[SIMBAD] Converted coords - ICRS RA: {icrs.ra}, Dec: {icrs.dec}, Distance: {coord.distance}, Search radius: {radius}"
        )

        # Build coordinate table for TAP query (both ICRS and FK4 frames)
        fk4 = icrs.fk4
        fk4_icrs = SkyCoord(fk4.ra, fk4.dec, fk4.distance, frame=ICRS)

        coords = QTable(
            names=("frame", "ra", "dec", "radius", "distance"),
            rows=[
                (
                    "icrs",
                    u.Quantity(icrs.ra),
                    u.Quantity(icrs.dec),
                    radius,
                    coord.distance,
                ),
                (
                    "fk4_icrs",
                    u.Quantity(fk4_icrs.ra),
                    u.Quantity(fk4_icrs.dec),
                    radius,
                    coord.distance,
                ),
            ],
        )

        # TAP query to find nearest objects (stars, pulsars, black holes)
        query = """
        SELECT
            sys_coords.frame,
            basic.oid,
            basic.main_id,
            basic.otype,
            basic.ra,
            basic.dec,
            basic.plx_value,
            RADIANS(DISTANCE(POINT('ICRS', basic.ra, basic.dec), POINT('ICRS', sys_coords.ra, sys_coords.dec))) * sys_coords."distance" AS distance_ly
        FROM TAP_UPLOAD.sys_coords
        JOIN basic ON CONTAINS(POINT('ICRS', basic.ra, basic.dec), CIRCLE('ICRS', sys_coords.ra, sys_coords.dec, sys_coords.radius)) = 1
        WHERE basic.otype IN ('*', 'Pulsar', 'BH', 'V*', 'PM*', 'HV*', 'C*', 'WD*', 'BD*', 'N*', 'sg*', 'AB*', 'Mi*', 'sr*', 'Ce*', 'RR*', 'Ro*', 'LP*', 'Er*', 'Fl*', 'Or*', 'SB*', 'El*', 'EB*', 'Be*', 'WR*', 'Al*', 'bC*', 'XB*', 'Sy*', 'CV*', 'No*', 'RG*', 'HB*', 'BS*', 'RC*', 'Pl')
        ORDER BY distance_ly ASC
        """

        mirrors = [
            ("simbad.cds.unistra.fr", 5),
            ("simbad.harvard.edu", 10),
        ]

        for mirror_url, timeout in mirrors:
            try:
                print(f"[SIMBAD] Trying TAP query on mirror: {mirror_url}")
                simbad = Simbad()
                simbad.TIMEOUT = timeout
                simbad.server = mirror_url
                result = simbad.query_tap(query=query, sys_coords=coords)

                if result is not None and len(result) > 0:
                    # Print all results
                    print(f"[SIMBAD] Found {len(result)} objects via coordinates:")
                    for i, row in enumerate(result):
                        print(f"[SIMBAD]   {i+1}. oid: {row['oid']}, main_id: {row['main_id']}, otype: {row['otype']}, distance: {row['distance_ly']:.6f} ly, frame: {row['frame']}")
                    
                    # If name starts with WISE, prefer a WISE object closest to coordinates
                    if name and name.upper().startswith("WISE"):
                        # Filter for WISE objects and pick the closest one
                        wise_results = [row for row in result if str(row['main_id']).upper().startswith("WISE")]
                        if wise_results:
                            # Already sorted by distance, so first WISE result is closest
                            closest_wise = wise_results[0]
                            print(f"[SIMBAD] Name starts with WISE, selecting closest WISE object: '{closest_wise['main_id']}' at distance {closest_wise['distance_ly']:.6f} ly")
                            return closest_wise['main_id']
                        else:
                            print(f"[SIMBAD] Name starts with WISE but no WISE objects found in results, falling back to most common")
                    
                    # Count occurrences of each main_id to find the most common
                    from collections import Counter
                    main_id_counts = Counter(result["main_id"])
                    most_common_main_id, count = main_id_counts.most_common(1)[0]
                    
                    print(f"[SIMBAD] Most common main_id: '{most_common_main_id}' (appears {count} times out of {len(result)})")
                    return most_common_main_id
                else:
                    print(f"[SIMBAD] No results from TAP query on {mirror_url}")
            except Exception as e:
                print(f"[SIMBAD] Coordinate search failed on {mirror_url}: {e}")
                continue

        print("[SIMBAD] Coordinate search exhausted all mirrors, no results found")
        return None
    except Exception as e:
        print(f"[SIMBAD] Error in coordinate search: {e}")
        return None


def get_simbad_object(system_address, name, x=None, y=None, z=None):
    print(
        f"[SIMBAD] get_simbad_object called: system_address={system_address}, name='{name}', coords=({x}, {y}, {z})"
    )

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
                print(f"[SIMBAD] Normalized name: '{name}' -> '{norm_name}'")
                break

        # Try to get from DB
        cur.execute(
            "SELECT * FROM system_simbad_data WHERE system_address=%s AND name=%s",
            (system_address, name),
        )
        record = cur.fetchone()
        if record:
            print(f"[SIMBAD] Cache hit for '{name}', returning cached record")
            return record  # cache hit

        # cache miss → query SIMBAD by name
        print(
            f"[SIMBAD] Cache miss for '{name}', querying SIMBAD by name: '{norm_name}'"
        )
        result = None
        successful_mirror = None
        mirrors = [
            ("simbad.cds.unistra.fr", 5),
            ("simbad.harvard.edu", 10),
        ]

        for mirror_url, timeout in mirrors:
            try:
                print(f"[SIMBAD] Trying name query on mirror: {mirror_url}")
                simbad = Simbad()
                simbad.TIMEOUT = timeout
                simbad.server = mirror_url
                simbad.add_votable_fields("ids", "plx", "oid")
                result = simbad.query_object(norm_name)
                if result is not None:
                    print(
                        f"[SIMBAD] Name query succeeded on {mirror_url}, found: {result['main_id'][0] if 'main_id' in result.colnames else 'unknown'}"
                    )
                    successful_mirror = mirror_url
                    break  # Success, exit the loop
                else:
                    print(f"[SIMBAD] Name query returned None on {mirror_url}")
            except Exception as query_error:
                print(f"[SIMBAD] Name query failed on {mirror_url}: {query_error}")
                if mirror_url == mirrors[-1]:  # Last mirror failed
                    pass
                continue  # Try next mirror

        # If name-based query failed and we have coordinates, try coordinate search
        if (
            (result is None or len(result) == 0)
            and x is not None
            and y is not None
            and z is not None
        ):
            print(
                f"[SIMBAD] Name-based query failed for '{name}', attempting coordinate search at ({x}, {y}, {z})"
            )
            main_id = search_simbad_by_coordinates(x, y, z, name=name)

            if main_id:
                # Found a nearby object via coordinates, now query SIMBAD with that main_id
                print(
                    f"[SIMBAD] Found nearby object '{main_id}', querying SIMBAD for full details"
                )
                for mirror_url, timeout in mirrors:
                    try:
                        print(
                            f"[SIMBAD] Trying detail query for '{main_id}' on mirror: {mirror_url}"
                        )
                        simbad = Simbad()
                        simbad.TIMEOUT = timeout
                        simbad.server = mirror_url
                        simbad.add_votable_fields("ids", "plx", "oid")
                        result = simbad.query_object(main_id)
                        if result is not None:
                            print(f"[SIMBAD] Detail query succeeded on {mirror_url}")
                            successful_mirror = mirror_url
                            break
                        else:
                            print(
                                f"[SIMBAD] Detail query returned None on {mirror_url}"
                            )
                    except Exception as query_error:
                        print(
                            f"[SIMBAD] Detail query failed on {mirror_url}: {query_error}"
                        )
                        continue
            else:
                print(f"[SIMBAD] Coordinate search found no nearby objects")

        # Now process the result (either from name query or coordinate fallback)
        if result is None or len(result) == 0:
            # All options exhausted - cache "not found" result with null fields
            print(f"[SIMBAD] All options exhausted for '{name}', caching empty record")
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
            print(
                f"[SIMBAD] Found data - simbad_name: {simbad_name}, oid: {simbad_ident}, parallax: {parallax}"
            )

        print(f"[SIMBAD] Storing record in database for '{name}'")
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
        print(
            f"[SIMBAD] Returning record for '{name}': simbad_name={record.get('simbad_name') if isinstance(record, dict) else 'N/A'}"
        )
        return record
    except Exception as e:
        print(f"[SIMBAD] ERROR in get_simbad_object: {e}")
        import traceback

        traceback.print_exc()
        return None
