
function togglePopup() {
  const $popup = $('#popupContainer');
  $popup.css('display', $popup.css('display') === 'none' ? 'flex' : 'none');
}

// Close the popup when clicking outside of it
$(window).on('click', function(event) {
const $popup = $('#popupContainer');
if (event.target === $popup[0]) {
  $popup.css('display', 'none');
}
});

$(document).ready(function() {


  // popup selector:



  // popup normal

  let activePopup = null;

  function showPopup(options) {
      if (activePopup) {
          activePopup.remove();
          activePopup = null;
          return;
      }

      const defaults = {
          message: "",
          inputPlaceholder: "",
          okText: "OK",
          cancelText: "Cancel",
          showInput: false,
          okCallback: function() {},
          cancelCallback: function() {}
      };

      const settings = $.extend({}, defaults, options);

      const popupTemplate = `
          <div class="popup">
              <p class="popup-message"></p>
              <input type="text" class="popup-input" style="display: none;">
              <button class="popup-ok-btn"></button>
              <button class="popup-cancel-btn"></button>
          </div>
      `;

      const $popup = $(popupTemplate);

      $popup.find('.popup-message').text(settings.message);
      $popup.find('.popup-ok-btn').text(settings.okText);
      $popup.find('.popup-cancel-btn').text(settings.cancelText);

      if (settings.showInput) {
          $popup.find('.popup-input')
              .show()
              .attr('placeholder', settings.inputPlaceholder);
      }

      $popup.find('.popup-ok-btn').click(function() {
          const inputValue = $popup.find('.popup-input').val();
          settings.okCallback(inputValue);
          $popup.remove();
          activePopup = null;
      });

      $popup.find('.popup-cancel-btn').click(function() {
          settings.cancelCallback();
          $popup.remove();
          activePopup = null;
      });

      $('.wrapper').append($popup);
      activePopup = $popup;
  }

  $('.closeButton').click(function() {
          showPopup({
              message: "Are you sure you want to discard this weeki?",
              okText: "Discard",
              cancelText: "Keep",
              okCallback: function() {
                  
                  const baseUrl = window.location.origin;
                  const fullUrl = `${baseUrl}/app/week`;
                  console.log(`Navigating to: ${fullUrl}`);
                  window.location.href = fullUrl;
              },
              cancelCallback: function() {
                  console.log("Action cancelled. Staying on the page.");
              }
          });
      });


      // 
  
    var $popup = $('.popup');
    var $toggleHidden = $('.toggleHidden');

    function openPopup() {
        $popup.css('display', 'block');
    }

    function closePopup() {
        $popup.css('display', 'none');
    }

    function deleteItem() {
        // function to delete item goes here
    }

    function toggleHidden() {
        $(this).find('.toggled').toggleClass('hidden');
    }

    $toggleHidden.on('click.myNamespace', toggleHidden);


    
});

$(document).ready(function() {

 

    // // Update active menu item when hash changes
    // $(window).on('hashchange', setActiveMenuItem);

    // // Add click event listeners to menu items
    // $('.menu-item').on('click', function(e) {
    //     $('.menu-item').removeClass('active');
    //     $(this).addClass('active');
    // });
});