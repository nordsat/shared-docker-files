import os
import sys
import argparse
import datetime
import logging
from contextlib import closing

import yaml
from yaml import BaseLoader
import psycopg2
import rasterio
from trollsift import parse
from posttroll.subscriber import create_subscriber_from_dict_config

_LOGGER = logging.getLogger("db-push")
logging.basicConfig(level=logging.INFO)


def main(args=None):
    parsed_args = parse_args(args=args)

    try:
        trollflow_config = read_yaml_config(parsed_args.tf2_config_file, use_base_loader=True)
        pattern = trollflow_config['product_list']['fname_pattern']
        config = read_yaml_config(parsed_args.config_file)
    except Exception as exc:
        _LOGGER.error(f"Failed to load configurations: {str(exc)}")
        sys.exit(1)

    if parsed_args.files:
        _LOGGER.info("Batch processing files…")
        conn = _pg_connect(config)
        if not conn:
            sys.exit("Fatal: Could not establish database connection for batch ingest.")

        try:
            ingest_into_postgis(conn=conn, files=parsed_args.files, config=config, pattern=pattern)
        finally:
            if not conn.closed:
                conn.close()
        _LOGGER.info("Batch processing complete. Exiting.")
    else:
        subscribe_and_ingest(config=config, pattern=pattern)


def parse_args(args=None):
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Sync Sentinel-1 Footprints to PostGIS.")
    parser.add_argument("config_file", help="The configuration file for sync-db.")
    parser.add_argument("tf2_config_file", help="The trollflow2 configuration file.")
    parser.add_argument("files", nargs="*", action="store")
    return parser.parse_args(args)



def read_yaml_config(yaml_file: str, use_base_loader: bool = False):
    """Utility to read YAML configurations."""
    with open(yaml_file) as fd:
        if use_base_loader:
            return yaml.load(fd.read(), Loader=BaseLoader)
        return yaml.safe_load(fd.read())


def subscribe_and_ingest(config: dict, pattern: str):
    """Subscribe to posttroll messages and maintain a persistent DB connection."""
    conn = _pg_connect(config)
    if not conn:
        sys.exit("Fatal: Could not establish initial database connection.")

    subscriber_cfg = config.get('subscriber_settings', {})

    with closing(create_subscriber_from_dict_config(subscriber_cfg)) as sub:
        _LOGGER.info("Listening for messages...")

        for message in sub.recv():
            if message is None or message.type == 'beat':
                continue

            if message.type == 'del':
                _LOGGER.info(f"Deletion message received: {message}. (Handling not implemented)")
                continue

            try:
                files = message.data['uri']
            except KeyError:
                _LOGGER.error(f"Cannot find 'uri' in message: {message}")
                continue

            # Ensure connection is alive before trying to insert
            if conn.closed != 0:
                _LOGGER.warning("Database connection lost. Attempting to reconnect...")
                conn = _pg_connect(config)
                if not conn:
                    _LOGGER.error("Reconnection failed. Skipping message.")
                    continue

            ingest_into_postgis(conn=conn, files=files, config=config, pattern=pattern)


def _pg_connect(config: dict):
    """Connect to the database."""
    _LOGGER.info("Connecting to PostgreSQL...")
    try:
        conn = psycopg2.connect(
            host=config['pg_host_name'],
            port='5432',
            dbname=config['pg_database_name'],
            user=config['pg_user_name'],
            password=os.environ['POSTGRES_PASSWORD']
        )
        return conn
    except psycopg2.OperationalError as e:
        _LOGGER.error(f"Failed to connect to database: {e}")
        return None


def ingest_into_postgis(conn: psycopg2.extensions.connection, 
                        files: list, 
                        config: dict, 
                        pattern: str):
    """Filter files by product and trigger database insertion."""
    inserted = False

    if isinstance(files, str):
        files = [files]
    if not files:
        return False

    for input_file in files:
        basename = os.path.basename(input_file)

        _LOGGER.info(f"Processing {input_file}.")
        img_time, geom_json = collect_metadata_from_tiff(input_file=input_file)
        mda = parse(pattern, basename)

        if img_time and geom_json:
            if insert_into_db(conn, input_file, mda["productname"], img_time, geom_json, config):
                _LOGGER.info(f"Successfully registered {basename}.")
                inserted = True
    return inserted


