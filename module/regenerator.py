#!/usr/bin/python
# -*- coding: utf-8 -*-

# pylint:disable=too-many-public-methods, too-many-branches, too-many-statements,
# pylint:disable=too-many-nested-blocks, too-many-locals, too-many-lines,
# pylint:disable=too-many-instance-attributes

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

"""
This file is copied and updated from the Shinken Regenerator

The regenerator is used to build standard objects from the broks raised by the
Broker. This version is made to re-build Shiknen objects from the broks raised
by an Alignak broker.

Some small modifications introduced by Alignak are managed in this class.
"""
import os
import time
import uuid
import traceback

# pylint: disable=invalid-name
ALIGNAK = os.environ.get('ALIGNAK_DAEMON', None) is not None
if ALIGNAK:
    # Specific logger configuration
    import logging
    from alignak.log import ALIGNAK_LOGGER_NAME
    logger = logging.getLogger(ALIGNAK_LOGGER_NAME + ".webui")

    from alignak.message import Message

    # Import all objects we will need
    from alignak.objects.item import Items
    from alignak.objects.host import Host, Hosts
    from alignak.objects.hostgroup import Hostgroup, Hostgroups
    from alignak.objects.service import Service, Services
    from alignak.objects.servicegroup import Servicegroup, Servicegroups
    from alignak.objects.contact import Contact, Contacts
    from alignak.objects.contactgroup import Contactgroup, Contactgroups
    from alignak.objects.notificationway import NotificationWay, NotificationWays
    # from alignak.objects.realm import Realm, Realms
    from alignak.objects.timeperiod import Timeperiod, Timeperiods
    from alignak.daterange import Timerange
    from alignak.objects.command import Command, Commands
    from alignak.commandcall import CommandCall
    from alignak.objects.schedulerlink import SchedulerLink, SchedulerLinks
    from alignak.objects.reactionnerlink import ReactionnerLink, ReactionnerLinks
    from alignak.objects.pollerlink import PollerLink, PollerLinks
    from alignak.objects.brokerlink import BrokerLink, BrokerLinks
    from alignak.objects.receiverlink import ReceiverLink, ReceiverLinks
else:
    from shinken.log import logger

    from shinken.message import Message

    # Import all objects we will need
    from shinken.objects.item import Items
    from shinken.objects.host import Host, Hosts
    from shinken.objects.hostgroup import Hostgroup, Hostgroups
    from shinken.objects.service import Service, Services
    from shinken.objects.servicegroup import Servicegroup, Servicegroups
    from shinken.objects.contact import Contact, Contacts
    from shinken.objects.contactgroup import Contactgroup, Contactgroups
    from shinken.objects.notificationway import NotificationWay, NotificationWays
    from shinken.objects.timeperiod import Timeperiod, Timeperiods
    from shinken.daterange import Timerange
    from shinken.objects.command import Command, Commands
    from shinken.commandcall import CommandCall
    from shinken.objects.schedulerlink import SchedulerLink, SchedulerLinks
    from shinken.objects.reactionnerlink import ReactionnerLink, ReactionnerLinks
    from shinken.objects.pollerlink import PollerLink, PollerLinks
    from shinken.objects.brokerlink import BrokerLink, BrokerLinks
    from shinken.objects.receiverlink import ReceiverLink, ReceiverLinks


