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
import datetime

from config_parser import ConfigParser

# Check if Alignak is installed
ALIGNAK = os.environ.get('ALIGNAK_DAEMON', None) is not None

# Alignak / Shinken base module are slightly different
if ALIGNAK:
    # Specific logger configuration
    from alignak.log import logging, ALIGNAK_LOGGER_NAME

    logger = logging.getLogger(ALIGNAK_LOGGER_NAME + ".webui")
else:
    from shinken.log import logger

# Get plugin's parameters from configuration file
params = {
    'logs_type': ['INFO', 'WARNING', 'ERROR'],
    'logs_hosts': [],
    'logs_services': []
}

# Will be populated by the UI with it's own value
app = None


def _get_logs(*args, **kwargs):
    if app.logs_module.is_available():
        return app.logs_module.get_ui_logs(*args, **kwargs)

    logger.warning("[logs] no get history external module defined!")
    return None


# pylint: disable=global-statement,unused-argument
def load_config(the_app):
    global params

    currentdir = os.path.dirname(os.path.realpath(__file__))
    configuration_file = "%s/%s" % (currentdir, 'plugin.cfg')
    logger.info("[logs] Plugin configuration file: %s", configuration_file)
    try:
        scp = ConfigParser('#', '=')
        tmp = params.copy()
        tmp.update(scp.parse_config(configuration_file))
        params = tmp

        params['logs_type'] = [item.strip() for item in params['logs_type'].split(',')]
        if params['logs_hosts']:
            params['logs_hosts'] = [item.strip() for item in params['logs_hosts'].split(',')]
        if params['logs_services']:
            params['logs_services'] = [item.strip() for item in params['logs_services'].split(',')]

        logger.info("[logs] configuration loaded.")
        logger.info("[logs] configuration, fetching types: %s", params['logs_type'])
        logger.info("[logs] configuration, hosts: %s", params['logs_hosts'])
        logger.info("[logs] configuration, services: %s", params['logs_services'])
        return True
    except Exception as exp:
        logger.warning("[logs] configuration file (%s) not available: %s",
                       configuration_file, str(exp))
        return False


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

    params['logs_type'] = []

    logs_type_list = app.request.forms.getall('logs_typeList[]')
    logger.debug("[logs] Selected logs types : ")
    for log_type in logs_type_list:
        logger.debug("[logs] - log type : %s", log_type)
        params['logs_type'].append(log_type)

    app.bottle.redirect("/logs")


def get_history():
    user = app.get_user()

    filters = dict()

    service = app.request.GET.get('service', None)
    host = app.request.GET.get('host', None)

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

    logclass = app.request.GET.get('logclass', None)
    if logclass is not None:
        filters['logclass'] = int(logclass)

    command_name = app.request.GET.get('commandname', None)
    if command_name is not None:
        try:
            command_name = json.loads(command_name)
        except Exception:
            pass
        filters['command_name'] = command_name

    limit = int(app.request.GET.get('limit', 100))
    offset = int(app.request.GET.get('offset', 0))

    logs = _get_logs(filters=filters, limit=limit, offset=offset)
    return {'records': logs}


# :TODO:maethor:171017: This function should be merge in get_history
def get_global_history():
    user = app.get_user()
    _ = user.is_administrator() or app.redirect403()

    midnight_timestamp = time.mktime(datetime.date.today().timetuple())
    range_start = int(app.request.GET.get('range_start', midnight_timestamp))
    range_end = int(app.request.GET.get('range_end', midnight_timestamp + 86399))
    logger.debug("[logs] get_global_history, range: %d - %d", range_start, range_end)

    logs = _get_logs(filters={'type': {'$in': params['logs_type']}},
                     range_start=range_start, range_end=range_end)

    if logs is None:
        message = "No module configured to get Shinken logs from database!"
    else:
        message = ""

    return {
        'records': logs,
        'params': params,
        'message': message,
        'range_start': range_start, 'range_end': range_end
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
