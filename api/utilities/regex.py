import re


def clean_content(content):
  # Strip any remaining HTML tags
  content = re.sub('<[^<]+?>', '', content)
  # Replace multiple newlines with a single newline
  content = re.sub(r'\n+', '\n', content)
  # Remove any potential dangerous patterns
  content = re.sub(r'[\"\"][\w\s]*(on\w+)[\w\s]*(=)[\w\s]*[\"\"][^>]*', '',
                   content)
  # Strip leading/trailing whitespace
  return content.strip()