# Class for a Regenerator. It will get broks, and "regenerate" real objects
# from them :)
class Regenerator(object):
    def __init__(self):

        # Our Real datas
        self.configs = {}
        self.hosts = Hosts([])
        self.services = Services([])
        self.notificationways = NotificationWays([])
        self.contacts = Contacts([])
        self.hostgroups = Hostgroups([])
        self.servicegroups = Servicegroups([])
        self.contactgroups = Contactgroups([])
        self.timeperiods = Timeperiods([])
        self.commands = Commands([])
        # WebUI - Manage notification ways
        self.notificationways = NotificationWays([])
        self.schedulers = SchedulerLinks([])
        self.pollers = PollerLinks([])
        self.reactionners = ReactionnerLinks([])
        self.brokers = BrokerLinks([])
        self.receivers = ReceiverLinks([])
        # From now we only look for realms names
        self.realms = set()

        self.tags = {}
        self.services_tags = {}

        # And in progress one
        self.inp_hosts = {}
        self.inp_services = {}
        self.inp_hostgroups = {}
        self.inp_servicegroups = {}
        self.inp_contactgroups = {}

        # Not yet initialized at least once
        self.initialized = False

        # Do not ask for full data resent too much
        self.last_need_data_send = time.time()

        # Flag to say if our data came from the scheduler or not
        # (so if we skip *initial* broks)
        self.in_scheduler_mode = False

        # The Queue where to launch message, will be fill from the broker
        self.from_q = None

    def load_external_queue(self, from_q):
        """Load an external queue for sending messages"""
        self.from_q = from_q

    def load_from_scheduler(self, sched):
        """If we are called from a scheduler it self, we load the data from it

        Note that this is only when the WebUI is declared as a module of a scheduler.
        Never seen such a configuration!
        """
        # Ok, we are in a scheduler, so we will skip some useless steps
        self.in_scheduler_mode = True

        logger.warning("Using the WebUI as a module of a scheduler "
                       "is not recommended because not enough tested! "
                       "You should declare the WebUI as a module in your master broker.")

        # Go with the data creation/load
        configuration = sched.conf

        # Simulate a drop conf
        brok = sched.get_program_status_brok()
        brok.prepare()
        self.manage_program_status_brok(brok)

        # Now we will lie and directly map our objects :)
        logger.debug("Regenerator::load_from_scheduler")
        self.hosts = configuration.hosts
        self.services = configuration.services
        self.notificationways = configuration.notificationways
        self.contacts = configuration.contacts
        self.hostgroups = configuration.hostgroups
        self.servicegroups = configuration.servicegroups
        self.contactgroups = configuration.contactgroups
        self.timeperiods = configuration.timeperiods
        self.commands = configuration.commands
        # WebUI - Manage notification ways
        self.notificationways = configuration.notificationways

        # We also load the realms
        for host in self.hosts:
            # WebUI - Manage realms if declared (use realm_name, or realm or default 'All')
            self.realms.add(getattr(host, 'realm_name', getattr(host, 'realm', 'All')))
            # WebUI - be aware that the realm may be a string or an object
            # This will be managed later.

    def want_brok(self, brok):
        """If we are in a scheduler mode, some broks are dangerous,
        so we will skip them

        Note that this is only when the WebUI is declared as a module of a scheduler.
        Never seen such a configuration!
        """
        if self.in_scheduler_mode:
            return brok.type not in ['program_status',
                                     'initial_host_status', 'initial_hostgroup_status',
                                     'initial_service_status', 'initial_servicegroup_status',
                                     'initial_contact_status', 'initial_contactgroup_status',
                                     'initial_timeperiod_status', 'initial_command_status']

        # Not in don't want? so want! :)
        return True

    def manage_brok(self, brok):
        """ Look for a manager function for a brok, and call it """
        manage = getattr(self, 'manage_' + brok.type + '_brok', None)
        # WebUI - do not make a log because Shinken creates a brok per log!
        if not manage:
            return

        # WebUI - Shinken uses id as a brok identifier whereas Alignak uses uuid
        # the idea is to make every regenerated object have both identifiers. It
        # will make it easier to migrate from Shinken to Alignak objects.
        # This is because some broks contain objects and not only dictionaries!

        # Shinken uses id as a brok identifier
        if getattr(brok, 'id', None):
            brok.uuid = brok.id
        else:
            # whereas Alignak uses uuid!
            if getattr(brok, 'uuid', None):
                brok.id = brok.uuid

        # Same identifier logic for the brok contained data identifier
        if brok.data.get('id', None):
            brok.data['uuid'] = brok.data['id']
        else:
            if brok.data.get('uuid', None):
                brok.data['id'] = brok.data['uuid']

        # No id for the data contained in the brok, force set on identifier.
        if brok.data.get('id', None) is None:
            brok.data['uuid'] = str(uuid.uuid4())
            brok.data['id'] = brok.data['uuid']

        logger.debug("Got a brok: %s", brok.type)

        try:
            # Catch all the broks management exceptions to avoid breaking the module
            manage(brok)
        except Exception as exp:  # pylint: disable=broad-except
            logger.error("Exception on brok management: %s", str(exp))
            logger.error("Traceback: %s", traceback.format_exc())
            logger.error("Brok '%s': %s", brok.type, brok.data)

    # pylint: disable=no-self-use
    def update_element(self, element, data):
        for prop in data:
            setattr(element, prop, data[prop])

    def _update_realm(self, data):
        """Set and return the realm the daemon is attached to
        If no realm_name attribute exist, then use the realm attribute and
        set as default value All if it is empty
        """
        if 'realm_name' not in data:
            data['realm_name'] = data.get('realm', None) or 'All'

        # Update realms list
        self.realms.add(data['realm_name'])

    def _update_events(self, element):
        """Update downtimes and comments for an element
        """
        # WebUI - manage the different downtimes and comments structures
        # We need to rebuild Downtime and Comment relationship with their parent element
        if isinstance(element.downtimes, dict):
            element.downtimes = list(element.downtimes.values())
        for downtime in element.downtimes:
            downtime.ref = element
            if getattr(downtime, 'uuid', None) is not None:
                downtime.id = downtime.uuid

        if isinstance(element.comments, dict):
            element.comments = list(element.comments.values())
        for comment in element.comments:
            comment.ref = element
            if getattr(comment, 'uuid', None) is not None:
                comment.id = comment.uuid
            comment.persistent = True

    def all_done_linking(self, inst_id):
        """Now we get all data about an instance, link all this stuff :)"""

        # In a scheduler we are already "linked" so we can skip this
        if self.in_scheduler_mode:
            logger.debug("Regenerator: We skip the all_done_linking phase "
                         "because we are in a scheduler")
            return

        start = time.time()
        logger.info("Linking objects together for %s, starting...", inst_id)

        # check if the instance is really defined, so got ALL the
        # init phase
        if inst_id not in list(self.configs.keys()):
            logger.warning("Warning: the instance %d is not fully given, bailout", inst_id)
            return

        self.configs[inst_id]['_all_data_received'] = True

        # We consider the regenerator as initialized once a scheduler has finished to push its data!
        self.initialized = True

        # Try to load the in progress list and make them available for
        # finding
        try:
            inp_hosts = self.inp_hosts[inst_id]
            inp_hostgroups = self.inp_hostgroups[inst_id]
            inp_contactgroups = self.inp_contactgroups[inst_id]
            inp_services = self.inp_services[inst_id]
            inp_servicegroups = self.inp_servicegroups[inst_id]
        except Exception as exp:  # pylint: disable=broad-except
            logger.error("Warning all done: %s", str(exp))
            return

        # WebUI - the linkify order in this function is important because of
        # the relations that may exist between the objects. The order changed
        # because it was more logical to linkify timeperiods and contacts
        # stuff before hosts and services

        # WebUI - linkify timeperiods
        for tp in self.timeperiods:
            new_exclude = []
            for ex in tp.exclude:
                excluded_name = ex.timeperiod_name
                t = self.timeperiods.find_by_name(excluded_name)
                if t:
                    new_exclude.append(t)
                else:
                    logger.warning("Unknown TP %s for TP: %s", excluded_name, tp)
            tp.exclude = new_exclude

        # WebUI - linkify contacts groups with their contacts
        for cg in inp_contactgroups:
            logger.debug("Contacts group: %s", cg.get_name())
            new_members = []
            for (i, cname) in cg.members:
                c = self.contacts.find_by_name(cname)
                if c:
                    new_members.append(c)
                else:
                    logger.warning("Unknown contact %s for contactgroup: %s", cname, cg)
            cg.members = new_members

        # Merge contactgroups with real ones
        for group in inp_contactgroups:
            logger.debug("Update existing contacts group: %s", group.get_name())
            # If the contactgroup already exist, just add the new contacts into it
            cg = self.contactgroups.find_by_name(group.get_name())
            if cg:
                logger.debug("- update members: %s / %s", group.members, group.contactgroup_members)
                # Update contacts and contacts groups members
                cg.members = group.members
                cg.contactgroup_members = group.contactgroup_members
                # Copy group identifiers because they will have changed after a restart
                cg.id = group.id
                cg.uuid = group.uuid
            else:
                logger.debug("- add a group")
                self.contactgroups.add_item(group)

        # Merge contactgroups with real ones
        for group in self.contactgroups:
            # Link with the other groups
            new_groups = []
            for cgname in group.contactgroup_members:
                for cg in self.contactgroups:
                    if cgname == cg.get_name() or cgname == cg.uuid:
                        new_groups.append(cg)
                        logger.debug("Found contactgroup %s", cg.get_name())
                        break
                else:
                    logger.warning("No contactgroup %s for contactgroup: %s",
                                   cgname, group.get_name())
            group.contactgroup_members = new_groups
        for group in self.contactgroups:
            logger.debug("- members: %s / %s", group.members, group.contactgroup_members)

        # Linkify hosts groups with their hosts
        for hg in inp_hostgroups:
            logger.debug("Hosts group: %s", hg.get_name())
            new_members = []
            for (i, host_name) in hg.members:
                host = inp_hosts.find_by_name(host_name)
                if host:
                    new_members.append(host)
                else:
                    logger.warning("Unknown host %s for hostgroup: %s", host_name, hg.get_name())
            hg.members = new_members
            logger.debug("- group members: %s", hg.members)

        # Merge hosts groups with real ones
        for group in inp_hostgroups:
            logger.debug("Update existing hosts group: %s", group.get_name())
            # If the hostgroup already exist, just add the new members and groups into it
            hg = self.hostgroups.find_by_name(group.get_name())
            if hg:
                logger.debug("- update members: %s / %s", group.members, group.hostgroup_members)
                # Update hosts and hosts groups members
                hg.members = group.members
                hg.hostgroup_members = group.hostgroup_members
                # Copy group identifiers because they will have changed after a restart
                hg.id = group.id
                hg.uuid = group.uuid
            else:
                logger.debug("- add a group")
                self.hostgroups.add_item(group)

        # Merge hosts groups with real ones
        for group in self.hostgroups:
            # Link with the other groups
            new_groups = []
            for hgname in group.hostgroup_members:
                for hg in self.hostgroups:
                    if hgname == hg.get_name() or hgname == hg.uuid:
                        new_groups.append(hg)
                        logger.debug("Found hostgroup %s", hg.get_name())
                        break
                else:
                    logger.warning("No hostgroup %s for hostgroup: %s", hgname, group.get_name())
            group.hostgroup_members = new_groups
        for group in self.hostgroups:
            logger.debug("- members: %s / %s", group.members, group.hostgroup_members)

        # Manage hosts templates
        self.hosts.templates = {}
        for host in list(inp_hosts.templates.values()):
            logger.debug("Host template: %s", host)
            logger.debug("Host template: %s", host)

            # Now link Command() objects
            self.linkify_a_command(host, 'check_command')
            self.linkify_a_command(host, 'event_handler')
            self.linkify_a_command(host, 'snapshot_command')

            # Now link timeperiods
            self.linkify_a_timeperiod_by_name(host, 'notification_period')
            self.linkify_a_timeperiod_by_name(host, 'check_period')
            self.linkify_a_timeperiod_by_name(host, 'maintenance_period')
            self.linkify_a_timeperiod_by_name(host, 'snapshot_period')

            # And link contacts too
            self.linkify_contacts(host, 'contacts')
            logger.debug("Host template %s has contacts: %s", host.get_name(), host.contacts)

            # We can really declare this host template
            self.hosts.add_template(host)

        # Now link hosts with their hosts groups, commands and timeperiods
        for host in inp_hosts:
            if host.hostgroups:
                hgs = host.hostgroups
                if not isinstance(hgs, list):
                    hgs = host.hostgroups.split(',')
                new_groups = []
                logger.debug("Searching hostgroup for the host %s, hostgroups: %s",
                             host.get_name(), hgs)
                for hgname in hgs:
                    for group in self.hostgroups:
                        if hgname == group.get_name() or hgname == group.uuid:
                            new_groups.append(group)
                            logger.debug("Found hostgroup %s", group.get_name())
                            break
                    else:
                        logger.warning("No hostgroup %s for host: %s", hgname, host.get_name())
                host.hostgroups = new_groups
                logger.debug("Linked %s hostgroups %s", host.get_name(), host.hostgroups)

            # Now link Command() objects
            self.linkify_a_command(host, 'check_command')
            self.linkify_a_command(host, 'event_handler')
            self.linkify_a_command(host, 'snapshot_command')

            # Now link timeperiods
            self.linkify_a_timeperiod_by_name(host, 'notification_period')
            self.linkify_a_timeperiod_by_name(host, 'check_period')
            self.linkify_a_timeperiod_by_name(host, 'maintenance_period')
            self.linkify_a_timeperiod_by_name(host, 'snapshot_period')

            # And link contacts too
            self.linkify_contacts(host, 'contacts')
            logger.debug("Host %s has contacts: %s", host.get_name(), host.contacts)

            # Linkify tags
            for t in host.tags:
                if t not in self.tags:
                    self.tags[t] = 0
                self.tags[t] += 1

            # We can really declare this host OK now
            old_host = self.hosts.find_by_name(host.get_name())
            if old_host is not None:
                self.hosts.remove_item(old_host)
            self.hosts.add_item(host)

        # Linkify services groups with their services
        for group in inp_servicegroups:
            logger.debug("Services group: %s", group.get_name())
            new_members = []
            for (i, sname) in group.members:
                if i not in inp_services:
                    logger.warning("Unknown service %s for services group: %s", sname, group)
                else:
                    new_members.append(inp_services[i])

            group.members = new_members
            logger.debug("- group members: %s", group.members)

        # Merge services groups with real ones
        for service_group in inp_servicegroups:
            logger.debug("Update existing services group: %s", service_group.get_name())
            # If the services group already exist, just add the new services into it
            group = self.servicegroups.find_by_name(service_group.get_name())
            if group:
                logger.debug("- update members: %s / %s", group.members, group.servicegroup_members)
                # Update services and services groups members
                group.members = group.members
                group.servicegroup_members = group.servicegroup_members
                # Copy group identifiers because they will have changed after a restart
                group.id = group.id
                group.uuid = group.uuid
            else:
                logger.debug("- add a group")
                self.servicegroups.add_item(service_group)

        # Merge services groups with real ones
        for group in self.servicegroups:
            # Link with the other groups
            new_groups = []
            for sgname in group.servicegroup_members:
                for sg in self.servicegroups:
                    if sgname == sg.get_name() or sgname == sg.uuid:
                        new_groups.append(sg)
                        logger.debug("Found servicegroup %s", sg.get_name())
                        break
                else:
                    logger.warning("No servicegroup %s for servicegroup: %s",
                                   sgname, group.get_name())
            group.servicegroup_members = new_groups
        for group in self.servicegroups:
            logger.debug("- members: %s / %s", group.members, group.servicegroup_members)

        # Now link services with hosts, services groups, commands and time periods
        for service in inp_services:
            if service.servicegroups:
                sgs = service.servicegroups
                if not isinstance(sgs, list):
                    sgs = service.servicegroups.split(',')
                new_groups = []
                logger.debug("Searching servicegroup for the service %s, servicegroups: %s",
                             service.get_full_name(), sgs)
                for sgname in sgs:
                    for group in self.servicegroups:
                        if sgname == group.get_name() or sgname == group.uuid:
                            new_groups.append(group)
                            logger.debug("Found servicegroup %s", group.get_name())
                            break
                    else:
                        logger.warning("No servicegroup %s for service: %s",
                                       sgname, service.get_full_name())
                service.servicegroups = new_groups
                logger.debug("Linked %s servicegroups %s",
                             service.get_full_name(), service.servicegroups)

            # Now link with host
            service.host = self.hosts.find_by_name(service.host_name)
            if service.host:
                for host_service in service.host.services:
                    if getattr(host_service, 'service_description', None) == \
                            service.service_description:
                        service.host.services.remove(host_service)
                        break
                service.host.services.append(service)
            else:
                logger.warning("Service: %s, host not found: %s", service, service.host_name)

            # Now link Command() objects
            self.linkify_a_command(service, 'check_command')
            self.linkify_a_command(service, 'event_handler')
            self.linkify_a_command(service, 'snapshot_command')

            # Now link timeperiods
            self.linkify_a_timeperiod_by_name(service, 'notification_period')
            self.linkify_a_timeperiod_by_name(service, 'check_period')
            self.linkify_a_timeperiod_by_name(service, 'maintenance_period')
            self.linkify_a_timeperiod_by_name(service, 'snapshot_period')

            # And link contacts too
            self.linkify_contacts(service, 'contacts')
            logger.debug("Service %s has contacts: %s", service.get_full_name(), service.contacts)

            # Linkify services tags
            for t in service.tags:
                if t not in self.services_tags:
                    self.services_tags[t] = 0
                self.services_tags[t] += 1

            # We can really declare this service OK now
            self.services.add_item(service, index=True)

        # Manage services templates
        self.services.templates = {}
        for service in list(inp_services.templates.values()):
            logger.debug("Service template: %s", service)

            # Now link Command() objects
            self.linkify_a_command(service, 'check_command')
            self.linkify_a_command(service, 'event_handler')
            self.linkify_a_command(service, 'snapshot_command')

            # Now link timeperiods
            self.linkify_a_timeperiod_by_name(service, 'notification_period')
            self.linkify_a_timeperiod_by_name(service, 'check_period')
            self.linkify_a_timeperiod_by_name(service, 'maintenance_period')
            self.linkify_a_timeperiod_by_name(service, 'snapshot_period')

            # And link contacts too
            self.linkify_contacts(service, 'contacts')
            logger.debug("Service template %s has contacts: %s",
                         service.get_name(), service.contacts)

            # We can really declare this service template
            self.services.add_template(service)

        # Manage services templates
        self.services.templates = {}
        for service in list(inp_services.templates.values()):
            logger.debug("Service template: %s", service)

            # Now link Command() objects
            self.linkify_a_command(service, 'check_command')
            self.linkify_a_command(service, 'event_handler')
            self.linkify_a_command(service, 'snapshot_command')

            # Now link timeperiods
            self.linkify_a_timeperiod_by_name(service, 'notification_period')
            self.linkify_a_timeperiod_by_name(service, 'check_period')
            self.linkify_a_timeperiod_by_name(service, 'maintenance_period')
            self.linkify_a_timeperiod_by_name(service, 'snapshot_period')

            # And link contacts too
            self.linkify_contacts(service, 'contacts')
            logger.debug("Service template %s has contacts: %s",
                         service.get_name(), service.contacts)

            # We can really declare this service template
            self.services.add_template(service)

        # Add realm of the hosts
        for host in inp_hosts:
            # WebUI - Manage realms if declared (Alignak)
            if getattr(host, 'realm_name', None):
                self.realms.add(host.realm_name)
            else:
                # WebUI - Manage realms if declared (Shinken)
                if getattr(host, 'realm', None):
                    self.realms.add(host.realm)

        # Now we can link all impacts/source problem list
        # but only for the new ones here of course
        for host in inp_hosts:
            self.linkify_dict_srv_and_hosts(host, 'impacts')
            self.linkify_dict_srv_and_hosts(host, 'source_problems')
            # todo: refactor this part for Alignak - to be tested.
            # self.linkify_host_and_hosts(h, 'parent_dependencies')
            # self.linkify_host_and_hosts(h, 'child_dependencies')
            self.linkify_host_and_hosts(host, 'parents')
            self.linkify_dict_srv_and_hosts(host, 'parent_dependencies')
            self.linkify_dict_srv_and_hosts(host, 'child_dependencies')

        # Now services too
        for service in inp_services:
            self.linkify_dict_srv_and_hosts(service, 'impacts')
            self.linkify_dict_srv_and_hosts(service, 'source_problems')
            # todo: refactor this part for Alignak - to be tested.
            # self.linkify_service_and_services(s, 'parent_dependencies')
            # self.linkify_service_and_services(s, 'child_dependencies')
            self.linkify_dict_srv_and_hosts(service, 'parent_dependencies')
            self.linkify_dict_srv_and_hosts(service, 'child_dependencies')

        # clean old objects
        del self.inp_hosts[inst_id]
        del self.inp_hostgroups[inst_id]
        del self.inp_contactgroups[inst_id]
        del self.inp_services[inst_id]
        del self.inp_servicegroups[inst_id]

        for item_type in ['timeperiod', 'command', 'contact', 'host', 'service',
                          'contactgroup', 'hostgroup', 'servicegroup']:
            items = getattr(self, "%ss" % item_type, [])
            if not items:
                logger.info("Got no %ss", item_type)
                continue

            logger.info("Got %d %ss", len(items), item_type)
            if not isinstance(items, Items):
                continue
            for item in getattr(items, 'items'):
                logger.debug("- %s", item)
            if getattr(items, 'templates'):
                logger.info("Got %d %ss templates", len(getattr(items, 'templates')), item_type)
                for item in getattr(items, 'templates'):
                    logger.debug("- %s", item)

        logger.info("Linking objects together, end. Duration: %s", time.time() - start)

    def linkify_a_command(self, o, prop):
        """We look for o.prop (CommandCall) and we link the inner
        Command() object with our real ones"""
        logger.debug("Linkify a command: %s", prop)
        cc = getattr(o, prop, None)
        if not cc:
            setattr(o, prop, None)
            return

        # WebUI - the command may have different representation
        # (a simple name, an object or a simple identifier)
        cmd_name = cc
        if isinstance(cc, CommandCall):
            cmd_name = cc.command
        try:
            cc.command = self.commands.find_by_name(cmd_name)
            logger.debug("- %s = %s", prop, cc.command.get_name() if cc.command else 'None')
        except AttributeError:
            cc = self.commands.find_by_name(cmd_name)
            logger.debug("- %s = %s", prop, cc.get_name() if cc else 'None')

    def linkify_commands(self, o, prop):
        """We look at o.prop and for each command we relink it"""
        logger.debug("Linkify commands: %s", prop)
        v = getattr(o, prop, None)
        if not v:
            # If do not have a command list, put a void list instead
            setattr(o, prop, [])
            return

        for cc in v:
            # WebUI - the command must has different representation
            # (a simple name, an object or a simple identifier)
            cmdname = cc
            if hasattr(cc, 'command'):
                cmdname = cc.command
            if hasattr(cmdname, 'uuid') and cmdname.uuid in self.commands:
                cc.command = self.commands[cmdname.uuid]
            else:
                cc.command = self.commands.find_by_name(cmdname)
            logger.debug("- %s = %s", prop, cc.command.get_name() if cc.command else 'None')

    def linkify_a_timeperiod(self, o, prop):
        """We look at the timeperiod() object of o.property
        and we replace it with our true one"""
        t = getattr(o, prop, None)
        if not t:
            setattr(o, prop, None)
            return

        if isinstance(t, Timeperiod):
            logger.debug("- already linkified to an object")
            return

        logger.debug("Linkify a timeperiod: %s, found: %s", prop, type(t))
        logger.debug("Linkify a timeperiod: %s, found: %s", prop, t)
        for tp in self.timeperiods:
            if t == tp.get_name() or t == tp.uuid:
                setattr(o, prop, tp)
                break
        else:
            logger.warning("Timeperiod not linkified: %s / %s !", type(t), t)

    def linkify_a_timeperiod_by_name(self, o, prop):
        """same than before, but the value is a string here"""
        tpname = getattr(o, prop, None)
        if not tpname:
            setattr(o, prop, None)
            return

        tp = self.timeperiods.find_by_name(tpname)
        setattr(o, prop, tp)

    def linkify_contacts(self, o, prop):
        """We look at o.prop and for each contacts in it,
        we replace it with true object in self.contacts"""
        v = getattr(o, prop, None)
        if not v:
            return

        new_v = []
        for cname in v:
            c = self.contacts.find_by_name(cname)
            if c:
                new_v.append(c)
            else:
                # WebUI - search contact by id because we did not found by name
                for contact in self.contacts:
                    if cname == contact.uuid:
                        new_v.append(contact)
                        break

        setattr(o, prop, new_v)

    def linkify_dict_srv_and_hosts(self, item, prop):
        """We got a service/host dict, we want to get back to a flat list"""
        value = getattr(item, prop, None)
        if not value:
            setattr(item, prop, [])
            return

        logger.debug("Linkify Dict Srv/Host for %s - %s = %s", item.get_full_name(), prop, value)
        new_v = []
        if 'hosts' not in value or 'services' not in value:
            # WebUI - Alignak do not use the same structure as Shinken
            for item_id in value:
                for host in self.hosts:
                    if item_id == host.id:
                        new_v.append(host)
                        break
                else:
                    for service in self.services:
                        if item_id == service.id:
                            new_v.append(service)
                            break
        else:
            # WebUI - plain old Shinken structure
            for name in value['services']:
                elts = name.split('/')
                host_name = elts[0]
                service_description = elts[1]
                service = self.services.find_srv_by_name_and_hostname(host_name,
                                                                      service_description)
                if service:
                    new_v.append(service)
            for host_name in value['hosts']:
                host = self.hosts.find_by_name(host_name)
                if host:
                    new_v.append(host)
        setattr(item, prop, new_v)

    def linkify_host_and_hosts(self, item, prop):
        value = getattr(item, prop)
        if not value:
            setattr(item, prop, [])
            return

        logger.debug("Linkify host>hosts for %s - %s = %s", item.get_name(), prop, value)
        new_v = []
        for host_name in value:
            host = self.hosts.find_by_name(host_name)
            if host:
                new_v.append(host)
            else:
                # WebUI - we did not found by name, let's try with an identifier
                for host in self.hosts:
                    if host_name == host.uuid:
                        new_v.append(host)
                        break

        setattr(item, prop, new_v)

    def linkify_service_and_services(self, item, prop):
        """TODO confirm this function is useful !"""
        value = getattr(item, prop)
        if not value:
            setattr(item, prop, [])
            return

        logger.debug("Linkify service>services for %s - %s = %s", item.get_name(), prop, value)
        new_v = []
        for service_id in value:
            service = self.services.find_by_name(service_id)
            if service:
                new_v.append(service)
            else:
                for service in self.services:
                    if service_id == service.uuid:
                        new_v.append(service)
                        break

        setattr(item, prop, new_v)