def collect_metadata_from_tiff(input_file: str):
    """Use rasterio to collect exact footprint from grid or GCPs and datetime."""
    try:
        with rasterio.open(input_file) as ds:

            tags = ds.tags
            time_str = tags.get('TIFFTAG_DATETIME')
            if time_str:
                img_time = datetime.datetime.strptime(time_str, '%Y:%m:%d %H:%M:%S')
            else:
                _LOGGER.error(f"TIFFTAG_DATETIME missing in {input_file}")
                img_time = None
            gcps, gcp_crs = ds.gcps

            if gcps:  # Sentinel 1 GRD data for example
                _LOGGER.info(f"Detected GCPs in {input_file}. Building Multipoint cloud.")
                points = [f"{gcp.x} {gcp.y}" for gcp in gcps]
                geom_wkt = f"MULTIPOINT({', '.join(points)})"

                # Default to 4326 if undefined, otherwise extract from GCP CRS
                srid = 4326
                if gcp_crs and gcp_crs.is_epsg_code:
                    srid = gcp_crs.to_epsg()

            else:  # standard grid
                _LOGGER.info(f"Detected standard affine grid in {input_file}. Building Bounding Box.")
                crs = ds.crs
                if not crs or not crs.is_epsg_code:
                    _LOGGER.error(f"Missing valid EPSG CRS in standard TIFF {input_file}. Cannot proceed.")
                    return img_time, None, None
                srid = crs.to_epsg()
                bounds = ds.bounds
                geom_wkt = (
                    f"POLYGON(({bounds.left} {bounds.bottom}, "
                    f"{bounds.left} {bounds.top}, "
                    f"{bounds.right} {bounds.top}, "
                    f"{bounds.right} {bounds.bottom}, "
                    f"{bounds.left} {bounds.bottom}))"
                )

            return img_time, geom_wkt, srid

    except Exception as ex:
        _LOGGER.exception(f"Cannot collect info from file {input_file}. Exception: {str(ex)}")
        return None, None


def insert_into_db(conn: psycopg2.extensions.connection, 
                   filename: str, 
                   product_name: str, 
                   image_time: datetime.datetime, 
                   geom_wkt: str, 
                   native_srid: int, 
                   db_config: dict):
    """Safely insert into database using EPSG:3575 and Concave Hull for maximum WMS efficiency."""
    table = db_config['pg_table_name']
    
    select_query = f"SELECT 1 FROM {table} WHERE filename = %s;"
    
    # 1. Read the GCP Multipoint (or affine Polygon) in its native SRID (usually 4326)
    # 2. Instantly transform the points to your working projection (3575)
    # 3. Shrink-wrap the points using ST_ConcaveHull (0.95 tightness)
    insert_query = f"""
        INSERT INTO {table} (filename, product_name, time, geom) 
        VALUES (
            %s, %s, %s, 
            ST_ConcaveHull(
                ST_Transform(
                    ST_SetSRID(ST_GeomFromText(%s), %s), 
                    3575
                ), 
                0.95, -- Target percent: tweak this between 0.90 and 0.99 if needed
                false -- Do not allow interior holes
            )
        );
    """

    inserted = False
    try:
        with conn.cursor() as curs:
            curs.execute(select_query, (filename,))
            if curs.fetchone():
                _LOGGER.info(f"File {filename} is already in the database. Skipping.")
            else:
                curs.execute(insert_query, (filename, product_name, image_time, geom_wkt, native_srid))
                inserted = True
            conn.commit()
    except psycopg2.Error as e:
        _LOGGER.error(f"Database error during insert: {str(e)}")
        conn.rollback()

    return inserted


if __name__ == "__main__":
    main(sys.argv[1:])
