#!/usr/bin/env python
# -*- coding: utf-8 -*-

# pylint:disable=too-many-public-methods, too-many-branches, too-many-statements,
# pylint:disable=too-many-nested-blocks, too-many-locals, too-many-lines,
# pylint:disable=too-many-instance-attributes, too-many-arguments, consider-using-ternary

# Copyright (C) 2009-2012:
#    Gabes Jean, naparuba@gmail.com
#    Gerhard Lausser, Gerhard.Lausser@consol.de
#    Gregory Starck, g.starck@gmail.com
#    Hartmut Goebel, h.goebel@goebel-consult.de
#    Andreas Karfusehr, andreas@karfusehr.de
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
import datetime
import copy
import math
import operator
import re

from collections import OrderedDict

# pylint: disable=invalid-name
ALIGNAK = os.environ.get('ALIGNAK_DAEMON', None) is not None
if ALIGNAK:
    # from alignak.misc.sorter import hst_srv_sort
    from alignak.misc.perfdata import PerfDatas
    from alignak.macroresolver import MacroResolver
else:
    # from shinken.misc.sorter import hst_srv_sort
    from shinken.misc.perfdata import PerfDatas
    from shinken.macroresolver import MacroResolver


# pylint: disable=no-self-use
class Helper(object):
    def __init__(self):
        pass

    def print_date(self, timestamp, dt_format='%Y-%m-%d %H:%M:%S'):
        """
        For a unix time return something like
        Tue Aug 16 13:56:08 2011

        :param timestamp:
        :param dt_format:
        :return:
        """
        if timestamp == 0 or timestamp is None:
            return 'N/A'

        if dt_format:
            return time.strftime(dt_format, time.localtime(timestamp))

        return time.asctime(time.localtime(timestamp))

    def print_duration(self, timestamp, just_duration=False, x_elts=0):
        """
        For a time, print something like
        10m 37s  (just duration = True)
        N/A if got bogus number (like 1970 or None)
        1h 30m 22s ago (if t < now)
        Now (if t == now)
        in 1h 30m 22s
        Or in 1h 30m (no sec, if we ask only_x_elements=2, 0 means all)

        :param timestamp:
        :param just_duration:
        :param x_elts:
        :return:
        """
        if timestamp == 0 or timestamp is None:
            return 'N/A'

        # Get the difference between now and the time of the user
        seconds = int(time.time()) - int(timestamp)

        # If it's now, say it :)
        if seconds == 0:
            return 'Now'

        in_future = False

        # Remember if it's in the future or not
        if seconds < 0:
            in_future = True

        # Now manage all case like in the past
        seconds = abs(seconds)

        seconds = int(round(seconds))
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)
        weeks, days = divmod(days, 7)
        months, weeks = divmod(weeks, 4)
        years, months = divmod(months, 12)

        minutes = int(minutes)
        hours = int(hours)
        days = int(days)
        weeks = int(weeks)
        months = int(months)
        years = int(years)

        duration = []
        if years > 0:
            duration.append('%dy' % years)
        else:
            if months > 0:
                duration.append('%dM' % months)
            if weeks > 0:
                duration.append('%dw' % weeks)
            if days > 0:
                duration.append('%dd' % days)
            if hours > 0:
                duration.append('%dh' % hours)
            if minutes > 0:
                duration.append('%dm' % minutes)
            if seconds > 0:
                duration.append('%ds' % seconds)

        # Now filter the number of printed elements if ask
        if x_elts >= 1:
            duration = duration[:x_elts]

        # Maybe the user just want the duration
        if just_duration:
            return ' '.join(duration)

        # Now manage the future or not print
        if in_future:
            return 'in ' + ' '.join(duration)

        return ' '.join(duration) + ' ago'

    def print_duration_and_date(self, timestamp, just_duration=False, x_elts=2):
        """
        Prints the duration with the date as title

        :param timestamp:
        :param just_duration:
        :param x_elts:
        :return:
        """
        return "<span title='%s'>%s</span>" \
               % (self.print_date(timestamp, dt_format="%d %b %Y %H:%M:%S"),
                  self.print_duration(timestamp, just_duration, x_elts=x_elts))

    def sort_elements(self, elements):
        e_list = copy.copy(elements)
        # todo: restore this feature (see Helper class!)
        # e_list.sort(hst_srv_sort)
        return e_list

    def group_by_daterange(self, date_list, key):
        today = datetime.datetime.now().date()

        groups = OrderedDict([
            ('In the future', []),
            ('Today', []),
            ('Yesterday', []),
            ('This month', [])])

        for entry in date_list:
            my_date = datetime.datetime.fromtimestamp(key(entry)).date()
            if my_date > today:
                groups['In the future'].append(entry)
            elif my_date == today:
                groups['Today'].append(entry)
            elif my_date.year == today.year and \
                    my_date.month == today.month and \
                    my_date.day == today.day - 1:
                groups['Yesterday'].append(entry)
            elif my_date.year == today.year and my_date.month == today.month:
                groups['This month'].append(entry)
            elif my_date.year == today.year:
                month = my_date.strftime("%B")
                if month not in groups:
                    groups[month] = []
                groups[month].append(entry)
            else:
                if my_date.year not in groups:
                    groups[my_date.year] = []
                groups[my_date.year].append(entry)

        return groups

    def get_small_icon_state(self, obj):  # pylint: disable=too-many-return-statements
        """
        Get the small state for host/service icons and satellites ones

        :param obj:
        :return:
        """
        if obj.__class__.my_type in ['service', 'host']:
            if obj.state == 'PENDING':
                return 'unknown'
            if obj.state == 'OK':
                return 'ok'
            if obj.state == 'UP':
                return 'up'
            # Outch, not a good state...
            if obj.problem_has_been_acknowledged:
                return 'ack'
            if obj.in_scheduled_downtime:
                return 'downtime'
            if obj.is_flapping:
                return 'flapping'
            # Ok, no excuse, it's a true error...
            return obj.state.lower()
        # Maybe it's a satellite
        if obj.__class__.my_type in ['scheduler', 'poller',
                                     'reactionner', 'broker',
                                     'receiver']:
            if not obj.alive:
                return 'critical'
            if not obj.reachable:
                return 'warning'
            return 'ok'
        return 'unknown'

    def get_business_impact_text(self, business_impact, text=False):
        """
        Give a business impact as text and stars if need
        If text=True, returns text+stars, else returns stars only ...
        :param business_impact:
        :param text:
        :return:
        """
        txts = {0: 'None', 1: 'Low', 2: 'Normal',
                3: 'Important', 4: 'Very important', 5: 'Business critical'}
        nb_stars = max(0, business_impact - 2)
        stars = '<small style="vertical-align: middle;">' \
                '<i class="fas fa-star"></i></small>' * nb_stars

        if text:
            res = "%s %s" % (txts.get(business_impact, 'Unknown'), stars)
        else:
            res = stars
        return res

    def get_on_off(self, status=False, title=None, message=''):
        """
        Give an enabled/disabled state based on font-awesome with optional title and message

        :param status:
        :param title:
        :param message:
        :return:
        """
        if not title:
            if status:
                title = 'Enabled'
            else:
                title = 'Disabled'

        if status:
            return '''<span title="%s" class="fas fa-check font-green">%s</span>''' % (title, message)

        return '''<span title="%s" class="fas fa-times font-red">%s</span>''' % (title, message)

    def get_link(self, obj, short=False):
        if obj.__class__.my_type == 'service':
            if short:
                name = obj.get_name()
            else:
                name = obj.get_full_name()

            return '<a href="/service/%s"> %s </a>' % (obj.get_full_name(), name)

        # if not service, host
        return '<a href="/host/%s"> %s </a>' % (obj.get_full_name(), obj.get_full_name())

    def get_link_dest(self, obj):
        """
        Give only the /service/blabla or /host blabla string, like for buttons inclusion

        :param obj:
        :return:
        """
        return "/%s/%s" % (obj.__class__.my_type, obj.get_full_name())

    def get_fa_icon_state(self, obj=None, cls='host', state='UP', disabled=False, label='',
                          use_title=True):
        """
            Get an Html formatted string to display host/service state

            If obj is specified, obj class and state are used.
            If obj is None, cls and state parameters are used.

            If disabled is True, the font used is greyed

            If label is empty, only an icon is returned
            If label is set as 'state', the icon title is used as text
            Else, the content of label is used as text near the icon.

            If use_title is False, do not include title attribute.

            Returns a span element containing a Font Awesome icon that depicts
           consistently the host/service current state (see issue #147)
        """
        state = obj.state.upper() if obj is not None else state.upper()
        flapping = (obj and obj.is_flapping) or state == 'FLAPPING'
        ack = (obj and obj.problem_has_been_acknowledged) or state == 'ACK'
        downtime = (obj and obj.in_scheduled_downtime) or state == 'DOWNTIME'
        hard = (not obj or obj.state_type == 'HARD')

        # Icons depending upon element and real state ...
        icons = {
            'host': {
                'UP': 'server',
                'DOWN': 'server',
                'UNREACHABLE': 'server',
                'ACK': 'check',
                'DOWNTIME': 'clock',
                'FLAPPING': 'cog fa-spin',
                'PENDING': 'server',
                'UNKNOWN': 'server'
            },
            'service': {
                'OK': 'arrow-up',
                'CRITICAL': 'arrow-down',
                'WARNING': 'exclamation',
                'UNREACHABLE': 'question',
                'ACK': 'check',
                'DOWNTIME': 'clock',
                'FLAPPING': 'cog fa-spin',
                'PENDING': 'spinner fa-circle-notch',
                'UNKNOWN': 'question'
            }
        }

        cls = obj.__class__.my_type if obj is not None else cls

        back = '''<i class="fas fa-%s fa-stack-2x font-%s"></i>''' \
               % (icons[cls]['FLAPPING'] if flapping else 'circle',
                  state.lower() if not disabled else 'greyed')
        if flapping:
            back += '''<i class="fas fa-circle fa-stack-1x font-%s"></i>''' \
                    % (state.lower() if not disabled else 'greyed')

        title = "%s is %s" % (cls, state)

        if flapping:
            icon_color = 'fa-inverse' if not disabled else 'font-greyed'
            title += " and is flapping"
        else:
            icon_color = 'fa-inverse'

        if downtime or ack or not hard:
            icon_style = 'style="opacity: 0.5"'
        else:
            icon_style = ""

        if state == 'DOWNTIME':
            icon = icons[cls]['DOWNTIME']
            title += " and in scheduled downtime"
        elif state == 'ACK':
            icon = icons[cls]['ACK']
            title += " and acknowledged"
        else:
            icon = icons[cls].get(state, 'UNKNOWN')

        if obj and not (obj.active_checks_enabled or obj.passive_checks_enabled):
            icon_color = 'bg-lightgrey'

        front = '''<i class="fas fa-%s fa-stack-1x %s"></i>''' % (icon, icon_color)

        if use_title:
            icon_text = '''<span class="fa-stack" %s title="%s">%s%s</span>''' \
                        % (icon_style, title, back, front)
        else:
            icon_text = '''<span class="fa-stack" %s>%s%s</span>''' \
                        % (icon_style, back, front)

        if label == '':
            return icon_text

        color = state.lower() if not disabled else 'greyed'
        if label == 'title':
            label = title
        return '''
          <span class="font-%s">
             %s&nbsp;<span class="num">%s</span>
          </span>
          ''' % (color, icon_text, label)

    def get_fa_icon_state_and_label(self, obj=None, cls='host', state='UP', label="",
                                    disabled=False, use_title=True):
        color = state.lower() if not disabled else 'greyed'
        return '''
          <span class="font-%s">
             %s&nbsp;<span class="num">%s</span>
          </span>
          ''' % (color,
                 self.get_fa_icon_state(obj=obj, cls=cls, state=state,
                                        disabled=disabled, use_title=use_title),
                 label)

    # :TODO:maethor:150609: Rewrite this function
    def get_navi(self, total, pos, step=30):
        """
        Get the pages navigation HTML widget

        :param total:
        :param pos:
        :param step:
        :return:
        """
        step = float(step)
        nb_pages = math.ceil(total / step) if step != 0 else 0
        current_page = int(pos / step) if step != 0 else 0
        step = int(step)

        res = []

        nb_max_items = 2

        if current_page >= nb_max_items:
            # Name, start, end, is_current
            res.append(('«', 0, step, False))
            res.append(('...', None, None, False))

        # pylint: disable=undefined-variable
        # Because xrange...
        for i in range(current_page - int(nb_max_items / 2),
                       current_page + 1 + int(nb_max_items / 2)):
            if i < 0:
                continue
            is_current = (i == current_page)
            start = int(i * step)
            # Maybe we are generating a page too high, bail out
            if start > total:
                continue

            end = int((i + 1) * step)
            res.append(('%d' % (i + 1), start, end, is_current))

        if current_page < nb_pages - nb_max_items:
            start = int((nb_pages - (nb_max_items - 1)) * step)
            end = int(total)
            # end = int(nb_pages * step)
            res.append(('...', None, None, False))
            res.append(('»', start, end, False))

        return res

    def get_html_color(self, state):
        colors = {
            'CRITICAL': "#d9534f",
            'DOWN': "#d9534f",
            'WARNING': "#f0ad4e",
            'OK': "#5cb85c",
            'UP': "#5cb85c",
            'PENDING': '#49AFCD',
            'UNKNOWN': '#49AFCD'
        }

        if state in colors:
            return colors[state]

        return colors['UNKNOWN']

    def get_perfdata_pie(self, perf_data):
        if perf_data.max is not None:
            color = self.get_html_color('OK')
            used_value = perf_data.value - (perf_data.min or 0)
            unused_value = perf_data.max - (perf_data.min or 0) - used_value
            if perf_data.warning or perf_data.critical:
                if perf_data.warning <= perf_data.critical:
                    if perf_data.value >= perf_data.warning:
                        color = self.get_html_color('WARNING')
                    if perf_data.value >= perf_data.critical:
                        color = self.get_html_color('CRITICAL')
                else:
                    # inverted thresholds : OK > WARNING > CRITICAL
                    if perf_data.value <= perf_data.warning:
                        color = self.get_html_color('WARNING')
                    if perf_data.value <= perf_data.critical:
                        color = self.get_html_color('CRITICAL')
                    used_value, unused_value = unused_value, used_value

            used_value = perf_data.value - (perf_data.min or 0)
            unused_value = perf_data.max - (perf_data.min or 0) - used_value
            if unused_value + used_value:
                used_pct = (float(used_value) / float(unused_value + used_value)) * 100
            else:
                used_pct = None

            title = "%s %s%s" % (perf_data.name, perf_data.value, perf_data.uom)
            if perf_data.uom != '%' and isinstance(used_pct, float):
                title += " ({:.2f}%)".format(used_pct)

            return '<span class="sparkline piechart" title="%s" role="img" sparkType="pie" ' \
                   'sparkBorderWidth="0" sparkSliceColors="[%s,#f5f5f5]" values="%s,%s"></span>' \
                   % (title, color, used_value, unused_value)
        return ""

    def get_perfdata_pies(self, elt):
        return " ".join([self.get_perfdata_pie(p) for p in PerfDatas(elt.perf_data)])

    def get_perfdata_table(self, elt):
        perfdatas = PerfDatas(elt.perf_data)
        display_min = any(p.min for p in perfdatas)
        display_max = any(p.max is not None for p in perfdatas)
        display_warning = any(p.warning is not None for p in perfdatas)
        display_critical = any(p.critical is not None for p in perfdatas)

        html = '<table class="table table-condensed table-w-condensed">'
        html += '<tr><th></th><th>Label</th><th>Value</th>'
        if display_min:
            html += '<th>Min</th>'
        if display_max:
            html += '<th>Max</th>'
        if display_warning:
            html += '<th>Warning</th>'
        if display_critical:
            html += '<th>Critical</th>'
        html += '</tr>'

        for perf_data in perfdatas:
            html += '<tr><td>%s</td><td>%s</td><td>%s %s</td>' \
                    % (self.get_perfdata_pie(perf_data),
                       perf_data.name, perf_data.value, perf_data.uom)
            if display_min:
                if perf_data.min is not None:
                    html += '<td>%s %s</td>' % (perf_data.min, perf_data.uom)
                else:
                    html += '<td></td>'
            if display_max:
                if perf_data.max is not None:
                    html += '<td>%s %s</td>' % (perf_data.max, perf_data.uom)
                else:
                    html += '<td></td>'
            if display_warning:
                if perf_data.warning is not None:
                    html += '<td>%s %s</td>' % (perf_data.warning, perf_data.uom)
                else:
                    html += '<td></td>'
            if display_critical:
                if perf_data.critical is not None:
                    html += '<td>%s %s</td>' % (perf_data.critical, perf_data.uom)
                else:
                    html += '<td></td>'
            html += '</tr>'
        html += '</table>'

        return html

    def get_html_id(self, elt):
        """
        We want the html id of an host or a service. It's basically
        the full_name with / changed as -- (because in html, / is not valid :) )

        :param elt:
        :return:
        """
        return self.strip_html_id(elt.get_full_name())

    def strip_html_id(self, item):
        return item.replace('/', '--').replace(' ', '_').replace('.', '_').replace(':', '_')

    def make_html_id(self, item):
        """
        Make an HTML element identifier

        :param item:
        :return:
        """
        return re.sub('[^A-Za-z0-9]', '', item)

    def get_uri_name(self, item):
        """
        URI with spaces are BAD, must change them with %20

        :param item:
        :return:
        """
        return item.get_full_name().replace(' ', '%20')

    def get_aggregation_paths(self, path):
        path = path.strip()
        if path and not path.startswith('/'):
            path = '/' + path
        if path.endswith('/'):
            path = path[-1]
        return [s.strip() for s in path.split('/')]

    def compute_aggregation_tree_worse_state(self, tree):
        # First ask to our sons to compute their states
        for son in tree['sons']:
            self.compute_aggregation_tree_worse_state(son)
        # Ok now we can look at worse between our services
        # and our sons
        # get a list of all states
        states = [s['state'] for s in tree['sons']]
        for son in tree['services']:
            states.append(son.state.lower())

        # ok now look at what is worse here
        for order in ['critical', 'warning', 'unknown', 'unreachable', 'ok', 'pending']:
            if order in states:
                tree['state'] = order
                return

        # Should be never call or we got a major problem...
        tree['state'] = 'unknown'

    def assume_and_get_path_in_tree(self, tree, paths):
        current_full_path = ''
        for path in paths:
            # Don't care about void path, like for root
            if not path:
                continue
            current_full_path += '/' + path
            found = False
            for son in tree['sons']:
                # Maybe we find the good son, if so go on this level
                if path == son['path']:
                    tree = son
                    found = True
                    break
            # Did we find our son? If no, create it and jump into it
            if not found:
                son = {
                    'path': path,
                    'sons': [],
                    'services': [],
                    'state': 'unknown',
                    'full_path': current_full_path
                }
                tree['sons'].append(son)
                tree = son
        return tree

    def get_host_service_aggregation_tree(self, host):
        tree = {'path': '/', 'sons': [], 'services': [], 'state': 'unknown', 'full_path': '/'}
        for service in host.services:
            paths = self.get_aggregation_paths(service.aggregation)
            leaf = self.assume_and_get_path_in_tree(tree, paths)
            leaf['services'].append(service)

        self.compute_aggregation_tree_worse_state(tree)

        return tree

    def print_aggregation_tree(self, tree, html_id, expanded=False):
        path = tree['path']
        full_path = tree['full_path']
        sons = tree['sons']
        services = tree['services']
        state = tree['state']
        _id = '%s-%s' % (html_id, self.strip_html_id(full_path))
        html = ''

        display = 'block'
        icon = 'minus'
        list_state = 'expanded'

        if path != '/':
            html += """<a class="toggle-list" data-state="%s" data-target="ag-%s">
            <span class="alert-small alert-%s"> <i class="fas fa-%s"></i> %s&nbsp;</span> </a>""" \
                 % (list_state, _id, state, icon, path)

        html += """<ul name="ag-%s" class="list-group" style="display: %s;">""" % (_id, display)
        # If we got no parents, no need to print the expand icon
        if sons:
            for son in sons:
                sub_s = self.print_aggregation_tree(son, html_id, expanded=expanded)
                html += '<li class="list-group-item">%s</li>' % sub_s

        html += '<li class="list-group-item">'
        if path == '/' and services:
            html += """<span class="alert-small"> Others </span>"""

        if services:
            html += '<ul class="list-group">'
            # Sort our services before print them
            # todo: restore this feature (see Helper class!)
            # services.sort(hst_srv_sort)
            for svc in services:
                html += '<li class="list-group-item">'
                html += helper.get_fa_icon_state(svc)
                html += self.get_link(svc, short=True)
                if svc.business_impact > 2:
                    html += "(" + self.get_business_impact_text(svc.business_impact) + ")"
                html += """ is <span class="font-%s"><strong>%s</strong></span>""" \
                        % (svc.state.lower(), svc.state)
                html += " since %s" % self.print_duration(svc.last_state_change,
                                                          just_duration=True, x_elts=2)
                html += "</li>"
            html += "</ul></li>"
        else:
            html += "</li>"

        html += "</ul>"

        return html

    def print_business_rules(self, tree, level=0, source_problems=None):
        if source_problems is None:
            source_problems = []
        node = tree['node']
        name = node.get_full_name()
        fathers = tree['fathers']
        fathers = sorted(fathers, key=lambda dict: dict['node'].get_full_name())

        html = ''

        # Do not print the node if it's the root one, we already know its state!
        if level != 0:
            html += helper.get_fa_icon_state(node)
            html += self.get_link(node, short=True)
            if node.business_impact > 2:
                html += "(" + self.get_business_impact_text(node.business_impact) + ")"
            html += """ is <span class="font-%s"><strong>%s</strong></span>""" % (
                node.state.lower(), node.state)
            html += """ since <span title="%s">%s""" % (
                time.strftime("%d %b %Y %H:%M:%S", time.localtime(node.last_state_change)),
                self.print_duration(node.last_state_change, just_duration=True, x_elts=2))

        # If we got no parents, no need to print the expand icon
        if fathers:
            # We look if the below tree is good or not
            tree_is_good = (node.state_id == 0)

            # If the tree is good, we will use an expand image
            # and hide the tree
            if tree_is_good:
                display = 'none'
                list_state = 'collapsed'
                icon = 'plus'
            else:  # we will already show the tree, and use a reduce image
                display = 'block'
                list_state = 'expanded'
                icon = 'minus'

            # If we are the root, we already got this
            if level != 0:
                html += '<a class="pull-right toggle-list" data-state="%s" data-target="bp-%s">' \
                        '<i class="fas fa-%s"></i></a>' % (list_state, self.make_html_id(name), icon)

            html += """<ul class="list-group" name="bp-%s" style="display: %s;">""" \
                    % (self.make_html_id(name), display)

            for ascendant in fathers:
                sub_node = ascendant['node']
                sub_s = self.print_business_rules(
                    ascendant, level=level + 1, source_problems=source_problems)
                html += '<li class="list-group-item %s">%s</li>' \
                        % (self.get_small_icon_state(sub_node), sub_s)
            html += "</ul>"

        return html

    def get_timeperiod_html(self, timeperiod):
        if not timeperiod.dateranges:
            return ''

        # Build a definition list ...
        content = '''<dl>'''
        for date_range in sorted(timeperiod.dateranges,
                                 key=operator.methodcaller("get_start_and_end_time")):
            (dr_start, dr_end) = date_range.get_start_and_end_time()
            dr_start = time.strftime("%d %b %Y", time.localtime(dr_start))
            dr_end = time.strftime("%d %b %Y", time.localtime(dr_end))
            if dr_start == dr_end:
                content += '''<dd>%s:</dd>''' % dr_start
            else:
                content += '''<dd>From: %s, to: %s</dd>''' % (dr_start, dr_end)

            if date_range.timeranges:
                content += '''<dt>'''
                idx = 1
                for timerange in date_range.timeranges:
                    content += '''&nbsp;%s-%s''' \
                               % ("%02d:%02d" % (timerange.hstart, timerange.mstart),
                                  "%02d:%02d" % (timerange.hend, timerange.mend))
                    idx += 1
                content += '''</dt>'''
        content += '''</dl>'''

        # Build a definition list ...
        if timeperiod.exclude:
            content += '''<dl> Excluded: '''
            for excl in timeperiod.exclude:
                content += self.get_timeperiod_html(excl)
            content += '''</dl>'''

        return content

    def get_contact_avatar(self, contact, size=24, with_name=True, with_link=True):
        name = contact
        title = name

        # Maybe it is a UI contact
        try:
            title = contact.get_name()
            name = contact.get_username()
        except Exception:
            pass

        html = '<img src="/avatar/%s?s=%s" class="img-circle">' % (name, size)

        if contact == '(Nagios Process)':
            name = "Nagios Process"
            title = name
            html = '<i class="fas fa-server"></i>'
        elif contact == 'Alignak':
            name = "Alignak"
            title = name
            html = '<i class="fas fa-server"></i>'

        if with_name:
            html += '&nbsp;'
            html += title

        if with_link and contact not in ['(Nagios Process)', 'Alignak']:
            html = '<a href="/contact/%s">%s</a>' % (name, html)

        html = '<span class="user-avatar" title="%s">%s</span>' % (title, html)

        return html

    def render_url(self, obj, items, css=''):
        """Returns formatted HTML for an element URL

        """
        result = []
        for (icon, title, url) in items:
            if not url:
                # Nothing to do here!
                continue

            # Replace MACROS in url, title and description
            # todo: some missing arguments in the function calls... all replaced with empty lists
            if hasattr(obj, 'get_data_for_checks'):
                if url:
                    if ALIGNAK:
                        url = MacroResolver().resolve_simple_macros_in_string(
                            url, obj.get_data_for_checks([]), [], [])
                    else:
                        url = MacroResolver().resolve_simple_macros_in_string(
                            url, obj.get_data_for_checks([]))
                if title:
                    if ALIGNAK:
                        title = MacroResolver().resolve_simple_macros_in_string(
                            title, obj.get_data_for_checks([]), [], [])
                    else:
                        title = MacroResolver().resolve_simple_macros_in_string(
                            title, obj.get_data_for_checks([]))

            link = 'href="%s" target="_blank" ' % url
            if not url:
                link = 'href="#" '

            if icon:
                icon = '<i class="fas fa-%s"></i>' % icon
            else:
                icon = ''

            if not title:
                result.append('<a %s>%s&nbsp;%s</a>' % (link, icon, url))
            else:
                result.append('<a %s %s>%s&nbsp;%s</a>' % (link, css, icon, title))

        return result

    def get_element_urls(self, item, prop, title=None, icon=None, css=''):
        """"Return list of element notes urls

        The notes_url or actions_url fields are containing a simple url or a string in which
        individual url are separated with a | character.

        Each url must contain an URI string and may also contain an icon and a title:

        action_url URL1,ICON1,ALT1|URL2,ICON2,ALT2|URL3,ICON3,ALT3

        As documented in Shinken:
        * URLx are the url you want to use
        * ICONx are the images you want to display the link as. It can be either a local
         file, relative to the folder webui/plugins/eltdetail/htdocs/ or an url.
        * ALTx are the alternative texts you want to display when the ICONx file is missing,
         or not set.

        The UI do not use any icon file but the font-awesome icons font. As such, ICONx information
        is the name of an icon in the font awesome icons list.

        The ALTx information is the text label used for the hyperlink or button on the page.

        """
        if not item or not hasattr(item, prop):
            return []

        # We build a list of: title, icon, description, url
        notes = []

        # Several notes are defined in the notes attribute with | character
        for note in getattr(item, prop).split('|'):
            # An element is: url[,icon][,title] - icon and title are optional
            try:
                (url, icon, title) = note.split(',')
            except ValueError:
                try:
                    (url, icon) = note.split(',')
                except ValueError:
                    url = note

            notes.append((icon, title, url))

        return self.render_url(item, notes, css=css)

    def get_element_notes(self, obj, title=None, icon=None, css=''):
        """"See the comment of get_element_urls"""
        return self.get_element_urls(obj, 'notes',
                                     title=title, icon=icon, css=css)

    def get_element_notes_url(self, obj, title=None, icon=None, css=''):
        """"See the comment of get_element_urls"""
        return self.get_element_urls(obj, 'notes_url',
                                     title=title, icon=icon, css=css)

    def get_element_actions_url(self, obj, title=None, icon=None, css=''):
        """"See the comment of get_element_urls"""
        return self.get_element_urls(obj, 'action_url',
                                     title=title, icon=icon, css=css)

    def hst_srv_sort(self, svc1, svc2):
        """Sort hosts and services by impact, states and co"""
        if svc1.business_impact > svc2.business_impact:
            return -1
        if svc2.business_impact > svc1.business_impact:
            return 1

        # Ok, we compute a importance value so
        # For host, the order is UP, UNREACH, DOWN
        # For service: OK, UNKNOWN, WARNING, CRIT
        # And DOWN is before CRITICAL (potential more impact)
        tab = {
            'host': {0: 0, 1: 4, 2: 1},
            'service': {0: 0, 1: 2, 2: 3, 3: 1}
        }
        state1 = tab[svc1.__class__.my_type].get(svc1.state_id, 0)
        state2 = tab[svc2.__class__.my_type].get(svc2.state_id, 0)
        # ok, here, same business_impact
        # Compare warn and crit state
        if state1 > state2:
            return -1
        if state2 > state1:
            return 1

        # Ok, so by name...
        if svc1.get_full_name() > svc2.get_full_name():
            return 1

        return -1

    def worse_first(self, svc1, svc2):
        """Sort hosts and services by impact, states and co"""
        # Ok, we compute a importance value so
        # For host, the order is UP, UNREACH, DOWN
        # For service: OK, UNKNOWN, WARNING, CRIT
        # And DOWN is before CRITICAL (potential more impact)
        tab = {
            'host': {0: 0, 1: 4, 2: 1},
            'service': {0: 0, 1: 2, 2: 3, 3: 1}
        }
        state1 = tab[svc1.__class__.my_type].get(svc1.state_id, 0)
        state2 = tab[svc2.__class__.my_type].get(svc2.state_id, 0)

        # ok, here, same business_impact
        # Compare warn and crit state
        if state1 > state2:
            return -1
        if state2 > state1:
            return 1

        # Same? ok by business impact
        if svc1.business_impact > svc2.business_impact:
            return -1
        if svc2.business_impact > svc1.business_impact:
            return 1

        # Ok, so by name...
        # Ok, so by name...
        if svc1.get_full_name() > svc2.get_full_name():
            return -1

        return 1

    def last_state_change_earlier(self, svc1, svc2):
        """Sort hosts and services by last_state_change time"""
        if svc1.last_state_change > svc2.last_state_change:
            return -1
        if svc1.last_state_change < svc2.last_state_change:
            return 1

        return 0

    def get_event_icon(self, event, disabled=False, label='', use_title=True):
        '''
            Get an Html formatted string to display a monitoring event

            If disabled is True, the font used is greyed

            If label is empty, only an icon is returned
            If label is set as 'state', the icon title is used as text
            Else, the content of label is used as text near the icon.

            If use_title is False, do not include title attribute.

            Returns a span element containing a Font Awesome icon that depicts
           consistently the event and its state
        '''
        cls = event.get('type', 'unknown').lower()
        state = event.get('state', 'n/a').upper()
        state_type = event.get('state_type', 'n/a').upper()
        hard = (state_type == 'HARD')

        # Icons depending upon element and real state ...
        # ; History
        icons = {
            "unknown": {
                "class": "history_Unknown",
                "text": "Unknown event",
                "icon": "question"
            },

            "retention_load": {
                "class": "history_RetentionLoad",
                "text": "Retention load",
                "icon": "save"
            },
            "retention_save": {
                "class": "history_RetentionSave",
                "text": "Retention save",
                "icon": "save"
            },

            "alert": {
                "class": "history_Alert",
                "text": "Monitoring alert",
                "icon": "bolt"
            },

            "notification": {
                "class": "history_Notification",
                "text": "Monitoring notification sent",
                "icon": "paper-plane"
            },

            "check_result": {
                "class": "history_CheckResult",
                "text": "Check result",
                "icon": "bolt"
            },

            "comment": {
                "class": "history_WebuiComment",
                "text": "WebUI comment",
                "icon": "send"
            },
            "timeperiod_transition": {
                "class": "history_TimeperiodTransition",
                "text": "Timeperiod transition",
                "icon": "clock-o"
            },
            "external_command": {
                "class": "history_ExternalCommand",
                "text": "External command",
                "icon": "wrench"
            },

            "event_handler": {
                "class": "history_EventHandler",
                "text": "Monitoring event handler",
                "icon": "bolt"
            },
            "flapping_start": {
                "class": "history_FlappingStart",
                "text": "Monitoring flapping start",
                "icon": "flag"
            },
            "flapping_stop": {
                "class": "history_FlappingStop",
                "text": "Monitoring flapping stop",
                "icon": "flag-o"
            },
            "downtime_start": {
                "class": "history_DowntimeStart",
                "text": "Monitoring downtime start",
                "icon": "ambulance"
            },
            "downtime_cancelled": {
                "class": "history_DowntimeCancelled",
                "text": "Monitoring downtime cancelled",
                "icon": "ambulance"
            },
            "downtime_end": {
                "class": "history_DowntimeEnd",
                "text": "Monitoring downtime stopped",
                "icon": "ambulance"
            },
            "acknowledge_start": {
                "class": "history_AckStart",
                "text": "Monitoring acknowledge start",
                "icon": "check"
            },
            "acknowledge_cancelled": {
                "class": "history_AckCancelled",
                "text": "Monitoring acknowledge cancelled",
                "icon": "check"
            },
            "acknowledge_end": {
                "class": "history_AckEnd",
                "text": "Monitoring acknowledge expired",
                "icon": "check"
            },
        }

        back = '''<i class="fa fa-circle fa-stack-2x font-%s"></i>''' \
               % (state.lower() if not disabled else 'greyed')

        icon_color = 'fa-inverse'
        icon_style = ""
        if not hard:
            icon_style = 'style="opacity: 0.5"'

        try:
            icon = icons[cls]['icon']
            title = icons[cls]['text']
        except KeyError:
            cls = 'unknown'
            icon = icons[cls]['icon']
            title = icons[cls]['text']

        front = '''<i class="fa fa-%s fa-stack-1x %s"></i>''' % (icon, icon_color)

        if use_title:
            icon_text = '''<span class="fa-stack" %s title="%s">%s%s</span>''' \
                        % (icon_style, title, back, front)
        else:
            icon_text = '''<span class="fa-stack" %s>%s%s</span>''' \
                        % (icon_style, back, front)

        if label == '':
            return icon_text

        color = state.lower() if not disabled else 'greyed'
        if label == 'title':
            label = title
        return '''
          <span class="font-%s">
             %s&nbsp;<span class="num">%s</span>
          </span>
          ''' % (color, icon_text, label)


# pylint: disable=invalid-name
helper = Helper()
