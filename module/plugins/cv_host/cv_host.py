#!/usr/bin/python

# -*- coding: utf-8 -*-

# Copyright (C) 2009-2012:
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
import re

from config_parser import ConfigParser

# Check if Alignak is installed
ALIGNAK = os.environ.get('ALIGNAK_DAEMON', None) is not None

# Alignak / Shinken base module are slightly different
if ALIGNAK:
    # Specific logger configuration
    from alignak.log import logging, ALIGNAK_LOGGER_NAME

    logger = logging.getLogger(ALIGNAK_LOGGER_NAME + ".webui")
    from alignak.misc.perfdata import PerfDatas
else:
    from shinken.log import logger
    from shinken.misc.perfdata import PerfDatas

plugin_name = os.path.splitext(os.path.basename(__file__))[0]

# Will be populated by the UI with it's own value
app = None


# Get plugin's parameters from configuration file
# Define service/perfdata name for each element in graph
params = {
    'svc_load_name': "load",
    'svc_load_used': "load1|load5|load15",
    'svc_load_uom': "",
    'svc_cpu_name': "Cpu|cpu|CPU",
    'svc_cpu_used': "^cpu_all_idle|cpu_all_iowait|cpu_all_usr|cpu_all_nice",
    'svc_cpu_uom': "^%$",
    'svc_dsk_name': "disks|Disks",
    'svc_dsk_used': "^(.*)used_pct$",
    'svc_dsk_uom': "^%$",
    'svc_mem_name': "memory|Memory",
    'svc_mem_used': "^(.*)$",
    'svc_mem_uom': "^%$",
    'svc_net_name': "NET Stats",
    'svc_net_used': "eth0_rx_by_sec|eth0_tx_by_sec|eth0_rxErrs_by_sec|eth0_txErrs_by_sec",
    'svc_net_uom': "p/s"
}


def _find_service_by_name(host, service):
    logger.debug("[cvhost], search service %s", service)
    for svc in host.services:
        if re.search(service, svc.get_name()):
            logger.debug("[cvhost], found!")
            return svc
    return None


def get_disks(host):
    res = {}
    state = 'UNKNOWN'

    service = _find_service_by_name(host, params['svc_dsk_name'])
    if service:
        logger.debug("[cvhost], found %s", service.get_full_name())
        state = service.state

        try:
            perf_data = PerfDatas(service.perf_data)
            for metric in perf_data:
                if metric.name and metric.value is not None:
                    logger.debug("[cvhost], metric '%s' = %s, uom: %s",
                                 metric.name, metric.value, metric.uom)
                    if re.search(params['svc_dsk_used'], metric.name) and \
                            re.match(params['svc_dsk_uom'], metric.uom):
                        res[metric.name] = metric.value
                        logger.debug("[cvhost], got '%s' = %s", metric.name, metric.value)
        except Exception as exp:
            logger.warning("[cvhost] get_disks, exception: %s", str(exp))

    logger.debug("[cvhost], get_disks %s", res)
    return state, res


def get_memory(host):
    res = {}
    state = 'UNKNOWN'

    service = _find_service_by_name(host, params['svc_mem_name'])
    if service:
        logger.debug("[cvhost], found %s", service.get_full_name())
        state = service.state

        try:
            perf_data = PerfDatas(service.perf_data)
            for metric in perf_data:
                if metric.name and metric.value is not None:
                    logger.debug("[cvhost], metric '%s' = %s, uom: %s",
                                 metric.name, metric.value, metric.uom)
                    if re.search(params['svc_mem_used'], metric.name) and \
                            re.match(params['svc_mem_uom'], metric.uom):
                        logger.debug("[cvhost], got '%s' = %s", metric.name, metric.value)
                        res[metric.name] = metric.value
        except Exception as exp:
            logger.warning("[cvhost] get_memory, exception: %s", str(exp))

    logger.debug("[cvhost], get_memory %s", res)
    return state, res


