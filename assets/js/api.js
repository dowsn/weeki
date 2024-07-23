

const apiCall = async (path, method = 'GET', data = null) => {
  const apiURL = `${window.location.origin}/api/`;
  const headers = {
    'Content-Type': 'application/json',
  };

  // Get the access token from local storage
  let accessToken = localStorage.getItem('accessToken');

  if (!accessToken) {
    throw new Error('No access token available. User needs to log in.');
  }

  // Add the access token to the headers
  headers['Authorization'] = `Bearer ${accessToken}`;

  const config = {
    method,
    headers,
    credentials: 'include',
  };

  if (data && (method === 'POST' || method === 'PUT' || method === 'PATCH')) {
    config.body = JSON.stringify(data);
  }

  try {
    const response = await fetch(`${apiURL}${path}`, config);

    if (response.status === 401) {
      // Token might be expired, try to refresh it
      const newAccessToken = await refreshToken();
      if (newAccessToken) {
        // Retry the original request with the new token
        headers['Authorization'] = `Bearer ${newAccessToken}`;
        const retryResponse = await fetch(`${apiURL}${path}`, {...config, headers});
        return await retryResponse.json();
      } else {
        throw new Error('Unable to refresh token. User needs to log in again.');
      }
    }

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error('API call failed:', error.message);
    throw error;
  }
};

const refreshToken = async () => {
  const refreshToken = localStorage.getItem('refreshToken');
  if (!refreshToken) {
    return null;
  }

  try {
    const response = await fetch(`${apiURL}token/refresh/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ refresh: refreshToken }),
    });

    if (!response.ok) {
      throw new Error('Failed to refresh token');
    }

    const data = await response.json();
    localStorage.setItem('accessToken', data.access);
    return data.access;
  } catch (error) {
    console.error('Token refresh failed:', error.message);
    return null;
  }
};