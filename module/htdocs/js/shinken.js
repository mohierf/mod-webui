/*Copyright (C) 2009-2019 :
     Gabes Jean, naparuba@gmail.com
     Gerhard Lausser, Gerhard.Lausser@consol.de
     Gregory Starck, g.starck@gmail.com
     Hartmut Goebel, h.goebel@goebel-consult.de
     Andreas Karfusehr, andreas@karfusehr.de
     Frederic Mohier, frederic.mohier@gmail.com

 This file is part of Shinken.

 Shinken is free software: you can redistribute it and/or modify
 it under the terms of the GNU Affero General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 Shinken is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU Affero General Public License for more details.

 You should have received a copy of the GNU Affero General Public License
 along with Shinken.  If not, see <http://www.gnu.org/licenses/>.
*/

// Former shinken-refresh.js
// -----
var refresh_logs=false;

/* By default, we set the page to reload each period defined in WebUI configuration */
var nb_refresh_try = 0;
if (! sessionStorage.getItem("refresh_enabled")) {
   if (refresh_logs) console.debug("Refresh active storage does not exist");
   // Store default value ...
   sessionStorage.setItem("refresh_enabled", app_refresh_period==0 ? '0' : '1');
}

if (refresh_logs) console.debug("Refresh active is ", sessionStorage.getItem("refresh_enabled"));

if (sessionStorage.getItem("refresh_enabled") == '1') {
    enable_refresh();
} else {
    disable_refresh();
}


/*
 * This function is called on each refresh of the current page.
 * ----------------------------------------------------------------------------
 *  It is to be noted that this function makes an Ajax call on the current URL
 * to get the new version of the current page. This is the most interesting
 * strategy for refreshing ... but the drawbacks are that it gets an entire
 * Html page including <head>, <body> and ... <script>
 *
 *  The only elements that are replaced in the current page are :
 * - #page-content
 * - #overall-hosts-states
 * - #overall-services-states
 * => These elements are the real "dynamic" elements in the page ...
 *
 *  Because of the new received Html inclusion method, the embedded scripts
 * are not executed ... this implies that the necessary scripts for refresh
 * management are to be included in this function in the always Ajax promise!
 * ---------------------------------------------------------------------------
 */
var processing_refresh = false;
var nb_refresh = 0;
function do_refresh(forced){
   if (processing_refresh) {
      if (refresh_logs) console.debug("Avoid simultaneous refreshes ...");
      return;
   }
   if (refresh_logs) console.debug("Refreshing: ", document.URL);

   // Refresh starting indicator ...
   $('#header_loading').addClass('fa-spin');
   processing_refresh = true;

   // Because of mem leak, we avoid to do too much soft refreshes and sometimes we force a full reload
   if (nb_refresh > 10){
       if (document.visibilityState == 'hidden'){
           if (refresh_logs) console.debug("Reloading page: ", document.URL);
           location.reload();
       }
   }
   nb_refresh += 1;

   $.ajax({
     url: document.URL,
     method: "get",
     dataType: "html"
   })
   .done(function( html, textStatus, jqXHR ) {
      /* This var declaration includes the response in the document body ... bad luck!
       * ------------------------------------------------------------------------------
       * In fact, each refresh do include all the received Html and then we filter
       * what we are interested in ... not really efficient and quite buggy !
       */
      var $response = $('<div />').html(html);
      // Refresh current page content ...
      $('#page-content').html($response.find('#page-content').html());

      // Refresh header bar hosts/services state ...
      if ($('#overall-hosts-states').length > 0) {
         $('#overall-hosts-states').html($response.find('#overall-hosts-states').html());
         $('#hosts-states-popover-content').html($response.find('#hosts-states-popover-content').html());
         $('#overall-services-states').html($response.find('#overall-services-states').html());
         $('#services-states-popover-content').html($response.find('#services-states-popover-content').html());
      }

      // Refresh Dashboard currently ...
      if (dashboard_currently) {
         $('#one-eye-overall').html($response.find('#one-eye-overall').html());
         $('#one-eye-icons').html($response.find('#one-eye-icons').html());
         $('#livestate-graphs').html($response.find('#livestate-graphs').html());
      }

      // Clean the DOM after refresh update ...
      $response.remove();

/*
      @mohierf: for future refresh implementation ...
      -----------------------------------------------
      // The solution is to not parse received Html with jQuery and extract some parts
      // of the data using regexp ...
      var content = html.match(/<!--begin-page-content--[^>]*>((\r|\n|.)*)<!--end-page-content--/m);
      content = content ? content[1] : 'Refresh for page content failed!';
      var script = content.match(/<script[^>]*>((\r|\n|.)*)<\/script/m);
      script = script ? script[1] : 'Refresh for hosts states failed!';
      var $response = $('<div />').html(content);
      $('#page-content').html($response.find('#page-content').html()).append('<script>'+script+'</script>');

      var content = html.match(/<!--begin-hosts-states--[^>]*>((\r|\n|.)*)<!--end-hosts-states--/m);
      content = content ? content[1] : 'Refresh for hosts states failed!';
      var script = content.match(/<script[^>]*>((\r|\n|.)*)<\/script/m);
      script = script ? script[1] : 'Refresh for hosts states failed!';
      var $response = $('<div />').html(content);
      $('#overall-hosts-states').html($response.find('#overall-hosts-states').html()).append('<script>'+script+'</script>');

      var content = html.match(/<!--begin-services-states--[^>]*>((\r|\n|.)*)<!--end-services-states--/m);
      content = content ? content[1] : 'Refresh for services states failed!';
      var script = content.match(/<script[^>]*>((\r|\n|.)*)<\/script/m);
      script = script ? script[1] : 'Refresh for hosts states failed!';
      var $response = $('<div />').html(content);
      $('#overall-services-states').html($response.find('#overall-services-states').html()).append('<script>'+script+'</script>');
*/

      // Each plugin may provide its on_page_refresh function that will be called here ...
      if (typeof on_page_refresh !== 'undefined' && $.isFunction(on_page_refresh)) {
         if (refresh_logs) console.debug('Calling page refresh function ...');
         on_page_refresh(forced);
      }

      if (typeof display_charts !== 'undefined' && $.isFunction(display_charts)) {
         if (refresh_logs) console.debug('Calling display charts function ...');
         display_charts();
      }

      /*
      // Refresh bindings of actions buttons ...
      if (typeof bind_actions !== 'undefined' && $.isFunction(bind_actions)) {
         if (refresh_logs) console.debug('Calling actions bindings function ...', bind_actions);
         bind_actions();
      }
      */

      tooltips();

      if (typeof headerPopovers !== 'undefined') {
          headerPopovers();
      }

      // Look at the hash part of the URI. If it match a nav name, go for it
      if (location.hash.length > 0) {
         if (refresh_logs) console.debug('Displaying tab: ', location.hash)
         $('.nav-tabs li a[href="' + location.hash + '"]').trigger('click');
      } else {
         if (refresh_logs) console.debug('Displaying first tab')
         $('.nav-tabs li a:first').trigger('click');
      }
   })
   .fail(function( jqXHR, textStatus, errorThrown ) {
      if (refresh_logs) console.error('Done: ', jqXHR, textStatus, errorThrown);
   })
   .always(function() {
      // Refresh is finished
      $('#header_loading').removeClass('fa-spin');
      processing_refresh = false;
   });
}


