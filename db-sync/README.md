# db-sync

This folder contains the scripts used to create LAYERS file for MapFile and sync them into a POSTGIS database.

## postgis

Source: https://registry.hub.docker.com/r/postgis/postgis/

### deploy container

mounts:
`./pg-data/:/var/lib/postgresql/data` -> save data from database on the host

```
podman run -d --replace --rm --name postgis --network pytroll_network -v ./pg-data/:/var/lib/postgresql/data -e POSTGRES_PASSWORD=pytroll postgis/postgis

```

### table to be created in postgis db
CREATE TABLE products (filename varchar, product_name varchar, time timestamp, geom geometry);

## sync-db

### build container

```
podman build -t db-sync .
```

### deploy container to run sync-db

mounts:
- `/eodata/hrit_out/:/mnt/output/` -> where products are mounted
- `./output:/usr/local/bin/db-sync/output/` -> where the mapfile layers output is placed on your host. This is the input for the WMS server.

#### for ope
```
podman run -d --replace  --name db-sync --network pytroll_network -v /eodata/hrit_out/:/mnt/output/ -v ./output:/usr/local/bin/db-sync/output/ db-sync python3 db-and-mapfile-handle.py db-and-mapfile-handle.yaml
```


#### for testing
```
podman run -d --replace  --name db-sync --network pytroll_network -v /eodata/hrit_out/:/mnt/output/ -v ./output:/usr/local/bin/db-sync/output/  -v ./db-and-mapfile-handle.yaml:/usr/local/bin/db-sync/db-and-mapfile-handle.yaml -v ./db-and-mapfile-handle.py:/usr/local/bin/db-sync/db-and-mapfile-handle.py db-sync python3 db-and-mapfile-handle.py db-and-mapfile-handle.yaml
```

## mapserver

Source: https://github.com/camptocamp/docker-mapserver#readme

### deploy container

mounts:
- `/root/seviri-processing/ewc-config/scripts/mapserver-demo.map:/etc/mapserver/mapserver.map` -> Mapfile structure.
- `./output/mapfile_layers.map:/etc/mapfile_pytroll_layers.map` -> mapfile layers created by the db-sync container

```
podman run --replace --network pytroll_network  -p 80:80/tcp --name mapserver -d --rm -v /eodata/hrit_out/:/mnt/output/ -v /root/seviri-processing/ewc-config/scripts/mapserver-demo.map:/etc/mapserver/mapserver.map -v ./output/mapfile_layers.map:/etc/mapfile_pytroll_layers.map docker.io/camptocamp/mapserver:7.6
```

Verify that all containers are in the same network
```
podman ps --filter network=pytroll_network 
```

