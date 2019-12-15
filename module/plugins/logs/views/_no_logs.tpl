      <div class="col-lg-8 col-lg-offset-2">
        <div class="page-header">
          <h3>What a bummer! We couldn't find any log.</h3>
        </div>

        <div class="panel panel-default">
          <div class="panel-heading"><h3 class="panel-title">What you can do</h3></div>
          <div class="panel-body">
            The WebUI is looking for logs in MongoDB. Please check :
            <ul>
              <li>That a log module is enabled in the broker. For instance: <mark>mongo-logs</mark> or <mark>logstore-mongodb</mark></li>
              <li>That the broker log module and the Web UI use the same database and log collection. The Web UI get logs from the <mark>{{app.get_config('logs_collection', 'not set!')}}</mark> collection in the database <mark>{{app.get_config('database', 'not set!')}}</mark></li>
              <li>That this query returns stuff in the mongo shell:
               <br>&nbsp;<code>use {{app.get_config('database', 'not set!')}}</code>
               <br>&nbsp;<code>db.{{app.get_config('logs_collection', 'not set!')}}.find({{ query }})</code>
               <br><em>You can adjust <code>database</code> and <code>logs_collection</code> in the Web UI configuration.</em></li>
              <li>You can customize this query in the webui config with the <code>plugin.logs.*</code> variables:
               <br>Define the list of interesting events in the <code>plugin.logs.events</code> list. Currently: <mark>{{ ', '.join(params['events']) }}</mark> are fetched.</li>
            </ul>
          </div>
        </div>
      </div>
