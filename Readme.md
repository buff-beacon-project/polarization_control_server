# Polarization motor control server
Designed to control the polarization of the various stations in the loophole free Bell test experiment.

## Setup  

This service starts a small http_server that creates REST endpoints for health (http://localhost:port/healthz) and (http://localhost:port/metrics). A special monitoring docker container is used to check this URL in the docker-compose to see if the container is responsive. If it isn't then the monitoring service will restart it.

For the monitoring service, make sure to run:
```chmod +x monitor.sh```

Also make sure that a `logs` directory exists. In the `configs\polarization.yam` file, make sure to set the ports. The Redis server where the counts are stored is required for the optimization loops. There is also the option to send log files directly to a Loki log server for viewing in Grafana. Just supply the hostname and port for this service.

To register this service with Prometheus for metrics monitoring, create a `JSON` file in the `prometheus_service` directory on the machine hosting Prometheus. JSON file content (modified to include the ip/port of this monitoring service):

```
[
  {
    "targets": ["192.168.4.109:8080"],
    "labels": {
      "job": "echo_service",
      "instance": "echo-01"
    }
  }
]
```

## Sending commands  
Commands are sent as a JSON dictionary with the following format: `{'cmd': 'command', {'params': {dictionary of optional parameters}}}`. Sending the command `{'cmd': 'commands', 'params': {}} will return a list of all available commands.

## Additional paths  
In the `polarization.yaml` file, it is possible to add additional paths or polarization settings required.

## Caching  
To account for the birefringence in our Pockel's cells, an optimization that compensates for the effective Jones matrix of the Pockel's cells. These angles are cached. For options where the Pockels cells at the Alice or Bob stations are being set, it is possible to ignore the cached angles with the optional paramter `"use_cache": bool`. It is also possible to update the cahced values with the newly computed setting using `"update_cache": bool`. For instance, setting `"use_cache": false, "update_cache": true` will recompute the optimal angles and use these as the new cache value going forward.

The Jones matrices can be updated in the `polarization.yaml` file.