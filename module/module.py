#!/usr/bin/python
# -*- coding: utf-8 -*-

# pylint: disable=attribute-defined-outside-init

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


"""
This Class is a plugin for the Shinken/Alignak Broker. It is in charge to get broks
and recreate real objects to propose a Web User Interface :)
"""

# pylint: disable=invalid-name, wrong-import-position
WEBUI_VERSION = "3.0.0 beta"
WEBUI_COPYRIGHT = "2009-2019"
WEBUI_LICENSE = "License GNU AGPL as published by the FSF, minimum version 3 of the License."

import os
import string
import random
import traceback
import sys
import signal
import time
import threading
import imp
import logging
import requests

from collections import deque

# Bottle import
from bottle import request, response
import bottle

# Check if Alignak is installed
ALIGNAK = os.environ.get('ALIGNAK_DAEMON', None) is not None
print("Underlying monitoring framework: %s" % ('Alignak' if ALIGNAK else 'Shinken'))

# Alignak / Shinken base module are slightly different
if ALIGNAK:
    # Specific logger configuration
    from alignak.log import ALIGNAK_LOGGER_NAME

    logger = logging.getLogger(ALIGNAK_LOGGER_NAME + ".webui")

    from alignak.basemodule import BaseModule
    from alignak.modulesmanager import ModulesManager
    from alignak.daemon import Daemon
    from alignak.util import to_bool
else:
    # Shinken logger configuration
    from shinken.log import logger

    from shinken.basemodule import BaseModule
    from shinken.modulesctx import modulesctx
    from shinken.modulesmanager import ModulesManager
    from shinken.daemon import Daemon
    from shinken.util import to_bool

# Local import
# Regenerate objects from the received broks
from .regenerator import Regenerator
# Data manager
from .datamanager import WebUIDataManager
# Helper functions
from .helper import helper
# UI user features
from .ui_user import User

# Sub modules
from .submodules.prefs import PrefsMetaModule
from .submodules.auth import AuthMetaModule
from .submodules.logs import LogsMetaModule
from .submodules.graphs import GraphsMetaModule
from .submodules.helpdesk import HelpdeskMetaModule

# WebUI application
root_app = bottle.default_app()
webui_app = bottle.Bottle()

# Debug
ALIGNAK_UI_DEBUG = False
if os.environ.get('ALIGNAK_UI_DEBUG', None) or os.environ.get('SHINKEN_UI_DEBUG', None):
    ALIGNAK_UI_DEBUG = True
    bottle.debug(True)

# Look at the webui module root dir too
webuimod_dir = os.path.abspath(os.path.dirname(__file__))
htdocs_dir = os.path.join(webuimod_dir, 'htdocs')

bottle.TEMPLATE_PATH.append(os.path.join(webuimod_dir, 'views'))
bottle.TEMPLATE_PATH.append(webuimod_dir)

properties = {
    'daemons': ['broker'],
    'type': 'webui',
    'phases': ['running'],
    'external': True
}


def get_instance(mod_conf):
    """
    Called by the plugin manager to get an instance of the module

    :param mod_conf: the module configuration parameters
    :return:
    """
    if ALIGNAK:
        logger.info("Give an instance of WebuiBroker for alias: %s", mod_conf.module_alias)
    else:
        logger.info("Give an instance of WebuiBroker for alias: %s", mod_conf.module_name)

    return WebuiBroker(mod_conf)


def resolve_auth_secret(configuration):
    """Read auth_secret from the configuration or a file (if it exists), else self generate one"""
    candidate = getattr(configuration, 'auth_secret', None)
    if not candidate:
        # Look for file
        auth_secret_file = getattr(configuration,
                                   'auth_secret_file', '/var/lib/shinken/auth_secret')
        if os.path.exists(auth_secret_file):
            with open(auth_secret_file) as secret:
                candidate = secret.read()
        else:
            # Self generate a secret
            chars = string.ascii_letters + string.digits
            candidate = ''.join([random.choice(chars) for _ in range(32)])
            try:
                with os.fdopen(os.open(auth_secret_file,
                                       os.O_WRONLY | os.O_CREAT, 0o600), 'w') as secret:
                    secret.write(candidate)
            except Exception as exp:
                logger.error("Authentication secret file creation failed: %s, error: %s",
                             auth_secret_file, str(exp))
    return candidate


