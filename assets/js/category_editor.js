$(document).ready(function() {
  const topicForm = new TopicForm('topicModal', saveTopicCallback);
  const $activeList = $('#active-topics');
  const $inactiveList = $('#inactive-topics');

  if ($activeList.length && $inactiveList.length) {
      new Sortable($activeList[0], {
          group: 'topics',
          animation: 150,
          handle: '.drag-handle',
          onEnd: updateTopicOrder
      });
      new Sortable($inactiveList[0], {
          group: 'topics',
          animation: 150,
          handle: '.drag-handle',
          onEnd: updateTopicOrder
      });
  }

  function saveTopicCallback(topic) {
      const $topicItem = $(`.topic-item[data-id="${topic.id}"]`);
      if ($topicItem.length) {
          $topicItem.css('backgroundColor', topic.color);
          $topicItem.find('h3').text(topic.name);
      }
      updateTopicOrder();
  }

  $('#deleteTopicBtn').on('click', function(e) {
      e.preventDefault();
      const topicId = $('#topicId').val();
      if (confirm('Are you sure you want to delete this topic?')) {
          $.ajax({
              url: `on/delete-topic/${topicId}/`,
              method: 'POST',
              headers: {
                  'X-CSRFToken': getCookie('csrftoken')
              },
              success: function(data) {
                  if (data.status === 'success') {
                      $(`.topic-item[data-id="${topicId}"]`).remove();
                      topicForm.close();
                      updateTopicOrder();
                  }
              }
          });
      }
  });

  function updateTopicOrder() {
      const activeTopics = $activeList.children().map(function() {
          return $(this).data('id');
      }).get();
      const inactiveTopics = $inactiveList.children().map(function() {
          return $(this).data('id');
      }).get();
      const allTopics = activeTopics.concat(inactiveTopics);
      $.ajax({
          url: 'on/update-topic-order/',
          method: 'POST',
          headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': getCookie('csrftoken')
          },
          data: JSON.stringify({topic_order: allTopics}),
          success: function(data) {
              if (data.status === 'success') {
                  console.log('Topic order updated successfully');
              }
          }
      });
  }

  window.openTopicModal = function(topicId) {
      $.getJSON(`/get-topic/${topicId}/`, function(data) {
          if (data.status === 'success') {
              topicForm.open(data.topic);
          }
      });
  };
});

class TopicForm {
  constructor(modalId, onSave) {
      this.$modal = $(`#${modalId}`);
      this.$form = this.$modal.find('form');
      this.$closeBtn = this.$modal.find('.close');
      this.onSave = onSave;

      this.$topicId = $('#topicId');
      this.$topicName = $('#topicName');
      this.$topicColor = $('#topicColor');
      this.$topicDescription = $('#topicDescription');
      this.$topicActive = $('#topicActive');

      this.$closeBtn.on('click', () => this.close());
      this.$form.on('submit', (e) => this.handleSubmit(e));
  }

  open(topic = null) {
      if (topic) {
          this.$topicId.val(topic.id);
          this.$topicName.val(topic.name);
          this.$topicColor.val(topic.color);
          this.$topicDescription.val(topic.description);
          if (this.$topicActive.length) {
              this.$topicActive.prop('checked', topic.active);
          }
          this.editingTopic = topic;
      } else {
          this.$form[0].reset();
          this.editingTopic = null;
      }
      this.$modal.show();
  }

  close() {
      this.$modal.hide();
  }

  handleSubmit(e) {
      e.preventDefault();
      const topic = this.editingTopic || {};
      topic.id = this.$topicId.val();
      topic.name = this.$topicName.val();
      topic.color = this.$topicColor.val();
      topic.description = this.$topicDescription.val();
      topic.active = this.$topicActive.length ? this.$topicActive.prop('checked') : true;

      $.ajax({
          url: 'on/update-topic/',
          method: 'POST',
          headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': getCookie('csrftoken')
          },
          data: JSON.stringify(topic),
          success: (data) => {
              if (data.status === 'success') {
                  this.onSave(topic);
                  this.close();
              } else {
                  alert(data.message || 'Error updating topic');
              }
          }
      });
  }
}

function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
          const cookie = jQuery.trim(cookies[i]);
          if (cookie.substring(0, name.length + 1) === (name + '=')) {
              cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
              break;
          }
      }
  }
  return cookieValue;
}