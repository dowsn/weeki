const ajaxCall = async (path, data = null, method = 'POST') => {
  const appURL = `${window.location.origin}/app/`;

  const headers = {
    'X-CSRFToken': getCsrfToken(),
  };

  const config = {
    method: method,
    headers,
    credentials: 'include', // This includes cookies, which is important for session-based auth
  };

  if (data) {
    config.body = JSON.stringify(data);  // Send data as JSON
  }

  try {
    console.log(`Making ${method} request to ${appURL}${path}`); // Debug log
    const response = await fetch(`${appURL}${path}`, config);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error('API call failed:', error);
    throw error;
  }
};

// Function to get CSRF token
function getCsrfToken() {
  return document.querySelector('[name=csrfmiddlewaretoken]').value;
}