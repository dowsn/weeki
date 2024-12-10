// const
var base_url = window.location.origin;


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
            <button class="popup-cancel-btn"></button>
            <button class="popup-ok-btn"></button>
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
        togglePopup();
        activePopup = null;
    });

    $popup.find('.popup-cancel-btn').click(function() {
        settings.cancelCallback();
        $popup.remove();
        togglePopup();
        activePopup = null;
    });

    $('.wrapper').append($popup);
    activePopup = $popup;
}

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


$(document).ready(function() {
  const $switcher = $('.switcher');
  const $buttons = $switcher.find('button');
  const $slider = $switcher.find('.slider');
  function moveSlider(index) {
    $slider.css('transform', `translateX(${index * 100}%)`);
  }
  
  $buttons.each(function(index) {
    $(this).on('click', function() {
      var value = $(this).attr('value');
      $buttons.removeClass('active');
      $(this).addClass('active');
      moveSlider(index);
      if ($switcher.hasClass('week_sorting')) {
       
        
        ajaxCall('api', 'update_profile', { sorting_type: value })
        .then(response => {
          if (response.success === true) {
            location.reload();
          } else {
            console.log(response.message);
          }
        })
        .catch(error => {
          console.error('Error updating profile:', error);
        });


        
      } else if ($switcher.hasClass('topic_view')) {
        
        ajaxCall('api', 'update_profile', { topic_view: value })
        .then(response => {
          if (response.success === true) {
            location.reload();
          } else {
            console.log(response.message);
          }
        })
        .catch(error => {
          console.error('Error updating profile:', error);
        });
      }
    });
  });
  // Initialize slider position based on the active button
  const $activeButton = $switcher.find('button.active');
  if ($activeButton.length) {
    moveSlider($activeButton.index());
  }
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