function check_refresh(){
   // We first test if the backend is available
   $.ajax({
      url: '/gotfirstdata?callback=?',
      dataType: "jsonp",
      method: "GET"
   })
   .done(function( data, textStatus, jqXHR ) {
      if (sessionStorage.getItem("refresh_enabled") === '1') {
         // Go Refresh
         do_refresh();
      }
   })
   .fail(function( jqXHR, textStatus, errorThrown ) {
      if (refresh_logs) console.error('UI backend is not available for refresh, retrying later ...');
      if (nb_refresh_try > 0){
          alertify.log("The Web UI backend is not available", "info", 5000);
      }
      nb_refresh_try += 1;
   });
}


function disable_refresh() {
   if (refresh_logs) console.debug("Stop refresh");
   $('#header_loading').addClass('fa-striked');
   $('#header_loading').parent().data('tooltip', false)
                                .attr('data-original-title', "Enable auto-refresh")
                                .tooltip({html: 'true', placement: 'bottom'});
   //$('#header_loading').parent().prop('title', "Enable auto-refresh");
   sessionStorage.setItem("refresh_enabled", '0');
}


function enable_refresh() {
   if (refresh_logs) console.debug("Stop refresh");
   $('#header_loading').removeClass('fa-striked');
   $('#header_loading').parent().data('tooltip', false)
                                .attr('data-original-title', "Disable auto-refresh")
                                .tooltip({html: 'true', placement: 'bottom'});
   sessionStorage.setItem("refresh_enabled", '1');
}


$(document).ready(function(){
   // Start refresh periodical check ...
   setInterval("check_refresh();", app_refresh_period * 1000);

   // Toggle refresh ...
   $('body').on("click", '.js-toggle-page-refresh', function (e, data) {
      if (sessionStorage.getItem("refresh_enabled") == '1') {
         disable_refresh();
      } else {
         enable_refresh();
      }
      if (refresh_logs) console.debug("Refresh active is ", sessionStorage.getItem("refresh_enabled"));
   });

});

// Former shinken-actions.js
// -----
var actions_logs=false;

/**
 * Get current user preference value:
 * - key
 * - callback function called after data are posted
**/
function get_user_preference(key, callback) {

   $.get("/user/get_pref", { 'key' : key }, function( data, textStatus, jqXHR ) {
      if (actions_logs) console.debug('Got: '+key, data, textStatus);

      if (data && typeof callback !== 'undefined' && $.isFunction(callback)) {
         if (actions_logs) console.debug('Calling callback function ...', callback);
         callback(JSON.parse(data));
      }
   });
}

/**
 * Save current user preference value:
 * - key / value
 * - callback function called after data are posted
**/
function save_user_preference(key, value, callback) {

   $.get("/user/save_pref", { 'key' : key, 'value' : value }, function() {
      if (actions_logs) console.debug('User preference saved: ', key, value);
      // raise_message_ok("User parameter saved");

      if (value && typeof callback !== 'undefined' && $.isFunction(callback)) {
         if (actions_logs) console.debug('Calling callback function ...', callback);
         callback(JSON.parse(value));
      }
   });
}