# Class for the WebUI Broker
class WebuiBroker(BaseModule, Daemon):
    # pylint: disable=super-init-not-called
    def __init__(self, mod_conf):
        """UI initialisation

        mod_conf is a Module object that contains:
        - all the variables used to configure the Broker daemon
        - all the variables declared in the module configuration
        - a 'properties' value that is the module properties as defined globally in this file

        :param mod_conf: alignak.objects.module.Module
        """
        BaseModule.__init__(self, mod_conf)

        self.alignak = ALIGNAK
        if self.alignak:
            # pylint: disable=global-statement
            global logger

            logger = logging.getLogger(ALIGNAK_LOGGER_NAME + ".webui")
            logger.setLevel(getattr(mod_conf, 'log_level', logging.INFO))

        # Allow to use log_file or log_filename for the specific UI logger
        if getattr(mod_conf, 'log_filename', None) is None and getattr(mod_conf, 'log_file', None):
            mod_conf.log_filename = getattr(mod_conf, 'log_file')

        if getattr(mod_conf, 'log_filename', None):
            # If the file name is a relative path, uses the default daemon log directory
            log_filename = getattr(mod_conf, 'log_filename')
            if not os.path.isabs(log_filename):
                log_filename = os.path.abspath(
                    os.path.join(getattr(mod_conf, 'logdir', os.getcwd()), log_filename))

            # Configure a timed rotation file logger
            for hdlr in logger.handlers:
                if isinstance(hdlr, logging.handlers.TimedRotatingFileHandler):
                    # We still have a file logger - but this should never happen!
                    break
            else:
                file_handler = logging.handlers.TimedRotatingFileHandler(
                    log_filename,
                    when=getattr(mod_conf, 'log_rotation_when', 'midnight'),
                    interval=getattr(mod_conf, 'log_rotation_interval', 1),
                    backupCount=getattr(mod_conf, 'log_rotation_count', 7))
                file_handler.setFormatter(
                    logging.Formatter(getattr(mod_conf, 'log_format',
                                              '[%(asctime)s] %(levelname)s: [%(name)s] %(message)s'),
                                      getattr(mod_conf, 'log_date',
                                              '%Y-%m-%d %H:%M:%S')))
                file_handler.setLevel(getattr(mod_conf, 'log_level', logging.INFO))
                logger.addHandler(file_handler)
                logger.info("Configured Web UI log to: %s", log_filename)

        logger.debug("inner properties: %s", self.__dict__)
        logger.debug("received configuration: %s", mod_conf.__dict__)

        if getattr(self, 'use_ssl', None) is None:
            self.use_ssl = False

        self.my_configuration = mod_conf
        logger.info("received configuration:")
        for prop in sorted(self.my_configuration.__dict__.keys()):
            # Clean the content of no more useful properties and no configuration properties
            if prop in ['configuration_warnings', 'configuration_errors',
                        'tags', 'customs', 'plus']:
                setattr(self.my_configuration, prop, [])
                continue
            logger.info("- %s: %s", prop, getattr(mod_conf, prop, 'XxX'))

        self.plugins = []

        if ALIGNAK_UI_DEBUG:
            logger.warning("Using Bottle Web framework in debug mode.")

        # A daemon must have these properties
        self.type = 'webui'
        self.name = 'webui'
        self.module_type = getattr(mod_conf, 'module_type', 'unset')
        self.module_name = getattr(mod_conf, 'module_name', 'unset')

        # Configure Alignak Arbiter API endpoint
        self.alignak_endpoint = getattr(mod_conf, 'alignak_endpoint', 'http://127.0.0.1:7770')
        self.alignak_check_period = int(getattr(mod_conf, 'alignak_check_period', '10'))
        self.alignak_livestate = {}
        self.alignak_events_count = int(getattr(mod_conf, 'alignak_events_count', '1000'))
        self.alignak_events = deque(maxlen=int(os.environ.get('ALIGNAK_EVENTS_LOG_COUNT',
                                                              self.alignak_events_count)))

        # Threads
        self.my_data_thread = None
        self.my_fmwk_thread = None

        # We will protect the operations on
        # the non read+write with a lock and 2 counters
        self.global_lock = threading.RLock()
        self.nb_readers = 0
        self.nb_writers = 0

        # Web UI modules
        self.modules = getattr(mod_conf, 'modules', [])
        if self.modules and not isinstance(self.modules, list):
            self.modules = [self.modules]
        if self.modules and not self.modules[0]:
            self.modules = []
        self.modules_dir = getattr(mod_conf, 'modules_dir', './modules')
        logger.info("modules directory: %s", self.modules_dir)

        # Web server configuration
        self.host = getattr(mod_conf, 'host', '0.0.0.0')
        self.port = int(getattr(mod_conf, 'port', '7767'))
        logger.info("server: %s:%d", self.host, self.port)

        # Build session cookie
        self.auth_secret = resolve_auth_secret(mod_conf)
        self.session_cookie = getattr(mod_conf, 'cookie_name', 'user_session')
        logger.info("user session cookie name: %s", self.session_cookie)
        # TODO : common preferences
        self.play_sound = to_bool(getattr(mod_conf, 'play_sound', '0'))
        logger.info("sound: %s", self.play_sound)
        # TODO : common preferences
        self.login_text = getattr(mod_conf, 'login_text', None)
        # TODO : common preferences
        self.company_logo = getattr(mod_conf, 'company_logo', 'undefined')
        if not self.company_logo:
            # Set a dummy value if value defined in the configuration
            # is empty to force using the default logo ...
            self.company_logo = 'undefined'
        # TODO : common preferences
        self.gravatar = to_bool(getattr(mod_conf, 'gravatar', '0'))
        # TODO : common preferences
        self.allow_html_output = to_bool(getattr(mod_conf, 'allow_html_output', '0'))
        # TODO : common preferences
        # self.max_output_length = int(getattr(modconf, 'max_output_length', '100'))
        # TODO : common preferences
        self.refresh_period = int(getattr(mod_conf, 'refresh_period', '60'))
        logger.info("refresh period: %s", self.refresh_period)
        self.refresh = (self.refresh_period == 0)
        # Use element tag as image or use text
        self.tag_as_image = to_bool(getattr(mod_conf, 'tag_as_image', '0'))

        # Manage user's ACL
        self.manage_acl = to_bool(getattr(mod_conf, 'manage_acl', '1'))
        self.allow_anonymous = to_bool(getattr(mod_conf, 'allow_anonymous', '0'))

        # Allow to customize default downtime duration
        self.default_downtime_hours = int(getattr(mod_conf, 'default_downtime_hours', '48'))
        self.shinken_downtime_fixed = int(getattr(mod_conf, 'shinken_downtime_fixed', '1'))
        self.shinken_downtime_trigger = int(getattr(mod_conf, 'shinken_downtime_trigger', '0'))
        self.shinken_downtime_duration = int(getattr(mod_conf, 'shinken_downtime_duration', '0'))

        # Allow to customize default acknowledge parameters
        self.default_ack_sticky = int(getattr(mod_conf, 'default_ack_sticky', '2'))
        self.default_ack_notify = int(getattr(mod_conf, 'default_ack_notify', '1'))
        self.default_ack_persistent = int(getattr(mod_conf, 'default_ack_persistent', '1'))

        # MongoDB connection
        self.uri = getattr(mod_conf, "uri", "")
        if not self.uri:
            logger.warning("You defined an empty MongoDB connection URI "
                           "or you did not defined any MongoDB URI. "
                           "Features like user's preferences, dashboard or system "
                           "log and hosts availability will not be available.")

        # Advanced options
        self.http_backend = getattr(mod_conf, 'http_backend', 'auto')
        self.remote_user_enable = getattr(mod_conf, 'remote_user_enable', '0')
        self.remote_user_variable = getattr(mod_conf, 'remote_user_variable', 'X_REMOTE_USER')
        self.serveropts = {}
        umask = getattr(mod_conf, 'umask', None)
        if umask is not None:
            self.serveropts['umask'] = int(umask)
        bind_address = getattr(mod_conf, 'bind_address', None)
        if bind_address:
            self.serveropts['bind_address'] = str(bind_address)

        # Apache htpasswd file for authentication
        self.htpasswd_file = getattr(mod_conf, 'htpasswd_file', None)
        if self.htpasswd_file:
            if not os.path.exists(self.htpasswd_file):
                logger.warning("htpasswd file '%s' does not exist.", self.htpasswd_file)
                self.htpasswd_file = None

        # Load the config dir and make it an absolute path
        self.config_dir = getattr(mod_conf, 'config_dir', 'share')
        self.config_dir = os.path.abspath(self.config_dir)
        logger.info("Config dir: %s", self.config_dir)

        # Load the share dir and make it an absolute path
        self.share_dir = getattr(mod_conf, 'share_dir', 'share')
        self.share_dir = os.path.abspath(self.share_dir)
        logger.info("Share dir: %s", self.share_dir)

        # todo: @mohierf: remove this photos dir... not used anywhere
        # Load the photo dir and make it an absolute path
        self.photo_dir = getattr(mod_conf, 'photos_dir', 'photos')
        self.photo_dir = os.path.abspath(self.photo_dir)
        logger.info("Photo dir: %s", self.photo_dir)

        # User information
        self.user_session = None
        self.user_info = None

        # todo: @mohierf: still useful ? No value in webui.cfg, so always False ...
        # self.embeded_graph = to_bool(getattr(modconf, 'embeded_graph', '0'))

        # Look for an additional pages dir
        self.additional_plugins_dir = getattr(mod_conf, 'additional_plugins_dir', '')
        if self.additional_plugins_dir:
            self.additional_plugins_dir = os.path.abspath(self.additional_plugins_dir)
        logger.info("Additional plugins dir: %s", self.additional_plugins_dir)

        # Web UI timezone
        self.timezone = getattr(mod_conf, 'timezone', 'Europe/Paris')
        if self.timezone:
            logger.info("Setting our timezone to %s", self.timezone)
            os.environ['TZ'] = self.timezone
            time.tzset()
        logger.info("parameter timezone: %s", self.timezone)

        # Visual alerting thresholds
        # --------------------------
        # All the hosts and services that are in a HARD non OK/UP state
        # are considered as problems if their
        # business_impact is greater than or equal this value
        self.problems_business_impact = int(getattr(mod_conf, 'problems_business_impact', '1'))
        # important_problems_business_impact is used to filter
        # the alerting badges in the header bar (default is 3)
        self.important_problems_business_impact = \
            int(getattr(mod_conf, 'important_problems_business_impact', '3'))
        logger.info("minimum business impacts, all UI: %s, most important: %s",
                    self.problems_business_impact, self.important_problems_business_impact)

        self.PROBLEMS_SEARCH_STRING = \
            "isnot:UP isnot:OK isnot:PENDING isnot:ACK isnot:DOWNTIME isnot:SOFT bi:>=%d" \
            % self.problems_business_impact

        # Inner computation rules for the problems
        self.disable_inner_problems_computation = \
            int(getattr(mod_conf, 'disable_inner_problems_computation', '0'))

        # Used in the dashboard view to select background color for percentages
        self.hosts_states_warning = int(getattr(mod_conf, 'hosts_states_warning', '95'))
        self.hosts_states_critical = int(getattr(mod_conf, 'hosts_states_critical', '90'))
        self.services_states_warning = int(getattr(mod_conf, 'services_states_warning', '95'))
        self.services_states_critical = int(getattr(mod_conf, 'services_states_critical', '90'))

        # Web UI information
        self.app_version = getattr(mod_conf, 'about_version', WEBUI_VERSION)
        self.app_copyright = getattr(mod_conf, 'about_copyright', WEBUI_COPYRIGHT)
        self.app_license = WEBUI_LICENSE

        # We will save all widgets
        self.widgets = {}

        # We need our regenerator now (before main) so if we are in a scheduler,
        # rg will be able to skip some broks
        self.rg = Regenerator()

        # My bottle object ...
        self.bottle = bottle

        bottle.BaseTemplate.defaults['app'] = self
        bottle.BaseTemplate.defaults['alignak'] = ALIGNAK

    def init(self):
        """
        Called by Broker so we can do init stuff

        :return:
        """
        logger.info("Initializing ...")
        if self.alignak:
            logger.info("Running the Web UI for the Alignak framework.")
        else:
            logger.info("Running the Web UI for the Shinken framework.")

        self.rg.load_external_queue(self.from_q)
        # Return True to confirm correct initialization
        return True

    def setup_new_conf(self):
        """Abstract method - best is to override"""
        logger.info("In setup_new_conf")
        time.sleep(1)

    def do_loop_turn(self):
        """This function is called/used when you need a module with
        a loop function (and use the parameter 'external': True)
        """
        logger.info("In loop")
        time.sleep(1)

    def hook_pre_scheduler_mod_start(self, sched):
        """
        This is called only when we are in a scheduler
        and just before we are started. So we can gain time, and
        just load all scheduler objects without fear :) (we
        will be in another process, so we will be able to hack objects
        if need)

        :param sched:
        :return:
        """
        self.rg.load_from_scheduler(sched)

    def want_brok(self, b):
        """
        In a scheduler we will have a filter of what we really want as a brok

        :param b:
        :return:
        """
        return self.rg.want_brok(b)

    # pylint: disable=access-member-before-definition
    def manage_signal(self, sig, frame):
        """Generic function to handle signals
        Only called when the module process received SIGINT or SIGKILL. Note that
        Alignak may also notify other signals like SIGHUP

        :param sig: signal sent
        :type sig:
        :param frame: frame before catching signal
        :type frame:
        :return: None
        """
        logger.debug("received a signal: %s", sig)

        if sig == signal.SIGHUP:
            # if SIGHUP, try to reload the configuration
            logger.info("The WebUI is not able to reload its configuration...")

        if not self.interrupted:
            logger.info("The WebUI received a request to stop.")
            self.interrupted = True
        # super(BaseModule, self).manage_signal(sig=sig, frame=frame)

    # pylint: disable=no-value-for-parameter
    def main(self):
        """
            Module main function
        """
        logger.info("starting...")
        logger.debug("I (%s) am now running as a process, pid=%d", self.name, os.getpid())

        # WebUI modules management
        # ---
        # I used a large If/Else to avoid breaking the existing behavior but I am quite sure
        # that the Alignak branch code is fully compatible with Shinken. I prefer separating
        # to avoid too many testings...
        if not self.alignak:
            self.debug_output = []
            self.modules_dir = modulesctx.get_modulesdir()
            self.modules_manager = ModulesManager('webui', self.find_modules_path(), [])
            self.modules_manager.set_modules(self.modules)
            logger.info("WebUI Shinken modules %s", self.modules)

            self.do_load_modules()
            for inst in self.modules_manager.instances:
                f = getattr(inst, 'load', None)
                if f and callable(f):
                    f(self)
            # We can now output some previously silenced debug output
            for debug_log in self.debug_output:
                logger.debug("[WebUI] debug: %s", debug_log)
            del self.debug_output
            logger.info("loaded modules %s", self.modules)

        else:
            self.debug_output = []
            logger.info("configured modules %s", [m.get_name() for m in self.modules])
            logger.info("my name: %s", self.name)

            self.modules_manager = ModulesManager(self)
            # self.modules_manager.modules = self.modules

            # # Ok now start, or restart the WebUI modules!
            # self.do_load_modules(self.modules)
            # # and start external modules too
            # self.modules_manager.start_external_instances()

            # This function is loading all the installed 'webui' daemon modules...
            # self.do_load_modules(self.modules)
            if self.modules_manager.load_and_init(self.modules):
                if self.modules_manager.instances:
                    logger.info("I correctly loaded my modules: [%s]",
                                ','.join([inst.name for inst in self.modules_manager.instances]))
                else:
                    logger.info("I do not have any module")
            else:  # pragma: no cover, not with unit tests...
                logger.error("Errors were encountered when checking and loading modules:")
                for msg in self.modules_manager.configuration_errors:
                    logger.error(msg)

            if self.modules_manager.configuration_warnings:  # pragma: no cover, not tested
                for msg in self.modules_manager.configuration_warnings:
                    logger.warning(msg)

            logger.info("imported %d modules", len(self.modules_manager.instances))

            for inst in self.modules_manager.instances:
                logger.info("loading %s", inst.get_name())
                f = getattr(inst, 'load', None)
                if f and callable(f):
                    logger.info("running module load function")
                    f(self)
            logger.info("loaded modules %s", [m.get_name() for m in self.modules])

            # We can now output some previously silenced debug output
            for debug_log in self.debug_output:
                logger.debug("debug: %s", debug_log)
            del self.debug_output

        if not os.path.exists(bottle.TEMPLATE_PATH[0]):
            logger.error("The view path do not exist at %s", bottle.TEMPLATE_PATH)
            sys.exit(2)

        # Load internal sub modules
        self.auth_module = AuthMetaModule(AuthMetaModule.find_modules(
            self.modules_manager.get_internal_instances()), self)
        self.prefs_module = PrefsMetaModule(PrefsMetaModule.find_modules(
            self.modules_manager.get_internal_instances()), self)
        self.logs_module = LogsMetaModule(LogsMetaModule.find_modules(
            self.modules_manager.get_internal_instances()), self)
        self.graphs_module = GraphsMetaModule(GraphsMetaModule.find_modules(
            self.modules_manager.get_internal_instances()), self)
        self.helpdesk_module = HelpdeskMetaModule(HelpdeskMetaModule.find_modules(
            self.modules_manager.get_internal_instances()), self)

        # Data manager
        self.datamgr = WebUIDataManager(self.rg, self.problems_business_impact,
                                        self.important_problems_business_impact,
                                        self.disable_inner_problems_computation)
        self.helper = helper

        # Check directories
        # We check if the photo directory exists. If not, try to create it
        for directory in [self.share_dir, self.photo_dir, self.config_dir]:
            logger.debug("Checking dir: %s", directory)
            if not os.path.exists(directory):
                try:
                    # os.mkdir(dir)
                    os.makedirs(directory, mode=0o777)
                    logger.info("Created directory: %s", directory)
                except Exception as exp:
                    logger.error("Directory creation failed: %s, error: %s", directory, str(exp))
            else:
                logger.debug("Still existing directory: %s", directory)

        # Bottle objects
        # todo: remove this, storing the current request is not useful :/
        self.request = bottle.request
        self.response = bottle.response

        try:
            # I register my exit function
            self.set_exit_handler()

            # Set our current installation path to the Python Path
            # This will allow to resolve some tricky importation ;)
            sys.path.append(os.path.abspath(os.path.dirname(__file__)))

            # First load the additional plugins so they will have the lead on URI routes
            if self.additional_plugins_dir:
                self.load_plugins(self.additional_plugins_dir)

            # Modules can also override some views if need
            for inst in self.modules_manager.instances:
                f = getattr(inst, 'get_webui_plugins_path', None)
                if f and callable(f):
                    mod_plugins_path = os.path.abspath(f(self))
                    self.load_plugins(mod_plugins_path)

            # Then look at the plugins into core and load all we can there
            core_plugin_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'plugins')
            self.load_plugins(core_plugin_dir)

            # Declare the whole app static files AFTER the plugin ones
            self.declare_common_static()

            logger.debug("declared routes:")
            for route in webui_app.routes:
                logger.debug("- %s", route.__dict__)
                if route.name:
                    if route.config:
                        logger.debug("- %s for %s, configuration: %s",
                                     route.name, route.rule, route.config)
                    else:
                        logger.debug("- %s for %s", route.name, route.rule)

            # Launch the data thread ...
            self.my_data_thread = threading.Thread(None, self.manage_brok_thread, 'datathread')
            self.my_data_thread.start()
            # TODO: look for alive and killing

            # Launch the Alignak arbiter data thread ...
            if self.alignak and self.alignak_endpoint:
                logger.info("Starting Alignak arbiter check thread...")
                self.my_fmwk_thread = threading.Thread(None, self.fmwk_thread, 'fmwk_hread')
                self.my_fmwk_thread.start()
            # TODO: have a Shinken polling thread too may be a great idea?

            logger.info("starting Web UI server on %s:%d ...", self.host, self.port)
            bottle.TEMPLATES.clear()
            webui_app.run(host=self.host, port=self.port,
                          server=self.http_backend, **self.serveropts)
        except Exception as exp:
            logger.error("do_main exception: %s", str(exp))
            logger.error("traceback: %s", traceback.format_exc())
            sys.exit(1)

    def push_external_command(self, e):  # pylint: disable=global-statement
        """
            A plugin sends us an external command. Notify this command
            to the monitoring framework ...
        """
        logger.debug("Got an external command: %s", e.__dict__)
        if self.alignak:
            logger.info("Sending a command to Alignak")
            req = requests.Session()
            raw_data = req.get("%s/command" % self.alignak_endpoint,
                               params={'command': e.cmd_line})
            logger.debug("Result: %s", raw_data.content)
            logger.info("Sent")
            return

        try:
            logger.info("Sending a command to Shinken")
            self.from_q.put(e)
            logger.info("Sent")
        except Exception as exp:
            logger.error("[WebUI] External command push, exception: %s", str(exp))

    def wait_for_no_writers(self):
        """
        Shinken broker module only
        -----------------------------------------------------
        It will say if we can launch a page rendering or not.
        We can only if there is no writer running from now

        :return:
        """
        while not self.interrupted:
            self.global_lock.acquire()
            # We will be able to run
            if self.nb_writers == 0:
                # Ok, we can run, register us as readers
                self.nb_readers += 1
                self.global_lock.release()
                break
            # Oups, a writer is in progress. We must wait a bit
            self.global_lock.release()
            # Before checking again, we should wait a bit
            # like 1ms
            time.sleep(0.001)

    def wait_for_no_readers(self):
        """
        Shinken broker module only
        -----------------------------------------------------
        It will say if we can launch a brok management or not
        We can only if there is no readers running from now

        :return:
        """
        start = time.time()
        while not self.interrupted:
            self.global_lock.acquire()
            # We will be able to run
            if self.nb_readers == 0:
                # Ok, we can run, register us as writers
                self.nb_writers += 1
                self.global_lock.release()
                break
            # Ok, we cannot run now, wait a bit
            self.global_lock.release()
            # Before checking again, we should wait a bit (1ms)
            time.sleep(0.001)
            # We should warn if we cannot update broks
            # for more than 30s because it can be not good
            if time.time() - start > 30:
                logger.warning("wait_for_no_readers, we are in lock/read since more than 30s!")
                start = time.time()

    def lockable_function(self, f):
        """
        Shinken broker module only
        -----------------------------------------------------
        We want a lock manager version of the plugin functions

        :param f:
        :return:
        """
        def lock_version(**args):
            self.wait_for_no_writers()
            try:
                return f(**args)
            finally:
                # We can remove us as a reader from now. It's NOT an atomic operation
                # so we REALLY not need a lock here (yes, I try without and I got
                # a not so accurate value there....)
                self.global_lock.acquire()
                self.nb_readers -= 1
                self.global_lock.release()

        return lock_version

    def manage_brok_thread(self):
        """
        Shinken broker module only
        -----------------------------------------------------
        It's the thread function that will get broks and update data. Will lock the whole thing
        while updating

        :return:
        """
        logger.debug("manage_brok_thread start ...")

        while not self.interrupted:
            start = time.clock()
            # Get messages in the queue
            try:
                message = self.to_q.get()
            except EOFError:
                # Broken queue ... the broker deleted the module queue
                time.sleep(1.0)
                continue
            except Exception as exp:
                logger.warning("Broken module queue: %s", str(exp))
                time.sleep(1.0)
                continue

            # try to relaunch dead module
            # self.check_and_del_zombie_modules()

            if not message:
                continue

            logger.debug("manage_brok_thread got %d broks, queue length: %d",
                         len(message), self.to_q.qsize())
            for b in message:
                b.prepare()
                self.wait_for_no_readers()
                try:
                    self.rg.manage_brok(b)

                    # Question:
                    # Do not send broks to internal modules ...
                    # No internal WebUI modules have something to do with broks!
                    for mod in self.modules_manager.get_internal_instances():
                        try:
                            mod.manage_brok(b)
                        except Exception as exp:
                            logger.warning("The mod %s raise an exception: %s, "
                                           "I'm tagging it to restart later",
                                           mod.get_name(), str(exp))
                            logger.debug("Back trace of this kill: %s", traceback.format_exc())
                            self.modules_manager.set_to_restart(mod)
                except Exception as exp:
                    logger.error("manage_brok_thread exception: %s", str(exp))
                    logger.error("Exception type: %s", type(exp))
                    logger.error("Back trace of this kill: %s", traceback.format_exc())
                    # No need to raise here, we are in a thread, exit!
                    os.exit(2)
                finally:
                    # logger.debug("manage_brok_thread finally")
                    # We can remove us as a writer from now. It's NOT an atomic operation
                    # so we REALLY not need a lock here (yes, I try without and I got
                    # a not so accurate value there....)
                    self.global_lock.acquire()
                    self.nb_writers -= 1
                    self.global_lock.release()

            logger.debug("time to manage %d broks (time %.2gs)",
                         len(message), time.clock() - start)
        logger.info("Exiting the manage broks thread...")

    def fmwk_thread(self):
        """A thread function that periodically gets its state from the Alignak arbiter

        This function gets Alignak status in our alignak_livestate and
        then it gets the Alignak events in our alignak_events queue
        """
        logger.debug("fmwk_thread start ...")

        req = requests.Session()
        alignak_timestamp = 0
        errors_count = 0
        while not self.interrupted:
            # Get Alignak status
            try:
                raw_data = req.get("%s/status"
                                   % self.alignak_endpoint)
                data = raw_data.json()
                self.alignak_livestate = data.get('livestate', 'Unknown')
                logger.debug("[fmwk_thread] Livestate: %s", data)
            except Exception as exp:
                errors_count += 1
                logger.debug("[fmwk_thread] get status, exception: %s", exp)
                if errors_count > 10:
                    errors_count = 0
                    logger.info("[fmwk_thread] get status (more than 10 errors), "
                                "exception: %s", exp)

            try:
                # Get Alignak most recent events
                # count is the maximum number of events we will be able to get
                # timestamp is the most recent event we got
                raw_data = req.get("%s/events_log?details=1&count=%d&timestamp=%d"
                                   % (self.alignak_endpoint, self.alignak_events_count,
                                      alignak_timestamp))
                data = raw_data.json()
                logger.debug("[fmwk_thread] got %d event log", len(data))
                for log in data:
                    # Data contains: {
                    #   u'date': u'2018-11-24 16:28:03', u'timestamp': 1543073283.434844,
                    #   u'message': u'RETENTION LOAD: scheduler-master', u'level': u'info'
                    # }
                    alignak_timestamp = max(alignak_timestamp, log['timestamp'])
                    if log not in self.alignak_events:
                        logger.debug("[fmwk_thread] New event log: %s", log)
                        self.alignak_events.appendleft(log)
                logger.debug("[fmwk_thread] %d log events", len(self.alignak_events))
            except Exception as exp:
                errors_count += 1
                logger.debug("[fmwk_thread] get events, exception: %s", exp)
                if errors_count > 10:
                    errors_count = 0
                    logger.info("[fmwk_thread] get events (more than 10 errors), "
                                "exception: %s", exp)

            # Sleep for a while...
            time.sleep(self.alignak_check_period)
        logger.info("Exiting the framework status thread...")

    def load_plugins(self, plugin_dir):
        """
        Here we will load all plugins (pages) under the webui/plugins
        directory. Each one can have a page, views and htdocs dir that we must
        route correctly

        :param plugin_dir:  the directory where to search for plugins
        :return:
        """
        logger.info("load plugins directory: %s", plugin_dir)

        # Load plugin directories
        if not os.path.exists(plugin_dir):
            logger.error("load plugins directory does not exist: %s", plugin_dir)
            return

        plugin_dirs = [
            fname for fname in os.listdir(plugin_dir)
            if fname not in ['__pycache__'] and os.path.isdir(os.path.join(plugin_dir, fname))]

        # todo: Hmmm..... confirm it is necessary!
        # sys.path.append(plugin_dir)

        # Try to import all found plugins
        for fdir in plugin_dirs:
            self.load_plugin(fdir, plugin_dir)

    def load_plugin(self, fdir, plugin_dir):
        """Load a WebUI plugin"""
        logger.debug("loading plugin %s ...", fdir)
        try:
            # Put the full qualified path of the module we want to load
            # for example we will give  webui/plugins/eltdetail/
            mod_path = os.path.join(plugin_dir, fdir)
            # Then we load the plugin.py inside this directory
            m = imp.load_module(fdir, *imp.find_module(fdir, [mod_path]))
            m_dir = os.path.abspath(os.path.dirname(m.__file__))

            for (f, entry) in list(m.pages.items()):
                logger.debug("entry: %s", entry)
                # IMPORTANT: apply VIEW BEFORE route!
                view = entry.get('view', None)
                if view:
                    f = bottle.view(view)(f)

                # Maybe there is no route to link, so pass
                route = entry.get('route', None)
                name = entry.get('name', None)
                search_engine = entry.get('search_engine', False)
                if route:
                    method = entry.get('method', 'GET')

                    # Ok, we will just use the lock for all
                    # plugin page, but not for static objects
                    # so we set the lock at the function level.
                    _ = webui_app.route(route, callback=self.lockable_function(f),
                                        method=method, name=name, search_engine=search_engine)

                # If the plugin declare a static entry, register it
                # and remember: really static! because there is no lock
                # for them!
                static = entry.get('static', False)
                if static:
                    self.add_static_route(fdir, m_dir)

                # It's a valid widget entry if it got all data, and at least one route
                # ONLY the first route will be used for Add!
                widget_lst = entry.get('widget', [])
                widget_name = entry.get('widget_name', None)
                if widget_name and widget_lst and route:
                    for place in widget_lst:
                        if place not in self.widgets:
                            self.widgets[place] = []
                        self.widgets[place].append({
                            'widget_name': widget_name,
                            'widget_alias': entry.get('widget_alias', widget_name),
                            'widget_icon': entry.get('widget_icon', 'plus'),
                            'widget_desc': entry.get('widget_desc', widget_name),
                            'base_uri': route,
                            'widget_picture': entry.get('widget_picture', None),
                            'deprecated': entry.get('deprecated', False)
                        })

            # And we add the views dir of this plugin in our TEMPLATE
            # PATH
            logger.debug("plugin views dir: %s", os.path.join(m_dir, 'views'))
            bottle.TEMPLATE_PATH.append(os.path.join(m_dir, 'views'))

            # And finally register me so the pages can get data and other
            # useful stuff
            m.app = self

            # Load/set plugin configuration
            f = getattr(m, 'load_config', None)
            if f and callable(f):
                logger.debug("calling plugin %s, load configuration", fdir)
                f(self)

            logger.info("loaded plugin %s", fdir)

        except Exception as exp:
            logger.error("loading plugin %s, exception: %s", fdir, str(exp))

    # pylint: disable=no-self-use
    def get_url(self, name):
        """Get URL for a named route"""
        logger.debug("get_url for '%s'", name)

        try:
            return webui_app.get_url(name)
        except Exception as exp:
            logger.error("get_url, exception: %s", str(exp))

        return '/'

    def add_static_route(self, fdir, m_dir):  # pylint: disable=no-self-use
        """
        Add static route in the Web server

        :param fdir:
        :param m_dir:
        :return:
        """
        logger.debug("add static route: %s", fdir)
        static_route = '/static/' + fdir + '/:path#.+#'

        def plugin_static(path):
            return bottle.static_file(path, root=os.path.join(m_dir, 'htdocs'))
        webui_app.route(static_route, callback=plugin_static)

    def declare_common_static(self):
        # pylint: disable=unused-variable
        """Declare the common static routes"""
        @webui_app.route('/static/photos/:path#.+#')
        def give_photo(path):
            # If the file really exist, give it. If not, give a dummy image.
            if os.path.exists(os.path.join(self.photo_dir, path + '.png')):
                return bottle.static_file(path + '.png', root=self.photo_dir)

            return bottle.static_file('images/default_user.png', root=htdocs_dir)

        @webui_app.route('/static/logo/:path#.+#')
        def give_logo(path):
            """
            Returns the configured company logo if it exists, else
            it returns the logo according to the Shinken/Alignak framework configuration

            The company logo must be a png file located in the configured `photos_dir`
            :return:
            """
            # If the file really exist, give it. If not, give a dummy image.
            if os.path.exists(os.path.join(self.photo_dir, path + '.png')):
                return bottle.static_file(path + '.png', root=self.photo_dir)

            if ALIGNAK:
                return bottle.static_file('images/logos/logo_alignak.png', root=htdocs_dir)

            return bottle.static_file('images/logos/logo_shinken.png', root=htdocs_dir)

        @webui_app.route('/tag/:path#.+#')
        def give_tag(path):
            # TODO: Should be more logical to locate tags images in tags directory !
            # tag_path = "/images/tags/%s" % path
            # BUT: implies modifications in all Shinken packages ...

            # If a tag image (tag.png) exists in the share dir, give it ...
            tag_path = "%s/images/sets/%s" % (self.share_dir, path)
            logger.debug("searching tag: %s", os.path.join(tag_path, 'tag.png'))
            if os.path.exists(os.path.join(tag_path, 'tag.png')):
                return bottle.static_file('tag.png', root=tag_path)

            # Default tags icons are located in images/tags directory ...
            tag_path = "%s/images/tags/%s" % (htdocs_dir, path)
            logger.debug("searching for: %s", os.path.join(tag_path, 'tag.png'))
            if os.path.exists(os.path.join(tag_path, 'tag.png')):
                return bottle.static_file('tag.png', root=tag_path)

            return bottle.static_file('images/default_tag.png', root=htdocs_dir)

        # Route static files css files
        @webui_app.route('/static/:path#.+#')
        def server_static(path):
            # By default give from the root in bottle_dir/htdocs. If the file is missing,
            # search in the share dir
            # TODO: should be more logical to search in share_dir first ?
            root = htdocs_dir
            p = os.path.join(root, path)
            if not os.path.exists(p):
                root = self.share_dir
            return bottle.static_file(path, root=root)

        @webui_app.route('/favicon.ico')
        def give_favicon():
            """
            Returns the favicon path according to the Shinken/Alignak framework configuration
            :return:
            """
            if ALIGNAK:
                return bottle.static_file('alignak.ico', root=os.path.join(htdocs_dir, 'images/logos'))

            return bottle.static_file('shinken.ico', root=os.path.join(htdocs_dir, 'images/logos'))

        # And add the opensearch xml
        @webui_app.route('/opensearch.xml')
        def give_opensearch():
            base_url = self.request.url.replace('opensearch.xml', '')
            response.headers['Content-Type'] = 'text/xml'
            return bottle.template('opensearch', base_url=base_url)

        @webui_app.route('/modal/:path#.+#')
        def give_modal(path):
            logger.debug("get modal window content: %s", path)
            return bottle.template('modal_' + path)

    def check_authentication(self, username, password):
        """
        Check if provided username/password is accepted for login the Web UI

        Several steps:
        1/ one of the WebUI modules providing a 'check_auth' method must authenticate the user
        2/ username must be in the known contacts of Shinken

        :param username:
        :param password:
        :return:
        """
        logger.info("Checking authentication for user: %s", username)
        self.user_session = None
        self.user_info = None

        logger.info("Requesting authentication for user: %s", username)
        user = self.auth_module.check_auth(username, password)
        if user:
            # Check existing contact ...
            c = self.datamgr.get_contact(name=username)
            if not c:
                logger.error("You need to have a contact having the same name as your user: %s",
                             username)
                return False

            user = User.from_contact(c)

            self.user_session = self.auth_module.get_session()
            logger.info("User session: %s", self.user_session)
            self.user_info = self.auth_module.get_user_info()
            logger.info("User information: %s", self.user_info)

            if self.user_session and self.user_info:
                user.set_information(self.user_session, self.user_info)

            return True

        logger.warning("The user '%s' has not been authenticated.", username)
        return False

    def can_action(self, username=None):
        """
        Current user can launch commands ?
        If username is provided, check for the specified user ...

        :param username:
        :return:
        """
        if username:
            user = User.from_contact(self.datamgr.get_contact(name=username))
        else:
            user = request.environ.get('USER', None)

        try:
            retval = user and ((not self.manage_acl)
                               or user.is_administrator()
                               or user.is_commands_allowed())
        except Exception:  # pylint: disable=broad-except
            retval = False
        return retval

    def get_ui_external_links(self):
        """
        External UI links from other modules
        ------------------------------------------------------------------------------------------
        Web UI modules may implement a 'get_external_ui_link' function to provide an extra menu
        in the Web UI. This function must return:
        {'label': 'Menu item', 'uri': 'http://...'}

        :return:
        """
        logger.debug("Fetching UI external links ...")

        lst = []
        for mod in self.modules_manager.get_internal_instances():
            try:
                f = getattr(mod, 'get_external_ui_link', None)
                if f and callable(f):
                    lst.append(f())
            except Exception as exp:
                logger.warning("Warning: The mod %s raised an exception when calling "
                               "its get_external_ui_link function: %s, ", mod.get_name(), str(exp))

        return lst

    def get_search_string(self):
        """Return the search query from get parameters."""
        search_params = self.request.GET.getall('search')
        if search_params:
            return ' '.join(self.request.GET.getall('search'))

        return ''

    def update_search_string_with_default_search(self, requested_search, default_search='',
                                                 redirect=True):
        search = default_search if requested_search is None else requested_search

        if search != requested_search:
            if redirect:
                self.bottle.redirect("?search=%s" % search)

        return search

    # pylint: disable=dangerous-default-value
    def update_search_string_with_default_filters(self, requested_search, filters=[], prepend=True,
                                                  redirect=True):
        search = requested_search or ''

        if prepend:
            for f in reversed(filters):
                if f not in search:
                    search = f + " " + search
        else:
            for f in filters:
                if f not in search:
                    search = search + " " + f

        if search != requested_search:
            if redirect:
                self.bottle.redirect("?search=%s" % search)

        return search

    def update_search_string_with_default_bi_filter(self, requested_search, redirect=True):
        search = requested_search or ''

        if "bi:" not in requested_search:
            search = requested_search + " bi:>=%d" % self.problems_business_impact

        if search != requested_search:
            if redirect:
                self.bottle.redirect("?search=%s" % search)

        return search

    def get_and_update_search_string_with_problems_filters(self, redirect=True):
        problems_filters = [
            'isnot:UP', 'isnot:OK', 'isnot:PENDING', 'isnot:ACK', 'isnot:DOWNTIME', 'isnot:SOFT'
        ]

        requested_search = self.get_search_string()

        search = self.update_search_string_with_default_search(requested_search,
                                                               self.PROBLEMS_SEARCH_STRING,
                                                               redirect=False)
        search = self.update_search_string_with_default_filters(search, problems_filters,
                                                                redirect=False)
        search = self.update_search_string_with_default_bi_filter(search,
                                                                  redirect=False)

        if search != requested_search:
            if redirect:
                self.bottle.redirect("?search=%s" % search)

        return search

    def redirect404(self, msg="Not found"):
        raise self.bottle.HTTPError(404, msg)

    def redirect403(self, msg="Forbidden"):
        raise self.bottle.HTTPError(403, msg)

    # pylint: disable=no-self-use
    def get_user(self):
        return request.environ.get('USER', None)

    def get_plugin_config(self, plugin):
        config = {'name': plugin}
        for prop in self.my_configuration.__dict__:
            if not prop.startswith('plugin.'):
                continue

            parameter = prop.replace('plugin.', '')
            # Get the plugin parameters
            if parameter.startswith(plugin + '.'):
                config[parameter.replace(plugin + '.', '')] = getattr(self.my_configuration, prop)
        return config

    def get_config(self, key=None, value=None):
        if not key:
            return self.my_configuration

        return getattr(self.my_configuration, key, value)


