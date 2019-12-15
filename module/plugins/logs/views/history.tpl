%setdefault('navi', None)

%helper = app.helper
%import time

%date_format='%Y-%m-%d %H:%M:%S'

%if not add_more:
   %if total_records == 0:
      %include("_no_logs.tpl")
   %end
   <table class="table table-condensed">
      <colgroup>
         <col style="width: 10%" />
         <!-- <col style="width: 90%" /> -->
      </colgroup>
      <thead>
         <tr>
            <th colspan="20"><h4>{{message}}</h4></th>
         </tr>
         <tr>
            <th>{{ params['time_field'] }}</th>
            %for field in params['other_fields']:
               <th>{{field}}</th>
            %end
         </tr>
      </thead>

      <tbody style="font-size:x-small;">
%else:
      <tr>
         <td colspan="20"><h4>{{message}}</h4></td>
      </tr>
%end

            %for log in records:
            <tr>
               %if params['date_format'] == 'timestamp':
               <td>{{ time.strftime(date_format, time.localtime(log[params['time_field']])) }}</td>
               %else:
               <td>{{ log[params['time_field']] }}</td>
               %end

               %for field in params['other_fields']:
                  %if '.' in field:
                  %before = field.split('.')[0]
                  %after = field.split('.')[1]
                  %before_value = log.get(before, None)
                  %value = before_value.get(after, '') if before else ''
                  %else:
                  %value = log.get(field, '')
                  %end

                  %if field in ['host_name']:
                  <td><a href="/host/{{value}}"> {{value}} </a></td>
                  %else:
                  <td>{{value}}</td>
                  %end
               %end
            </tr>
            %end

%if not add_more:
      </tbody>
   </table>
%end
