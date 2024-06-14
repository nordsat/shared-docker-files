import os
import sys
import yaml
import argparse
import datetime
import psycopg2
import rasterio
import traceback
import logging
from contextlib import closing
from posttroll.subscriber import create_subscriber_from_dict_config

_LOGGER = logging.getLogger("db-sync")

logging.basicConfig(level=logging.INFO)

"""
Example of a needed config:
---
# You can either give a trollflow2 config file or a hardcoded list of products
trollflow2_config_file: home/trygveas/Git/ewc-config/config_fci_nc/trollflow2_fci_nc.yaml
product_list:
  areas:
    nordsat1km:
      products:
        airmass:
        true_color_day:
        natural_color_day:
# Also needed postgis credentials, database and table name to use.
pg_table_name: products
pg_user_name: postgres
pg_password: password
pg_database_name: postgres
# This host_name is used for communication between running containers
pg_host_name: some-postgres
# THis host name is from this script running from commandline to postgis database
host_name: localhost
# File name if the generated mapserver map layers configuration. This needs to be included in your mapserver map file.
mapfile_include_layers_filename: mapfile_layers.map

subscriber_settings:
    nameserver: false
    addresses: ipc://bla

"""

def read_config(yaml_file):
    """Read a config file."""
    with open(yaml_file) as fd:
        data = yaml.safe_load(fd.read())
    
    return data

def subscribe_and_ingest(config, areas):
    """Subscribe to posttroll messages and ingest the data filename/uri.

       It is inserted into a postgis to be used by mapserver.
    """
    with closing(create_subscriber_from_dict_config(config['subscriber_settings'])) as sub:
        for message in sub.recv():

            if message is None or message.type == 'beat':
                _LOGGER.warning(f"Skipping message {message}. Not used here.")
                continue

            try:
                files = message.data['uri']

            except KeyError:
                _LOGGER.error(f"Can not find uri in message: {message}")
                continue

            conn = pg_connect(config)

            if conn and conn.status:
                print("Postgis DB connected with STATUS:", conn.status, flush=True)
            else:
                print("Failed to get connection to postgis db. Message will not be atempt inserted.")
                continue
            
            inserted = ingest_into_postgis(conn, files, config, areas)
            
            if inserted:

                # Create or update MAPfile
                layer_string = create_mapserver_layer_config(conn, areas, config)

                tmp_layer_file_path = f"{config['mapfile_include_layers_filename']}" 

                with open(tmp_layer_file_path, 'wt') as fd:
                    fd.write(layer_string)

                #if os.path.exists(tmp_layer_file):
                #    os.rename(tmp_layer_file, config['mapfile_include_layers_filename'])


def parse_args(args=None):
    """Parse commandline arguments."""
    parser = argparse.ArgumentParser(
        "Message writer",
        description="Write message into a json file for wms"
    )
    parser.add_argument(
        "config_file",
        help="The configuration file to run on."
    )
    parser.add_argument("files", nargs="*", action="store")

    return parser.parse_args(args)


def read_trollflow2_config(tf2c):
    """Read trollflow2 config."""
    trollflow2_config = read_config(tf2c)
    areas = trollflow2_config['product_list']['areas']

    return areas


def ingest_into_postgis(conn, files, config, areas):
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
        for product in areas[area]['products']:
            for f in files:

                _LOGGER.info(f"Considering file {f}")
                bn_f = os.path.basename(f)

                if product in bn_f:
                    img_time, geom = collect_data_from_file(f)

                    if geom:
                        inserted.append(insert_into_db(conn, f, product, img_time, geom, config))

    return any(inserted)


