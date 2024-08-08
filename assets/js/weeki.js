$(document).ready(function() {

  const favoriteStars = document.querySelectorAll('.favorite-star-input');
  favoriteStars.forEach(star => {
      star.addEventListener('change', function() {
          // You can add any additional logic here
          console.log('Favorite status:', this.checked);
      });
  });

  $('.newWeekiText').click();
  // Resizing
  const $contentEditable = $('.newWeekiText');
  function adjustHeight() {
    $contentEditable.height(`${$(window).height() - 100}px`);
  }
  adjustHeight();
  $(window).on('resize', adjustHeight);

  // Form submission
  const $form = $('form');
  const $hiddenInput = $('<input>', {
    type: 'hidden',
    name: 'content'
  });
  $form.append($hiddenInput);

  function submitForm() {
    $hiddenInput.val($contentEditable.html());
    $form[0].submit(); // Use native form submission to avoid jQuery's recursive submit
  }

  $form.on('submit', function(e) {
    e.preventDefault();
    submitForm();
  });

  // Handle the save button click
  const $saveButton = $('.saveButton');
  if ($saveButton.length) {
    $saveButton.on('click', submitForm);
  }

  

    // recording

  const $transcriptContainer = $('.newWeekiText');
  const $recordButton = $('.recordButton');
  let fullTranscript = [];
  let interimTranscript = '';
  let mediaRecorder;
  let socket;
  let isRecording = false;
  let stream;

  let lastTranscriptTime = Date.now();
  let silenceTimer;
  const SILENCE_THRESHOLD = 8000; // 8 seconds
  const SILENCE_CHECK_INTERVAL = 1000; // Check every second

  let lastTranscriptLength = 0;

  function updateTranscriptDisplay() {
    let existingContent = $transcriptContainer.html();

    // Remove any existing interim span
    existingContent = existingContent.replace(/<span class="interim">.*?<\/span>/, '');

    // Trim any trailing spaces
    existingContent = existingContent.trim();

    // Remove the last transcript to avoid duplication
    if (lastTranscriptLength > 0) {
      existingContent = existingContent.slice(0, -lastTranscriptLength).trim();
    }

    // Add a space if there's existing content
    if (existingContent && fullTranscript.length > 0) {
      existingContent += ' ';
    }

    let newContent = fullTranscript.join(' ');
    lastTranscriptLength = newContent.length;

    if (interimTranscript) {
      newContent += ' <span class="interim">' + interimTranscript + '</span>';
    }

    $transcriptContainer.html(existingContent + newContent);
    $transcriptContainer.scrollTop($transcriptContainer[0].scrollHeight);
    lastTranscriptTime = Date.now();
  }

  // Add event listener for manual text input
  $transcriptContainer.on('input', function() {
    if (!isRecording) {
      lastTranscriptLength = 0;
      fullTranscript = [$transcriptContainer.text()];
    }
  });

  function toggleRecording() {
      if (!isRecording) {
          startRecording();
      } else {
          stopRecording();
      }
  }



  function startRecording() {
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
      navigator.mediaDevices.getUserMedia({audio: true})
        .then(audioStream => {
          stream = audioStream;
          mediaRecorder = new MediaRecorder(stream);
          mediaRecorder.addEventListener('dataavailable', handleDataAvailable);
          mediaRecorder.start(250);

          $recordButton.html('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80"><rect x="20" y="15" width="15" height="50" rx="2" ry="2" class="svg-fill" /><rect x="45" y="15" width="15" height="50" rx="2" ry="2" class="svg-fill" /></svg>').addClass('recording');
          isRecording = true;
          if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({action: 'start'}));
          } else {
            console.error("WebSocket is not open. Cannot send start signal.");
          }

          fullTranscript = [];
          lastTranscriptLength = 0;
          lastTranscriptTime = Date.now();

          startSilenceDetection();
        })
        .catch(err => {
          console.error("Error accessing the microphone:", err);
          alert("Error accessing the microphone. Please ensure you have given permission and no other application is using it.");
        });
    } else {
      console.error("getUserMedia not supported on your browser!");
      alert("Voice recording is not supported on your browser. Please try using a modern browser like Chrome or Firefox.");
    }
  }

  function handleDataAvailable(event) {
    if (event.data.size > 0 && socket && socket.readyState === WebSocket.OPEN && isRecording) {
      socket.send(event.data);
    }
  }

  function startSilenceDetection() {
    silenceTimer = setInterval(() => {
      if (isRecording && Date.now() - lastTranscriptTime >= SILENCE_THRESHOLD) {
        console.log("Stopping recording due to silence");
        stopRecording();
      }
    }, SILENCE_CHECK_INTERVAL);
  }

  function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
    }
    if (stream) {
      stream.getTracks().forEach(track => track.stop());
    }

    $recordButton.html('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80"><circle cx="40" cy="40" r="35" fill="red" /></svg>').removeClass('recording');
    isRecording = false;
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({action: 'stop'}));
    } else {
      console.error("WebSocket is not open. Cannot send stop signal.");
    }

    clearInterval(silenceTimer);
  }

  function initializeWebSocket() {
    const host = window.location.hostname;
    socket = new WebSocket('wss://' + host + '/listen');
    socket.onopen = () => {
      console.log({event: 'onopen'});
      $recordButton.prop('disabled', false);
    }
    socket.onmessage = (message) => {
      const received = JSON.parse(message.data);
      if (received.transcript) {
        console.log(received.transcript, received.is_final);
        if (received.is_final) {
          fullTranscript.push(received.transcript);
          interimTranscript = '';
        } else {
          interimTranscript = received.transcript;
        }
        updateTranscriptDisplay();
        // Update lastTranscriptTime here as well
        lastTranscriptTime = Date.now();
      }
    }
    socket.onclose = () => {
      console.log({event: 'onclose'});
      $recordButton.prop('disabled', true);
      setTimeout(initializeWebSocket, 3000);
    }
    socket.onerror = (error) => {
      console.log({event: 'onerror', error});
    }
  }

  initializeWebSocket();
  $recordButton.on('click', toggleRecording);
  


  // EDIT FORM 

  
  // Get the current date
  // Category selection
    const $editForm = $('#editWeekiForm');
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

 
    // add later if edite on edit form 
    // $contentEditable.on('input', updateSubmitButtonText);
  });