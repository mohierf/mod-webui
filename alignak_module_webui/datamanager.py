#!/usr/bin/python
# -*- coding: utf-8 -*-

# pylint:disable=too-many-public-methods, too-many-branches, too-many-statements,
# pylint:disable=too-many-nested-blocks, too-many-locals, too-many-lines,
# pylint:disable=too-many-instance-attributes

# Copyright (C) 2009-2014:
#   Gabes Jean, naparuba@gmail.com
#   Gerhard Lausser, Gerhard.Lausser@consol.de
#   Gregory Starck, g.starck@gmail.com
#   Hartmut Goebel, h.goebel@goebel-consult.de
#   Frederic Mohier, frederic.mohier@gmail.com
#   Guillaume Subiron, maethor@subiron.org
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


import re
import itertools
import time

# Specific logger configuration
import logging
from alignak.log import ALIGNAK_LOGGER_NAME
# pylint: disable=invalid-name
logger = logging.getLogger(ALIGNAK_LOGGER_NAME + ".webui")

# from alignak.misc.datamanager import DataManager

# # Import all objects we will need
# from alignak.objects.host import Host, Hosts
# from alignak.objects.hostgroup import Hostgroup, Hostgroups
# from alignak.objects.service import Service, Services
# from alignak.objects.servicegroup import Servicegroup, Servicegroups
# from alignak.objects.contact import Contact, Contacts
# from alignak.objects.contactgroup import Contactgroup, Contactgroups
# from alignak.objects.notificationway import NotificationWay, NotificationWays
# from alignak.objects.timeperiod import Timeperiod, Timeperiods
# from alignak.objects.command import Command, Commands
# # from alignak.misc.sorter import last_state_change_earlier


