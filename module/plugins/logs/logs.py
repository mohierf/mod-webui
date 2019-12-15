#!/usr/bin/python

# -*- coding: utf-8 -*-

# Copyright (C) 2009-2014:
#    Gabes Jean, naparuba@gmail.com
#    Gerhard Lausser, Gerhard.Lausser@consol.de
#    Gregory Starck, g.starck@gmail.com
#    Hartmut Goebel, h.goebel@goebel-consult.de
#    Frederic Mohier, frederic.mohier@gmail.com
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
import json
import time
from datetime import datetime, date

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

    # Field used for the host name filter
    'host_name_field': 'host_name',

    # Field used for the service name filter
    'service_description_field': 'service_description',

    # Shinken mongo logs module uses an integer timestamp
    'date_format': 'timestamp',

    # stats plugin search criteria
    'command_filter': '',
    # Field used for the command name filter
    'command_name_field': 'command_name',

    'contact_filter': '',
    # Field used for the contact name filter
    'contact_name_field': 'contact_name',

    # Shinken mongo logs module uses 'message' to store a log information
    'other_fields': ['message'],

    'events_list': [
        'INFO', 'WARNING', 'ERROR',
        'CURRENT SERVICE STATE', 'INITIAL SERVICE STATE',
        'SERVICE ALERT', 'SERVICE DOWNTIME ALERT', 'SERVICE FLAPPING ALERT',
        'CURRENT HOST STATE', 'INITIAL HOST STATE',
        'HOST ALERT', 'HOST DOWNTIME ALERT', 'HOST FLAPPING ALERT',
        'SERVICE NOTIFICATION', 'HOST NOTIFICATION',
        'PASSIVE SERVICE CHECK', 'PASSIVE HOST CHECK',
        'SERVICE EVENT HANDLER', 'HOST EVENT HANDLER',
        'EXTERNAL COMMAND'
    ],

    # Events may be several from the former list...
    # 'events': ['INFO', 'WARNING', 'ERROR'],
    'events': [
        'HOST ALERT', 'SERVICE ALERT',
        'HOST NOTIFICATION', 'SERVICE NOTIFICATION'
    ],

    # Hosts filtering
    'hosts': [
        ''
    ],

    # Services filtering
    'logs_services': []
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

    logger.info("[logs] loading configuration ...")

    plugin_configuration = the_app.get_plugin_config('logs')
    for prop, default in list(plugin_configuration.items()):
        # Those are list of strings...
        if prop in ['other_fields', 'events', 'hosts', 'logs_services']:
            if ',' in default:
                default = [item.strip() for item in default.split(',')]
            else:
                default = [default]

        params[prop] = default

    logger.info("[logs] configuration, timestamp field: %s", params['time_field'])
    logger.info("[logs] configuration, date format: %s", params['date_format'])
    logger.info("[logs] configuration, other fields: %s", params['other_fields'])
    logger.info("[logs] configuration, fetching events: %s", params['events'])
    logger.info("[logs] configuration, hosts: %s", params['hosts'])
    logger.info("[logs] configuration, services: %s", params['logs_services'])

    logger.info("[logs] configuration loaded.")


def form_hosts_list():
    return {'params': params}


def set_hosts_list():
    params['hosts'] = []

    new_hosts_list = app.request.forms.getall('new_hosts_list[]')
    for host in new_hosts_list:
        params['hosts'].append(host)
    logger.debug("[logs] new hosts list: %s", params['hosts'])

    # Returns an ok response
    app.response.content_type = 'application/json'
    return json.dumps({"status": "ok"})


def form_services_list():
    return {'params': params}


def set_services_list():
    # Form cancel
    if app.request.forms.get('cancel'):
        app.bottle.redirect("/logs")

    params['logs_services'] = []

    services_list = app.request.forms.getall('servicesList[]')
    logger.debug("[logs] Selected services : ")
    for service in services_list:
        logger.debug("[logs] - service : %s", service)
        params['logs_services'].append(service)

    app.bottle.redirect("/logs")


def set_events_list():
    params['events'] = []

    new_events_list = app.request.forms.getall('new_events_list[]')
    for event in new_events_list:
        params['events'].append(event)
    logger.debug("[logs] new events list: %s", params['events'])

    # Returns an ok response
    app.response.content_type = 'application/json'
    return json.dumps({"status": "ok"})


def set_period():
    # Returns the new events list
    app.response.content_type = 'application/json'
    return json.dumps({"status": "ok"})


