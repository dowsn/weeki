

function openWeek() {

         const week_selector = $('#weekSelector');
         const selected_week = week_selector.val();
         const selected_year = week_selector.attr('data-year');

        console.log(selected_week);
        console.log(selected_year);

         if (selected_week && selected_year) {
             window.location.href = `/app/week/${selected_year}/${selected_week}`;
         }
   }

function editWeeki(weeki_id) {

  const weeki_url = `/app/weeki/edit/${weeki_id}`;

  window.location.href = weeki_url;
  
}


function deleteWeeki(weeki_id) {
  // Confirm deletion with the user
  if (confirm("Are you sure you want to delete this weeki?")) {
      // Construct the correct URL for the delete operation
      const deleteUrl = `${window.location.origin}/app/weeki/delete/${weeki_id}`;

      // Send DELETE request to the server
      fetch(deleteUrl, {
          method: 'DELETE',
          headers: {
              'X-CSRFToken': getCsrfToken(), // Function to get CSRF token
              'Content-Type': 'application/json'
          },
      })
      .then(response => response.json())
      .then(data => {
          if (data.success) {
            const deleteButton = $(`.delete-btn[data-weeki-id="${weeki_id}"]`);
            if (deleteButton) {
                // Navigate up the DOM to find the weeki-box
                const weekiBox = deleteButton.closest('.weeki-box');
                if (weekiBox) {
                    weekiBox.remove();
                } else {
                    console.error('Could not find the weeki-box to remove');
                }
            } else {
                console.error('Could not find the delete button');
            }
          }
      })
      .catch(error => {
          console.error('Error:', error);
          alert("An error occurred while deleting the weeki.");
      });
  }
   console.warn(`Could not find weeki element with ID ${weeki_id} to remove.`);
}



 



// Helper function to get CSRF token from cookies

function getCsrfToken() {
  return document.querySelector('[name=csrfmiddlewaretoken]').value;
}
// function deleteWeeki(weeki_id) {

//   const weeki_url = `/app/weeki/delete/${weeki_id}`;

//   window.location.href = weeki_url;

// }











