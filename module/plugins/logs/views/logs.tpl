%rebase("layout", css=['logs/css/logs.css', 'logs/css/selectize.default.css', 'logs/css/selectize.bootstrap3.css'], js=['logs/js/history.js', 'logs/js/selectize.min.js'], title='System logs')

%helper = app.helper
%import time
%import datetime

%date_format='%Y-%m-%d %H:%M:%S'

<script type="text/javascript">
  $(document).ready(function() {
    // Events selection
    var events_options = [
    %for event in params['events_list']:
      {event: '{{ event }}', label: '{{ event }}'},
    %end
    ];

    var events_items = [
    %for event in params['events']:
      '{{ event }}',
    %end
    ];


    $('#select-events').selectize({
      persist: false,
      maxItems: null,
      valueField: 'event',
      labelField: 'label',
      searchField: ['event', 'label'],
      sortField: [
         {field: 'event', direction: 'asc'}
      ],
      options: events_options,
      items: events_items,
      render: {
         item: function(item, escape) {
            return '<div>' +
               (item.label ? '<span class="label">' + escape(item.label) + '</span>' : '') +
            '</div>';
         },
         option: function(item, escape) {
            var name = $.trim((item.label || ''));
            var label = name || item.event;
            var caption = item.label ? item.label : null;
            return '<div>' +
               '<mark class="text-primary label">' + escape(label) + '</mark>' +
               (caption ? '<small class="text-secondary caption"> (' + escape(caption) + ')</small>' : '') +
            '</div>';
         }
      },
      onChange(value) {
        // New item chosen in the list
        $.post(
          "/logs/set_events_list",
          {
            "new_events_list": value
          },
          function(data){
             $("#inner_history").empty();

             // Reload logs from 0
             get_system_logs(false, 100, 0);
          }
        );
      }
   });

    // Hosts selection
    %hosts = app.datamgr.get_hosts()
    var hosts_options = [
    %for host in hosts:
      {host_name: '{{ host.host_name }}', label: '{{ host.display_name if host.display_name else '' }}'},
    %end
    ];

    var hosts_items = [
    %for host in params['hosts']:
      '{{ host }}',
    %end
    ];

    $('#select-hosts').selectize({
      persist: false,
      maxItems: null,
      valueField: 'host_name',
      labelField: 'label',
      searchField: ['host_name', 'label'],
      sortField: [
         {field: 'host_name', direction: 'asc'}
      ],
      options: hosts_options,
      items: hosts_items,
      render: {
         item: function(item, escape) {
            return '<div>' +
               (item.host_name ? '<span class="label">' + escape(item.host_name) + '</span>' : 'XxX') +
            '</div>';
         },
         option: function(item, escape) {
            var caption = $.trim((item.label || ''));
            return '<div>' +
               '<mark class="text-primary label">' + escape(item.host_name) + '</mark>' +
               (caption ? '<small class="text-secondary caption"> (' + escape(caption) + ')</small>' : '') +
            '</div>';
         }
      },
      onChange(value) {
        // New item chosen in the list
        $.post(
          "/logs/set_hosts_list",
          {
            "new_hosts_list": value
          },
          function(data){
             $("#inner_history").empty();

             // Reload logs from 0
             get_system_logs(false, 100, 0);
          }
        );
      }
   });

    // Initial start/stop range ...
    var range_start = moment.unix({{range_start}}, 'YYYY-MM-DD');
    var range_end = moment.unix({{range_end}}, 'YYYY-MM-DD');

    $("#dtr_logs").daterangepicker({
      ranges: {
         'today':         [moment().add('days', 0), moment()],
         '1 day':         [moment().add('days', -1), moment()],
         '2 days':        [moment().add('days', -2), moment()],
         '1 week':        [moment().add('days', -7), moment()],
         '1 month':       [moment().add('month', -1), moment()]
      },
      format: 'YYYY-MM-DD',
      separator: ' to ',
      maxDate: moment(),
      startDate: range_start,
      endDate: range_end,
      timePicker: false,
      timePickerIncrement: 1,
      timePicker12Hour: false,
      showDropdowns: false,
      showWeekNumbers: false,
      opens: 'right',
      },
      function(start, end, label) {
        range_start = start; range_end = end;

        // New time period chosen in the list
        $.post(
          "/logs/set_period",
          {
            "range_start": $('#range_start').val(),
            "range_end": $('#range_end').val()
          },
          function(data){
             $("#inner_history").empty();

             // Reload logs from 0
             get_system_logs(false, 100, 0);
          }
        );
      }
    );

    // Set default date range values
    $('#dtr_logs').val(range_start.format('YYYY-MM-DD') + ' to ' +  range_end.format('YYYY-MM-DD'));
    $('#range_start').val(range_start.format('X'));
    $('#range_end').val(range_end.format('X'));

    // Update dates on apply button ...
    $('#dtr_logs').on('apply.daterangepicker', function(ev, picker) {
      range_start = picker.startDate;
      range_end = picker.endDate;
      $('#range_start').val(range_start.unix());
      $('#range_end').val(range_end.unix());
    });

    // Reload logs from 0
    get_system_logs(false, 100, 0);
  });
</script>

<div class="panel panel-default">
  <div class="panel-body">

   <div class="row">
      <div class="form-group col-md-12">
        <label for="dtr_logs">Filtered dates:</label>
        <div class="input-group">
          <span class="input-group-addon"><i class="fas fa-calendar"></i></span>
          <input type="text" class="form-control" id="dtr_logs" placeholder="..." />
        </div>
        <input type="hidden" id="range_start" name="range_start" />
        <input type="hidden" id="range_end" name="range_end" />
      </div>


  <div class="panel panel-default">
    <div class="panel-heading">
      <h4 class="panel-title">
        <a data-toggle="collapse" class="collapsed" href="#collapse-filters">
          <i class="chevron fas fa-fw" ></i> Filtering events and hosts
        </a>
      </h4>
    </div>
    <div id="collapse-filters" class="panel-collapse collapse">
      <div class="panel-body">
         <div class="form-group col-md-12">
            <label for="select-events">Filtered events:</label>
            <select id="select-events" class="events" placeholder="Pick some events to show..."></select>
         </div>
         <div class="form-group col-md-12">
            <label for="select-hosts">Filtered hosts:</label>
            <select id="select-hosts" class="hosts" placeholder="Pick some hosts to show..."></select>
         </div>
      </div>
    </div>
  </div>
   </div>

  %if hasattr(records,"__iter__"):
    <div id="inner_history">
       %if total_records == 0:
         %include("_no_logs.tpl")
       %end
    </div>

    <div class="text-center" id="loading-spinner">
      <h3><i class="fas fa-spinner fa-spin"></i> Loading history data…</h3>
    </div>
  %else:
   No logs found
  %end
  </div>
</div>
