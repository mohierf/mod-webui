var history_offset = 0;
var logs_url = '/logs/inner';
var scrolled = false;

function get_system_logs(add_more, limit, offset) {
    console.log("get_system_logs", add_more, $("#inner_history").data('getting_history'), limit, offset);

    // todo: reactivate ?
    // disable_refresh();

    if ($("#inner_history").data('getting_history') === true) return;

    $("#inner_history").data('getting_history', true);

    $("#loading-spinner").fadeIn(1000, function() {
        var url = logs_url;
        url = url +'?';
        if (limit !== undefined) {
            url = url + 'limit=' + limit;
        } else {
            url = url + 'limit=100';
        }
        if (offset !== undefined) {
            history_offset = offset;
        }
        url = url + '&offset=' + history_offset;
        if (add_more !== undefined && add_more) {
            url = url + '&add_more=1';
        }
        if ($('#range_start').length) {
            url = url + '&range_start=' + $('#range_start').val();
        }
        if ($('#range_end').length) {
            url = url + '&range_end=' + $('#range_end').val();
        }
        if ($('#inner_history').data('service') !== undefined) {
            url = url + '&service=' + $('#inner_history').data('service');
        }
        if ($('#inner_history').data('host') !== undefined) {
            url = url + '&host=' + $('#inner_history').data('host');
        }
        if ($('#inner_history').data('command_filter') !== undefined) {
            url = url + '&command_filter=' + $('#inner_history').data('command_filter');
        }
        if ($('#inner_history').data('contact_filter') !== undefined) {
            url = url + '&contact_filter=' + $('#inner_history').data('contact_filter');
        }
        if ($('#inner_history').data('no_hosts_filter') !== undefined) {
            url = url + '&no_hosts_filter=1';
        }

        $.get(url, function(data){
            if (add_more) {
                $("#inner_history tbody").append(data);
            } else {
                $("#inner_history").append(data);
            }
            history_offset+=100;

            $("#loading-spinner").fadeOut(1000);
            $("#inner_history").data('getting_history', false);
        });
    });
}

$("#inner_history").data('getting_history', false);

$(window).scroll(function() {
    if ($("#inner_history").data('getting_history') === true) return;

    if (($(window).scrollTop() + $(window).height() + 150) > $(document).height()) {
        // Scroll detected at least conce :)
        scrolled = true;

        // Add more items to the history
        get_system_logs(true);
    }
});