/**
 * Save common preference value
 * - key / value
 * - callback function called after data are posted
**/
function save_common_preference(key, value, callback) {

   $.get("/user/save_common_pref", { 'key' : key, 'value' : value}, function() {
      if (actions_logs) console.debug('Common preference saved: ', key, value);
      // raise_message_ok("Common parameter saved");

      if (value && typeof callback !== 'undefined' && $.isFunction(callback)) {
         if (actions_logs) console.debug('Calling callback function ...', callback);
         callback(JSON.parse(value));
      }
   });
}


/*
 * Launch the request
 */
function launch(url, response_message){
   if (actions_logs) console.debug('Launch external command: ', url);

   $.ajax({
      url: url,
      dataType: "jsonp",
      method: "GET",
      data: { response_text: response_message }
   })
   .done(function( data, textStatus, jqXHR ) {
      if (actions_logs) console.debug('Done: ', url, data, textStatus, jqXHR);
      raise_message_ok(data.text)
   })
   .fail(function( jqXHR, textStatus, errorThrown ) {
      if (actions_logs) console.error('Done: ', url, jqXHR, textStatus, errorThrown);
      raise_message_ko(textStatus);
   })
   .always(function(  ) {
      window.setTimeout(function() {
         // Refresh the current page after a short delay
         do_refresh();
      }, 5000);
   });
}


/*
 * Message raise part
 */
function raise_message_ok(text){
   alertify.log(text, "success", 5000);
}

function raise_message_ko(text){
   alertify.log(text, "error", 5000);
}


/*
 * Get element information
 */
function get_element(name) {
   var parts = name.split('/');
   var elt = {
      type : 'UNKNOWN',
      name : 'NOVALUE'
   };
   if (parts.length == 1){
      // 1 element means HOST
      elt.type = 'HOST';
      elt.name = parts[0];
   } else {
      // 2 means Service
      elt.type = 'SVC';
      elt.name = parts[0]+'/'+parts[1];

      // And now for all elements, change the / into a $SLASH$ macro
      for (var i=2; i<parts.length; i++){
         elt.name = elt.name+ '$SLASH$'+ parts[i];
      }
   }
   return elt
}

/*
 * Event handlers
 */
/* The command that will launch an event handler */
function try_to_fix(name) {
   var elt = get_element(name);
   var url = '/action/LAUNCH_'+elt.type+'_EVENT_HANDLER/'+elt.name;
   // We can launch it :)
   launch(url, elt.type+': '+name+', event handler activated');
}



/*
This is used to submit a passive check result for a particular host.
The "status_code" indicates the state of the host check and should
be one of the following: 0=UP, 1=UNREACHABLE, 2=DOWN.
The "plugin_output" argument contains the text returned from the
host check, along with optional performance data.

This is used to submit a passive check result for a particular service.
The "return_code" field should be one of the following: 0=OK,
1=WARNING, 2=CRITICAL, 3=UNKNOWN.
The "plugin_output" field contains text output from the service
check, along with optional performance data.
*/
function submit_check(name, return_code, output){
   var elt = get_element(name);
   if (elt.type == 'SVC') {
       elt.type = 'SERVICE';
   }
   var url = '/action/PROCESS_'+elt.type+'_CHECK_RESULT/'+elt.name+'/'+return_code+'/'+output;
   // We can launch it :)
   launch(url, elt.type+': '+name+', check result submitted');
}


/*
 * Launch the check_command
 */
function recheck_now(name) {
   var elt = get_element(name);
   var now = '$NOW$';
   var url = '/action/SCHEDULE_FORCED_'+elt.type+'_CHECK/'+elt.name+'/'+now;
   // We can launch it :)
   launch(url, elt.type+': '+name+', check forced');
}


/*
 * Enable/disable host/service checks
 * See #226
 */
function toggle_active_checks(name, b){
   var elt = get_element(name);

   if (actions_logs) console.debug("Toggle active checks for: ", name, ", currently: ", b)

   if (b) {
      var url = '/action/ENABLE_' + elt.type + '_CHECK/' + elt.name;
      launch(url, 'Active checks enabled');
   } else {
      var url = '/action/DISABLE_' + elt.type + '_CHECK/' + elt.name;
      launch(url, 'Active checks disabled');
   }
}
function toggle_passive_checks(name, b){
   var elt = get_element(name);

   if (actions_logs) console.debug("Toggle passive checks for: ", name, ", currently: ", b)

   if (b) {
      var url = '/action/ENABLE_PASSIVE_' + elt.type + '_CHECKS/' + elt.name;
      launch(url, 'Passive checks enabled');
   } else {
      var url = '/action/DISABLE_PASSIVE_' + elt.type + '_CHECKS/' + elt.name;
      launch(url, 'Passive checks disabled');
   }
}
function toggle_host_checks(name, b){
   var elt = get_element(name);

   if (elt.type == 'HOST') {
      if (actions_logs) console.debug("Toggle host checks for: ", name, ", currently: ", b);

      if (b) {
          var url = '/action/ENABLE_HOST_SVC_CHECKS/' + elt.name;
          launch(url, 'Host services checks enabled');
      } else {
          var url = '/action/DISABLE_HOST_SVC_CHECKS/' + elt.name;
          launch(url, 'Host services checks disabled');
      }
   }
}