###############
# Brok management part
###############

    def before_after_hook(self, brok, obj):
        """
        This can be used by derived classes to compare the data in the brok
        with the object which will be updated by these data. For example,
        it is possible to find out in this method whether the state of a
        host or service has changed.
        """

#######
# INITIAL PART
#######

    def manage_program_status_brok(self, b):
        """A scheduler provides its initial status

        Shinken brok contains:
        data = {"is_running": 1,
                "instance_id": self.instance_id,
                "instance_name": self.instance_name,
                "last_alive": now,
                "interval_length": self.conf.interval_length,
                "program_start": self.program_start,
                "pid": os.getpid(),
                "daemon_mode": 1,
                "last_command_check": now,
                "last_log_rotation": now,
                "notifications_enabled": self.conf.enable_notifications,
                "active_service_checks_enabled": self.conf.execute_service_checks,
                "passive_service_checks_enabled": self.conf.accept_passive_service_checks,
                "active_host_checks_enabled": self.conf.execute_host_checks,
                "passive_host_checks_enabled": self.conf.accept_passive_host_checks,
                "event_handlers_enabled": self.conf.enable_event_handlers,
                "flap_detection_enabled": self.conf.enable_flap_detection,
                "failure_prediction_enabled": 0,
                "process_performance_data": self.conf.process_performance_data,
                "obsess_over_hosts": self.conf.obsess_over_hosts,
                "obsess_over_services": self.conf.obsess_over_services,
                "modified_host_attributes": 0,
                "modified_service_attributes": 0,
                "global_host_event_handler": self.conf.global_host_event_handler,
                'global_service_event_handler': self.conf.global_service_event_handler,
                'check_external_commands': self.conf.check_external_commands,
                'check_service_freshness': self.conf.check_service_freshness,
                'check_host_freshness': self.conf.check_host_freshness,
                'command_file': self.conf.command_file
                }
        Note that some parameters values are hard-coded and useless ... and some configuration
        parameters are missing!

        Alignak brok contains many more information:
        _config: all the more interesting configuration parameters
        are pushed in the program status brok sent by each scheduler.
        At minimum, the UI will receive all the framework configuration parameters.
        _running: all the running scheduler information: checks count, results, live synthesis
        _macros: the configure Alignak macros and their value

        """
        data = b.data
        c_id = data['instance_id']
        c_name = data.get('instance_name', c_id)
        logger.info("Got a configuration from %s", c_name)
        logger.debug("Data: %s", data)

        now = time.time()
        if c_id in self.configs:
            # It may happen that the same scheduler sends several times its initial status brok.
            # Let's manage this and only consider one brok per minute!
            # We already have a configuration for this scheduler instance
            if now - self.configs[c_id]['_timestamp'] < 60:
                logger.info("Got near initial program status for %s. Ignoring this information.",
                            c_name)
                return

        # Clean all in_progress things.
        # And in progress one
        self.inp_hosts[c_id] = Hosts([])
        self.inp_services[c_id] = Services([])
        self.inp_hostgroups[c_id] = Hostgroups([])
        self.inp_servicegroups[c_id] = Servicegroups([])
        self.inp_contactgroups[c_id] = Contactgroups([])

        # And we save the data in the configurations
        data['_timestamp'] = now
        data['_all_data_received'] = False

        # Shinken renames some "standard" parameters, restore the common name...
        if 'notifications_enabled' in data:
            data['enable_notifications'] = data.pop('notifications_enabled')
        if 'event_handlers_enabled' in data:
            data['enable_event_handlers'] = data.pop('event_handlers_enabled')
        if 'flap_detection_enabled' in data:
            data['enable_flap_detection'] = data.pop('flap_detection_enabled')
        if 'active_service_checks_enabled' in data:
            data['execute_service_checks'] = data.pop('active_service_checks_enabled')
        if 'active_host_checks_enabled' in data:
            data['execute_host_checks'] = data.pop('active_host_checks_enabled')
        if 'passive_service_checks_enabled' in data:
            data['accept_passive_service_checks'] = data.pop('passive_service_checks_enabled')
        if 'passive_host_checks_enabled' in data:
            data['accept_passive_host_checks'] = data.pop('passive_host_checks_enabled')

        self.configs[c_id] = data

        # We should clean all previously added hosts and services
        logger.info("Cleaning hosts/service of %s", c_name)
        to_del_hosts = [h for h in self.hosts if h.instance_id == c_id]
        to_del_srv = [s for s in self.services if s.instance_id == c_id]

        if to_del_hosts:
            # Clean hosts from hosts and hostgroups
            logger.info("Cleaning %d hosts", len(to_del_hosts))

            for host in to_del_hosts:
                self.hosts.remove_item(host)

            # Exclude from all hostgroups members the hosts of this scheduler instance
            for hostgroup in self.hostgroups:
                logger.debug("Cleaning hostgroup %s: %d members",
                             hostgroup.get_name(), len(hostgroup.members))
                try:
                    # hg.members = [h for h in hg.members if host.instance_id != c_id]
                    hostgroup.members = []
                    for host in hostgroup.members:
                        if host.instance_id != c_id:
                            hostgroup.members.append(host)
                        else:
                            logger.debug("- removing host: %s", host)
                except Exception as exp:  # pylint: disable=broad-except
                    logger.error("Exception when cleaning hostgroup: %s", str(exp))

                logger.debug("hostgroup members count after cleaning: %d members",
                             len(hostgroup.members))

        if to_del_srv:
            # Clean services from services and servicegroups
            logger.debug("Cleaning %d services", len(to_del_srv))

            for service in to_del_srv:
                self.services.remove_item(service)

            # Exclude from all servicegroups members the services of this scheduler instance
            for servicegroup in self.servicegroups:
                logger.debug("Cleaning servicegroup %s: %d members",
                             servicegroup.get_name(), len(servicegroup.members))
                try:
                    # sg.members = [s for s in sg.members if s.instance_id != c_id]
                    servicegroup.members = []
                    for service in servicegroup.members:
                        if service.instance_id != c_id:
                            servicegroup.members.append(service)
                        else:
                            logger.debug("- removing service: %s", service)
                except Exception as exp:  # pylint: disable=broad-except
                    logger.error("Exception when cleaning servicegroup: %s", str(exp))

                logger.debug("- members count after cleaning: %d members",
                             len(servicegroup.members))

    def manage_initial_host_template_status_brok(self, b):
        """Got a new host template"""
        data = b.data
        host_name = data['name']
        inst_id = data['instance_id']

        # Try to get the in progress Hosts
        inp_hosts = self.inp_hosts[inst_id]

        logger.debug("Creating a host template: %s - %s from scheduler %s",
                     data['id'], host_name, inst_id)
        logger.debug("Creating a host template: %s ", data)

        host = Host({'register': '0'})
        self.update_element(host, data)

        # Ok, put in in the in progress hosts
        inp_hosts.add_template(host)

    def manage_initial_host_status_brok(self, b):
        """Got a new host"""
        data = b.data
        host_name = data['host_name']
        inst_id = data['instance_id']

        # Try to get the in progress Hosts
        try:
            inp_hosts = self.inp_hosts[inst_id]
        except Exception as exp:  # pylint: disable=broad-except
            logger.error("[Regenerator] initial_host_status:: Not good!  %s", str(exp))
            return
        logger.debug("Creating a host: %s - %s from scheduler %s", data['id'], host_name, inst_id)
        logger.debug("Creating a host: %s ", data)

        host = Host({})
        self.update_element(host, data)

        # Update downtimes/comments
        self._update_events(host)

        # Ok, put in in the in progress hosts
        inp_hosts[host.id] = host

    def manage_initial_hostgroup_status_brok(self, b):
        """Got a new hosts group"""
        data = b.data
        hgname = data['hostgroup_name']
        inst_id = data['instance_id']

        # Try to get the in progress Hostgroups
        inp_hostgroups = self.inp_hostgroups[inst_id]
        logger.debug("Creating a hostgroup: %s from scheduler %s", hgname, inst_id)
        logger.debug("Creating a hostgroup: %s ", data)

        # With void members
        hg = Hostgroup([])

        # populate data
        self.update_element(hg, data)

        # We will link hosts into hostgroups later
        # so now only save it
        inp_hostgroups[hg.id] = hg

        members = getattr(hg, 'members', [])
        if not isinstance(members, list):
            members = members.split(',')
        hg.members = members
        logger.debug("- hostgroup host members: %s", hg.members)
        # It looks like Shinken do not provide sub groups this information!
        sub_groups = getattr(hg, 'hostgroup_members', [])
        if not isinstance(sub_groups, list):
            sub_groups = sub_groups.split(',')
        sub_groups = [] if (sub_groups and not sub_groups[0]) else [g.strip() for g in sub_groups]
        hg.hostgroup_members = sub_groups
        logger.debug("- hostgroup group members: %s", hg.hostgroup_members)

    def manage_initial_service_template_status_brok(self, b):
        """Got a new service template"""
        data = b.data
        host_name = data['host_name']
        if not host_name:
            host_name = ''
        sdesc = data['service_description']
        if not sdesc:
            sdesc = ''
        inst_id = data['instance_id']

        # Try to get the in progress Hosts
        inp_services = self.inp_services[inst_id]

        logger.debug("Creating a service template: %s - %s/%s from scheduler %s",
                     data['id'], type(host_name), sdesc, inst_id)
        logger.debug("Creating a service template: %s ", data)

        service = Service({'register': '0'})
        self.update_element(service, data)

        # Ok, put in in the in progress hosts
        inp_services.add_template(service)

    def manage_initial_service_status_brok(self, b):
        """Got a new service"""
        data = b.data
        host_name = data['host_name']
        sdesc = data['service_description']
        inst_id = data['instance_id']

        # Try to get the in progress Hosts
        inp_services = self.inp_services[inst_id]
        logger.debug("Creating a service: %s - %s/%s from scheduler %s", data['id'], host_name,
                     sdesc, inst_id)
        logger.debug("Creating a service: %s ", data)

        if isinstance(data['display_name'], list):
            data['display_name'] = data['service_description']

        service = Service({})
        self.update_element(service, data)

        # Update downtimes/comments
        self._update_events(service)

        # Ok, put in in the in progress hosts
        inp_services[service.id] = service

    def manage_initial_servicegroup_status_brok(self, b):
        """Got a new services group"""
        data = b.data
        sgname = data['servicegroup_name']
        inst_id = data['instance_id']

        # Try to get the in progress Hostgroups
        inp_servicegroups = self.inp_servicegroups[inst_id]
        logger.debug("Creating a servicegroup: %s from scheduler %s", sgname, inst_id)
        logger.debug("Creating a servicegroup: %s ", data)

        # With void members
        sg = Servicegroup([])

        # populate data
        self.update_element(sg, data)

        # We will link hosts into hostgroups later
        # so now only save it
        inp_servicegroups[sg.id] = sg

        members = getattr(sg, 'members', [])
        if not isinstance(members, list):
            members = members.split(',')
        sg.members = members
        logger.debug("- servicegroup service members: %s", sg.members)
        # It looks like Shinken do not provide sub groups this information!
        sub_groups = getattr(sg, 'servicegroup_members', [])
        if not isinstance(sub_groups, list):
            sub_groups = sub_groups.split(',')
        sub_groups = [] if (sub_groups and not sub_groups[0]) else [g.strip() for g in sub_groups]
        sg.servicegroup_members = sub_groups
        logger.debug("- servicegroup group members: %s", sg.servicegroup_members)

    def manage_initial_contact_template_status_brok(self, b):
        """
        For Contacts, it's a global value, so 2 cases:
        We already got it from another scheduler instance -> we update it
        We don't -> we create it
        In both cases we need to relink it
        """
        data = b.data
        cname = data['name']
        inst_id = data['instance_id']

        logger.debug("Creating a contact template: %s from scheduler %s", cname, inst_id)
        logger.debug("Creating a contact template: %s", data)

        contact = Contact({'register': '0'})
        self.update_element(contact, data)
        self.contacts.add_template(contact)

    def manage_initial_contact_status_brok(self, b):
        """
        For Contacts, it's a global value, so 2 cases:
        We already got it from another scheduler instance -> we update it
        We don't -> we create it
        In both cases we need to relink it
        """
        data = b.data
        cname = data['contact_name']
        inst_id = data['instance_id']

        logger.debug("Creating a contact: %s from scheduler %s", cname, inst_id)
        logger.debug("Creating a contact: %s", data)

        contact = self.contacts.find_by_name(cname)
        if contact:
            self.update_element(contact, data)
        else:
            contact = Contact({})
            self.update_element(contact, data)
            self.contacts.add_item(contact)

        # Delete some useless contact values
        # WebUI - todo, perharps we should not nullify these values!
        del contact.host_notification_commands
        del contact.service_notification_commands
        del contact.host_notification_period
        del contact.service_notification_period

        # Now manage notification ways too
        # Same than for contacts. We create or update if it still exists
        nws = contact.notificationways
        if nws and not isinstance(nws, list):
            logger.error("Contact %s, bad formed notification ways, ignoring!", contact.get_name())
            return

        if nws and not isinstance(nws[0], NotificationWay):
            # Alignak sends notification ways as dictionaries
            new_notifways = []
            for nw_uuid in nws:
                nw = None
                for nw in self.notificationways:
                    if nw_uuid == nw.get_name() or nw_uuid == nw.uuid:
                        break
                else:
                    logger.warning("Contact %s has an unknown NW: %s", contact.get_name(), nws)
                    continue

                logger.debug("Contact %s, found the NW: %s", contact.get_name(), nw.__dict__)

                # Linking the notification way with commands
                self.linkify_commands(nw, 'host_notification_commands')
                self.linkify_commands(nw, 'service_notification_commands')

                # Now link timeperiods
                self.linkify_a_timeperiod(nw, 'host_notification_period')
                self.linkify_a_timeperiod(nw, 'service_notification_period')

                new_notifways.append(nw)

            contact.notificationways = new_notifways
        else:
            # Shinken old way...
            new_notifways = []
            for cnw in nws:
                nwname = cnw.get_name()
                logger.debug("- notification way: %s", nwname)

                nw = self.notificationways.find_by_name(nwname)
                if nw:
                    # Update it...
                    for prop in NotificationWay.properties:
                        if hasattr(cnw, prop):
                            setattr(nw, prop, getattr(cnw, prop))
                else:
                    self.notificationways.add_item(cnw)
                    nw = self.notificationways.find_by_name(nwname)

                # Linking the notification way with commands
                self.linkify_commands(nw, 'host_notification_commands')
                self.linkify_commands(nw, 'service_notification_commands')

                # Now link timeperiods
                self.linkify_a_timeperiod(nw, 'host_notification_period')
                self.linkify_a_timeperiod(nw, 'service_notification_period')

                new_notifways.append(nw)

            contact.notificationways = new_notifways

    def manage_initial_contactgroup_status_brok(self, b):
        """Got a new contacts group"""
        data = b.data
        cgname = data['contactgroup_name']
        inst_id = data['instance_id']

        # Try to get the in progress Contactgroups
        inp_contactgroups = self.inp_contactgroups[inst_id]
        logger.debug("Creating a contactgroup: %s from scheduler %s", cgname, inst_id)
        logger.debug("Creating a contactgroup: %s", data)

        # With void members
        cg = Contactgroup([])

        # populate data
        self.update_element(cg, data)

        # We will link contacts into contactgroups later
        # so now only save it
        inp_contactgroups[cg.id] = cg

        members = getattr(cg, 'members', [])
        if not isinstance(members, list):
            members = members.split(',')
        cg.members = members
        logger.debug("- contactgroup contact members: %s", cg.members)
        sub_groups = getattr(cg, 'contactgroup_members', [])
        if not isinstance(sub_groups, list):
            sub_groups = sub_groups.split(',')
        sub_groups = [] if (sub_groups and not sub_groups[0]) else [g.strip() for g in sub_groups]
        cg.contactgroup_members = sub_groups
        logger.debug("- contactgroup group members: %s", cg.contactgroup_members)

    def manage_initial_timeperiod_status_brok(self, b):
        """
        For Timeperiods we got 2 cases: do we already got it or not.
        if got: just update it
        if not: create it and declare it in our main timeperiods
        """
        data = b.data
        tpname = data['timeperiod_name']
        inst_id = data['instance_id']

        logger.debug("Creating a timeperiod: %s from scheduler %s", tpname, inst_id)
        logger.debug("Creating a timeperiod: %s ", data)

        tp = self.timeperiods.find_by_name(tpname)
        if tp:
            self.update_element(tp, data)
        else:
            tp = Timeperiod({})
            self.update_element(tp, data)
            self.timeperiods.add_item(tp)

        # Alignak do not keep the Timerange objects and serializes as dict...
        # so we must restore Timeranges from the dictionary
        logger.debug("Timeperiod: %s", tp)

        # WebUI - try to manage time periods correctly!
        # Alignak :
        # - date range: <class 'alignak.daterange.MonthWeekDayDaterange'>
        # - time range: <type 'dict'>
        # Shinken :
        # - date range: <class 'shinken.daterange.MonthWeekDayDaterange'>
        # - time range: <class 'shinken.daterange.Timerange'>
        # Transform some inner items
        new_drs = []
        for dr in tp.dateranges:
            new_dr = dr
            # new_dr = Daterange(dr.syear, dr.smon, dr.smday, dr.swday, dr.swday_offset,
            #                    dr.eyear, dr.emon, dr.emday, dr.ewday, dr.ewday_offset,
            #                    dr.skip_interval, dr.other)
            logger.debug("- date range: %s (%s)", type(dr), dr.__dict__)
            # logger.warning("- date range: %s (%s)", type(new_dr), new_dr.__dict__)
            new_trs = []
            for tr in dr.timeranges:
                # Time range may be a dictionary or an object
                logger.debug("  time range: %s - %s", type(tr), tr)
                try:
                    # Dictionary for Alignak
                    entry = "%02d:%02d-%02d:%02d" \
                            % (tr['hstart'], tr['mstart'], tr['hend'], tr['mend'])
                except TypeError:
                    # Object for Shinken
                    entry = "%02d:%02d-%02d:%02d" \
                            % (tr.hstart, tr.mstart, tr.hend, tr.mend)

                logger.debug("  time range: %s", entry)
                new_trs.append(Timerange(entry))
            new_dr.timeranges = new_trs
            logger.debug("- date range: %s", dr.__dict__)
            new_drs.append(new_dr)

        tp.dateranges = new_drs

    def manage_initial_command_status_brok(self, b):
        """
        For command we got 2 cases: do we already got it or not.
        if got: just update it
        if not: create it and declare it in our main commands
        """
        data = b.data
        cname = data['command_name']
        inst_id = data['instance_id']

        logger.debug("Creating a command: %s from scheduler %s", cname, inst_id)
        logger.debug("Creating a command: %s ", data)

        c = self.commands.find_by_name(cname)
        if c:
            self.update_element(c, data)
        else:
            c = Command({})
            self.update_element(c, data)
            self.commands.add_item(c)

    def manage_initial_notificationway_status_brok(self, b):
        """
        For notification ways we got 2 cases: do we already got it or not.
        if got: just update it
        if not: create it and declare it in our main commands
        """
        data = b.data
        nw_name = data['notificationway_name']
        inst_id = data['instance_id']

        logger.debug("Creating a notification way: %s from scheduler %s", nw_name, inst_id)
        logger.debug("Creating a notification way: %s ", data)

        nw = self.notificationways.find_by_name(nw_name)
        if nw:
            logger.debug("- updating a notification way: %s from scheduler %s", nw_name, inst_id)
            self.update_element(nw, data)
        else:
            nw = NotificationWay({})
            self.update_element(nw, data)
            self.notificationways.add_item(nw)

        # Linking the notification way with commands
        self.linkify_commands(nw, 'host_notification_commands')
        self.linkify_commands(nw, 'service_notification_commands')

        # Now link timeperiods
        self.linkify_a_timeperiod(nw, 'host_notification_period')
        self.linkify_a_timeperiod(nw, 'service_notification_period')

        logger.debug("Created: %s ", nw.get_name())

    def manage_initial_scheduler_status_brok(self, b):
        """Got a scheduler status"""
        data = b.data

        sched = SchedulerLink({})
        self._update_realm(data)
        self.update_element(sched, data)
        self.schedulers[data['scheduler_name']] = sched

    def manage_initial_poller_status_brok(self, b):
        """Got a poller status"""
        data = b.data

        poller = PollerLink({})
        self._update_realm(data)
        self.update_element(poller, data)
        self.pollers[data['poller_name']] = poller

    def manage_initial_reactionner_status_brok(self, b):
        """Got a reactionner status"""
        data = b.data

        reac = ReactionnerLink({})
        self._update_realm(data)
        self.update_element(reac, data)
        self.reactionners[data['reactionner_name']] = reac

    def manage_initial_broker_status_brok(self, b):
        """Got a broker status"""
        data = b.data

        broker = BrokerLink({})
        self._update_realm(data)
        self.update_element(broker, data)
        self.brokers[data['broker_name']] = broker

    def manage_initial_receiver_status_brok(self, b):
        """Got a receiver status"""
        data = b.data

        receiver = ReceiverLink({})
        self._update_realm(data)
        self.update_element(receiver, data)
        self.receivers[data['receiver_name']] = receiver

    def manage_initial_broks_done_brok(self, b):
        """This brok is here when the WHOLE initial phase is done.
        It is the last brok sent by the scheduler.
        So we got all data, we can link all together :)"""
        inst_id = b.data['instance_id']
        self.all_done_linking(inst_id)

