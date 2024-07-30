$(document).ready(function() {
  // Get the current date
  
    const $form = $('#editWeekiForm');
    const $categoryButtons = $('.category-button');
    const $categoryInput = $('#id_category');

    $categoryButtons.on('click', function() {
        $categoryButtons.removeClass('active');
        $(this).addClass('active');
        $categoryInput.val($(this).data('category-id'));
    });

    // Set initial category value
    const $activeButton = $('.category-button.active');
    if ($activeButton.length) {
        $categoryInput.val($activeButton.data('category-id'));
    }

  
    const $textarea = $('.newWeekiText[name="content"]');
    const $submitButton = $('#newWeekiButton');

    // Check if the textarea already contains some text on page load
    if ($textarea.val().trim().length > 0) {
        console.log("ma text")
        $submitButton.text('Save');
    }

    $textarea.on('input', function() {
        if ($(this).val().trim().length > 0) {
            $submitButton.text('Save');
        } else {
            $submitButton.text('Submit');
        }
    });


  $('#newWeekiButton').on('click', function(e) {
          e.preventDefault();
          var buttonText = $(this).text().trim();

          if (buttonText === 'Record') {
              // Custom action for 'Record'
              console.log('Record button clicked');
              // Add your custom logic here
              // For example, you might want to change the button text to 'Save'
              $(this).text('Stop');
          } else if (buttonText === 'Save') {
              // Submit the form
              $('form').submit();
          }
      });

});