/*
 * Enable/disable all notifications
 */
function toggle_all_notifications(b){
   if (actions_logs) console.debug("Toggle all notifications, currently: ", b)

   if (b) {
      var url = '/action/ENABLE_NOTIFICATIONS'
      launch(url, 'All notifications enabled');
   } else {
      var url = '/action/DISABLE_NOTIFICATIONS';
      launch(url, 'All notifications disabled');
   }
}


/*
 * Enable/disable host/service notifications
 */
function toggle_notifications(name, b){
   if (actions_logs) console.debug("Toggle notifications for: ", name, ", currently: ", b)

   var elt = get_element(name);
   // Inverse the active check or not for the element
   if (b) { // go disable
      var url = '/action/ENABLE_'+elt.type+'_NOTIFICATIONS/'+elt.name;
      launch(url, elt.type+', notifications enabled');
   } else { // Go enable
      var url = '/action/DISABLE_'+elt.type+'_NOTIFICATIONS/'+elt.name;
      launch(url, elt.type+', notifications disabled');
   }
}


/*
 * Enable/disable host/service event handler
 */
function toggle_event_handlers(name, b){
   var elt = get_element(name);
   // Inverse the event handler or not for the element
   if (b) { // go disable
      var url = '/action/ENABLE_'+elt.type+'_EVENT_HANDLER/'+elt.name;
      launch(url, elt.type+', event handler enabled');
   } else { // Go enable
      var url = '/action/DISABLE_'+elt.type+'_EVENT_HANDLER/'+elt.name;
      launch(url, elt.type+', event handler disabled');
   }
}


/*
 * Enable/disable host/service flapping detection
 */
function toggle_flap_detection(name, b){
   if (actions_logs) console.debug("Toggle flapping detection for: ", name, ", currently: ", b)

   var elt = get_element(name);
   // Inverse the flap detection for the element
   if (b) { //go disable
      var url = '/action/ENABLE_'+elt.type+'_FLAP_DETECTION/'+elt.name;
      launch(url, elt.type+', flapping detection enabled');
   } else {
      var url = '/action/DISABLE_'+elt.type+'_FLAP_DETECTION/'+elt.name;
      launch(url, elt.type+', flapping detection disabled');
   }
}


/*
 * Comments
 */
/*
 Adds a comment to a particular host.
 If the "persistent" field is set to zero (0), the comment will be deleted
 the next time Nagios is restarted. Otherwise, the comment will persist
 across program restarts until it is deleted manually.
*/
var shinken_comment_persistent = '1';
/* The command that will add a persistent comment */
function add_comment(name, user, comment){
   var elt = get_element(name);
   var url = '/action/ADD_'+elt.type+'_COMMENT/'+elt.name+'/'+shinken_comment_persistent+'/'+user+'/'+comment;
   // We can launch it :)
   launch(url, elt.type+': '+name+', comment added');
}

/* The command that will delete a comment */
function delete_comment(name, i) {
   var elt = get_element(name);
   var url = '/action/DEL_'+elt.type+'_COMMENT/'+i;
   // We can launch it :)
   launch(url, elt.type+': '+name+', comment deleted');
}

function submit_comment_form(id){
    var user = $('#user_' + id).val();
    var name = $('#name_' + id).val();
    var comment = $('#comment_' + id).val();

    add_comment(name, user, comment);
}

/*
 * Downtimes
 */
/*
 Schedules downtime for a specified host.
 If the "fixed" argument is set to one (1), downtime will start and end
 at the times specified by the "start" and "end" arguments.
 Otherwise, downtime will begin between the "start" and "end" times and
 last for "duration" seconds.
 The "start" and "end" arguments are specified in time_t format (seconds
 since the UNIX epoch).
 The specified host downtime can be triggered by another downtime entry
 if the "trigger_id" is set to the ID of another scheduled downtime entry.
 Set the "trigger_id" argument to zero (0) if the downtime for the
 specified host should not be triggered by another downtime entry.
*/
function do_schedule_downtime(name, start_time, end_time, user, comment, shinken_downtime_fixed, shinken_downtime_trigger, shinken_downtime_duration){
   var elt = get_element(name);
   var url = '/action/SCHEDULE_'+elt.type+'_DOWNTIME/'+elt.name+'/'+start_time+'/'+end_time+'/'+shinken_downtime_fixed+'/'+shinken_downtime_trigger+'/'+shinken_downtime_duration+'/'+user+'/'+comment;
   launch(url, elt.type+': '+name+', downtime scheduled');
}

/* The command that will delete a downtime */
function delete_downtime(name, i) {
   var elt = get_element(name);
   var url = '/action/DEL_'+elt.type+'_DOWNTIME/'+i;
   // We can launch it :)
   launch(url, elt.type+': '+name+', downtime deleted');
}

