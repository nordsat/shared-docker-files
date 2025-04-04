import os
import sys
import argparse
import datetime
import traceback
import logging

from contextlib import closing

import yaml
from yaml import BaseLoader
import psycopg2
import rasterio
from posttroll.subscriber import create_subscriber_from_dict_config

_LOGGER = logging.getLogger("db-sync")

logging.basicConfig(level=logging.INFO)


def subscribe_and_ingest(config: dict, areas: dict):
    """Subscribe to posttroll messages and ingest the data filename/uri.

       It is inserted into a postgis to be used by mapserver.
    """
    conn = pg_connect(config)
    layer_string = create_mapserver_layer_config(conn=conn, areas=areas, config=config)
    if layer_string:
        tmp_layer_file_path = f"{config['mapfile_include_layers_filename']}"

        with open(tmp_layer_file_path, 'wt') as fd:
            fd.write(layer_string)

    with closing(create_subscriber_from_dict_config(config['subscriber_settings'])) as sub:
        for message in sub.recv():

            if message is None or message.type == 'beat':
                _LOGGER.warning(f"Skipping message {message}. Not used here.")
                continue

            if message.type == 'del':
                _LOGGER.info(f"Deleting product due to message: {message}")
                deleted = False
                continue

            try:
                files = message.data['uri']

            except KeyError:
                _LOGGER.error(f"Cannot find uri in message: {message}")
                continue

            conn = pg_connect(config)

            if conn and conn.status:
                _LOGGER.info(f"Postgis DB connected with STATUS: {conn.status}")
            else:
                _LOGGER.error(
                    f"Failed to get connection to postgis db. Message will be skipped. {message}"
                )
                continue

            inserted = ingest_into_postgis(conn=conn, files=files, config=config, areas=areas)

            if inserted:

                # Create MAPfile layers
                layer_string = create_mapserver_layer_config(conn=conn, areas=areas, config=config)
                if not layer_string:
                    _LOGGER.error(f"File from {message} was inserted into the database, but layer were not added to mapfile. Check errors above.")
                    continue

                tmp_layer_file_path = f"{config['mapfile_include_layers_filename']}"

                with open(tmp_layer_file_path, 'wt') as fd:
                    fd.write(layer_string)


def ingest_into_postgis(conn: psycopg2.connect, files: list, config: dict, areas: dict):
    """Ingest into POSTGIS.

       If file basename starts with a configured product try to insert into database.
       Return True of one or more products were inserted
    """
    inserted = []

    if isinstance(files, str):
        files = [files, ]

    if files is None:
        files = []

    for area in areas:

        for product_name in areas[area]['products']:

            for input_file in files:
                _LOGGER.info(f"Considering file {input_file} for prodcut {product_name} for area {area}")
                bn_f = os.path.basename(input_file)

                if product_name in bn_f:
                    img_time, geom = collect_data_from_file(input_file=input_file)

                    if geom:
                        _LOGGER.info("Adding file to db.")
                        _LOGGER.debug(str(geom))
                        inserted.append(
                            insert_into_db(
                                conn=conn,
                                filename=input_file,
                                product_name=product_name,
                                image_time=img_time,
                                geom=geom,
                                db_config=config
                            )
                        )

    return any(inserted)


def get_from_db(conn: psycopg2.connect, select_string: str):
    """Use selec string to retrieve data from db."""
    result = None
    try:
        _LOGGER.info(f"Connection: {conn}")

        if conn and conn.status:
            _LOGGER.info(f"STATUS: {conn.status}")

            curs = conn.cursor()
            curs.execute(f"{select_string}")
            fetched = curs.fetchone()
            curs.close()
            result = fetched[0]

    except psycopg2.OperationalError as poe:
        _LOGGER.error(f"Failed pg connect/execute: {str(poe)}")
        pass

    return result