def get_cpu(host):
    res = {}
    state = 'UNKNOWN'

    service = _find_service_by_name(host, params['svc_cpu_name'])
    if service:
        logger.debug("[cvhost], found %s", service.get_full_name())
        state = service.state

        try:
            perf_data = PerfDatas(service.perf_data)
            for metric in perf_data:
                if metric.name and metric.value is not None:
                    logger.debug("[cvhost], metric '%s' = %s, uom: %s",
                                 metric.name, metric.value, metric.uom)
                    if re.search(params['svc_cpu_used'], metric.name) and \
                            re.match(params['svc_cpu_uom'], metric.uom):
                        logger.debug("[cvhost], got '%s' = %s", metric.name, metric.value)
                        res[metric.name] = metric.value
        except Exception as exp:
            logger.warning("[cvhost] get_cpu, exception: %s", str(exp))

    logger.debug("[cvhost], get_cpu %s", res)
    return state, res


def get_load(host):
    res = {}
    state = 'UNKNOWN'

    service = _find_service_by_name(host, params['svc_load_name'])
    if service:
        logger.debug("[cvhost], found %s", service.get_full_name())
        state = service.state

        try:
            perf_data = PerfDatas(service.perf_data)
            for metric in perf_data:
                if metric.name and metric.value is not None:
                    logger.debug("[cvhost], metric '%s' = %s, uom: %s",
                                 metric.name, metric.value, metric.uom)
                    if re.search(params['svc_load_used'], metric.name) and \
                            re.match(params['svc_load_uom'], metric.uom):
                        logger.debug("[cvhost], got '%s' = %s", metric.name, metric.value)
                        res[metric.name] = metric.value
        except Exception as exp:
            logger.warning("[cvhost] get_load, exception: %s", str(exp))

    logger.debug("[cvhost], get_load %s", res)
    return state, res


def get_network(host):
    res = {}
    state = 'UNKNOWN'

    service = _find_service_by_name(host, params['svc_net_name'])
    if service:
        logger.debug("[cvhost], found %s", service.get_full_name())
        state = service.state

        try:
            perf_data = PerfDatas(service.perf_data)
            for metric in perf_data:
                if metric.name and metric.value is not None:
                    logger.debug("[cvhost], metric '%s' = %s, uom: %s",
                                 metric.name, metric.value, metric.uom)
                    if re.search(params['svc_net_used'], metric.name) and \
                            re.match(params['svc_net_uom'], metric.uom):
                        logger.debug("[cvhost], got '%s' = %s", metric.name, metric.value)
                        res[metric.name] = metric.value
        except Exception as exp:
            logger.warning("[cvhost] get_network, exception: %s", str(exp))

    logger.debug("[cvhost], get_network %s", res)
    return state, res


def get_printer(host):
    res = {}
    state = 'UNKNOWN'

    res = _find_service_by_name(host, params['svc_prn_name'])
    if res:
        logger.debug("[cvhost], found %s", res.get_full_name())
        state = res.state

        try:
            perf_data = PerfDatas(res.perf_data)
            for metric in perf_data:
                if metric.name and metric.value is not None:
                    logger.debug("[cvhost], metric '%s' = %s, uom: %s",
                                 metric.name, metric.value, metric.uom)
                    if re.search(params['svc_prn_used'], metric.name) and \
                            re.match(params['svc_prn_uom'], metric.uom):
                        logger.debug("[cvhost], got '%s' = %s", metric.name, metric.value)
                        res[metric.name] = metric.value
        except Exception as exp:
            logger.warning("[cvhost] get_printer, exception: %s", str(exp))

    logger.debug("[cvhost], get_printer %s", res)
    return state, res


def get_services(host):
    res = {}
    state = 'UNKNOWN'

    # Get host's services list
    for service in host.services:
        state = max(state, service.state_id)

        view_state = service.state
        if service.problem_has_been_acknowledged:
            view_state = 'ACK'
        if service.in_scheduled_downtime:
            view_state = 'DOWNTIME'
        # all.append((s.get_name(), view_state))
        res[service.get_name()] = view_state
        # services_states[s.get_name()] = s.state

    # Compute the worst state of all packages
    state = compute_worst_state(res)

    logger.debug("[cvhost], get_services %s", res)
    return state, res


