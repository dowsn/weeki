import json
import requests
import os
import time


def midjourney_send_and_get_job_id(prompt: str):
  endpoint = "https://api.ttapi.io/midjourney/v1/imagine"

  headers = {"TT-API-KEY": os.environ.get("MIDJOURNEY_API_KEY")}

  data = {
      "prompt": prompt,
      "mode": "relax",
      "hookUrl": "",
      "timeout": 600,
      "getUImages": True
  }

  response = requests.post(endpoint, headers=headers, json=data)

  print(response.status_code)
  print(response.json())

  job_id = response.json()["data"]["jobId"]

  return job_id


def midjourney_main(prompt: str, user_id):
  job_id = midjourney_send_and_get_job_id(prompt)

  # Wait for 10 minutes
  time.sleep(300)

  response = midjourney_receive_image(job_id)

  first_image_url = response["data"]["images"][0]

  download_image_from_url_and_save(first_image_url, user_id)


def midjourney_receive_image(job_id):

  headers = {"TT-API-KEY": os.environ.get("MIDJOURNEY_API_KEY")}

  endpoint = "https://api.ttapi.io/midjourney/v1/fetch"

  data = {
      "jobId": job_id,
  }
  response = requests.post(endpoint, headers=headers, json=data)

  print(response.status_code)
  print(response.json())

  return response.json()


import requests
import os
import time


def download_image_from_url_and_save(url, user_id):
  # Send a GET request to the URL
  response = requests.get(url)
  # Check if the request was successful
  if response.status_code == 200:
    # Define the root folder and the full path for the file
    media_folder = 'media/profile_images'
    full_path = os.path.join(media_folder, f"{user_id}.png")
    # Write the content to the file in the root folder
    with open(full_path, 'wb') as file:
      file.write(response.content)
    print(f"Image downloaded successfully: {full_path}")
  else:
    print(f"Failed to download image. Status code: {response.status_code}")


def midjourney_send_and_get_job_id(prompt: str):
  endpoint = "https://api.ttapi.io/midjourney/v1/imagine"
  headers = {"TT-API-KEY": os.environ.get("MIDJOURNEY_API_KEY")}
  data = {
      "prompt": prompt,
      "mode": "relax",
      "hookUrl": "",
      "timeout": 600,
      "getUImages": True
  }
  response = requests.post(endpoint, headers=headers, json=data)
  print(response.status_code)
  print(response.json())
  job_id = response.json()["data"]["jobId"]
  return job_id


def midjourney_receive_image(job_id):
  headers = {"TT-API-KEY": os.environ.get("MIDJOURNEY_API_KEY")}
  endpoint = "https://api.ttapi.io/midjourney/v1/fetch"
  data = {
      "jobId": job_id,
  }
  response = requests.post(endpoint, headers=headers, json=data)
  print(response.status_code)
  print(response.json())
  return response.json()


def midjourney_main(prompt: str, user_id):
  job_id = midjourney_send_and_get_job_id(prompt)
  max_attempts = 12  # 5 minutes * 12 = 1 hour total wait time
  attempt = 0
  while attempt < max_attempts:
      time.sleep(300)  # Wait for 5 minutes
      response = midjourney_receive_image(job_id)
      if response["status"] == "SUCCESS":
          first_image_url = response["data"]["images"][0]
          download_image_from_url_and_save(first_image_url, user_id)
          print(f"Image successfully processed and saved for user {user_id}")
          return True
      else:
          print(f"Attempt {attempt + 1}: Image not ready yet. Trying again in 5 minutes.")
          attempt += 1
  print(f"Failed to get a successful response after {max_attempts} attempts.")
  return False


# This function would be called by your cron job
# def cron_job_handler():
#   # You would need to implement a way to get pending jobs
#   # This could be from a database or a queue system
#   pending_jobs = get_pending_jobs()  # You need to implement this function

#   for job in pending_jobs:
#     success = midjourney_main(job['prompt'], job['user_id'])
#     if success:
#       mark_job_as_completed(job['id'])  # You need to implement this function
#     else:
#       mark_job_as_failed(job['id'])  # You need to implement this function

# # Run the cron job handler
# if __name__ == "__main__":
#   cron_job_handler()
