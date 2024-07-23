
$(document).ready(function() {
  
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