def compute_worst_state(all_states):
    _ref = {
        'OK': 0, 'UP': 0, 'DOWN': 3, 'UNREACHABLE': 1, 'UNKNOWN': 1,
        'CRITICAL': 3, 'WARNING': 2, 'PENDING': 1, 'ACK': 1, 'DOWNTIME': 1
    }
    cur_level = 0
    for (key, value) in all_states.items():
        logger.debug("[cvhost], compute_worst_state: %s/%s", key, value)
        level = _ref[value]
        cur_level = max(cur_level, level)
    return {
        3: 'CRITICAL',
        2: 'WARNING',
        1: 'UNKNOWN',
        0: 'OK'}[cur_level]


# pylint: disable=global-statement
def get_page(name, item_type):
    global params

    # user = app.check_user_authentication()

    logger.debug("[cvhost], get_page for %s, type: '%s'", name, item_type)

    currentdir = os.path.dirname(os.path.realpath(__file__))
    configuration_file = "%s/%s.cfg" % (currentdir, item_type)
    logger.debug("Plugin configuration file: %s", configuration_file)
    try:
        scp = ConfigParser('#', '=')
        tmp = params.copy()
        tmp.update(scp.parse_config(configuration_file))
        params = tmp

        logger.debug("[cvhost] configuration loaded.")
        logger.debug("[cvhost] configuration, load: %s (%s)",
                     params['svc_load_name'], params['svc_load_used'])
        logger.debug("[cvhost] configuration, cpu: %s (%s)",
                     params['svc_cpu_name'], params['svc_cpu_used'])
        logger.debug("[cvhost] configuration, disk: %s (%s)",
                     params['svc_dsk_name'], params['svc_dsk_used'])
        logger.debug("[cvhost] configuration, memory: %s (%s)",
                     params['svc_mem_name'], params['svc_mem_used'])
        logger.debug("[cvhost] configuration, network: %s (%s)",
                     params['svc_net_name'], params['svc_net_used'])
        # logger.info("[cvhost] configuration, printer: %s (%s)",
        # params['svc_prn_name'], params['svc_prn_used'])
    except Exception as exp:
        logger.warning("[cvhost] configuration file (%s) not available or bad formed: %s",
                       configuration_file, str(exp))
        app.redirect404()
        # return {
        #     'app': app, 'config': type,
        #     'all_perfs': {}, 'all_states': {}
        # }

    all_perfs = {}
    all_states = {
        "global": 'UNKNOWN', "cpu": 'UNKNOWN', "disks": 'UNKNOWN', "memory": 'UNKNOWN',
        "network": 'UNKNOWN', "printer": 'UNKNOWN', "services": 'UNKNOWN'
    }

    # Ok, we can lookup it
    user = app.get_user()
    host = app.datamgr.get_host(name, user) or app.redirect404()

    # Set the host state first
    all_states["host"] = host.state
    if host.is_problem and host.problem_has_been_acknowledged:
        all_states["host"] = 'ACK'
    if host.in_scheduled_downtime:
        all_states["host"] = 'DOWNTIME'
    # First look at disks
    all_states["disks"], all_perfs['disks'] = get_disks(host)
    # Then memory
    all_states["memory"], all_perfs['memory'] = get_memory(host)
    # Then CPU
    all_states['cpu'], all_perfs['cpu'] = get_cpu(host)
    # Then load
    all_states['load'], all_perfs['load'] = get_load(host)
    # Then printer ... TODO: later if needed !
    # all_states['printer'], all_perfs['printer'] = get_printer(host)
    # And Network
    all_states['network'], all_perfs['network'] = get_network(host)
    # And services
    all_states['services'], all_perfs['services'] = get_services(host)
    # Then global
    all_states["global"] = compute_worst_state(all_states)

    logger.debug("[cvhost] overall state: %s", all_states)

    return {
        'app': app,
        'elt': host,
        'config': item_type,
        'all_perfs': all_perfs,
        'all_states': all_states
    }


pages = {
    get_page: {
        'name': 'CustomView', 'route': '/cv/<name:path>/<type:path>',
        'view': 'cv_host', 'static': True
    }
}
