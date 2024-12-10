class TopicForm {
  constructor(modalId, onSave) {
    this.modal = document.getElementById(modalId);
    this.form = this.modal.querySelector('form');
    this.closeBtn = this.modal.querySelector('.close');
    this.onSave = onSave;

    this.topicName = document.getElementById('topicName');
    this.topicColor = document.getElementById('topicColor');
    this.topicDescription = document.getElementById('topicDescription');

    this.closeBtn.addEventListener('click', () => this.close());
    this.form.addEventListener('submit', (e) => this.handleSubmit(e));
  }

  open(topic = null) {
    if (topic) {
      this.topicName.value = topic.name;
      this.topicColor.value = topic.color;
      this.topicDescription.value = topic.description;
      this.editingTopic = topic;
    } else {
      this.form.reset();
      this.editingTopic = null;
    }
    this.modal.style.display = 'block';
  }

  close() {
    this.modal.style.display = 'none';
  }

  handleSubmit(e) {
    e.preventDefault();
    const topic = this.editingTopic || {};
    topic.name = this.topicName.value;
    topic.color = this.topicColor.value;
    topic.description = this.topicDescription.value;
    this.onSave(topic);
    this.close();
  }
}

// This will be used to initialize the form in different contexts
window.initTopicForm = function(modalId, onSave) {
  return new TopicForm(modalId, onSave);
};