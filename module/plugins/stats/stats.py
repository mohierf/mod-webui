#!/usr/bin/python

# -*- coding: utf-8 -*-

# Copyright (C) 2009-2014:
#    Guillaume Subiron, maethor@subiron.org
#
# This file is part of Shinken.
#
# Shinken is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Shinken is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Shinken.  If not, see <http://www.gnu.org/licenses/>.
import os
import time
from datetime import datetime, timedelta

from collections import Counter, OrderedDict
from itertools import groupby

from copy import deepcopy
from logevent import LogEvent

# Check if Alignak is installed
ALIGNAK = os.environ.get('ALIGNAK_DAEMON', None) is not None

# Alignak / Shinken base module are slightly different
if ALIGNAK:
    # Specific logger configuration
    from alignak.log import logging, ALIGNAK_LOGGER_NAME

    logger = logging.getLogger(ALIGNAK_LOGGER_NAME + ".webui")
else:
    from shinken.log import logger

# Plugin's default parameters
params = {
    # Field used to store a timestamp date
    'time_field': 'time',

    # Field used for the event type filter
    'type_field': 'type',

    # Shinken mongo logs module uses an integer timestamp
    'date_format': 'timestamp',

    # stats plugin search criteria
    # 'stats_command_name_filter': '',
    'command_filter': '',
    # Field used for the command name filter
    'command_name_field': 'command_name',

    # 'stats_contact_name_filter': '',
    'contact_filter': '',
    # Field used for the contact name filter
    'contact_name_field': 'contact_name',

    # Log type may be:
    #  INFO
    #  WARNING
    #  ERROR
    #  CURRENT SERVICE STATE
    #  INITIAL SERVICE STATE
    #  SERVICE ALERT
    #  SERVICE DOWNTIME ALERT
    #  SERVICE FLAPPING ALERT
    #  CURRENT HOST STATE
    #  INITIAL HOST STATE
    #  HOST ALERT
    #  HOST DOWNTIME ALERT
    #  HOST FLAPPING ALERT
    #  SERVICE NOTIFICATION
    #  HOST NOTIFICATION
    #  PASSIVE SERVICE CHECK
    #  PASSIVE HOST CHECK
    #  SERVICE EVENT HANDLER
    #  HOST EVENT HANDLER
    #  EXTERNAL COMMAND
    # 'events': ['INFO', 'WARNING', 'ERROR'],
    'events': [
        'HOST NOTIFICATION', 'SERVICE NOTIFICATION'
    ],

    'days': 30
}

# Will be populated by the UI with it's own value
app = None


def _get_logs(*args, **kwargs):
    if app.logs_module.is_available():
        return app.logs_module.get_ui_logs(*args, **kwargs)

    logger.warning("[stats] no logs module available for the Web UI!")
    return None


# pylint: disable=global-statement
def load_config(the_app):
    """Load the configuration from specific parameters used in the global WebUI configuration
    :param the_app: the current application
    :return:
    """
    global params

    logger.info("[stats] loading configuration ...")

    plugin_configuration = the_app.get_plugin_config('stats')
    for prop, default in list(plugin_configuration.items()):
        # Old specific parameters
        if prop in ['stats_command_name_filter']:
            params['command_filter'] = the_app.get_config('stats_command_name_filter', '')
        if prop in ['stats_contact_name_filter']:
            params['contact_filter'] = the_app.get_config('stats_contact_name_filter', '')

        # Those are list of strings...
        if prop in ['events']:
            if ',' in default:
                default = [item.strip() for item in default.split(',')]
            else:
                default = [default]

        params[prop] = default

    logger.info("[stats] configuration, timestamp field: %s", params['time_field'])
    logger.info("[stats] configuration, date format: %s", params['date_format'])
    logger.info("[stats] configuration, fetching events: %s", params['events'])
    logger.info("[stats] configuration, days count: %s", params['days'])
    logger.info("[stats] configuration, command filter: %s", params['command_filter'])
    logger.info("[stats] configuration, contact filter: %s", params['contact_filter'])

    logger.info("[stats] configuration loaded.")


def _graph(logs):
    groups_hour = groupby(reversed(logs), key=lambda x: (x['time'] - (x['time'] % 3600)))

    data = OrderedDict()
    for key, value in groups_hour:
        # Filling voids with zeros
        if data:
            while next(reversed(data)) < (key - 3600):
                data[next(reversed(data)) + 3600] = 0
        data[key] = len(list(value))

    # Smooth graph
    avg = sum(data.values()) / len(list(data.values()))
    variance = sum([(v - avg)**2 for v in list(data.values())]) / len(list(data.values()))
    deviation = variance**0.5

    # Remove every value that is 3 times out of standard deviation
    for key, value in list(data.items()):
        if value > (avg + deviation * 3):
            data[key] = avg

    # Remove every value that is out of standard deviation and more than two times previous value
    for key, value in list(data.items()):
        if key - 3600 in data and key + 3600 in data:
            if value > (avg + deviation) and value > (2 * data[key - 3600]):
                data[key] = (data[key - 3600] + data[key + 3600]) / 2

    if datetime.fromtimestamp(logs[-1]['time']) < (datetime.now() - timedelta(7)):
        # Group by 24h
        data_24 = OrderedDict()
        for key, value in list(data.items()):
            the_time = (key - key % (3600 * 24))
            if the_time not in data_24:
                data_24[the_time] = 0
            data_24[the_time] += value
        data = data_24

    # Convert timestamp to milliseconds
    # Convert timestamp ms to s
    graph = [{'t': k * 1000, 'y': v} for k, v in list(data.items())]

    return graph


