$(document).ready(function() {

  $('.option').each(function () {
      $(this).on('click', function () {
          var selected_year = $(this).attr('year')

          window.location.href = `/on/year/${selected_year}`;

      });
  });    
});

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
      const blackElement = `<div class="weekiColorElement" style="background-color: var(--main)"></div>`;
      elementHTML = `<div class="weekiColors">${blackElement}</div>`;
    } else if (values.current) {
      elementHTML = `<div class="weekiColors editableWeek ${currentWeekClass}"></div>`;
    } else {
      // Empty weeks
      elementHTML = ''; // This will clear any existing content
    }

    // Always update the cell, even if it's to clear it
    grid.find(`td[value='${key}']`).html(elementHTML);
    grid.find(`td[value='${key}']`).attr("start", values.start_date);
  });

  removeEmptyQuarters();

  // Add click event to td elements
  grid.find('td[value]').click(function() {
   
    if($(this).find('.weekiColors').hasClass('editableWeek')){
      var tdValue = $(this).attr('value');
      var year = $('.yearSelector').attr('year');



      if (year && tdValue) {
          window.location.href = '/on/week/' + year + '/' + tdValue;
    } 
  }
})
}

function removeEmptyQuarters() {
  const table = document.querySelector('.table');
  const rows = Array.from(table.rows);
  const quarters = [
    rows.slice(0, 5),   // Quarter I
    rows.slice(5, 10),  // Quarter II
    rows.slice(10, 15), // Quarter III
    rows.slice(15)      // Quarter IV
  ];

  quarters.forEach((quarterRows, index) => {
    let hasWeekiColor = false;

    // Check if any cell in this quarter has a weekiColor element
    quarterRows.forEach(row => {
      Array.from(row.cells).forEach(cell => {
        if (cell.querySelector('.weekiColorElement')) {
          hasWeekiColor = true;
        }
      });
    });

    // If no weekiColor found, remove this quarter
    if (!hasWeekiColor) {
      quarterRows.forEach(row => {
        if (row.parentNode) {  // Check if the row still exists in the DOM
          row.parentNode.removeChild(row);
        }
      });
      console.log(`Removed Quarter ${index + 1} due to no weekiColor elements`);
    }
  });
}