#################
# Status Update part
#################

    def manage_update_program_status_brok(self, b):
        """Each scheduler sends us a "I'm alive" brok.
        If we never heard about this one, we got some problem and we ask him some initial data :)

        """
        data = b.data
        c_id = data['instance_id']
        c_name = data.get('instance_name', c_id)
        logger.debug("Got a scheduler update status from %s", c_name)
        logger.debug("Data: %s", data)

        # If we got an update about an unknown instance, cry and ask for a full version!
        # Checked that Alignak will also provide information if it gets such a message...
        if c_id not in list(self.configs.keys()):
            # Do not ask data too quickly, very dangerous
            # one a minute
            if time.time() - self.last_need_data_send > 60 and self.from_q is not None:
                logger.debug("I ask the broker for instance id data: %s", c_id)
                if ALIGNAK:
                    # Alignak: _type, data, source
                    msg = Message(_type='NeedData', data={'full_instance_id': c_id}, source='WebUI')
                else:
                    # Shinken: id, type, data, source
                    msg = Message(id=0, type='NeedData', data={'full_instance_id': c_id}, source='WebUI')
                self.from_q.put(msg)
                self.last_need_data_send = time.time()
            return

        # Tag with the update time and store the configuration
        data['_timestamp'] = time.time()
        self.configs[c_id].update(data)

    def manage_update_host_status_brok(self, b):
        """Got an host update
        Something changed in the host configuration"""
        data = b.data
        host_name = data['host_name']
        host = self.hosts.find_by_name(host_name)
        if not host:
            return

        # There are some properties that should not change and are already linked
        # so just remove them
        clean_prop = ['uuid', 'check_command', 'hostgroups',
                      'contacts', 'notification_period', 'contact_groups',
                      'check_period', 'event_handler',
                      'maintenance_period', 'realm', 'customs', 'escalations']

        # some are only used when a topology change happened
        toplogy_change = b.data['topology_change']
        if not toplogy_change:
            # No childs property in Alignak hosts
            clean_prop.extend(['parents', 'child_dependencies', 'parent_dependencies'])

        for prop in clean_prop:
            del data[prop]

        logger.debug("Updated host: %s", host_name)
        self.before_after_hook(b, host)
        self.update_element(host, data)

        # We can have some change in our impacts and source problems.
        self.linkify_dict_srv_and_hosts(host, 'impacts')
        self.linkify_dict_srv_and_hosts(host, 'source_problems')

        # If the topology change, update it
        if toplogy_change:
            logger.debug("Topology change for %s %s", host.get_name(), host.parent_dependencies)
            self.linkify_host_and_hosts(host, 'parents')
            self.linkify_host_and_hosts(host, 'childs')
            self.linkify_dict_srv_and_hosts(host, 'parent_dependencies')
            self.linkify_dict_srv_and_hosts(host, 'child_dependencies')

        # Update downtimes/comments
        self._update_events(host)

    def manage_update_service_status_brok(self, b):
        """Got a service update
        Something changed in the service configuration"""
        # There are some properties that should not change and are already linked
        # so just remove them
        clean_prop = ['uuid', 'check_command', 'servicegroups',
                      'contacts', 'notification_period', 'contact_groups',
                      'check_period', 'event_handler',
                      'maintenance_period', 'customs', 'escalations']

        # some are only use when a topology change happened
        toplogy_change = b.data['topology_change']
        if not toplogy_change:
            clean_prop.extend(['child_dependencies', 'parent_dependencies'])

        data = b.data
        for prop in clean_prop:
            del data[prop]

        host_name = data['host_name']
        sdesc = data['service_description']
        service = self.services.find_srv_by_name_and_hostname(host_name, sdesc)
        if not service:
            return

        logger.debug("Updated service: %s/%s", host_name, sdesc)
        self.before_after_hook(b, service)
        self.update_element(service, data)

        # We can have some change in our impacts and source problems.
        self.linkify_dict_srv_and_hosts(service, 'impacts')
        self.linkify_dict_srv_and_hosts(service, 'source_problems')

        # If the topology change, update it
        if toplogy_change:
            self.linkify_dict_srv_and_hosts(service, 'parent_dependencies')
            self.linkify_dict_srv_and_hosts(service, 'child_dependencies')

        # Update downtimes/comments
        self._update_events(service)

    def _update_satellite_status(self, sat_list, sat_name, data):
        """Update a satellite status"""
        logger.debug("Update satellite '%s' status: %s", sat_name, data)

        try:
            # Get the satellite object
            satellite = sat_list[sat_name]
            # Update its realm
            self._update_realm(data)
            # Update its properties
            self.update_element(satellite, data)
        except KeyError:
            # Not yet known
            pass
        except Exception as exp:  # pylint: disable=broad-except
            logger.warning("Failed updating %s satellite status: %s", sat_name, exp)

    def manage_update_broker_status_brok(self, b):
        """Got a broker status update"""
        self._update_satellite_status(self.brokers, b.data['broker_name'], b.data)

    def manage_update_receiver_status_brok(self, b):
        """Got a receiver status update"""
        self._update_satellite_status(self.receivers, b.data['receiver_name'], b.data)

    def manage_update_reactionner_status_brok(self, b):
        """Got a reactionner status update"""
        self._update_satellite_status(self.reactionners, b.data['reactionner_name'], b.data)

    def manage_update_poller_status_brok(self, b):
        """Got a poller status update"""
        self._update_satellite_status(self.pollers, b.data['poller_name'], b.data)

    def manage_update_scheduler_status_brok(self, b):
        """Got a scheduler status update"""
        self._update_satellite_status(self.schedulers, b.data['scheduler_name'], b.data)

