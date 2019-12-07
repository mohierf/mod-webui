#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (C) 2009-2012:
#    Gabes Jean, naparuba@gmail.com
#    Mohier Frédéric frederic.mohier@gmail.com
#    Karfusehr Andreas, frescha@unitedseed.de
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
import re
import json
import random

# Check if Alignak is installed
ALIGNAK = os.environ.get('ALIGNAK_DAEMON', None) is not None

# Alignak / Shinken base module are slightly different
if ALIGNAK:
    # Specific logger configuration
    from alignak.log import logging, ALIGNAK_LOGGER_NAME

    logger = logging.getLogger(ALIGNAK_LOGGER_NAME + ".webui")
else:
    from shinken.log import logger

# Will be populated by the UI with it's own value
app = None

# Plugin's parameters
params = {}


# Hook called by WebUI module once the plugin is loaded ...
# pylint: disable=global-statement
def load_config(the_app):
    global params

    logger.info("loading configuration ...")
    logger.info("app configuration: %s", the_app.c)

    properties = {
        'worldmap-zoom': '{"default_zoom": 16}',
        'worldmap-lng': '{"default_lng": 5.080625}',
        'worldmap-lat': '{"default_lat": 45.054148}',
        'worldmap-hosts': '{"hosts_level": [1,2,3,4,5]}',
        'worldmap-services': '{"services_level": [1,2,3,4,5]}',
        'worldmap-layer': '{"layer": ""}',
    }

    for prop, default in list(properties.items()):
        params.update(json.loads(the_app.prefs_module.get_ui_common_preference(prop, default)))

    logger.info("configuration loaded.")
    logger.info("configuration, params: %s", params)


def search_hosts_with_coordinates(search, user):
    if "type:host" not in search:
        search = "type:host " + search

    logger.debug("worldmap, search parameters '%s'", search)
    hosts = app.datamgr.search_hosts_and_services(search, user)

    # We are looking for hosts with valid GPS coordinates,
    # and we just give them to the template to print them.
    # :COMMENT:maethor:150810: If you want default coordinates, just put them
    # in the 'generic-host' template.
    valid_hosts = []
    for host in hosts:
        logger.debug("found host '%s'", host.get_name())

        if host.business_impact not in params['hosts_level']:
            continue

        try:
            _lat = float(host.customs.get('_LOC_LAT', None))
            _lng = float(host.customs.get('_LOC_LNG', None))
            # lat/long must be between -180/180
            if not (-180 <= _lat <= 180 and -180 <= _lng <= 180):
                raise Exception()
        except Exception:
            logger.debug("host '%s' has invalid GPS coordinates", host.get_name())
            continue

        logger.debug("host '%s' located on worldmap: %f - %f",
                     host.get_name(), _lat, _lng)
        valid_hosts.append(host)

    return valid_hosts


# Our page. If the user call /worldmap
def show_worldmap():
    user = app.get_user()

    # Apply search filter if exists ...
    search = app.request.query.get('search', "type:host")

    # So now we can just send the valid hosts to the template
    return {'search_string': search, 'params': params,
            'mapId': 'hostsMap',
            'hosts': search_hosts_with_coordinates(search, user)}


def show_worldmap_widget():
    user = app.get_user()

    wid = app.request.query.get('wid', 'widget_worldmap_' + str(int(time.time())))
    collapsed = (app.request.query.get('collapsed', 'False') == 'True')

    # We want to limit the number of elements, The user will be able to increase it
    nb_elements = max(0, int(app.request.query.get('nb_elements', '10')))

    # Apply search filter if exists ...
    search = app.request.query.get('search', "type:host")

    items = search_hosts_with_coordinates(search, user)

    # Ok, if needed, apply the widget refine search filter
    refine_search = app.request.query.get('search', '')
    if refine_search:
        pat = re.compile(refine_search, re.IGNORECASE)
        items = [i for i in items if pat.search(i.get_full_name())]

    items = items[:nb_elements]

    options = {
        'search': {
            'value': refine_search,
            'type': 'hst_srv',
            'label': 'Filter by name'
        },
        'nb_elements': {
            'value': nb_elements,
            'type': 'int',
            'label': 'Max number of elements to show'
        },
    }

    title = 'Worldmap'
    if refine_search:
        title = 'Worldmap (%s)' % refine_search

    return {
        'wid': wid,
        'mapId': "map_%d" % random.randint(1, 9999),
        'collapsed': collapsed,
        'options': options,
        'base_url': '/widget/worldmap',
        'title': title,
        'params': params,
        'hosts': items
    }


widget_desc = """<h4>Worldmap</h4>
Show a map of all monitored hosts.
"""

# We export our properties to the webui
pages = {
    show_worldmap: {
        'name': 'Worldmap', 'route': '/worldmap', 'view': 'worldmap',
        'static': True, 'search_engine': True
    },
    show_worldmap_widget: {
        'name': 'wid_Worldmap', 'route': '/widget/worldmap', 'view': 'worldmap_widget',
        'widget': ['dashboard'],
        'widget_desc': widget_desc,
        'widget_name': 'worldmap',
        'widget_alias': 'Worldmap',
        'widget_icon': 'globe',
        'widget_picture': '/static/worldmap/img/widget_worldmap.png',
        'static': True
    }
}
