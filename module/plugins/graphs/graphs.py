#!/usr/bin/python

# -*- coding: utf-8 -*-

# Copyright (C) 2009-2012:
#    Gabes Jean, naparuba@gmail.com
#    Gerhard Lausser, Gerhard.Lausser@consol.de
#    Gregory Starck, g.starck@gmail.com
#    Hartmut Goebel, h.goebel@goebel-consult.de
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
import json
import random

import requests

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


def proxy_graph():
    """ This route proxies graphs returned by the graph module.
        The pnp4nagios/graphite image url have to be in the GET attributes,
        encoded with urlencode. The graphs metamodule takes care of that. This
        route should not be usefull anywhere else.
    """
    url = app.request.GET.get('url', '')

    try:
        request = requests.get(url)
        if request.status_code != 200:
            logger.error("[graph] Image URL not found: %d - %s", request.status_code, url)
            app.bottle.response.status = request.status_code
            app.bottle.response.content_type = 'application/json'
            return json.dumps(
                {'status': 'ko', 'message': request.content}
            )

    except Exception as exp:
        logger.error("[graph] exception: %s", str(exp))
        app.bottle.response.status = 409
        app.bottle.response.content_type = 'application/json'
        return json.dumps(
            {'status': 'ko', 'message': str(exp)}
        )

    app.response.content_type = str(request.headers['content-type'])
    app.response.set_header("Cache-Control", "public, max-age=300")
    return request.content


def get_service_graphs(host_name, service):
    user = app.get_user()
    elt = app.datamgr.get_service(host_name, service, user) or app.redirect404()
    html_string = ""
    if app.graphs_module.is_available():
        graphs = app.graphs_module.get_graph_uris(elt, duration=12 * 3600)
        for graph in graphs:
            html_string += "<p><img src='%s' width='600px'></p>" % graph['img_src']

    app.response.set_header("Cache-Control", "public, max-age=60")
    return html_string


def get_host_graphs(host_name):
    user = app.get_user()
    elt = app.datamgr.get_host(host_name, user) or app.redirect404()
    html_string = ""
    if app.graphs_module.is_available():
        graphs = app.graphs_module.get_graph_uris(elt, duration=12 * 3600)
        for graph in graphs:
            html_string += "<p><img src='%s' width='600px'></p>" % graph['img_src']

    app.response.set_header("Cache-Control", "public, max-age=60")
    return html_string


# Our page
def get_graphs_widget():
    user = app.get_user()
    # Graph URL may be: http://192.168.0.42/render/?width=320&height=240&fontSize=8&
    # lineMode=connected&from=04:57_20151203&until=04:57_20151204&tz=Europe/Paris&
    # title=Outlook_Web_Access/ - rta&target=alias(color(Outlook_Web_Access.rta,"green"),"rta")&
    # target=alias(color(constantLine(1000),"orange"),"Warning")&
    # target=alias(color(constantLine(3000),"red"),"Critical")
    url = app.request.GET.get('url', '')
    logger.debug("[graph] graph URL: %s", url)

    if not url:
        search = app.request.GET.get('search', '') or app.datamgr.get_hosts(user)[0].host_name
        elt = app.datamgr.get_element(search, user) or app.redirect(404)
    else:
        search = app.request.GET.get('search', '')
        elt = None

    duration = app.request.GET.get('duration', '86400')
    duration_list = {
        '3600': '1h',
        '86400': '1d',
        '172800': '2d',
        '604800': '7d',
        '2592000': '30d',
        '31536000': '365d'
    }

    wid = app.request.query.get('wid', 'widget_graphs_' + str(int(time.time())))
    collapsed = (app.request.query.get('collapsed', 'False') == 'True')

    options = {
        'search': {
            'value': search,
            'type': 'hst_srv',
            'label': 'Element name'
        },
        'url': {
            'value': url,
            'type': 'text',
            'label': 'Graph URL'
        },
        'duration': {
            'value': duration,
            'values': duration_list,
            'type': 'select',
            'label': 'Duration'
        },
    }

    title = 'Element graphs'
    if search:
        title = 'Element graphs for %s (%s)' % (search, duration_list[str(duration)])

    return {
        'elt': elt,
        'wid': wid,
        'graphsId': "graphs_%d" % random.randint(1, 9999),
        'collapsed': collapsed,
        'options': options,
        'base_url': '/widget/graphs',
        'url': url,
        'title': title,
        'duration': int(duration),
    }


widget_desc = """<h4>Graphs</h4>
Show the perfdata graph
"""

pages = {
    proxy_graph: {
        'name': 'Graph', 'route': '/graph', 'view': 'graph',
        'static': True
    },
    get_graphs_widget: {
        'name': 'wid_Graph', 'route': '/widget/graphs', 'view': 'widget_graphs',
        'widget': ['dashboard'],
        'widget_desc': widget_desc,
        'widget_name': 'graphs',
        'widget_alias': 'Graphs',
        'widget_icon': 'bar-chart',
        'widget_picture': '/static/graphs/img/widget_graphs.png',
        'static': True
    },
    get_service_graphs: {
        'name': 'GetServiceGraphs', 'route': '/graphs/:host_name/:service#.+#',
        'static': True
    },
    get_host_graphs: {
        'name': 'GetHostGraphs', 'route': '/graphs/:host_name',
        'static': True
    }
}
