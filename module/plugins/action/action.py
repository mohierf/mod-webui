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

# We will need external commands here
import os
import re
import time

# Check if Alignak is installed
ALIGNAK = os.environ.get('ALIGNAK_DAEMON', None) is not None

# Alignak / Shinken base module are slightly different
if ALIGNAK:
    from alignak.external_command import ExternalCommand, ExternalCommandManager
    # Specific logger configuration
    from alignak.log import logging, ALIGNAK_LOGGER_NAME

    logger = logging.getLogger(ALIGNAK_LOGGER_NAME + ".webui")
else:
    from shinken.external_command import ExternalCommand, ExternalCommandManager
    from shinken.log import logger

# Will be populated by the UI with it's own value
app = None


# Function handling $NOW$ macro
def substitute_now():
    return str(int(time.time()))


def substitute_slash():
    return '/'


# This dictionary associate macros with expansion function
subs = {
    '$NOW$': substitute_now,
    '$SLASH$': substitute_slash,
    # Add new macros here
}


# Expand macro in a string. It returns the string with macros defined in subs dictionary expanded
def expand_macros(cmd=None):
    macros = re.findall(r'(\$\w+\$)', cmd)
    cmd_expanded = cmd
    for macro in macros:
        subfunc = subs.get(macro)
        if subfunc is None:
            continue
        cmd_expanded = cmd_expanded.replace(macro, subfunc())

    return cmd_expanded


def forge_response(callback, status, text):
    if callback:
        return "%s({'status':%s,'text':'%s'})" % (callback, status, text)

    return "{'status':%s,'text':'%s'}" % (status, text)


# Our page
def get_page(cmd=None):

    app.response.content_type = 'application/json'

    callback = app.request.query.get('callback', None)
    response_text = app.request.query.get('response_text', 'Command launched')

    # Or he is not allowed to launch commands?
    if not app.can_action():
        return forge_response(callback, 403, 'You are not authorized to launch commands')

    now = substitute_now()
    elts = cmd.split('/')
    cmd_name = elts[0].upper()
    if ALIGNAK:
        cmd_name = elts[0].lower()
    cmd_args = elts[1:]
    logger.info("[actions] got command: %s with args: %s.", cmd_name, cmd_args)

    # Check if the command exist in the Alignak/Shinken external command list
    if cmd_name not in ExternalCommandManager.commands:
        logger.error("[actions] unknown command: %s", cmd_name)
        return forge_response(callback, 404, 'Unknown command %s' % cmd_name)

    # try:
    #     extcmd = "[%s] %s" % (now, ';'.join(elts))
    # except UnicodeDecodeError as e:
    #     extcmd = "[%s] %s" % (now, ';'.join(elts))
    ext_cmd = "[%s] %s" % (now, ';'.join(elts))

    # Expand macros
    ext_cmd = expand_macros(ext_cmd)
    logger.debug("[actions] external command: %s.", ext_cmd)
    app.push_external_command(ExternalCommand(ext_cmd))

    return forge_response(callback, 200, response_text)


pages = {
    get_page: {
        'name': 'Action', 'route': '/action/:cmd#.+#'
    }
}