/* The command that will delete all downtimes */
function delete_all_downtimes(name) {
   var elt = get_element(name);
   var url = '/action/DEL_ALL_'+elt.type+'_DOWNTIMES/'+elt.name;
   // We can launch it :)
   launch(url, elt.type+': '+name+', all downtimes deleted');
}



/*
 * Acknowledges
 */
/*
Allows you to acknowledge the current problem for the specified host/service.
By acknowledging the current problem, future notifications (for the same host state)
are disabled.

 If the "sticky" option is set to two (2), the acknowledgement will remain until
 the host returns to an UP state. Otherwise the acknowledgement will
 automatically be removed when the host changes state.
 If the "notify" option is set to one (1), a notification will be sent out to
 contacts indicating that the current host problem has been acknowledged.
 If the "persistent" option is set to one (1), the comment associated with the
 acknowledgement will survive across restarts of the Shinken process.
 If not, the comment will be deleted the next time Shinken restarts.
*/
function do_acknowledge(name, text, user, shinken_acknowledge_sticky, shinken_acknowledge_notify, shinken_acknowledge_persistent){
   var elt = get_element(name);
   var url = '/action/ACKNOWLEDGE_'+elt.type+'_PROBLEM/'+elt.name+'/'+shinken_acknowledge_sticky+'/'+shinken_acknowledge_notify+'/'+shinken_acknowledge_persistent+'/'+user+'/'+text;
   launch(url, elt.type+': '+name+', acknowledged');
}

/* The command that will delete an acknowledge */
function delete_acknowledge(name) {
   var elt = get_element(name);
   var url = '/action/REMOVE_'+elt.type+'_ACKNOWLEDGEMENT/'+elt.name;
   // We can launch it :)
   launch(url, elt.type+': '+name+', acknowledge deleted');
}


// Join the method to some html classes

var selected_elements = [];

function display_nav_actions() {
    $('#nav-filters').addClass('hidden');
    $('#nav-actions').removeClass('hidden');
    $('.navbar-inverse').addClass('navbar-inverse-2');
}

function hide_nav_actions() {
    $('#nav-actions').addClass('hidden');
    $('#nav-filters').removeClass('hidden');
    $('.navbar-inverse').removeClass('navbar-inverse-2');
}

function add_remove_elements(name){
   if (selected_elements.indexOf(name) != -1) {
      remove_element(name);
   } else {
      add_element(name);
   }
}

// Adding an element in the selected elements list
function add_element(name){
   // Force to check the checkbox
   $('td input[type=checkbox][data-item="'+name+'"]').prop("checked", true);

   $('td input[type=checkbox][data-item="'+name+'"]').closest('tr').addClass('selected');

   if (problems_logs) console.log('Select element: ', name)

   selected_elements.push(name);

   $('#js-nb-selected-elts').html(selected_elements.length);

   if (selected_elements.length > 0) {
      display_nav_actions();

      // Stop page refresh
      disable_refresh();
   }
}

// Removing an element from the selected elements list
function remove_element(name){
   // Force to uncheck the checkbox
   $('td input[type=checkbox][data-item="'+name+'"]').prop("checked", false);

   $('td input[type=checkbox][data-item="'+name+'"]').closest('tr').removeClass('selected');

   if (problems_logs) console.log('Unselect element: ', name)
   selected_elements.splice($.inArray(name, selected_elements),1);

   $('#js-nb-selected-elts').html(selected_elements.length);

   if (selected_elements.length == 0){
      hide_nav_actions();

      // Restart page refresh timer
      enable_refresh();
   }
}

// Flush selected elements list
function flush_selected_elements(){
   /* We must copy the list so we can parse it in a clean way
   without fearing some bugs */
   var cpy = $.extend({}, selected_elements);
   $.each(cpy, function(idx, name) {
      remove_element(name)
   });
}

function get_action_element(btn) {
    var elt = btn.data('element');
    if (! elt) {
        if (selected_elements.length == 1) {
            elt = selected_elements[0];
        }
    }

    return elt;
}

$("body").on("click", ".js-delete-comment", function () {
    var elt = $(this).data('element');
    var comment = $(this).data('comment');

    var strconfirm = confirm("Are you sure you want to delete this comment?");

    if (strconfirm == true) {
        delete_comment(elt, comment);
    }
});

$("body").on("click", ".js-schedule-downtime", function () {
    var elt = get_action_element($(this));

    var duration = $(this).data('duration');
    if (duration) {
        var downtime_start = moment().seconds(0).format('X');
        var downtime_stop = moment().seconds(0).add('minutes', duration).format('X');
        var comment = $(this).text() + " downtime scheduled from WebUI by " + user;
        if (elt) {
            do_schedule_downtime(elt, downtime_start, downtime_stop, g_user_name, comment, shinken_downtime_fixed, shinken_downtime_trigger, shinken_downtime_duration);
        } else {
            $.each(selected_elements, function(idx, name){
                do_schedule_downtime(name, downtime_start, downtime_stop, g_user_name, comment, shinken_downtime_fixed, shinken_downtime_trigger, shinken_downtime_duration);
            });
        }
    } else {
        if (elt) {
            display_modal("/forms/downtime/add/"+elt);
        } else {
            // :TODO:maethor:171008:
            alert("Sadly, you cannot define a custom timeperiod on multiple elements at once. This is not implemented yet.");
        }
    }

    flush_selected_elements();
});

