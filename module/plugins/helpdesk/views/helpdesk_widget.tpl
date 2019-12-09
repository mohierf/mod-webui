%rebase("widget")

%import json
%import time

%narrow=True

%if not tickets:
   <div class="text-center">
      <h3>No helpdesk records (tickets) found.</h3>
      <p>Your request did not return any results.</p>
   </div>
%else:
   %include("_helpdesk")
%end
