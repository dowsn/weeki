function openYear() {
      const yearSelector = document.getElementById('yearSelector');
      const selectedYear = yearSelector.value;

      if (selectedYear) {
          window.location.href = `/app/year/${selectedYear}`;
      }
}


function populateGrid(data) {
  var grid = $('#yearGridContainer');
  Object.entries(data).forEach(([key, values]) => {
    let elementHTML = '';
    let currentWeekClass = values.current ? "currentWeek" : "";

    if (values.week_colors && values.week_colors.length > 0) {
      const colorElements = values.week_colors.map(color => {
        return `<div class="weekiColorElement" style="background-color: ${color}"></div>`;
      }).join('');
      elementHTML = `<div class="weekiColors editableWeek ${currentWeekClass}">${colorElements}</div>`;
    } else if (values.past) {
      const blackElement = `<div class="weekiColorElement" style="background-color: var(--dark)"></div>`;
      elementHTML = `<div class="weekiColors editableWeek">${blackElement}</div>`;
    } else if (values.current) {
      elementHTML = `<div class="weekiColors editableWeek ${currentWeekClass}"></div>`;
    } else {
      // Empty weeks
      elementHTML = ''; // This will clear any existing content
    }

    // Always update the cell, even if it's to clear it
    grid.find(`td[value='${key}']`).html(elementHTML);
  });


  // Add click event to td elements
  grid.find('td[value]').click(function() {
   
    if($(this).find('.weekiColors').hasClass('editableWeek')){
      var tdValue = $(this).attr('value');
      var year = $('#yearSelector').val();


      if (year && tdValue) {
          window.location.href = '/app/week/' + year + '/' + tdValue;
    } 
  }
})
}