def create_mapserver_layer_config(conn: psycopg2.connect, areas, config: dict):
    """Update mapserver layer config with time_extent from database"""
    layer_string = ""

    for area in areas:
        for product in areas[area]['products']:

            _LOGGER.debug(f"Product: {product}")

            # SELECT time extent
            time_extent = ""
            time_default = ""
            try:
                time_interval = int(config["time_slot_interval_in_minutes"])
                select_string = (
                    f"select to_char(min(time),'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"') "
                    f"|| '/' || to_char(max(time), 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"') "
                    f"|| '/PT{time_interval}M' "
                    f"from {config['pg_table_name']} where product_name='{product}';"
                )
            except ValueError:
                select_string = (f"select string_agg(to_char(time,'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"'), ',') as times "
                                 f"from {config['pg_table_name']} where product_name='{product}';")
            _LOGGER.info(select_string)
            time_extent = get_from_db(conn=conn, select_string=select_string)
            if time_extent:
                try:
                    time_default = time_extent.split('/')[1]
                except IndexError:
                    time_default = time_extent.split(",")[-1]
            else:
                _LOGGER.error(f"Skipping product {product} because time_extent is missing.")
                continue

            _LOGGER.debug(f"TIME EXTENT {time_extent}")

            # SELECT extent
            extent = ""
            wms_extent_select_string = (
                f"select st_extent(geom) from {config['pg_table_name']} "
                f"where product_name='{product}';"
            )
            extent = get_from_db(conn=conn, select_string=wms_extent_select_string)
            if extent:
                extent = extent.replace("BOX(",'').replace(',', ' ').replace(")", '')
            else:
                _LOGGER.error(f"Skipping product {product} because extent is missing.")
                continue

            _LOGGER.debug(f"EXTENT {extent}")

            # SELECT srid
            srid = ""
            srid_select_string = (
                f"select st_srid(geom) from {config['pg_table_name']} "
                f"where product_name='{product}';"
            )
            srid = get_from_db(conn=conn, select_string=srid_select_string)
            if not srid:
                _LOGGER.error(f"Skipping product {product} because SRID is missing.")
                continue

            _LOGGER.debug(f"SRID {srid}")

            # Create LAYERS for MapFile for a product
            mapfile_layer_template=f"""
  LAYER
    STATUS OFF
    NAME "time_idx_{product}"
    TYPE POLYGON
    # Mapserver requires some unique field for SQL query
    DATA "geom from (select * from {config['pg_table_name']} where product_name='{product}') as foo using unique id"
    METADATA
      "wms_title" "TIME INDEX"
      "wms_srs" "EPSG:{srid}"
      "wms_timeextent" "{time_extent}"
      "wms_timeitem" "time" #column in postgis table of type timestamp
      "wms_timedefault" "{time_default}"
      "wms_enable_request" "!*"
      "wms_extent" "{extent}"
    END
    PROJECTION
      "init=epsg:{srid}"
    END
    CONNECTIONTYPE postgis
    CONNECTION "host={config['pg_host_name']} user={config['pg_user_name']} dbname={config['pg_database_name']} port=5432 password={os.environ['POSTGRES_PASSWORD']}"
  END

  LAYER
    PROJECTION
      "init=epsg:{srid}"
    END
    NAME "{product}"
    STATUS ON
    TYPE raster
    METADATA
      "wms_title" "{product}"
      "wms_srs" "EPSG:{srid}"
      "wms_timeextent" "{time_extent}"
      "wms_enable_request" "*"
      "wms_timeitem" "time"
      "wms_extent" "{extent}"
    END
    TILEINDEX time_idx_{product}
    TILEITEM "filename"
  END
"""

            layer_string += mapfile_layer_template

    return layer_string