class WebUIDataManager(object):

    def __init__(self, rg=None, problems_business_impact=0, important_problems_business_impact=0,
                 disable_inner_problems_computation=0):
        super(WebUIDataManager, self).__init__()
        self.regenerator = rg
        self.problems_business_impact = problems_business_impact
        self.important_problems_business_impact = important_problems_business_impact
        self.disable_inner_problems_computation = disable_inner_problems_computation

    @property
    def is_initialized(self):
        return len(self.get_contacts()) > 0

    @staticmethod
    def _is_related_to(item, user):
        """ Indicates if an item and a user are related """
        # if no user or user is an admin, always consider there is a relation
        if not user or user.is_administrator():
            return item

        logger.debug("[WebUI - relation], DM _is_related_to: %s", item.__class__)
        return user.is_related_to(item)

    @staticmethod
    def _only_related_to(items, user):
        """ This function is just a wrapper to _is_related_to for a list.

            :returns: List of elements related to the user
        """
        # if no user or user is an admin, always consider there is a relation
        if not user or user.is_administrator():
            return items

        try:
            logger.debug("[WebUI - relation], DM _only_related_to: %s", items)
            return [item for item in items if user.is_related_to(item)]
        except TypeError:
            return items if user.is_related_to(items) else None

    ##
    # Hosts
    ##
    def get_hosts(self, user=None):
        """ Get a list of all hosts.

            :param user: concerned user
            :returns: list of all hosts
        """
        return self.search_hosts_and_services('type:host', user)

    def get_important_hosts(self, user=None):
        return self.search_hosts_and_services('type:host bi:>=%d'
                                              % self.important_problems_business_impact, user)

    def get_host(self, name, user=None, template=False):
        """ Get a host by its hostname. """

        hosts = self.search_hosts_and_services('type:host host:^%s$' % name, user=user,
                                               template=template)
        return hosts[0] if hosts else None

    def get_host_services(self, hname, user):
        """ Get host services by its hostname. """
        return self.search_hosts_and_services('type:service host:%s' % (hname), user=user)

    def get_percentage_hosts_state(self, user=None, problem=False):
        """ Get percentage of hosts not in (or in) problems.

            :param problem: False to return the % of hosts not in problems,
                            True to return the % of hosts in problems.
                            False by default
        """
        host = self.get_hosts_synthesis(None, user)
        if not host['nb_elts']:
            return 0

        count = host['nb_elts'] - host['nb_problems']
        if problem:
            count = host['nb_problems']

        logger.debug("Hosts count: %s / %s / %s", count, host['nb_problems'], host['nb_elts'])
        return round(100.0 * (count / host['nb_elts']), 1)

    def get_hosts_synthesis(self, items=None, user=None):
        if items is not None:
            hosts = [item for item in items if item.__class__.my_type == 'host']
        else:
            hosts = self.get_hosts(user=user)
        logger.debug("[datamanager] get_hosts_synthesis, %d hosts", len(hosts))

        host_synth = {
            'nb_elts': len(hosts)
        }
        if not hosts:
            host_synth['bi'] = 0
            for state in ['up', 'down', 'unreachable',
                          'pending', 'unknown', 'ack', 'downtime', 'problems']:
                host_synth['nb_' + state] = 0
                host_synth['pct_' + state] = 0
            return host_synth

        host_synth['bi'] = max(h.business_impact for h in hosts)

        for state in ['up', 'pending']:
            host_synth['nb_' + state] = sum(1 for host in hosts if host.state == state.upper())
            host_synth['pct_' + state] = round(100.0 * host_synth['nb_' + state] / host_synth['nb_elts'], 1)
        for state in ['down', 'unreachable', 'unknown']:
            host_synth['nb_' + state] = sum(1 for host in hosts if host.state == state.upper()
                                      and not (host.problem_has_been_acknowledged
                                               or host.in_scheduled_downtime))
            host_synth['pct_' + state] = round(100.0 * host_synth['nb_' + state] / host_synth['nb_elts'], 1)

        # Our own computation !
        # ------
        # Shinken/Alignak does not always reflect the "problem" state
        # from a user point of view ...
        # To make UI more consistent, build our own problems counter!
        if not self.disable_inner_problems_computation:
            host_synth['nb_ack'] = 0
            host_synth['nb_problems'] = 0
            host_synth['nb_impacts'] = 0
            for host in hosts:
                if host.state_type.upper() not in ['HARD']:
                    continue
                # An host is a problem if it is in a HARD DOWN or UNKNOWN state
                if host.state.lower() in ['down', 'unknown']:
                    host.is_problem = True
                # An host is impacted if it is UNREACHABLE
                if host.state.lower() in ['unreachable']:
                    host.is_impact = True

                if host.is_problem and host.problem_has_been_acknowledged:
                    host_synth['nb_ack'] += 1

                if host.is_problem and not host.problem_has_been_acknowledged:
                    host_synth['nb_problems'] += 1
                    if host.is_impact:
                        host_synth['nb_impacts'] += 1
        else:
            host_synth['nb_problems'] = sum(1 for host in hosts if host.is_problem
                                      and not host.problem_has_been_acknowledged)
            host_synth['nb_impacts'] = sum(1 for host in hosts if host.is_problem
                                     and not host.problem_has_been_acknowledged
                                     and host.is_impact)
            host_synth['nb_ack'] = sum(1 for host in hosts if host.is_problem
                                 and host.problem_has_been_acknowledged)

        host_synth['pct_problems'] = round(100.0 * host_synth['nb_problems'] / host_synth['nb_elts'], 1)
        host_synth['pct_ack'] = round(100.0 * host_synth['nb_ack'] / host_synth['nb_elts'], 1)
        host_synth['nb_downtime'] = sum(1 for host in hosts if host.in_scheduled_downtime)
        host_synth['pct_downtime'] = round(100.0 * host_synth['nb_downtime'] / host_synth['nb_elts'], 1)

        logger.debug("[datamanager] get_hosts_synthesis: %s", host_synth)
        return host_synth

    def get_important_hosts_synthesis(self, user=None):
        return self.get_hosts_synthesis(items=self.get_important_hosts(user))

    ##
    # Services
    ##
    def get_services(self, user=None):
        """ Get a list of all services.

            :param user: concerned user
            :returns: list of all services
        """
        return self.search_hosts_and_services('type:service', user)

    def get_important_services(self, user=None):
        return self.search_hosts_and_services('type:service bi:>=%d'
                                              % self.important_problems_business_impact, user)

    def get_service(self, host_name, service_description, user, template=False):
        """ Get a service by its hostname and service description. """

        services = self.search_hosts_and_services('type:service host:^%s$ service:"^%s$"'
                                                  % (host_name, service_description), user=user,
                                                  template=template)
        return services[0] if services else None

    def get_percentage_service_state(self, user=None, problem=False):
        """ Get percentage of services not in (or in) problems.

            :param problem: False to return the % of services not in problems,
                            True to return the % of services in problems.
                            False by default
        """
        service = self.get_services_synthesis(None, user)
        if not service['nb_elts']:
            return 0

        # Services not in problem
        count = service['nb_elts'] - service['nb_problems']
        if problem:
            count = service['nb_problems']

        logger.debug("Services count: %s / %s / %s",
                     count, service['nb_problems'], service['nb_elts'])
        return round(100.0 * (count / service['nb_elts']), 1)

    def get_services_synthesis(self, items=None, user=None):
        if items is not None:
            services = [item for item in items if item.__class__.my_type == 'service']
        else:
            services = self.get_services(user=user)
        logger.debug("[datamanager] get_services_synthesis, %d services", len(services))

        svc_synth = {
            'nb_elts': len(services)
        }
        if not services:
            svc_synth['bi'] = 0
            for state in ['ok', 'warning', 'critical',
                          'pending', 'unreachable', 'unknown',
                          'ack', 'downtime', 'problems']:
                svc_synth['nb_' + state] = 0
                svc_synth['pct_' + state] = 0
            return svc_synth

        svc_synth['bi'] = max(s.business_impact for s in services)

        for state in ['ok', 'pending']:
            svc_synth['nb_' + state] = \
                sum(1 for service in services if service.state == state.upper())
            svc_synth['pct_' + state] = \
                round(100.0 * svc_synth['nb_' + state] / svc_synth['nb_elts'], 1)
        for state in ['warning', 'critical', 'unreachable', 'unknown']:
            svc_synth['nb_' + state] = \
                sum(1 for service in services if service.state == state.upper()
                    and not (service.problem_has_been_acknowledged
                             or service.in_scheduled_downtime))
            svc_synth['pct_' + state] = \
                round(100.0 * svc_synth['nb_' + state] / svc_synth['nb_elts'], 1)

        svc_synth['nb_impacts'] = 0
        # Our own computation !
        # ------
        # Shinken/Alignak does not always reflect the "problem"
        # state from a user point of view ...
        # To make UI more consistent, build our own problems counter!
        if not self.disable_inner_problems_computation:
            svc_synth['nb_ack'] = 0
            svc_synth['nb_problems'] = 0
            for service in services:
                if service.state_type.upper() not in ['HARD']:
                    continue
                # A service is a problem if it is in a HARD WARNING, CRITICAL or UNKNOWN state
                if service.state.lower() in ['warning', 'critical', 'unknown']:
                    service.is_problem = True
                # A service is impacted if its host is not UP
                if service.host.state not in ['up']:
                    service.is_impact = True
                # A service is impacted if it is UNREACHABLE
                if service.state.lower() in ['unreachable']:
                    service.is_impact = True

                if service.is_problem and service.problem_has_been_acknowledged:
                    svc_synth['nb_ack'] += 1

                if service.is_problem and not service.problem_has_been_acknowledged:
                    svc_synth['nb_problems'] += 1
                    if service.is_impact:
                        svc_synth['nb_impacts'] += 1
        else:
            svc_synth['nb_problems'] = \
                sum(1 for service in services if service.is_problem
                    and not service.problem_has_been_acknowledged)
            svc_synth['nb_impacts'] = \
                sum(1 for service in services if service.is_problem
                    and not service.problem_has_been_acknowledged and service.is_impact)
            svc_synth['nb_ack'] = \
                sum(1 for service in services if service.is_problem
                    and service.problem_has_been_acknowledged)

        svc_synth['pct_problems'] = round(100.0 * svc_synth['nb_problems'] / svc_synth['nb_elts'], 1)
        svc_synth['pct_ack'] = round(100.0 * svc_synth['nb_ack'] / svc_synth['nb_elts'], 1)
        svc_synth['nb_downtime'] = sum(1 for service in services if service.in_scheduled_downtime)
        svc_synth['pct_downtime'] = round(100.0 * svc_synth['nb_downtime'] / svc_synth['nb_elts'], 1)

        logger.debug("[datamanager] get_services_synthesis: %s", svc_synth)
        return svc_synth

    def get_important_services_synthesis(self, user=None):
        return self.get_services_synthesis(items=self.get_important_services(user))

    ##
    # Elements
    ##
    def get_element(self, name, user):
        """ Get an element by its name.
            :name: Must be "host" or "host/service"
        """
        if '/' in name:
            return self.get_service(name.split('/')[0], '/'.join(name.split('/')[1:]), user)

        host = self.get_host(name, user)
        if not host:
            return self.get_contact(name=name, user=user)

        return host

    ##
    # Searching
    ##
    def search_hosts_and_services(self, search, user, sorter=None, template=False):
        """ Search hosts and services.

            This method is the heart of the datamanager.
            All other methods are (almost...) based on this one.

            :search: Search string
            :user: concerned user
            :sorter: function to sort the items. default=None (means no sorting)
            :returns: list of hosts and services
        """
        # Make user an User object ... simple protection.
        # pylint: disable=invalid-name
        # Because unicode...
        if isinstance(user, str):
            user = self.regenerator.contacts.find_by_name(user)

        # todo: perhaps we should avoid building these lists for each search?
        items = []
        items.extend(self._only_related_to(self.regenerator.hosts, user))
        items.extend(self._only_related_to(self.regenerator.services, user))
        logger.debug("[datamanager] search_hosts_and_services, search for %s in %d items",
                     search, len(items))

        templates = []
        templates.extend(self._only_related_to(self.regenerator.hosts.templates.values(), user))
        templates.extend(self._only_related_to(self.regenerator.services.templates.values(), user))
        logger.debug("[datamanager] search_hosts_and_services, search for %s in %d templates",
                     search, len(templates))

        # Search patterns like: isnot:0 isnot:ack isnot:"downtime fred" name "vm fred"
        regex = re.compile(
            r'''
                                    # 1/ Search a key:value pattern.
                (?P<key>\w+):       # Key consists of only a word followed by a colon
                (?P<quote2>["']?)   # Optional quote character.
                (?P<value>.*?)      # Value is a non greedy match
                (?P=quote2)         # Closing quote equals the first.
                ($|\s)              # Entry ends with whitespace or end of string
                |                   # OR
                                    # 2/ Search a single string quoted or not
                (?P<quote>["']?)    # Optional quote character.
                (?P<name>.*?)       # Name is a non greedy match
                (?P=quote)          # Closing quote equals the opening one.
                ($|\s)              # Entry ends with whitespace or end of string
            ''',
            re.VERBOSE)

        # Replace "NOT foo" by "^((?!foo).)*$" to ignore foo
        search = re.sub(r'NOT ([^\ ]*)', r'^((?!\1).)*$', search)
        search = re.sub(r'not ([^\ ]*)', r'^((?!\1).)*$', search)

        patterns = []
        for match in regex.finditer(search):
            if match.group('name'):
                patterns.append(('name', match.group('name')))
            elif match.group('key'):
                patterns.append((match.group('key'), match.group('value')))
        logger.debug("[datamanager] search patterns: %s", patterns)

        for t, s in patterns:
            t = t.lower()
            logger.debug("[datamanager] searching for %s %s", t, s)

            if t == 'name':
                # Case insensitive
                pat = re.compile(s, re.IGNORECASE)
                new_items = []
                for i in items:
                    if (pat.search(i.get_full_name())
                            or (i.__class__.my_type == 'host' and i.alias and pat.search(i.alias))):
                        new_items.append(i)
                    else:
                        for j in i.impacts + i.source_problems:
                            if (pat.search(j.get_full_name())
                                    or (j.__class__.my_type == 'host'
                                        and j.alias and pat.search(j.alias))):
                                new_items.append(i)

                if not new_items:
                    for i in templates:
                        if pat.search(i.get_full_name()):
                            new_items.append(i)
                    for i in items:
                        if pat.search(i.output):
                            new_items.append(i)
                        else:
                            for j in i.impacts + i.source_problems:
                                if pat.search(j.output):
                                    new_items.append(i)

                items = new_items

            if (t in ['h', 'host']) and s.lower() != 'all':
                logger.debug("[datamanager] searching for an host %s", s)
                if template:
                    logger.debug("[datamanager] searching for an host template %s", s)
                # Case sensitive
                pat = re.compile(s)
                new_items = []
                for i in templates if template else items:
                    if i.__class__.my_type == 'host' and pat.search(i.get_name()):
                        new_items.append(i)
                    if i.__class__.my_type == 'service' and pat.search(i.get_host_name()):
                        new_items.append(i)

                items = new_items
                # Too verbose
                # logger.debug("[datamanager] host:%s, %d matching items", s, len(items))
                # for item in items:
                #     logger.debug("[datamanager] item %s is %s", item.get_name(), item.__class__)

            if (t in ['s', 'service']) and s.lower() != 'all':
                logger.debug("[datamanager] searching for a service %s", s)
                if template:
                    logger.debug("[datamanager] searching for a service template %s", s)
                pat = re.compile(s)
                new_items = []
                for i in items:
                    if i.__class__.my_type == 'service' and pat.search(i.get_name()):
                        new_items.append(i)

                items = new_items
                # Too verbose
                # logger.debug("[datamanager] service:%s, %d matching items", s, len(items))
                # for item in items:
                #     logger.debug("[datamanager] item %s is %s", item.get_name(), item.__class__)

            if (t in ['c', 'contact']) and s.lower() != 'all':
                logger.debug("[datamanager] searching for a contact %s", s)
                pat = re.compile(s)
                new_items = []
                for i in items:
                    if i.__class__.my_type == 'contact' and pat.search(i.get_name()):
                        new_items.append(i)
                    if i.__class__.my_type == 'host':
                        # :TODO:maethor:171012:
                        pass
                    if i.__class__.my_type == 'service':
                        # :TODO:maethor:171012:
                        pass

                items = new_items

            if (t in ['hg', 'hgroup', 'hostgroup']) and s.lower() != 'all':
                logger.debug("[datamanager] searching for items in the hostgroup %s", s)
                group = self.get_hostgroup(s)
                if group:
                    logger.debug("[datamanager] found the group: %s", group.get_name())
                    # This filters items that are related with the hostgroup only
                    # if the item has an hostgroups property
                    items = [i for i in items if getattr(i, 'get_hostgroups') and
                             group.get_name() in [g.get_name() for g in i.get_hostgroups()]]

            if (t in ['sg', 'sgroup', 'servicegroup']) and s.lower() != 'all':
                logger.debug("[datamanager] searching for items in the servicegroup %s", s)
                group = self.get_servicegroup(s)
                if group:
                    logger.debug("[datamanager] found the group: %s", group.get_name())
                    # Only the items that have a servicegroups property
                    items = [i for i in items if getattr(i, 'servicegroups') and
                             group.get_name() in [g.get_name() for g in i.servicegroups]]

            if (t in ['cg', 'cgroup', 'contactgroup']) and s.lower() != 'all':
                logger.debug("[datamanager] searching for items related with the contactgroup %s",
                             s)
                group = self.get_contactgroup(s, user)
                if group:
                    logger.debug("[datamanager] found the group: %s", group.get_name())

                    contacts = [c for c in self.get_contacts(user=user) if c in group.members]
                    logger.info("[datamanager] contacts: %s", contacts)

                    items = itertools.chain(*[
                        self._only_related_to(items, self.regenerator.contacts.find_by_name(c))
                        for c in contacts])
                    items = list(set(items))

            if t == 'realm':
                r = self.get_realm(s)
                if r:
                    items = [i for i in items if i.get_realm() == r]

            if t == 'htag' and s.lower() != 'all':
                items = [i for i in items if s in i.tags]

            if t == 'stag' and s.lower() != 'all':
                items = [i for i in items if s in i.tags]

            if t == 'ctag' and s.lower() != 'all':
                contacts = [c for c in self.get_contacts(user=user) if s in c.tags]
                items = itertools.chain(*[self._only_related_to(items, c) for c in contacts])
                items = list(set(items))

            if t == 'type' and s.lower() != 'all':
                items = [i for i in items if i.__class__.my_type == s]
                logger.debug("[datamanager] type:%s, %d matching items", s, len(items))
                for item in items:
                    logger.debug("[datamanager] item %s is %s", item.get_name(), item.__class__)

            if t in ['bp', 'bi']:
                try:
                    if s.startswith('>='):
                        items = [i for i in items if i.business_impact >= int(s[2:])]
                    elif s.startswith('<='):
                        items = [i for i in items if i.business_impact <= int(s[2:])]
                    elif s.startswith('>'):
                        items = [i for i in items if i.business_impact > int(s[1:])]
                    elif s.startswith('<'):
                        items = [i for i in items if i.business_impact < int(s[1:])]
                    else:
                        if s.startswith('='):
                            s = s[1:]
                        items = [i for i in items if i.business_impact == int(s)]
                except ValueError:
                    items = []

            if t in ['duration', 'last_check']:
                seconds_per_unit = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
                if t == 'duration':
                    times = [(i, time.time() - int(i.last_state_change)) for i in items]
                else:
                    times = [(i, time.time() - int(i.last_chk)) for i in items]
                try:
                    if s.startswith('>='):
                        s = int(s[2:-1]) * seconds_per_unit[s[-1].lower()]
                        items = [i[0] for i in times if i[1] >= s]
                    elif s.startswith('<='):
                        s = int(s[2:-1]) * seconds_per_unit[s[-1].lower()]
                        items = [i[0] for i in times if i[1] <= s]
                    elif s.startswith('>'):
                        s = int(s[1:-1]) * seconds_per_unit[s[-1].lower()]
                        items = [i[0] for i in times if i[1] > s]
                    elif s.startswith('<'):
                        s = int(s[1:-1]) * seconds_per_unit[s[-1].lower()]
                        items = [i[0] for i in times if i[1] < s]
                    else:
                        items = []
                except Exception:  # pylint: disable=broad-except
                    items = []

            if t == 'is':
                if s.lower() == 'ack':
                    items = [i for i in items if i.__class__.my_type == 'service'
                             or i.problem_has_been_acknowledged]
                    items = [i for i in items if i.__class__.my_type == 'host'
                             or (i.problem_has_been_acknowledged
                                 or i.host.problem_has_been_acknowledged)]
                elif s.lower() == 'downtime':
                    items = [i for i in items if i.__class__.my_type == 'service'
                             or i.in_scheduled_downtime]
                    items = [i for i in items if i.__class__.my_type == 'host'
                             or (i.in_scheduled_downtime or i.host.in_scheduled_downtime)]
                elif s.lower() == 'impact':
                    items = [i for i in items if i.is_impact]
                elif s.lower() == 'flapping':
                    items = [i for i in items if i.is_flapping]
                elif s.lower() == 'soft':
                    items = [i for i in items if i.state_type != 'HARD']
                elif s.lower() == 'hard':
                    items = [i for i in items if i.state_type == 'HARD']
                else:
                    # Manage SOFT & HARD state
                    # :COMMENT:maethor:171006: Kept for retrocompatility
                    if s.startswith('s'):
                        s = s[1:]
                        if len(s) == 1:
                            items = [i for i in items if i.state_id == int(s)
                                     and i.state_type != 'HARD']
                        else:
                            items = [i for i in items if i.state == s.upper()
                                     and i.state_type != 'HARD']
                    elif s.startswith('h'):
                        s = s[1:]
                        if len(s) == 1:
                            items = [i for i in items if i.state_id != int(s)
                                     and i.state_type == 'HARD']
                        else:
                            items = [i for i in items if i.state != s.upper()
                                     and i.state_type == 'HARD']
                    else:
                        if len(s) == 1:
                            items = [i for i in items if i.state_id == int(s)]
                        else:
                            items = [i for i in items if i.state == s.upper()]

            if t == 'isnot':
                if s.lower() == 'ack':
                    items = [i for i in items if i.__class__.my_type == 'service'
                             or not i.problem_has_been_acknowledged]
                    items = [i for i in items if i.__class__.my_type == 'host'
                             or (not i.problem_has_been_acknowledged
                                 and not i.host.problem_has_been_acknowledged)]
                elif s.lower() == 'downtime':
                    items = [i for i in items if i.__class__.my_type == 'service'
                             or not i.in_scheduled_downtime]
                    items = [i for i in items if i.__class__.my_type == 'host'
                             or (not i.in_scheduled_downtime
                                 and not i.host.in_scheduled_downtime)]
                elif s.lower() == 'impact':
                    items = [i for i in items if not i.is_impact]
                elif s.lower() == 'flapping':
                    items = [i for i in items if not i.is_flapping]
                elif s.lower() == 'soft':
                    items = [i for i in items if not i.state_type != 'HARD']
                elif s.lower() == 'hard':
                    items = [i for i in items if not i.state_type == 'HARD']
                else:
                    # Manage soft & hard state
                    if s.startswith('s'):
                        s = s[1:]
                        if len(s) == 1:
                            items = [i for i in items if i.state_id != int(s)
                                     and i.state_type != 'HARD']
                        else:
                            items = [i for i in items if i.state != s.upper()
                                     and i.state_type != 'HARD']
                    elif s.startswith('h'):
                        s = s[1:]
                        if len(s) == 1:
                            items = [i for i in items if i.state_id != int(s)
                                     and i.state_type == 'HARD']
                        else:
                            items = [i for i in items if i.state != s.upper()
                                     and i.state_type == 'HARD']
                    else:
                        if len(s) == 1:
                            items = [i for i in items if i.state_id != int(s)]
                        else:
                            items = [i for i in items if i.state != s.upper()]

            # :COMMENT:maethor:150616: Legacy filters, kept for bookmarks compatibility
            if t == 'ack':
                if s.lower() == 'false' or s.lower() == 'no':
                    patterns.append(("isnot", "ack"))
                if s.lower() == 'true' or s.lower() == 'yes':
                    patterns.append(("is", "ack"))
            if t == 'downtime':
                if s.lower() == 'false' or s.lower() == 'no':
                    patterns.append(("isnot", "downtime"))
                if s.lower() == 'true' or s.lower() == 'yes':
                    patterns.append(("is", "downtime"))
            if t == 'crit':
                patterns.append(("is", "critical"))

        if sorter is not None:
            items.sort(sorter)

        logger.debug("[datamanager] search_hosts_and_services, found %d matching items", len(items))

        logger.debug("[datamanager] ----------------------------------------")
        for item in items:
            logger.debug("[datamanager] item %s is %s", item.get_name(), item.__class__)
        logger.debug("[datamanager] ----------------------------------------")

        return items

    ##
    # Time periods
    ##
    def get_timeperiods(self, user=None, name=None):
        """ Get a list of known time periods

            :param user: concerned user
            :param name: only this element
            :returns: List of elements related to the user
        """
        logger.debug("[datamanager] get_timeperiods, name: %s, user: %s", name, user)
        items = self.regenerator.timeperiods
        logger.debug("[datamanager] got %d timeperiods", len(items))

        if name:
            return items.find_by_name(name)

        return self._only_related_to(items, user)

    def get_timeperiod(self, name):
        return self.get_timeperiods(name=name)

    ##
    # Commands
    ##
    def get_commands(self, user=None, name=None):
        """ Get a list of known commands

            :param user: concerned user
            :param name: only this element
            :returns: List of elements related to the user
        """
        logger.debug("[datamanager] get_commands, name: %s, user: %s", name, user)
        items = self.regenerator.commands
        logger.debug("[datamanager] got %d commands", len(items))

        if name:
            return items.find_by_name(name)

        return self._only_related_to(items, user)

    def get_command(self, name):
        return self.get_commands(name=name)

    ##
    # Contacts
    ##
    def get_contacts(self, user=None, name=None, template=False):
        """ Get a list of known contacts

            :param user: concerned user
            :param name: only this element
            :param template: True to get a template rather than a real object
            :returns: List of elements related to the user
        """
        logger.debug("[datamanager] get_contacts, name: %s", name)
        items = self.regenerator.contacts
        logger.debug("[datamanager] got %d contacts", len(items))

        if name:
            return items.find_by_name(name, template=template)

        return self._only_related_to(items, user)

    def get_contact(self, name=None, user=None, template=False):
        logger.debug("[datamanager] get_contact, name: %s, user: %s", name, user)

        return self.get_contacts(user=user, name=name, template=template)

    ##
    # Contacts groups
    ##
    def set_contactgroups_level(self, user):
        # All known contactgroups are level 0 groups ...
        for group in self.get_contactgroups(user=user):
            logger.debug("[datamanager] set_contactgroups_level, group: %s", group)
            if not hasattr(group, 'level'):
                self.set_contactgroup_level(group, 0, user)

    def set_contactgroup_level(self, group, level, user):
        logger.debug("[datamanager] set_contactgroup_level, group: %s, level: %d", group, level)
        setattr(group, 'level', level)

        for c_group in sorted(group.contactgroup_members):
            if not c_group:
                continue
            logger.debug("[datamanager] set_contactgroup_level, g: %s", c_group)
            try:
                child_group = self.get_contactgroup(c_group, user=user)
                self.set_contactgroup_level(child_group, level + 1, user)
            except AttributeError:
                pass

    def get_contactgroups(self, user=None, name=None, parent=None, members=False):
        """ Get a list of known contacts groups

            :param user: concerned user
            :param name: only this element
            :returns: List of elements related to the user
        """
        logger.debug("[datamanager] get_contactgroups, name: %s, members: %s", name, members)
        items = []
        if parent:
            group = self.get_contactgroups(user=user, name=parent)
            if group:
                items = [self.get_contactgroup(g) for g in group.contactgroup_members]
            else:
                return items
        else:
            items = self.regenerator.contactgroups
        logger.debug("[datamanager] got %d contactgroups", len(items))

        if name:
            return items.find_by_name(name)

        return self._only_related_to(items, user)

    def get_contactgroup(self, name, user=None, members=False):
        """ Get a specific contacts group

            :param name: searched contacts group name
            :param user: concerned user
            :returns: group which name matches else None
        """
        logger.debug("[datamanager] get_contactgroup, name: %s", name)

        return self._only_related_to(
            self.get_contactgroups(user=user, name=name, members=members), user)

    ##
    # Hosts groups
    ##
    def set_hostgroups_level(self, user):
        # All known hostgroups are level 0 groups ...
        for group in self.get_hostgroups(user=user):
            logger.debug("[datamanager] set_hostgroups_level, group: %s", group)
            if not hasattr(group, 'level'):
                self.set_hostgroup_level(group, 0, user)

    def set_hostgroup_level(self, group, level, user):
        setattr(group, 'level', level)
        logger.debug("[datamanager] set_hostgroup_level, group: %s, level: %d", group, level)

        for c_group in sorted(group.hostgroup_members, key=lambda g: g.hostgroup_name):
            if not c_group:
                continue
            logger.debug("[datamanager] set_hostgroup_level, g: %s", c_group.get_name())
            try:
                child_group = self.get_hostgroup(c_group.get_name(), user=user)
                self.set_hostgroup_level(child_group, level + 1, user)
            except AttributeError:
                pass

    def get_hostgroups(self, user=None, name=None, parent=None):
        """ Get a list of known hosts groups

            :param user: concerned user
            :param name: only this element
            :returns: List of elements related to the user
        """
        logger.debug("[datamanager] get_hostgroups, name: %s", name)
        items = []
        if parent:
            group = self.get_hostgroups(user=user, name=parent)
            if group:
                items = [self.get_hostgroup(g.get_name()) for g in group.hostgroup_members]
            else:
                return items
        else:
            items = self.regenerator.hostgroups
        logger.debug("[datamanager] got %d hostgroups", len(items))

        if name:
            return items.find_by_name(name)

        return self._only_related_to(items, user)

    def get_hostgroup(self, name, user=None):
        """ Get a specific hosts group

            :param name: searched hosts group name
            :param user: concerned user
            :returns: group which name matches else None
        """
        return self._is_related_to(self.get_hostgroups(user=user, name=name), user)

    ##
    # Services groups
    ##
    def set_servicegroups_level(self, user):
        # All known hostgroups are level 0 groups ...
        for group in self.get_servicegroups(user=user):
            if not hasattr(group, 'level'):
                self.set_servicegroup_level(group, 0, user)

    def set_servicegroup_level(self, group, level, user):
        setattr(group, 'level', level)

        for c_group in sorted(group.servicegroup_members):
            if not c_group:
                continue
            logger.debug("[datamanager] set_servicegroup_level, g: %s", c_group.get_name())
            try:
                child_group = self.get_servicegroup(c_group.get_name(), user=user)
                self.set_servicegroup_level(child_group, level + 1, user)
            except AttributeError:
                pass

    def get_servicegroups(self, user=None, name=None, parent=None):
        """ Get a list of known services groups

            :param user: concerned user
            :param name: only this element
            :param parent: only the sub groups of this group
            :returns: List of elements related to the user
        """
        logger.debug("[datamanager] get_servicegroups, name: %s", user)
        items = []
        if parent:
            group = self.get_servicegroups(user=user, name=parent)
            if group:
                items = [self.get_servicegroup(g) for g in group.servicegroup_members]
            else:
                return items
        else:
            items = self.regenerator.servicegroups
        logger.debug("[datamanager] got %d servicegroups", len(items))

        if name:
            return items.find_by_name(name)

        return self._only_related_to(items, user)

    def get_servicegroup(self, name, user=None):
        """ Get a specific hosts group

            :param name: searched hosts group name
            :param user: concerned user
            :returns: group which name matches else None
        """
        return self._is_related_to(
            self.get_servicegroups(user=user, name=name), user)

    ##
    # Hosts tags
    ##
    def get_host_tags(self):
        """ Get the hosts tags sorted by names. """
        logger.debug("[datamanager] get_host_tags")
        items = []
        names = list(self.regenerator.tags.keys())

        names.sort()
        for name in names:
            items.append((name, self.regenerator.tags[name]))

        logger.debug("[datamanager] got %d hosts tags", len(items))
        return items

    def get_hosts_tagged_with(self, tag, user):
        """ Get the hosts tagged with a specific tag. """
        return self.search_hosts_and_services('type:host htag:%s' % tag, user)

    ##
    # Services tags
    ##
    def get_service_tags(self):
        """ Get the services tags sorted by names. """
        items = []
        names = list(self.regenerator.services_tags.keys())

        names.sort()
        for name in names:
            items.append((name, self.regenerator.services_tags[name]))

        logger.debug("[datamanager] got %d services tags", len(items))
        return items

    def get_services_tagged_with(self, tag, user):
        """ Get the services tagged with a specific tag. """
        return self.search_hosts_and_services('type:service stag:%s' % tag, user)

    ##
    # Realms
    ##
    def get_realms(self, user=None, name=None):
        if name:
            if name in self.regenerator.realms:
                return name
            return None

        return self._only_related_to(self.regenerator.realms, user)

    def get_realm(self, name, user=None):
        return self._is_related_to(self.get_realms(user=user, name=name), user)

    ##
    # Shinken/Alignak program and daemons
    ##
    def get_configs(self):
        """Return the scheduler configurations received during the initialisation phase"""
        return list(self.regenerator.configs.values())

    def get_configuration_parameter(self, parameter):
        """Search for the required configuration parameter in the received scheduler
        configurations
        Returns None if the parameter is not found or no configuration yet received
        """
        configs = self.get_configs()
        if configs:
            config = configs[0]
            if '_config' in config:
                return config['_config'].get(parameter, None)

            return config.get(parameter, None)

        return None

    def get_framework_status(self):
        """Return a status for the underlying monitoring framework

        If all daemons are seen as alive, the status is 0 (Ok)
        If one daemon is not alive, the status is 2 (Critical)
        Else, if some connection attempts occured, the status is 1 (Warning)"""
        daemons = [
            ('scheduler', self.regenerator.schedulers),
            ('poller', self.regenerator.pollers),
            ('broker', self.regenerator.brokers),
            ('reactionner', self.regenerator.reactionners),
            ('receiver', self.regenerator.receivers)
        ]
        present = sum(1 for (_, satellites) in daemons if satellites)
        if not present:
            return None

        status = 0
        for (_, satellites) in daemons:
            for satellite in satellites:
                if not satellite.alive:
                    status = 2
                else:
                    if satellite.attempt:
                        status = 1

        return status

    def get_schedulers(self):
        return self.regenerator.schedulers

    def get_pollers(self):
        return self.regenerator.pollers

    def get_brokers(self):
        return self.regenerator.brokers

    def get_receivers(self):
        return self.regenerator.receivers

    def get_reactionners(self):
        return self.regenerator.reactionners

    ##
    # Shortcuts
    ##
    def get_overall_state(self, user):
        """ Get the worst state of all business impacting elements. """
        # :TODO:maethor:190103: Could be moved into dashboard
        impacts = self.search_hosts_and_services('isnot:ACK isnot:DOWNTIME is:impact', user)
        return impacts[0].state_id if impacts else 0

    def get_overall_it_state(self, user):
        """ Get the worst state of IT problems. """
        # :TODO:maethor:190103: Could be moved into dashboard
        hosts = self.search_hosts_and_services(
            'type:host isnot:ACK isnot:DOWNTIME isnot:impact', user)
        services = self.search_hosts_and_services(
            'type:service isnot:ACK isnot:DOWNTIME isnot:impact', user)
        hosts_state = hosts[0].state_id if hosts else 0
        services_state = services[0].state_id if services else 0
        return hosts_state, services_state

    def guess_root_problems(self, user, obj):
        """ Returns the root problems for a service. """
        if obj.__class__.my_type != 'service':
            return []

        items = obj.host.services
        return [s for s in self._only_related_to(items, user) if s.state_id != 0 and s != obj]

    # Return a tree of {'elt': Host, 'fathers': [{}, {}]}
    def get_business_parents(self, user, obj, levels=3):
        res = {'node': obj, 'fathers': []}
        # if levels == 0:
        #     return res

        for i in obj.parent_dependencies:
            # We want to get the levels deep for all elements, but
            # go as far as we should for bad elements
            if levels != 0 or i.state_id != 0:
                par_elts = self.get_business_parents(user, i, levels=levels - 1)
                res['fathers'].append(par_elts)

        return res