#################
# Check result and schedule part
#################
    def manage_host_check_result_brok(self, b):
        """This brok contains the result of an host check"""
        data = b.data
        host_name = data['host_name']

        host = self.hosts.find_by_name(host_name)
        if not host:
            logger.debug("Got a check result brok for an unknown host: %s", host_name)
            return

        logger.debug("Host check result: %s - %s (%s)", host_name, host.state, host.state_type)
        self.before_after_hook(b, host)
        # Remove identifiers if they exist in the data - it happens that the
        # identifier is changing on a configuration reload!
        if 'id' in data:
            data.pop('id')
        if 'uuid' in data:
            data.pop('uuid')
        self.update_element(host, data)

    def manage_host_next_schedule_brok(self, b):
        """This brok should arrive within a second after the host_check_result_brok.
        It contains information about the next scheduled host check"""
        self.manage_host_check_result_brok(b)

    def manage_service_check_result_brok(self, b):
        """A service check have just arrived, we UPDATE data info with this"""
        data = b.data
        host_name = data['host_name']
        service_description = data['service_description']
        service = self.services.find_srv_by_name_and_hostname(host_name, service_description)
        if not service:
            logger.debug("Got a check result brok for an unknown service: %s/%s",
                         host_name, service_description)
            return

        logger.debug("Service check result: %s/%s - %s (%s)",
                     host_name, service_description, service.state, service.state_type)
        self.before_after_hook(b, service)

        # Remove identifiers if they exist in the data - it happens that the
        # identifier is changing on a configuration reload!
        if 'id' in data:
            data.pop('id')
        if 'uuid' in data:
            data.pop('uuid')
        self.update_element(service, data)

    def manage_service_next_schedule_brok(self, b):
        """This brok should arrive within a second after the service_check_result_brok.
        It contains information about the next scheduled service check"""
        self.manage_service_check_result_brok(b)