def get_alignak_stats():
    user = app.get_user()
    _ = user.is_administrator() or app.redirect403()

    logger.info("Get Alignak stats")

    days = int(app.request.GET.get('days', params['days']))

    range_end = int(app.request.GET.get('range_end', time.time()))
    range_start = int(app.request.GET.get('range_start', range_end - (days * 86400)))

    # Restrictive filter on contact name
    filters = ['notification']

    logs = []
    for log in app.alignak_events:
        # Try to get a monitoring event
        try:
            logger.debug("Log: %s", log)
            event = LogEvent(log['message'])
            logger.debug("-> event: %s", event)
            if not event.valid:
                logger.warning("No monitoring event detected from: %s", log['message'])
                continue

            # -------------------------------------------
            data = deepcopy(log)

            if event.event_type == 'ALERT':
                data.update({
                    "host_name": event.data['hostname'],
                    "service_name": event.data['service_desc'] or 'n/a',
                    "state": event.data['state'],
                    "state_type": event.data['state_type'],
                    "type": "alert",
                })

            if event.event_type == 'NOTIFICATION':
                data.update({
                    "host_name": event.data['hostname'],
                    "service_name": event.data['service_desc'] or 'n/a',
                    "type": "notification",
                })

            if filters and data.get('type', 'unknown') not in filters:
                continue

            logs.append(data)
            logger.info(data)
        except ValueError:
            logger.warning("Unable to decode a monitoring event from: %s", log['message'])
            continue

    hosts = Counter()
    services = Counter()
    hostsservices = Counter()
    new_logs = []
    for l in logs:
        hosts[l['host_name']] += 1
        if 'service_description' in l:
            services[l['service_description']] += 1
            hostsservices[l['host_name'] + '/' + l['service_description']] += 1
        new_logs.append(l)

    return {
        'hosts': hosts,
        'services': services,
        'hostsservices': hostsservices,
        'days': days,
        'graph': _graph(new_logs) if new_logs else None
    }


def get_global_stats():
    user = app.get_user()
    _ = user.is_administrator() or app.redirect403()

    try:
        days = int(app.request.GET.get('days', params['days']))
    except ValueError:
        days = 30
    try:
        range_end = int(app.request.GET.get('range_end', time.time()))
    except ValueError:
        range_end = int(time.time())
    search_range_end = range_end
    try:
        range_start = int(app.request.GET.get('range_start', range_end - (days * 86400)))
    except ValueError:
        range_start = range_end - (days * 86400)
    search_range_start = range_start

    if params['date_format'] in ['datetime']:
        # Assuming UTC timestamps!
        search_range_start = datetime.utcfromtimestamp(range_start)
        search_range_end = datetime.utcfromtimestamp(range_end)

    logger.debug("[stats] get_global_stats, range: %d - %d", search_range_start, search_range_end)
    logger.debug("[stats] get_global_stats, range: %s - %s",
                 time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(search_range_start)),
                 time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(search_range_end)))

    filters = {}
    if params['events'] and params['events'][0]:
        filters = {params['type_field']: {'$in': params['events']}}
    if params['command_filter']:
        logger.info("[stats] command filter: %s", params['command_filter'])
        filters.update({
            params['command_name_field']: {'$regex': params['command_filter']},
        })
    if params['contact_filter']:
        filters.update({
            params['contact_name_field']: {'$regex': params['contact_filter']},
        })

    # logs is a pymongo Cursor object
    # query is the mongo query used to get logs
    logs, query = _get_logs(range_start=search_range_start, range_end=search_range_end,
                            limit=0, offset=0,
                            filters=filters, time_field=params['time_field'])
    logger.debug("[stats] got %d records.", logs.count())
    logger.debug("[stats] query: %s", query)

    hosts = Counter()
    services = Counter()
    hosts_services = Counter()
    new_logs = []
    for log in logs:
        # Alignak logstash parser....
        if 'alignak' in log:
            log = log['alignak']
            if 'time' not in log:
                log['time'] = int(time.mktime(log.pop('timestamp').timetuple()))

            if 'service' in log:
                log['service_description'] = log.pop('service')

        hosts[log['host_name']] += 1
        if 'service_description' in log:
            services[log['service_description']] += 1
            hosts_services[log['host_name'] + '/' + log['service_description']] += 1
        new_logs.append(log)

    return {
        'hosts': hosts,
        'services': services,
        'hostsservices': hosts_services,
        'days': days,
        'params': params,
        'graph': _graph(new_logs) if new_logs else None,
        'query': query
    }


