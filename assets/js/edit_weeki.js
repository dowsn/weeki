$(document).ready(function() {
    const topicButtons = $('.topic-button');
    const topicInput = $('input[name="topic"]');
    const form = $('#editWeekiForm');
    const week = form.attr('week');
    const year = form.attr('year');
    // const week = form.attr('week_id');
    const contentDiv = $('.editWeekiText');
    const csrfToken = $('[name=csrfmiddlewaretoken]').val();

    topicButtons.each(function() {
        $(this).on('click', function() {
            topicButtons.removeClass('active');
            $(this).addClass('active');
            topicInput.val($(this).data('topic-id'));
        });
    });

    function submitForm(action) {
        const formData = new FormData(form[0]);
        formData.set('content', contentDiv.html().trim());
        formData.set('action', action);

        // Log form data
        for (let [key, value] of formData.entries()) {
            console.log(key + ': ' + value);
        }

        $.ajax({
            url: '',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            headers: {
                'X-CSRFToken': csrfToken
            },
            success: function(data) {
                if(data.success === true) {
                   window.location.href = base_url + '/on/week' + '/' + year + '/' + week;
                  successUrl.searchParams.append('success', 'true');
                  window.location.href = successUrl.toString();
                } else {
                    console.log(data.message);
                }
               
            },
            error: function(xhr, status, error) {
                console.error('Error:', error);
                alert('An error occurred. Please try again.');
            }
        });
    }


  $('#deleteButton').click(function() {
      showPopup({
          message: "Are you sure you want to delete this weeki?",
          okText: "Delete",
          cancelText: "Keep",
          okCallback: function() {
              submitForm('delete')
              
          },
          cancelCallback: function() {
              console.log("Action cancelled. Staying on the page.");
          }
      });
  });

  
   

    $('#updateButton').on('click', function() { submitForm('update'); });
});