#################
# Acknowledge / downtime part
# ---
# Alignak raises broks for acknowledges and downtimes
#################
    def manage_acknowledge_raise_brok(self, b):
        """An acknowledge has been set on an item"""
        data = b.data
        host_name = data.get('host_name', data.get('host', None))
        if host_name:
            host = self.hosts.find_by_name(host_name)
            if not host:
                logger.warning("Got a acknowledge raise brok for an unknown host: %s", host_name)
                return

        service_description = data.get('service_description', data.get('service', None))
        if service_description:
            service = self.services.find_srv_by_name_and_hostname(host_name, service_description)
            if not service:
                logger.warning("Got a acknowledge raise brok for an unknown service: %s/%s",
                               host_name, service_description)
                return
            logger.info("Acknowledge set: %s/%s - %s",
                        host_name, service_description, service.state)
        else:
            logger.info("Acknowledge set: %s - %s",
                        host_name, host.state)

    def manage_acknowledge_expire_brok(self, b):
        """An acknowledge has been set on an item"""
        data = b.data
        host_name = data.get('host_name', data.get('host', None))
        if host_name:
            host = self.hosts.find_by_name(host_name)
            if not host:
                logger.warning("Got a acknowledge raise brok for an unknown host: %s", host_name)
                return

        service_description = data.get('service_description', data.get('service', None))
        if service_description:
            service = self.services.find_srv_by_name_and_hostname(host_name, service_description)
            if not service:
                logger.warning("Got a acknowledge raise brok for an unknown service: %s/%s",
                               host_name, service_description)
                return
            logger.info("Acknowledge expired: %s/%s - %s",
                        host_name, service_description, service.state)
        else:
            logger.info("Acknowledge expired: %s - %s", host_name, host.state)

    def manage_downtime_raise_brok(self, b):
        """A downtime has been set on an item"""
        data = b.data
        host_name = data.get('host_name', data.get('host', None))
        if host_name:
            host = self.hosts.find_by_name(host_name)
            if not host:
                logger.warning("Got a downtime raise brok for an unknown host: %s", host_name)
                return

        service_description = data.get('service_description', data.get('service', None))
        if service_description:
            service = self.services.find_srv_by_name_and_hostname(host_name, service_description)
            if not service:
                logger.warning("Got a downtime raise brok for an unknown service: %s/%s",
                               host_name, service_description)
                return
            logger.info("Downtime set: %s/%s - %s", host_name, service_description, service.state)
        else:
            logger.info("Downtime set: %s - %s", host_name, host.state)

    def manage_downtime_expire_brok(self, b):
        """A downtime has been set on an item"""
        data = b.data
        host_name = data.get('host_name', data.get('host', None))
        if host_name:
            host = self.hosts.find_by_name(host_name)
            if not host:
                logger.warning("Got a downtime end brok for an unknown host: %s", host_name)
                return

        service_description = data.get('service_description', data.get('service', None))
        if service_description:
            service = self.services.find_srv_by_name_and_hostname(host_name, service_description)
            if not service:
                logger.warning("Got a downtime end brok for an unknown service: %s/%s",
                               host_name, service_description)
                return
            logger.info("Downtime end: %s/%s - %s", host_name, service_description, service.state)
        else:
            logger.info("Downtime end: %s - %s", host_name, host.state)
