$(document).ready(function() {
    const categoryButtons = $('.category-button');
    const categoryInput = $('input[name="category"]');
    const form = $('#editWeekiForm');
    const contentDiv = $('.editWeekiText');
    const csrfToken = $('[name=csrfmiddlewaretoken]').val();

    categoryButtons.each(function() {
        $(this).on('click', function() {
            categoryButtons.removeClass('active');
            $(this).addClass('active');
            categoryInput.val($(this).data('category-id'));
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
                if (data.success) {
                    alert(data.message);
                    if (data.redirect_url) {
                        window.location.href = data.redirect_url;
                    }
                } else {
                    alert('Error: ' + JSON.stringify(data.errors));
                }
            },
            error: function(xhr, status, error) {
                console.error('Error:', error);
                alert('An error occurred. Please try again.');
            }
        });
    }

    $('#updateButton').on('click', function() { submitForm('update'); });
    $('#deleteButton').on('click', function() {
        if (confirm('Are you sure you want to delete this Weeki?')) {
            submitForm('delete');
        }
    });
});