@webui_app.hook('before_request')
def login_required():
    # :COMMENT:maethor:150718: This hack is crazy, but I don't know how to do it properly
    app = bottle.BaseTemplate.defaults['app']

    logger.debug("login_required, requested URL: %s", request.urlparts.path)
    # No static route need user authentication...
    if request.urlparts.path.startswith('/static'):
        return
    # Nor some specific routes
    if request.urlparts.path in ['/favicon.ico', '/gotfirstdata',
                                 '/user/get_pref', '/user/set_pref',
                                 app.get_url("Logout"),
                                 app.get_url("GetLogin"),
                                 app.get_url("SetLogin")]:
        return
    # No static route need user authentication...
    if request.urlparts.path in [app.get_url("Loading")]:
        if app.rg.initialized:
            time.sleep(2.0)
            bottle.redirect(app.get_url("Dashboard"))
        return

    logger.debug("login_required for %s, getting user cookie ...", request.urlparts.path)
    cookie_value = bottle.request.get_cookie(str(app.session_cookie), secret=app.auth_secret)
    if cookie_value:
        app.user_session = cookie_value.get('session', '')
        logger.debug("user session: %s", app.user_session)
        app.user_info = cookie_value.get('info', '')
        logger.debug("user info: %s", app.user_info)
        contact_name = cookie_value.get('login', cookie_value)
        logger.debug("user login: %s", contact_name)
    else:
        # Only the /currently should be accessible to anonymous users
        contact_name = 'anonymous'
        if not app.allow_anonymous:
            logger.info("anonymous access is forbidden. Redirecting to %s", app.get_url("GetLogin"))
            bottle.redirect(app.get_url("GetLogin"))
        if request.urlparts.path not in [app.get_url("Currently")]:
            logger.info("anonymous access is allowed only for the dashboard, not for %s",
                        request.urlparts.path)
            bottle.redirect(app.get_url("GetLogin"))

    contact = app.datamgr.get_contact(name=contact_name)
    if not contact:
        # If we got the data from our schedulers, the contact does not exist
        if app.rg.initialized:
            logger.info("contact does not exist: %s", contact_name)
            bottle.redirect(app.get_url("GetLogin"))
        else:
            # we did not yet received all data
            bottle.redirect(app.get_url("Loading"))

    user = User.from_contact(contact)
    if app.user_session and app.user_info:
        user.set_information(app.user_session, app.user_info)

    logger.debug("update current user: %s", user)
    request.environ['USER'] = user