$("body").on("click", ".js-delete-downtime", function () {
    var elt = $(this).data('element');
    var downtime = $(this).data('downtime');
    //display_modal("/forms/downtime/delete/"+elt+"?downtime="+downtime);

    var strconfirm = confirm("Are you sure you want to delete this downtime?");

    if (strconfirm == true) {
        delete_downtime(elt, downtime);
        add_comment(elt, g_user_name, "Dowtime "+ downtime + " for " + elt + " deleted by " + user);
    }
});

$("body").on("click", ".js-delete-all-downtimes", function () {
    var elt = get_action_element($(this));

    if (elt) {
        display_modal("/forms/downtime/delete_all/"+elt);
    } else {
        $.each(selected_elements, function(idx, name){
            delete_all_downtimes(name);
        });
    }

    flush_selected_elements();
});

$("body").on("click", ".js-add-acknowledge", function () {
    var elt = get_action_element($(this));

    if (elt) {
        display_modal("/forms/acknowledge/add/"+elt);
    } else {
        $.each(selected_elements, function(idx, name){
            do_acknowledge(name, 'Acknowledged by '+user, g_user_name, default_ack_sticky, default_ack_notify, default_ack_persistent);
        });
    }

    flush_selected_elements();
});

$("body").on("click", ".js-remove-acknowledge", function () {
    var elt = get_action_element($(this));

    if (elt) {
        display_modal("/forms/acknowledge/remove/"+elt);
    } else {
        $.each(selected_elements, function(idx, name){
            delete_acknowledge(name);
        });
    }

    flush_selected_elements();
});

$("body").on("click", ".js-recheck", function () {
    var elt = get_action_element($(this));

    if (elt) {
        recheck_now(elt);
    } else {
        $.each(selected_elements, function(idx, name){
            recheck_now(name);
        });
    }

    flush_selected_elements();
});

$("body").on("click", ".js-submit-ok", function () {
    var elt = get_action_element($(this));

    if (elt) {
        display_modal("/forms/submit_check/"+elt);
    } else {
        $.each(selected_elements, function(idx, name){
            submit_check(name, '0', 'Forced OK/UP by '+user);
        });
    }

    flush_selected_elements();
});

$("body").on("click", ".js-try-to-fix", function () {
    var elt = get_action_element($(this));

    if (elt) {
        try_to_fix(elt);
    } else {
        $.each(selected_elements, function(idx, name){
            try_to_fix(name);
        });
    }

    flush_selected_elements();
});

$("body").on("click", ".js-create-ticket", function () {
    var elt = $(this).data('element');
    display_modal("/helpdesk/ticket/add/"+elt);
});

$("body").on("click", ".js-create-ticket-followup", function () {
    var elt = $(this).data('element');
    var ticket = $(this).data('ticket');
    var status = $(this).data('status');
    display_modal("/helpdesk/ticket_followup/add/"+elt+'?ticket='+ticket+'&status='+status);
});

// Former shinken-bookmarks.js
// -----
var bkm_logs=false;

var bookmarks = [];
var bookmarksro = [];

// Save bookmarks lists
function save_bookmarks(){
   save_user_preference('bookmarks', JSON.stringify(bookmarks), function () {
      refresh_bookmarks(search_string);
   });
}

function save_bookmarksro(){
   save_common_preference('bookmarks', JSON.stringify(bookmarksro), function () {
      refresh_bookmarks(search_string);
   });
}

