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
import json

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


def lookup():
    app.response.content_type = 'application/json'

    name = app.request.GET.get('q', '')
    user = app.get_user()

    logger.debug("lookup: %s", name)

    result = []
    if '/' in name:
        logger.debug("lookup services for %s", name)
        splitted = name.split('/')
        hname = splitted[0]
        filtered_services = app.datamgr.get_host_services(hname, user)
        snames = ("%s/%s" % (hname, s.service_description) for s in filtered_services)
        result = [n for n in snames]
    else:
        filtered_hosts = app.datamgr.get_hosts(user)
        hnames = (h.host_name for h in filtered_hosts)
        result = [n for n in hnames if name in n]

    return json.dumps(result)


pages = {
    lookup: {
        'name': 'GetLookup', 'route': '/lookup', 'method': 'GET'
    }
}
