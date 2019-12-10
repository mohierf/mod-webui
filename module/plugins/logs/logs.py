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

    # Shinken mongo logs module uses an integer timestamp
    'date_format': 'timestamp',

    # Shinken mongo logs module uses 'message' to store a log information
    'other_fields': ['message'],

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
        'HOST ALERT', 'SERVICE ALERT', 'EXTERNAL COMMAND', 'HOST NOTIFICATION', 'SERVICE NOTIFICATION'
    ],

    # Hosts filtering
    'logs_hosts': [],

    # Services filtering
    'logs_services': []
}

# Will be populated by the UI with it's own value
app = None


def _get_logs(*args, **kwargs):
    if app.logs_module.is_available():
        return app.logs_module.get_ui_logs(*args, **kwargs)

    logger.warning("[logs] no get history external module defined!")
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
        if prop in ['other_fields', 'events', 'logs_hosts', 'logs_services']:
            if ',' in default:
                default = [item.strip() for item in default.split(',')]
            else:
                default = [default]

        params[prop] = default

    logger.info("[logs] configuration, timestamp field: %s", params['time_field'])
    logger.info("[logs] configuration, date format: %s", params['date_format'])
    logger.info("[logs] configuration, other fields: %s", params['other_fields'])
    logger.info("[logs] configuration, fetching events: %s", params['events'])
    logger.info("[logs] configuration, hosts: %s", params['logs_hosts'])
    logger.info("[logs] configuration, services: %s", params['logs_services'])

    logger.info("[logs] configuration loaded.")


def form_hosts_list():
    return {'params': params}


def set_hosts_list():
    # Form cancel
    if app.request.forms.get('cancel'):
        app.bottle.redirect("/logs")

    params['logs_hosts'] = []

    hosts_list = app.request.forms.getall('hostsList[]')
    logger.debug("[logs] Selected hosts : ")
    for host in hosts_list:
        logger.debug("[logs] - host : %s", host)
        params['logs_hosts'].append(host)

    app.bottle.redirect("/logs")


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


def form_logs_type_list():
    return {'params': params}


def set_logs_type_list():
    # Form cancel
    if app.request.forms.get('cancel'):
        app.bottle.redirect("/logs")

    params['events'] = []

    logs_type_list = app.request.forms.getall('logs_typeList[]')
    logger.debug("[logs] Selected logs types : ")
    for log_type in logs_type_list:
        logger.debug("[logs] - log type : %s", log_type)
        params['events'].append(log_type)

    app.bottle.redirect("/logs")


def get_history():
    user = app.get_user()

    filters = {}

    service = app.request.query.get('service', None)
    host = app.request.query.get('host', None)

    if host:
        if service:
            _ = app.datamgr.get_element(host + '/' + service, user) or app.redirect404()
        else:
            _ = app.datamgr.get_element(host, user) or app.redirect404()
    else:
        _ = user.is_administrator() or app.redirect403()

    if service:
        filters['service_description'] = service

    if host:
        filters['host_name'] = host

    logclass = app.request.query.get('logclass', None)
    if logclass is not None:
        filters['logclass'] = int(logclass)

    command_name = app.request.query.get('commandname', None)
    if command_name is not None:
        try:
            command_name = json.loads(command_name)
        except Exception:
            pass
        filters['command_name'] = command_name

    limit = int(app.request.query.get('limit', 100))
    offset = int(app.request.query.get('offset', 0))

    logs = _get_logs(filters=filters,
                     limit=limit,
                     offset=offset, time_field=params['time_field'])

    return {
        'time_field': params['time_field'],
        'type_field': params['type_field'],
        'other_fields': params['other_fields'],
        'records': logs
    }


# :TODO:maethor:171017: This function should be merge in get_history
def get_global_history():
    user = app.get_user()
    _ = user.is_administrator() or app.redirect403()

    midnight_timestamp = time.mktime(date.today().timetuple())
    try:
        range_start = int(app.request.GET.get('range_start', midnight_timestamp))
    except ValueError:
        range_start = midnight_timestamp
    search_range_start = range_start
    try:
        range_end = int(app.request.GET.get('range_end', midnight_timestamp + 86399))
    except ValueError:
        range_end = midnight_timestamp + 86399
    search_range_end = range_end

    if params['date_format'] in ['datetime']:
        # Assuming UTC timestamps!
        search_range_start = datetime.utcfromtimestamp(range_start)
        search_range_end = datetime.utcfromtimestamp(range_end)

    logger.info("[logs] get_global_history, range: %d - %d", search_range_start, search_range_end)

    filters = {}
    if params['events'] and params['events'][0]:
        filters = {params['type_field']: {'$in': params['events']}}

    # logs is a pymongo Cursor object
    logs = _get_logs(filters=filters,
                     range_start=search_range_start, range_end=search_range_end,
                     time_field=params['time_field'])

    message = ""
    if logs is None:
        message = "No module configured to get Shinken logs from database!"
    else:
        logger.info("[logs] got %d records.", logs.count())

    return {
        'records': logs,
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
    form_hosts_list: {
        'name': 'GetHostsList', 'route': '/logs/hosts_list',
        'view': 'form_hosts_list',
        'static': True
    },
    set_hosts_list: {
        'name': 'SetHostsList', 'route': '/logs/set_hosts_list',
        'view': 'logs', 'method': 'POST'
    },
    form_services_list: {
        'name': 'GetServicesList', 'route': '/logs/services_list',
        'view': 'form_services_list',
        'static': True
    },
    set_services_list: {
        'name': 'SetServicesList', 'route': '/logs/set_services_list',
        'view': 'logs', 'method': 'POST'
    },
    form_logs_type_list: {
        'name': 'GetLogsTypeList', 'route': '/logs/logs_type_list',
        'view': 'form_logs_type_list',
        'static': True
    },
    set_logs_type_list: {
        'name': 'SetLogsTypeList', 'route': '/logs/set_logs_type_list',
        'view': 'logs', 'method': 'POST'
    }
}