def get_history():
    user = app.get_user()

    filters = {}
    if params['events'] and params['events'][0]:
        filters = {
            params['type_field']: {'$in': params['events']}
        }

    range_start = None
    try:
        range_start = int(app.request.query.get('range_start', ""))
    except ValueError:
        logger.debug("No range start")
        pass
    search_range_start = range_start

    range_end = None
    try:
        range_end = int(app.request.query.get('range_end', ""))
    except ValueError:
        logger.debug("No range end")
        pass
    search_range_end = range_end

    if params['date_format'] in ['datetime']:
        # Assuming UTC timestamps!
        search_range_start = datetime.utcfromtimestamp(range_start)
        search_range_end = datetime.utcfromtimestamp(range_end)

    if search_range_start is not None or search_range_end is not None:
        logger.debug("[logs] get_history, range: %d - %d", search_range_start, search_range_end)
        logger.debug("[logs] get_history, range: %s - %s",
                     time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(search_range_start)),
                     time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(search_range_end)))

    service = app.request.query.get('service', None)
    host = app.request.query.get('host', None)

    no_hosts_filter = app.request.query.get('no_hosts_filter', None)
    if not no_hosts_filter:
        if params['hosts'] and params['hosts'][0]:
            filters.update({params['host_name_field']: {'$in': params['hosts']}})

        if host:
            if service:
                _ = app.datamgr.get_element(host + '/' + service, user) or app.redirect404()
            else:
                _ = app.datamgr.get_element(host, user) or app.redirect404()
        else:
            _ = user.is_administrator() or app.redirect403()

        if service:
            filters[params['service_description_field']] = service

        if host:
            filters[params['host_name_field']] = host

    command_filter = app.request.query.get('command_filter', None)
    logger.info("[logs] command filter: %s", command_filter)
    if command_filter:
        try:
            command_filter = json.loads(command_filter)
        except Exception:
            pass
        filters[params['command_name_field']] = command_filter

    contact_filter = app.request.query.get('contact_filter', None)
    if contact_filter:
        try:
            contact_filter = json.loads(contact_filter)
        except Exception:
            pass
        filters[params['contact_name_field']] = contact_filter

    try:
        limit = int(app.request.query.get('limit', 100))
    except ValueError:
        limit = 100
    try:
        offset = int(app.request.query.get('offset', 0))
    except ValueError:
        offset = 0

    logs, query = _get_logs(range_start=search_range_start, range_end=search_range_end,
                            filters=filters, time_field=params['time_field'],
                            limit=limit, offset=offset)

    add_more = app.request.query.get('add_more', None)

    message = "No module configured to get monitoring logs from database!"
    total_records = 0
    current_records = 0
    if logs is not None:
        total_records = logs.collection.count_documents(query, None)
        current_records = logs.collection.count_documents(query, None, skip=offset, limit=limit)

        if add_more:
            if current_records:
                message = "%d more records..." % current_records
            else:
                message = "No more records"
        else:
            message = "Got %d records out of %d" % (current_records, total_records)

        logger.debug("[logs] got %d records.", current_records)
        logger.debug("[logs] query: %s", query)

    return {
        'records': logs,
        'total_records': total_records,
        'current_records': current_records,
        'query': query,
        'params': params,
        'message': message,
        'add_more': add_more is not None,
        'range_start': range_start,
        'range_end': range_end
    }


# :TODO:maethor:171017: This function should be merge in get_history
def get_global_history():
    user = app.get_user()
    _ = user.is_administrator() or app.redirect403()

    midnight_timestamp = time.mktime(date.today().timetuple())
    try:
        range_start = int(app.request.query.get('range_start', midnight_timestamp))
    except ValueError:
        range_start = midnight_timestamp
    search_range_start = range_start
    try:
        range_end = int(app.request.query.get('range_end', midnight_timestamp + 86399))
    except ValueError:
        range_end = midnight_timestamp + 86399
    search_range_end = range_end

    if params['date_format'] in ['datetime']:
        # Assuming UTC timestamps!
        search_range_start = datetime.utcfromtimestamp(range_start)
        search_range_end = datetime.utcfromtimestamp(range_end)

    logger.info("[logs] get_global_history, range: %d - %d", search_range_start, search_range_end)
    logger.info("[logs] get_global_history, range: %s - %s",
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(search_range_start)),
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(search_range_end)))

    try:
        limit = int(app.request.query.get('limit', 100))
    except ValueError:
        limit = 100
    try:
        offset = int(app.request.query.get('offset', 0))
    except ValueError:
        offset = 0

    filters = {}
    if params['events'] and params['events'][0]:
        filters = {params['type_field']: {'$in': params['events']}}

    # logs is a pymongo Cursor object
    # query is the mongo query used to get logs
    # todo: allow pagination in the logs (limit / offset)
    logs, query = _get_logs(range_start=search_range_start, range_end=search_range_end,
                            limit=limit, offset=offset,
                            filters=filters, time_field=params['time_field'])

    add_more = app.request.query.get('add_more', None)

    message = "No module configured to get monitoring logs from database!"
    total_records = 0
    current_records = 0
    if logs is not None:
        total_records = logs.collection.count_documents(query, None)
        current_records = logs.collection.count_documents(query, None, skip=offset, limit=limit)

        if add_more:
            if current_records:
                message = "%d more records..." % current_records
            else:
                message = "No more records"
        else:
            message = "Got %d records out of %d" % (current_records, total_records)

        logger.info("[logs] got %d records.", current_records)
        logger.info("[logs] query: %s", query)

    return {
        'records': logs,
        'total_records': total_records,
        'current_records': current_records,
        'query': query,
        'params': params,
        'message': message,
        'range_start': range_start,
        'range_end': range_end
    }


pages = {
    get_global_history: {
        'name': 'History', 'route': '/logs',
        'view': 'logs',
        'static': True
    },
    get_history: {
        'name': 'HistoryHost', 'route': '/logs/inner',
        'view': 'history',
        'static': True
    },
    # form_hosts_list: {
    #     'name': 'GetHostsList', 'route': '/logs/hosts_list',
    #     'view': 'form_hosts_list',
    #     'static': True
    # },
    set_hosts_list: {
        'name': 'SetLogsHostsList', 'route': '/logs/set_hosts_list',
        'view': 'logs', 'method': 'POST'
    },
    # form_services_list: {
    #     'name': 'GetServicesList', 'route': '/logs/services_list',
    #     'view': 'form_services_list',
    #     'static': True
    # },
    # set_services_list: {
    #     'name': 'SetLogsServicesList', 'route': '/logs/set_services_list',
    #     'view': 'logs', 'method': 'POST'
    # },
    set_events_list: {
        'name': 'SetLogsEventsList', 'route': '/logs/set_events_list',
        'method': 'POST'
    },
    set_period: {
        'name': 'SetLogsPeriod', 'route': '/logs/set_period',
        'method': 'POST'
    }
}
