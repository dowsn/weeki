// $(document).ready(function() {
//   const modal = $('#topicEditModal');
//   const editButton = $('.edit-topic');
//   const closeButton = modal.find('.close');
//   const form = $('#topicEditForm');

//   editButton.click(function() {
//       const topicId = $(this).data('topic-id');

//       // Fetch topic form
//       $.ajax({
//           url: `/on/topic/${topicId}/`,
//           method: 'GET',
//           dataType: 'json',
//           success: function(data) {
//               form.html(data.html);
//               form.attr('data-topic-id', data.topic_id);
//               modal.show();
//           },
//           error: function(xhr, status, error) {
//               console.error("Error fetching topic form:", error);
//           }
//       });
//   });

//   closeButton.click(function() {
//       modal.hide();
//   });

//   $(window).click(function(event) {
//       if (event.target === modal[0]) {
//           modal.hide();
//       }
//   });

//   form.submit(function(e) {
//       e.preventDefault();
//       const formData = $(this).serialize();
//       const topicId = $(this).attr('data-topic-id');

//       $.ajax({
//           url: `/on/topic/${topicId}/`,
//           method: 'POST',
//           data: formData,
//           dataType: 'json',
//           success: function(data) {
//               if (data.success) {
//                   location.reload();
//               } else {
//                   let errorHtml = '<ul>';
//                   for (const [field, errors] of Object.entries(data.errors)) {
//                       errorHtml += `<li>${field}: ${errors.join(', ')}</li>`;
//                   }
//                   errorHtml += '</ul>';
//                   $('#formErrors').html(errorHtml).show();
//               }
//           },
//           error: function(xhr, status, error) {
//               console.error("Error updating topic:", error);
//               alert("Error updating topic. Please try again.");
//           }
//       });
//   });
// });