// String handling
function safe_string(string) {
   return String(string).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// Create bookmaks lists ...
function declare_bookmark(name, uri){
   var exists=false;
   $.each(bookmarks, function(idx, bm){
      if (bm.name == name) {
         exists=true;
         return false;
      }
   });
   if (! exists)  {
      if (bkm_logs) console.debug('Declaring user bookmark:', name, uri);
      bookmarks.push({'name' : name, 'uri' : uri});
      return true;
   }
   return false;
}

function declare_bookmarksro(name, uri){
   var exists=false;
   $.each(bookmarksro, function(idx, bm){
      if (bm.name == name) {
         exists=true;
         return false;
      }
   });
   if (! exists)  {
      if (bkm_logs) console.debug('Declaring global bookmark:', name, uri);
      bookmarksro.push({'name' : name, 'uri' : uri});
      return true;
   }
   return false;
}

// Refresh bookmarks in HTML
function refresh_bookmarks(_search_string){
   $('ul [aria-labelledby="bookmarks_menu"]').empty();
   if (bookmarks.length == 0 && bookmarksro.length == 0) {
      $('ul [aria-labelledby="bookmarks_menu"]').append('<li role="presentation" class="dropdown-header">No defined bookmarks</li>');
   }

   if (bookmarks.length) {
      $('ul [aria-labelledby="bookmarks_menu"]').append('<li role="presentation" class="dropdown-header"><strong>User bookmarks:</strong></li>');
      $.each(bookmarks, function(idx, bkm){
         $('ul [aria-labelledby="bookmarks_menu"]').append('<li role="presentation"><a role="menuitem" tabindex="-1" href="/all?search=' + bkm.uri + '"><i class="fas fa-bookmark"></i> ' + bkm.name + '</a></li>');
         if (bkm_logs) console.debug('Display user bookmark:', bkm.name);
      });
   }
   if (bookmarksro.length) {
      $('ul [aria-labelledby="bookmarks_menu"]').append('<li role="presentation" class="dropdown-header"><strong>Global bookmarks:</strong></li>');
      $.each(bookmarksro, function(idx, bkm){
         $('ul [aria-labelledby="bookmarks_menu"]').append('<li role="presentation"><a role="menuitem" tabindex="-1" href="/all?search=' + bkm.uri + '"><i class="fas fa-bookmark"></i> ' + bkm.name + '</a></li>');
         if (bkm_logs) console.debug('Display global bookmark:', bkm.name);
      });
   }

   if (_search_string) {
      $('ul [aria-labelledby="bookmarks_menu"]').append('<li role="presentation" class="divider"></li>');
      $('ul [aria-labelledby="bookmarks_menu"]').append('<li role="presentation"><a role="menuitem" href="#" action="display-add-bookmark" data-filter="'+_search_string+'"><i class="fas fa-plus"></i> Bookmark the current filter</a></li>');
   }
   if (bookmarks.length || bookmarksro.length) {
      $('ul [aria-labelledby="bookmarks_menu"]').append('<li role="presentation" class="divider"></li>');
      $('ul [aria-labelledby="bookmarks_menu"]').append('<li role="presentation"><a role="menuitem" href="#" action="manage-bookmarks" data-filter="'+_search_string+'"><i class="fas fa-tags"></i> Manage bookmarks</a></li>');
   }
}

// Delete a specific bookmark by its name
function delete_bookmark(name){
   new_bookmarks = [];
   $.each(bookmarks, function(idx, bm){
      if (bm.name != name) {
         new_bookmarks.push(bm);
      }
   });
   bookmarks = new_bookmarks;
   save_bookmarks();
   if (bkm_logs) console.debug('Deleted user bookmark:', name);
}

function delete_bookmarkro(name){
   new_bookmarksro = [];
   $.each(bookmarksro, function(idx, bm){
      if (bm.name != name) {
         new_bookmarksro.push(bm);
      }
   });
   bookmarksro = new_bookmarksro;
   save_bookmarksro();
   if (bkm_logs) console.debug('Deleted global bookmark:', name);
}

var search_string='';
$(document).ready(function(){
   search_string = safe_string($('#search').val());
   refresh_bookmarks(search_string);

   // Display modal to add a new bookmark ...
   $('body').on("click", '[action="display-add-bookmark"]', function (e, data) {
      search_string = safe_string($(this).data('filter'));
      display_modal('/modal/newbookmark');
   });

   // Add a new bookmark ...
   $('body').on("click", '[action="add-bookmark"]', function (e, data) {
      var bkm_type = $(this).data('bookmark_type');

      var name = safe_string($('#new_bookmark_name').val());
      if (name=='') return;

      // Do not save the bm if there is already one with this name
      var exists=false;
      $.each(bookmarks, function(idx, bm){
         if (bm.name == name) {
            exists=true;
         }
      });
      if (exists)  {
         alert('This bookmark name already exists !');
         return;
      }

      // Ok we can save bookmarks in our preferences
      declare_bookmark(name, search_string);
      save_bookmarks();

      // Refresh the bookmarks HTML
      $('#modal').modal('hide');
      refresh_bookmarks(search_string);
   });

   // Delete a bookmark ...
   $('body').on("click", '[action="delete-bookmark"]', function (e, data) {
      var bkm = $(this).data('bookmark');
      var bkm_type = $(this).data('bookmark_type');
      if (bkm && bkm_type) {
         if (bkm_type =='global') {
            delete_bookmarkro(bkm);
         } else {
            delete_bookmark(bkm);
         }
         location.reload();
      }
   });

   // Manage bookmarks ...
   $('body').on("click", '[action="manage-bookmarks"]', function (e, data) {
      display_modal('/modal/managebookmarks');
   });

   // Make a bookmark become global ...
   $('body').on("click", '[action="globalize-bookmark"]', function (e, data) {
      var bkm = $(this).data('bookmark');
      var bkm_type = $(this).data('bookmark_type');
      if (bkm && bkm_type == 'user') {
         var exists=false;
         var bookmark = null;
         $.each(bookmarks, function(idx, bm){
            if (bm.name == bkm) {
               exists=true;
               bookmark = bm;
               return false;
            }
         });
         if (exists)  {
            // Do not save the bookmark if there is already one with this name
            exists=false;
            $.each(bookmarksro, function(idx, bm){
               if (bm.name == bkm) {
                  exists=true;
                  return false;
               }
            });
            if (! exists) {
               // Ok we can save bookmarks in our preferences
               declare_bookmarksro(bookmark.name, bookmark.uri);
               delete_bookmark(bkm);
               save_bookmarksro();
            } else {
               alert('This common bookmark name already exists!');
            }
         }
      }

      // Refresh the bookmarks HTML
      $('#modal').modal('hide');
      refresh_bookmarks(search_string);
   });
});


// Former shinken-charts.js
// -----
function display_charts(){
    try {
        $(".piechart").sparkline('html', {
            enableTagOptions: true,
            disableTooltips: true,
            offset: -90
        });
    } catch (e) {

    }
}

display_charts();


// Former shinken-layout.js
// -----
var layout_logs=false;

/*
 * For IE missing window.console ...
*/
(function () {
    var f = function () {};
    if (!window.console) {
        window.console = {
            log:f, info:f, warn:f, debug:f, error:f
        };
    }
}());

/*
 * To load on run some additional js or css files.
*/
function loadjscssfile(filename, filetype){
   if (filetype=="js") {
      if (layout_logs) console.debug('Loading Js file: ', filename);
      window.setTimeout(function() {
         $.ajax({
            url: filename,
            dataType: "script",
            error: function () {
               console.error('Shinken script error, not loaded: ', filename);
            }
         });
      }, 100);
   } else if (filetype=="css") {
      if (layout_logs) console.debug('Loading Css file: ', filename);
      if (!$('link[href="' + filename + '"]').length)
         $('head').append('<link rel="stylesheet" type="text/css" href="' + filename + '">');
   }
}


/**
 * Display the layout modal form
 */
function display_modal(inner_url) {
   if (layout_logs) console.debug('Displaying modal: ', inner_url);
   disable_refresh();
   $('#modal').modal({
      keyboard: true,
      show: true,
      backdrop: 'static',
      remote: inner_url
   });
}

function headerPopovers() {
  // Topbar hosts popover
   $('#hosts-states-popover').popover({
      placement: 'bottom',
      container: 'body',
      trigger: 'manual',
      animation: false,
      template: '<div class="popover img-popover"><div class="arrow"></div><div class="popover-inner"><h3 class="popover-title"></h3><div class="popover-content"><p></p></div></div></div>',
      content: function() {
         return $('#hosts-states-popover-content').html();
      }
   }).on("mouseenter", function () {
      var _this = this;
      $(this).popover("show");
      $(this).siblings(".popover").on("mouseleave", function () {
          $(_this).popover('hide');
      });
   }).on("mouseleave", function () {
      var _this = this;
      setTimeout(function () {
          if (!$(".popover:hover").length) {
              $(_this).popover("hide");
          }
      }, 100);
   });

  // Topbar services popover
   $('#services-states-popover').popover({
      placement: 'bottom',
      container: 'body',
      trigger: 'manual',
      animation: false,
      template: '<div class="popover img-popover"><div class="arrow"></div><div class="popover-inner"><h3 class="popover-title"></h3><div class="popover-content"><p></p></div></div></div>',
      content: function() {
         return $('#services-states-popover-content').html();
      }
   }).on("mouseenter", function () {
      var _this = this;
      $(this).popover("show");
      $(this).siblings(".popover").on("mouseleave", function () {
          $(_this).popover('hide');
      });
   }).on("mouseleave", function () {
      var _this = this;
      setTimeout(function () {
          if (!$(".popover:hover").length) {
              $(_this).popover("hide");
          }
      }, 100);
   });
}


// Play alerting sound ...
function playAlertSound() {
    if (layout_logs) console.debug("Play sound");
    var audio = document.getElementById('alert-sound');
    var canPlay = audio && !!audio.canPlayType && audio.canPlayType('audio/wav') != "";
    if (canPlay) {
        audio.play();
    }
}

function disable_sound() {
   if (layout_logs) console.debug("Disabling sound");
   $('#sound_alerting')
       .addClass('fa-striked')
       .parent().data('tooltip', false)
       .attr('data-original-title', "Enable sound alert").tooltip({html: 'true', placement: 'bottom'});
   sessionStorage.setItem("sound_play", '0');
}


function enable_sound() {
   if (layout_logs) console.debug("Enabling sound");
   $('#sound_alerting')
       .removeClass('fa-striked')
       .parent().data('tooltip', false)
       .attr('data-original-title', "Disable sound alert").tooltip({html: 'true', placement: 'bottom'});
   sessionStorage.setItem("sound_play", '1');
   playAlertSound();
}


$(document).ready(function(){
   // Sidebar menu
   $('#sidebar-menu').metisMenu();


  // Sound
  if ($(".js-toggle-sound-alert").length) {
    // Set alerting sound icon ...
    if (! sessionStorage.getItem("sound_play")) {
        disable_sound();
    }

    $('body').on("click", '.js-toggle-sound-alert', function (e, data) {
      if (sessionStorage.getItem("sound_play") == '1') {
          disable_sound();
      } else {
          playAlertSound();
          enable_sound();
      }
    });
  }

  headerPopovers();
});


// Former shinken-tooltip.js
// -----
$.fn.tooltip.Constructor.DEFAULTS.placement = 'auto';

function tooltips(){
   $('[title]').tooltip({
       html: 'true'
   });
}

tooltips();
