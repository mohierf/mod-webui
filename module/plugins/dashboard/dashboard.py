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

import json

# Will be populated by the UI with it's own value
app = None


# Our page
def get_page():
    user = app.get_user()

    # Look for the widgets as the json entry
    pref = app.prefs_module.get_ui_user_preference(user, 'widgets')
    # If void, create an empty one
    if not pref:
        app.prefs_module.set_ui_user_preference(user, 'widgets', '[]')
        pref = '[]'
    widget_names = json.loads(pref)
    widgets = []

    for widget in widget_names:
        if 'id' not in widget or 'position' not in widget:
            continue

        # by default the widget is for /dashboard
        widget['for'] = widget.get('for', 'dashboard')
        if not widget['for'] == 'dashboard':
            # Not a dashboard widget? I don't want it so
            continue

        options = widget.get('options', {})
        collapsed = widget.get('collapsed', '0')

        options["wid"] = widget["id"]
        options["collapsed"] = collapsed
        widget['options'] = options
        widget['options_json'] = json.dumps(options)
        args = {'wid': widget['id'], 'collapsed': collapsed}
        args.update(options)
        widget['options_uri'] = '&'.join('%s=%s' % (k, v) for (k, v) in args.items())
        widgets.append(widget)

    return {'widgets': widgets}


def get_currently():
    user = app.get_user()

    # Search panels preferences
    pref = app.prefs_module.get_ui_user_preference(user, 'panels')
    # If void, create an empty one
    if not pref:
        app.prefs_module.set_ui_user_preference(user, 'panels', '{}')
        pref = '{}'
    panels = json.loads(pref)

    # Search graphs preferences
    pref = app.prefs_module.get_ui_user_preference(user, 'graphs')
    # If void, create an empty one
    if not pref:
        app.prefs_module.set_ui_user_preference(user, 'graphs', '{}')
        pref = '{}'
    graphs = json.loads(pref)

    return {'panels': panels, 'graphs': graphs}


pages = {
    get_page: {
        'name': 'Dashboard', 'route': '/dashboard', 'view': 'dashboard', 'static': True
    },
    get_currently: {
        'name': 'Currently', 'route': '/currently', 'view': 'currently', 'static': True
    }
}
