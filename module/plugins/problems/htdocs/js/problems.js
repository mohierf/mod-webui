/*Copyright (C) 2009-2011 :
     Gabes Jean, naparuba@gmail.com
     Gerhard Lausser, Gerhard.Lausser@consol.de
     Gregory Starck, g.starck@gmail.com
     Hartmut Goebel, h.goebel@goebel-consult.de
     Frederic Mohier, frederic.mohier@gmail.com
     Guillaume Subiron, maethor@subiron.org

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

var problems_logs=false;




// When we select all, add all problems in the selected list,
function select_all_problems(){
   // Maybe the actions are not allowed?
   if (!actions_enabled){
      return;
   }

   // Get all elements name ...
   $('td input[type=checkbox]').each(function(){
      // ... and add to the selected items list.
      add_element($(this).data('item'));
   });
}

// Unselect all
function unselect_all_problems(){
   flush_selected_elements();
}


function add_remove_elements(name){
   // Maybe the actions are not allowed. If so, don't do anything ...

   if (selected_elements.indexOf(name) != -1) {
      remove_element(name);
   } else {
      add_element(name);
   }
}


/* function when we add an element*/
function add_element(name){
   // Force to check the checkbox
   $('td input[type=checkbox][data-item="'+name+'"]').prop("checked", true);
   
   selected_elements.push(name);

   if (selected_elements.length > 0) {
      show_actions();
      
      // Stop page refresh
      stop_refresh();
   }
}

/* And of course when we remove it... */
function remove_element(name){
   // Force to uncheck the checkbox
   $('td input[type=checkbox][data-item="'+name+'"]').prop("checked", false);
   
   selected_elements.splice($.inArray(name, selected_elements),1);

   if (selected_elements.length == 0){
      hide_actions();

      // Restart page refresh timer
      start_refresh();
   }
}


/* Flush selected elements, so clean the list
but also uncheck them in the UI */
function flush_selected_elements(){
   /* We must copy the list so we can parse it in a clean way
   without fearing some bugs */
   var cpy = $.extend({}, selected_elements);
   $.each(cpy, function(idx, name) {
      remove_element(name)
   });
}


function on_page_refresh(){
   $('.collapse').on('show.bs.collapse', function () {
       $(this).closest('tr').prev().find('.output').removeClass("ellipsis", {duration:200});
   });

   $('.collapse').on('hide.bs.collapse', function () {
       $(this).closest('tr').prev().find('.output').addClass("ellipsis", {duration:200});
   });
   
   // Graphs popover
   $('[data-toggle="popover"]').popover({
      html: true,
      template: '<div class="popover img-popover"><div class="arrow"></div><div class="popover-inner"><h3 class="popover-title"></h3><div class="popover-content"><p></p></div></div></div>',
   });
   
}

// On page loaded ... 
$(document).ready(function(){
   // If actions are not allowed, disable the button 'select all' and the checkboxes
   if ("actions_enabled" in window && !actions_enabled) {
      $('#select_all_btn').addClass('disabled');
      $('[id^=selector').attr('disabled', true);
      
      // Get all elements ...
      $('input[type=checkbox]').each(function(){
         // ... and disable and hide checkbox
         $(this).prop("disabled", true).hide();
      });
   }

   // Problems element check boxes
   $('button[data-type="business-impact"]').click(function (e) {
      if (selected_elements.length == 0){
         $(this).html("Unselect all elements");
      } else {
         $(this).html("Select all elements");
      }
      
      // Add/remove element from selection
      $('input[type=checkbox][data-type="problem"][data-business-impact="'+$(this).data('item')+'"]').trigger('click');
   });

   // Problems element check boxes
   $('input[type=checkbox][data-type="problem"]').click(function (e) {
      e.stopPropagation();
      
      // Add/remove element from selection
      add_remove_elements($(this).data('item'));
   });
});