def create_mapserver_layer_config(conn, areas, config):
    """Update mapserver layer config with time_extent from database"""
    layer_string = ""

    for area in areas:
        for product in areas[area]['products']:

            time_extent = ""
            time_default = ""
            select_string = (f"select to_char(min(time),'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"') "
                             f"|| '/' || to_char(max(time), 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"') "
                             f"|| '/PT5M' "
                             f"from {config['pg_table_name']} where product_name='{product}';")
            try:
                print("Connection:", conn, flush=True)

                if conn and conn.status:
                    print("STATUS:", conn.status, flush=True)
                    curs = conn.cursor()
                    curs.execute(f"{select_string}")
                    fetched_time_extent = curs.fetchone()
                    curs.close()
                    time_extent = fetched_time_extent[0]

                    if time_extent:
                        time_default = time_extent.split('/')[1]
                    else:
                        continue

                    _LOGGER.info(f"TIME EXTENT {time_extent}")

            except psycopg2.OperationalError as poe:
                _LOGGER.error(f"Failed pg connect/execute: {str(poe)}")

            wms_extent_select_string = f"select st_extent(geom) from {config['pg_table_name']} where product_name='{product}';"

            extent = ""

            try:
                print("Connection:", conn, flush=True)

                if conn and conn.status:
                    print("STATUS:", conn.status, flush=True)

                    curs = conn.cursor()
                    curs.execute(f"{wms_extent_select_string}")
                    fetched_extent = curs.fetchone()
                    curs.close()
                    extent = fetched_extent[0]

                    if extent:
                        extent = extent.replace("BOX(",'').replace(',', ' ').replace(")", '')

                    else:
                        continue

                    _LOGGER.info(f"EXTENT {extent}")

            except psycopg2.OperationalError as poe:
                _LOGGER.error(f"Failed pg connect/execute: {str(poe)}")

            srid_select_string = f"select st_srid(geom) from {config['pg_table_name']} where product_name='{product}';"
            srid = ""

            try:
                print("Connection:", conn, flush=True)

                if conn and conn.status:
                    print("STATUS:", conn.status, flush=True)
                    curs = conn.cursor()
                    curs.execute(f"{srid_select_string}")
                    fetched_srid = curs.fetchone()
                    curs.close()

                    if fetched_srid:
                        srid = fetched_srid[0]
                    else:
                        continue

                    _LOGGER.info(f"SRID {srid}")

            except psycopg2.OperationalError as poe:
                _LOGGER.error(f"Failed pg connect/execute: {str(poe)}")

            _LOGGER.info(f"Product: {product}")

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
      "wms_enable_request" "*"
      "wms_extent" "{extent}"
    END
    PROJECTION
      "init=epsg:{srid}"
    END
    CONNECTIONTYPE postgis
    CONNECTION "host={config['pg_host_name']} user={config['pg_user_name']} dbname={config['pg_database_name']} port=5432 password={config['pg_password']}"
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


def collect_data_from_file(input_file):
    """Use rasterio to collect extent, time and srs info."""
    try:
        fname = os.path.basename(input_file)
        dataset = rasterio.open(input_file)

    except Exception as ex:
        print("Exception rasterio open is ", str(ex), flush=True)

    try:
        tags = dataset.tags()

    except Exception as ex:
        print("Exception dataset tags is ", str(ex), flush=True)
 
    try:
        img_time = datetime.datetime.strptime(tags['TIFFTAG_DATETIME'], '%Y:%m:%d %H:%M:%S')

    except Exception as ex:
        print("Exception img_time is ", str(ex), flush=True)
        traceback.print_exc()
        img_time = None

        return img_time, None
        
    try:
        bounds = dataset.bounds
        print(bounds, flush=True)
    except Exception as ex:
        print("Exception bounds is ", str(ex), flush=True)
        bounds = [1, 2, 3, 4]

    ll_x = bounds[0]
    ll_y = bounds[1]
    ur_x = bounds[2]
    ur_y = bounds[3]

    try:
        crs = dataset.crs.to_authority()

    except Exception as ex:
        print("Exception crs is ", str(ex), flush=True)
        crs = None

    if crs is None:
        _LOGGER.error(
            "crs from file is None. Authority was not found."
            "Need a crs to get geometry in postgis right."
            "Assigning one."
        )
        crs = []

        return img_time, None

    geom = "ST_SetSRID(ST_MakeBox2D(ST_Point({}, {}), ST_Point({}, {})), {})".format(
        ll_x,
        ll_y,
        ur_x,
        ur_y,
        crs[1]
    )

    return img_time, geom


def pg_connect(config):
    """Connect to the database."""
    print("Connecting to pg", flush=True)

    conn = psycopg2.connect(host=config['host_name'], port='5432', dbname=config['pg_database_name'],
                            user=config['pg_user_name'],
                            password=config['pg_password'])

    return conn


def insert_into_db(conn, filename, product_name, image_time, geom, db_config):
    """Check if file already exists, if not, insert into database. Return True if inserted."""
    insert = f"insert into {db_config['pg_table_name']}(filename, product_name, time, geom)"
    insert_string = "{} values('{}', '{}', '{:%Y-%m-%d %H:%M:%S}Z', {});".format(insert,
                                                                                 filename,
                                                                                 product_name,
                                                                                 image_time,
                                                                                 geom)
    select_string = f"select * from {db_config['pg_table_name']} where filename='{filename}';"
    inserted = False

    try:
        curs = conn.cursor()
        curs.execute(f"{select_string}")

        if curs.fetchone():
            print("File {} already in the db. Don't insert.".format(filename), flush=True)
        else:
            curs.execute(f"{insert_string}")
            inserted = True

        conn.commit()
        curs.close()

    except psycopg2.OperationalError as poe:
        print("Failed pg connect/execute:", str(poe))

    return inserted


def main(args=None):
    """Main script."""
    parsed_args = parse_args(args=args)
    config = read_config(parsed_args.config_file)

    try:
        # read from trollflow2 config file
        areas = read_trollflow2_config(config['trollflow2_config_file'])
    except:
        # or use config in this config file
        areas = config['product_list']['areas']

    subscribe_and_ingest(config, areas)


if __name__ == "__main__":
    main(sys.argv[1:])
