# Web User Interface, plugin logs

## Description
Used to display the system logs (*/logs*)
Used to display the log history for an host or service

## Configuration

Several log format are available:
- Shinken livestatus logs (module *logstore-mongodb*)
- Shinken logs (module *mongo-logs*)
- Alignak logstash parser


### Shinken livestatus (logstore-mongodb or mongo-logs)

See [this page](https://github.com/shinken-monitoring/mod-mongo-logs) for more information about the *mongo-logs* module and the log collection fields format.

MongoDB collection contains:
```json
{
  "_id":{"$oid":"5dee7465c3ed21d113aff743"},
  "comment":"",
  "plugin_output":"/bin/ping6 -n -U -w 10 -c 1 localhost",
  "attempt":1,
  "message":"[1575908453] HOST ALERT: localhost;DOWN;SOFT;1;/bin/ping6 -n -U -w 10 -c 1 localhost",
  "logclass":1,
  "options":"",
  "state_type":"SOFT",
  "lineno":735,
  "state":1,
  "host_name":"localhost",
  "time":1575908453,
  "service_description":"",
  "logobject":1,
  "type":"HOST ALERT",
  "contact_name":"",
  "command_name":"",
}
{"_id":{"$oid":"5dee7495c3ed21d113aff744"},"comment":"","plugin_output":"[Errno 2] No such file or directory","attempt":3,"message":"[1575908500] SERVICE ALERT: docker_shinken;local_memory_usage;CRITICAL;HARD;3;[Errno 2] No such file or directory","logclass":1,"options":"","state_type":"HARD","lineno":736,"state":2,"host_name":"docker_shinken","time":1575908500,"service_description":"local_memory_usage","logobject":2,"type":"SERVICE ALERT","contact_name":"","command_name":""}

```

To make some tests, you can import the *test-logs-logstore-mongodb.json* file into a Mongo collection:
```bash
   mongoimport --db=shinken --collection=ls-logs test-logs-logstore-mongodb.json
```

You can also export the Mongo collection to a file:
```bash
   mongoexport --db=shinken --collection=ls-logs --out=test-logs-logstore-mongodb.json
```

Then configure the Web UI as:
```ini
   ## Database configuration
   ## ----------
   # Database URI
   # Set an empty value to disable this feature
   ;uri=
   uri=mongodb://localhost
   
   # Database name where to fetch the logs/availability collections
   database=alignak
   
   # User authentication for database access
   ;username=
   ;password=
   
   # Logs collection name
   logs_collection=ls-logs
   
   
   ## Logs plugin
   ## ----------
   
   ## Configure the name of the collected and displayed fields
   ## ----------
   ## -- For Shinken mongo-logs module logs (default configuration)
   # List of available fields: comment, attempt, logobject, logclass, state_type, state, command_name,
   # plugin_output, contact_name, host_name, service_description, message, type, options, lineno
   # ---
   # Example:
   # {u'comment': u'', u'attempt': 1, u'logobject': 2, u'logclass': 1, u'state_type': u'SOFT',
   # u'state': 1, u'command_name': u'', u'plugin_output': u'CRITICAL - Plugin timed out after 10 seconds',
   # u'contact_name': u'', u'time': 1575973579, u'host_name': u'docker_shinken',
   # u'service_description': u'local_apt_packages',
   # u'message': u'[1575973579] SERVICE ALERT: docker_shinken;local_apt_packages;WARNING;SOFT;1;CRITICAL - Plugin timed out after 10 seconds',
   # u'_id': ObjectId('5def72cb5108b779c6b8c739'), u'type': u'SERVICE ALERT', u'options': u'', u'lineno': 468}
   # ---
   # Note that all the fields are not always of many interest :)
   
   # Use a specific date formatter
   plugin.logs.date_format=timestamp
   # Display the time field
   plugin.logs.time_field=time
   # The event type field
   plugin.logs.type_field=type
   # Display this list of fields
   plugin.logs.other_fields=type, state, state_type, host_name, service_description, plugin_output
   # Get only this list of events
   plugin.logs.events=HOST ALERT, SERVICE ALERT, EXTERNAL COMMAND, HOST NOTIFICATION, SERVICE NOTIFICATION
   ## ----------
   
```



### Alignak monitoring events logstash parser

See the Alignak repository, file *contrib/logstash/README.rst* for more explanations.

MongoDB collection contains:
```json
{
  "_id":{"$oid":"5c03aaed254c41a7d4000006"},
  "alignak":{
    "host_name":"host_2",
    "log_level":"ERROR",
    "state_type":"SOFT",
    "timestamp":{"$date":"2018-12-02T08:05:29.000Z"},
    "message":"I am always Down",
    "attempt":"2",
    "state":"DOWN",
    "event":"HOST ALERT",
  },
  "tags":["alignak-events"],
  "message":"[2018-12-02 09:05:29] ERROR: HOST ALERT: host_2;DOWN;SOFT;2;I am always Down",
  "@timestamp":{"$date":"2018-12-02T08:05:29.000Z"},
  "host":"fred-Ubuntu18",
  "@version":"1",
  "path":"/tmp/var/log/alignak/alignak-events.log",
  "type":"alignak_events_log",
}
{"_id":{"$oid":"5c03aaed254c41a7d4000007"},"alignak":{"host_name":"north_host_005","log_level":"ERROR","service":"dummy_critical","state_type":"SOFT","timestamp":{"$date":"2018-12-02T08:05:34.000Z"},"message":"north_host_005-dummy_critical-2","attempt":"1","state":"CRITICAL","event":"SERVICE ALERT"},"tags":["alignak-events"],"message":"[2018-12-02 09:05:34] ERROR: SERVICE ALERT: north_host_005;dummy_critical;CRITICAL;SOFT;1;north_host_005-dummy_critical-2","@timestamp":{"$date":"2018-12-02T08:05:34.000Z"},"host":"fred-Ubuntu18","@version":"1","path":"/tmp/var/log/alignak/alignak-events.log","type":"alignak_events_log"}

```

To make some tests, you can import the *test-logs-alignak-logstash.json* file into a Mongo collection:
```bash
   mongoimport --db=shinken --collection=alignak_events test-logs-alignak-logstash.json
```

You can also export the Mongo collection to a file:
```bash
   mongoexport --db=shinken --collection=alignak_events --out=test-logs-alignak-logstash.json
```

Then configure the Web UI as:
```ini
   ## Database configuration
   ## ----------
   # Database URI
   # Set an empty value to disable this feature
   ;uri=
   uri=mongodb://localhost
   
   # Database name where to fetch the logs/availability collections
   database=alignak
   
   # User authentication for database access
   ;username=
   ;password=
   
   # Logs collection name
   logs_collection=ls-logs
   
   
   ## Logs plugin
   ## ----------
   # Configure the date format for date range searching





```