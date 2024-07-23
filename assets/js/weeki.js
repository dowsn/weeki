$(document).ready(function() {
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
});