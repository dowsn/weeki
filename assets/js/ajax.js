const ajaxCall = async (app, path, data = null, method = 'POST') => {
  const appURL = `${window.location.origin}/${app}`;
  const headers = {
    'X-CSRFToken': getCsrfToken(),
    'Content-Type': 'application/json'
  };
  const config = {
    url: `${appURL}/${path}`,
    method: method,
    headers: headers,
    data: data ? JSON.stringify(data) : undefined,
    xhrFields: { withCredentials: true }
  };

  try {
    const response = await $.ajax(config);
    return response;
  } catch (error) {
    console.error('API call failed for this path:', path, 'error:', error);
    throw error;
  }
};

// Function to get CSRF token
function getCsrfToken() {
  return document.querySelector('[name=csrfmiddlewaretoken]').value;
}