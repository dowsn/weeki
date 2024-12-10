$(document).ready(function() {

  $('.closeButton').click(function() {
      showPopup({
          message: "Are you sure you want to discard this weeki?",
          okText: "Discard",
          cancelText: "Keep",
          okCallback: function() {

              const full_url = `${base_url}/on/week`;
              window.location.href = full_url;
          },
          cancelCallback: function() {
              console.log("Action cancelled. Staying on the page.");
          }
      });
  });




  const $contentEditable = $('.newWeekiText');
  const bottomBarHeight = 70; // Height of the bottom bar on mobile
  const mobileBreakpoint = 768; // Typical breakpoint for mobile devices
  const bottomPadding = 40; // Padding at the bottom of the content

  function adjustHeight() {
      const windowWidth = $(window).width();
      const windowHeight = $(window).height();

      if (windowWidth <= mobileBreakpoint) {
          // Mobile layout
          const safeHeight = windowHeight - bottomBarHeight;

          $contentEditable.css({
              'height': `${safeHeight}px`,
              'max-height': `${safeHeight}px`,
              'overflow-y': 'auto',
              'padding-bottom': `${bottomPadding}px`,
              'box-sizing': 'border-box'
          });
      } else {
          // Desktop layout - reset to default or set a different height
          $contentEditable.css({
              'height': `${windowHeight}px`, 
              'max-height': `${windowHeight}px`, 
              'overflow-y': 'auto',
              'padding-bottom': `${bottomPadding}px`,
          });
      }
  }

  function autoScroll() {
      $contentEditable.scrollTop($contentEditable[0].scrollHeight);
  }

  adjustHeight();
  $(window).on('resize', adjustHeight);

  // Auto-scroll on input
  $contentEditable.on('input', function() {
      autoScroll();
  });

  // Set focus on load
  $contentEditable.focus();

  // Remove the mousedown event handler that was preventing selection
  // $contentEditable.off('mousedown');

  // Form submission
  const $form = $('form');


  function submitForm() {
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
    let existingContent = $transcriptContainer.text();

    // Remove any existing interim span
    existingContent = existingContent.replace(/\*\*.*?\*\*/g, '');
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
      newContent += 
        '**' 
        + interimTranscript
        + '**';
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
    console.log("WebSocket connection established");
    console.log(host);
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
  // Topic selection
    const $editForm = $('#editWeekiForm');
    const $topicButtons = $('.topic-button');
    const $topicInput = $('#id_topic');

    $topicButtons.on('click', function() {
      $topicButtons.removeClass('active');
      $(this).addClass('active');
      $topicInput.val($(this).data('topic-id'));
    });

    // Set initial topic value
    const $activeButton = $('.topic-button.active');
    if ($activeButton.length) {
      $topicInput.val($activeButton.data('topic-id'));
    }

 
    // add later if edite on edit form 
    // $contentEditable.on('input', updateSubmitButtonText);
  });