==================
My comments - Fred
==================


Test environment
================

Get Shinken
-----------
Clone the Shinken repository:
```
   cd /home/fred 
   git clone https://github.com/naparuba/shinken
```

Update version
--------------

In *shinken/bin/__init__.py*, set version:

```
   VERSION = "2.4.3 Fred (master branch)"
```

Then 
```
   cd /home/fred/shinken
   sudo python setup.py install
```

Update configuration
--------------------

Clone the Shinken Web UI repository:
```
   cd /home/fred 
   git clone https://github.com/mohierf/mod-webui
```

Update the shinken systemctl script to change the location of your configuration:
```
   ## These vars will override the hardcoded ones in init script ##
   ### Fred ETC=/etc/shinken

   # Use the Shinken test configuration from the Shinken Web UI... why not :)
   ETC=/home/fred/mod-webui/test/test-configurations/shinken/etc
```

Run Shinken
-----------

```
   # Perhaps some permissions are missing in the /var folders with the current account :/
   # But it is not a problem... we only check the configuration is valid
   shinken-arbiter -c /home/fred/mod-webui/test/test-configurations/shinken/etc/shinken.cfg

   # Start the shinken services
   sudo systemctl start shinken
```


Note the many ugly and useful logs in the most recent verstion:
``` 
==> /var/log/shinken/reactionnerd.log <==
[1574883939] INFO: [Shinken] Cleaning BrokHandler <shinken.log.BrokHandler object at 0x7fe963e33bd0> from logger.handlers..
[1574883939] INFO: [Shinken] Cleaning BrokHandler <shinken.log.BrokHandler object at 0x7fe963e33bd0> from logger.handlers..
[1574883939] INFO: [Shinken] Cleaning BrokHandler <shinken.log.BrokHandler object at 0x7fe963e33bd0> from logger.handlers..
```

```
   # Stop the shinken services
   sudo systemctl stop shinken
```


Install and configure supervisor
--------------------------------

Using only the installed init.d services is not easy to add some new daemons ... so:
``` 
   sudo apt-get install supervisor
```

Then copy all the files included in the *etc/supervisor/conf.d* directory to the */etc/supervisor/conf.d* and then restart the supervisor service.

It is also possible to run the supervisord as a foreground process with the provided main configuration file:
```
   cd ~
   cd mod-webui/test/test-configurations/shinken
   sudo supervisord -n -c etc/supervisor/supervisor.conf
```