def collect_data_from_file(input_file: str):
    """Use rasterio to collect extent, time and srs info."""
    try:
        dataset = rasterio.open(input_file)

    except Exception as ex:
        _LOGGER.error(f"Cannot collect info from file {input_file}. Exception rasterio open is {str(ex)}")
        return None, None

    try:
        tags = dataset.tags()

    except Exception as ex:
        _LOGGER.error(f"Cannot collect info from file {input_file}. Exception dataset tags is {str(ex)}")
        return None, None

    try:
        img_time = datetime.datetime.strptime(tags['TIFFTAG_DATETIME'], '%Y:%m:%d %H:%M:%S')

    except Exception as ex:
        _LOGGER.error(f"Cannot collect info from file {input_file}. Exception img_time is {str(ex)}")
        traceback.print_exc()
        img_time = None

        return img_time, None

    try:
        bounds = dataset.bounds
        _LOGGER.info(f"Bounds: {bounds}")
    except Exception as ex:
        _LOGGER.error(f"Cannot collect info from file {input_file}. Exception bounds is {str(ex)}")
        return img_time, None

    ll_x = bounds[0]
    ll_y = bounds[1]
    ur_x = bounds[2]
    ur_y = bounds[3]

    try:
        crs = dataset.crs.to_authority()

    except Exception as ex:
        _LOGGER.error(f"Cannot collect info from file {input_file}. Exception crs is {str(ex)}")
        crs = None

    if crs is None:
        _LOGGER.error(
            "crs from file is None. Authority was not found."
            "Need a crs to get geometry in postgis right."
            f"Skipping {input_file}"
        )

        return img_time, None

    geom = "ST_SetSRID(ST_MakeBox2D(ST_Point({}, {}), ST_Point({}, {})), {})".format(
        ll_x,
        ll_y,
        ur_x,
        ur_y,
        crs[1]
    )

    return img_time, geom


## DATABASE METHODS
def pg_connect(config: dict):
    """Connect to the database."""
    _LOGGER.info("Connecting to pg")

    conn = psycopg2.connect(
        host=config['pg_host_name'],
        port='5432',
        dbname=config['pg_database_name'],
        user=config['pg_user_name'],
        password=os.environ['POSTGRES_PASSWORD']
    )

    return conn


def insert_into_db(
    conn: psycopg2.connect,
    filename: str,
    product_name: str,
    image_time: datetime.datetime,
    geom: str,
    db_config: dict
):
    """Check if file already exists, if not, insert into database. Return True if inserted."""
    insert = f"insert into {db_config['pg_table_name']}(filename, product_name, time, geom)"

    insert_string = "{} values('{}', '{}', '{:%Y-%m-%d %H:%M:%S}Z', {});".format(
        insert,
        filename,
        product_name,
        image_time,
        geom
    )
    select_string = f"select * from {db_config['pg_table_name']} where filename='{filename}';"

    inserted = False

    try:
        curs = conn.cursor()
        curs.execute(f"{select_string}")

        if curs.fetchone():
            _LOGGER.info(f"File {filename} already in the db. Don't insert.")
        else:
            curs.execute(f"{insert_string}")
            inserted = True

        conn.commit()
        curs.close()

    except psycopg2.OperationalError as poe:
        _LOGGER.error(f"Failed pg connect/execute: {str(poe)}")
        pass

    return inserted


def read_trollflow2_config(yaml_file: str):
    """Read trollflow2 config."""
    with open(yaml_file) as fd:
        trollflow2_config = yaml.load(fd.read(), Loader=BaseLoader)

    return trollflow2_config


def read_config(yaml_file: str):
    """Read a config file."""
    with open(yaml_file) as fd:
        db_sync_config = yaml.safe_load(fd.read())

    return db_sync_config


def parse_args(args=None):
    """Parse commandline arguments."""
    parser = argparse.ArgumentParser(
        "Database sync",
        description="Sync Postgis DB and update Mapfile layers."
    )
    parser.add_argument(
        "config_file",
        help="The configuration file for sync-db to run on."
    )
    parser.add_argument(
        "tf2_config_file",
        help="The trollflow2 configuration file to run on."
    )
    parser.add_argument("files", nargs="*", action="store")

    return parser.parse_args(args)


def main(args=None):
    """Main script."""
    parsed_args = parse_args(args=args)

    try:
        trollflow_config = read_trollflow2_config(yaml_file=parsed_args.tf2_config_file)
    except Exception as exc:
        _LOGGER.error(f"Could not read the trollflow2 config due to: {str(exc)}")
        sys.exit(1)

    areas = trollflow_config['product_list']['areas']

    try:
        config = read_config(yaml_file=parsed_args.config_file)
    except Exception as exc:
        _LOGGER.error(f"Could not read the db-sync config due to: {str(exc)}")
        sys.exit(1)

    subscribe_and_ingest(config=config, areas=areas)


if __name__ == "__main__":
    main(sys.argv[1:])
