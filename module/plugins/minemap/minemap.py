#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (C) 2009-2012:
#    Gabes Jean, naparuba@gmail.com
#    Mohier Frederic frederic.mohier@gmail.com
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
from collections import Counter

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


def show_minemap():
    user = app.get_user()

    # Apply search filter if exists ...
    search = app.request.query.get('search', "type:host")
    if "type:host" not in search:
        search = "type:host " + search
    logger.debug("search parameters '%s'", search)
    items = app.datamgr.search_hosts_and_services(search, user)
    logger.info("[minemap] got %d matching items: %s", len(items), [i.get_name() for i in items])

    # Fetch elements per page preference for user, default is 25
    elts_per_page = app.prefs_module.get_ui_user_preference(user, 'elts_per_page', 25)

    # We want to limit the number of elements
    step = int(app.request.GET.get('step', elts_per_page))
    if step != elts_per_page:
        elts_per_page = step
    start = int(app.request.GET.get('start', '0'))
    end = int(app.request.GET.get('end', start + step))
    logger.info("[minemap] got %d matching items: %s", len(items), [i.get_name() for i in items])

    # If we overflow, came back as normal
    total = len(items)
    if start > total:
        start = 0
        end = step

    navi = app.helper.get_navi(total, start, step=step)
    logger.info("[minemap2] got %d matching items: %s", len(items), [i.get_name() for i in items])
    logger.info("[minemap2] start %d, end: %d", start, end)

    # Limit the number of elements
    items = items[start:end]
    logger.info("[minemap3] displaying %d items: %s", len(items), [i.get_name() for i in items])

    # rows and columns will contain, respectively, all unique hosts and all unique services ...
    rows = []
    columns = []

    # items is a list of hosts
    for host in items:
        rows.append(host.get_name())
        for s in host.services:
            if s.service_description not in columns:
                columns.append(s.get_name())

    # Sort columns by descending occurence
    # rows.sort()
    columns = [c for c, i in Counter(columns).most_common()]

    return {
        'navi': navi,
        'elts_per_page': elts_per_page,
        'page': '/minemap',
        'rows': rows, 'columns': columns,
        'items': items[start:end]
    }


def show_minemaps():
    app.bottle.redirect("/minemap/all")


# Load plugin configuration parameters
# load_cfg()

pages = {
    show_minemap: {
        'name': 'Minemap', 'route': '/minemap', 'view': 'minemap', 'search_engine': True,
        'static': True
    },
    show_minemaps: {
        'name': 'Minemaps', 'route': '/minemaps', 'view': 'minemap',
        'static': True
    }
}