def get_service_stats(name):
    user = app.get_user()
    _ = user.is_administrator() or app.redirect403()

    try:
        days = int(app.request.GET.get('days', params['days']))
    except ValueError:
        days = 30
    try:
        range_end = int(app.request.GET.get('range_end', time.time()))
    except ValueError:
        range_end = int(time.time())
    search_range_end = range_end
    try:
        range_start = int(app.request.GET.get('range_start', range_end - (days * 86400)))
    except ValueError:
        range_start = range_end - (days * 86400)
    search_range_start = range_start

    if params['date_format'] in ['datetime']:
        # Assuming UTC timestamps!
        search_range_start = datetime.utcfromtimestamp(range_start)
        search_range_end = datetime.utcfromtimestamp(range_end)

    filters = {
        'service_description': name
    }
    if params['events'] and params['events'][0]:
        filters = {params['type_field']: {'$in': params['events']}}
    if params['command_filter']:
        filters.update({
            'command_filter': {'$regex': params['command_filter']},
        })
    if params['contact_filter']:
        filters.update({
            'contact_filter': {'$regex': params['contact_filter']},
        })

    logger.info("[stats] get_service_stats, range: %d - %d", search_range_start, search_range_end)
    logger.info("[stats] get_service_stats, range: %s - %s",
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(search_range_start)),
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(search_range_end)))

    logs, query = _get_logs(range_start=search_range_start, range_end=search_range_end,
                            limit=0, offset=0,
                            filters=filters, time_field=params['time_field'])
    logger.info("[stats] got %d records.", logs.count())
    logger.info("[stats] query: %s", query)

    hosts = Counter()
    for l in logs:
        hosts[l['host_name']] += 1
    return {
        'service': name,
        'hosts': hosts,
        'days': days,
        'params': params,
        'query': query
    }


def get_host_stats(name):
    user = app.get_user()
    _ = user.is_administrator() or app.redirect403()

    try:
        days = int(app.request.GET.get('days', params['days']))
    except ValueError:
        days = 30
    try:
        range_end = int(app.request.GET.get('range_end', time.time()))
    except ValueError:
        range_end = int(time.time())
    search_range_end = range_end
    try:
        range_start = int(app.request.GET.get('range_start', range_end - (days * 86400)))
    except ValueError:
        range_start = range_end - (days * 86400)
    search_range_start = range_start

    if params['date_format'] in ['datetime']:
        # Assuming UTC timestamps!
        search_range_start = datetime.utcfromtimestamp(range_start)
        search_range_end = datetime.utcfromtimestamp(range_end)

    filters = {
        'host_name': name
    }
    if params['events'] and params['events'][0]:
        filters = {params['type_field']: {'$in': params['events']}}
    if params['command_filter']:
        filters.update({
            'command_filter': {'$regex': params['command_filter']},
        })
    if params['contact_filter']:
        filters.update({
            'contact_filter': {'$regex': params['contact_filter']},
        })

    logger.info("[stats] get_host_stats, range: %d - %d", search_range_start, search_range_end)
    logger.info("[stats] get_host_stats, range: %s - %s",
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(search_range_start)),
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(search_range_end)))

    logs, query = _get_logs(range_start=search_range_start, range_end=search_range_end,
                            limit=0, offset=0,
                            filters=filters, time_field=params['time_field'])
    logger.info("[stats] got %d records.", logs.count())
    logger.info("[stats] query: %s", query)

    hosts = Counter()
    services = Counter()
    for l in logs:
        # Alignak logstash parser....
        if 'alignak' in l:
            l = l['alignak']
            if 'time' not in l:
                l['time'] = int(time.mktime(l.pop('timestamp').timetuple()))

            if 'service' in l:
                l['service_description'] = l.pop('service')

        hosts[l['host_name']] += 1
        if 'service_description' in l:
            services[l['service_description']] += 1

    return {
        'host': name,
        'hosts': hosts,
        'services': services,
        'days': days,
        'params': params,
        'query': query
    }


pages = {
    get_alignak_stats: {
        'name': 'AlignakStats', 'route': '/alignak/stats', 'view': 'stats'
    },

    get_global_stats: {
        'name': 'GlobalStats', 'route': '/stats', 'view': 'stats'
    },

    get_service_stats: {
        'name': 'Stats', 'route': '/stats/service/<name:path>', 'view': 'stats_service'
    },

    get_host_stats: {
        'name': 'Stats', 'route': '/stats/host/<name:path>', 'view': 'stats_host'
    }
}
