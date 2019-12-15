%rebase("layout", css=['logs/css/logs.css'], js=['logs/js/history.js', 'js/Chart.min.js'], title='Alert statistics for the last %s days' % days)

%total = sum(hosts.values())

%if not hosts and not services:
<div class="col-lg-8 col-lg-offset-2">
  <div class="page-header">
    <h3>What a bummer! We couldn't find any log.</h3>
  </div>

  <div class="panel panel-default">
    <div class="panel-heading"><h3 class="panel-title">What you can do</h3></div>
    <div class="panel-body">
      The Web UI is looking for logs in MongoDB. Please check :
      <ul>
        <li>That mongo-logs module is enable in the broker</li>
        <li>That this query returns stuff in mongo shinken database : <br>&nbsp;<code>db.logs.find({{ query }})</code>
      </ul>

      You can adjust <code>command_filter</code> and <code>contact_filter</code> regexes in the Web UI configuration.
    </div>
  </div>
</div>
%else:

<div class="col-lg-4">
  <div class="panel panel-default">
    %total = sum(hosts.values())
    <div class="panel-heading"><h3 class="panel-title">{{ total }} hosts alerts</h3></div>
    %if total:
    <table class="table table-striped table-condensed">
      %for l in hosts.most_common(15):
      <tr>
         <td width="160px">{{ l[1] }} ({{ round((l[1] / float(total)) * 100, 1) }}%)</td>
         <td><a href="/stats/host/{{ l[0] }}?days={{ days }}">{{ l[0] }}</a></td>
      </tr>
      %end
      %other = sum((h[1] for h in hosts.most_common()[15:]))
      <tr>
         <td>{{ other }} ({{ round((other / float(total)) * 100, 1) }}%)</td>
         <td><strong>Others</strong></td>
      </tr>
    </table>
    %end
  </div>
</div>

<div class="col-lg-4">
  <div class="panel panel-default">
    %total = sum(services.values())
    <div class="panel-heading"><h3 class="panel-title">{{ total }} services alerts</h3></div>
    %if total:
    <table class="table table-striped table-condensed">
      %for l in services.most_common(15):
      <tr><td width="160px">{{ l[1] }} ({{ round((l[1] / float(total)) * 100, 1) }}%)</td><td><a href="/stats/service/{{ l[0] }}?days={{ days }}">{{ l[0] }}</a></td></tr>
      %end
      %other = sum((s[1] for s in services.most_common()[15:]))
      <tr><td>{{ other }} ({{ round((other / float(total)) * 100, 1) }}%)</td><td><strong>Others</strong></td></tr>
    </table>
    %end
  </div>
</div>

<div class="col-lg-4">
  <div class="panel panel-default">
    %total = sum(hostsservices.values())
    <div class="panel-heading"><h3 class="panel-title">{{ total }} hosts/services alerts</h3></div>
    %if total:
    <table class="table table-striped table-condensed">
      %for l in hostsservices.most_common(15):
      <tr><td width="160px">{{ l[1] }} ({{ round((l[1] / float(total)) * 100, 1) }}%)</td><td>{{ l[0] }}</td></tr>
      %end
      %other = sum((h[1] for h in hostsservices.most_common()[15:]))
      <tr><td>{{ other }} ({{ round((other / float(total)) * 100, 1) }}%)</td><td><strong>Others</strong></td></tr>
    </table>
    %end
  </div>
</div>

<div class="col-lg-12">
  <div class="panel panel-default">
    <div class="panel-body">
      <canvas id="timeseries" height=40px></canvas>

      <script>
        $(document).ready(function() {
          var ctx = document.getElementById('timeseries').getContext('2d');
          var myChart = new Chart(ctx, {
            type: 'line',
            data: {
              datasets : [{
                label: "# of alerts",
                data: {{! graph }},
              }]
            },
            options: {
              scales: {
                xAxes: [{
                  //gridLines: {
                  //  offsetGridLines: true
                  //},
                  type: 'time',
                  distribution: 'linear',
                  time: {
                    minUnit: 'day',
                    tooltipFormat: 'll HH'
                  }
                }],
              }
            }
          });

          // Reload logs from 0
          get_system_logs(false, 100, 0);
        });
      </script>
    </div>
  </div>
</div>

<div class="col-xs-12">
  <div class="panel panel-default">
    <div class="panel-body">
      <div id="inner_history"
         data-no_hosts_filter="no_hosts_filter"
         data-command_filter="{{ params['command_filter'] }}"
         data-contact_filter="{{ params['contact_filter'] }}">
      </div>

      <div class="text-center" id="loading-spinner">
        <h3><i class="fas fa-spinner fa-spin"></i> Loading history data...</h3>
      </div>
    </div>
  </div>
</div>

<div class="col-xs-12">
  <center>
    <small>
      <p>
      This page has been generated using the following MongoDB query :<br>
      <code>{{ query }}</code>
      </p>
      <p class="text-left">
      You can customize this query in the webui config with the <code>plugin.stats.*</code> variables:
      <br>
      Set the <code>plugin.stats.days</code> to adjust the number of days. Currently, events are considered for the last <mark>{{ days }}</mark> days.
      <br>
      Define the list of interesting events in the <code>plugin.stats.events</code> list. Currently: <mark>{{ ', '.join(params['events']) }}</mark> are fetched.
      <br>
      Define a specific command in the <code>plugin.stats.command_filter</code> variable.
      %if params['command_filter']:
      Currently: commands are filtered with <mark>{{ params['command_filter'] }}</mark>.
      %else:
      Currently, commands are not filtered.
      %end
      <br>
      Define a specific contact in the <code>plugin.stats.contact_filter</code> variable.
      %if params['command_filter']:
      Currently: contacts are filtered with <mark>{{ params['contact_filter'] }}</mark>.
      %else:
      Currently, contacts are not filtered.
      %end
      <br>
      <strong>Note</strong> that the <code>command_filter</code> and <code>contact_filter</code> make sense only for the <mark>HOST NOTIFICATION</mark> and <mark>SERVICE NOTIFICATION</mark> events.
      </p>
    </small>
  </center>
</div>

%end
