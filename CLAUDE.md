# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Weeki is a Django-based conversational AI application that enables users to have structured conversations with AI agents. The application features real-time chat via WebSockets, topic management, user profiles, and integrations with various AI providers (Anthropic, XAI, OpenAI) and vector databases (Pinecone).

## Core Architecture

### Application Structure
- **`django_project/`** - Main Django project configuration and settings
- **`app/`** - Core Django app containing user models, chat sessions, topics, and main UI views
- **`api/`** - REST API and WebSocket endpoints, contains the AI conversation agents
- **`accounts/`** - User authentication and profile management
- **`payments/`** - Stripe integration for subscription handling
- **`blog/`** - Simple blog functionality
- **`assets/`** - Static files (CSS, JS, images, fonts)
- **`templates/`** - Django templates for web interface

### Key Models (app/models.py)
- **`Profile`** - Extended user profile with encrypted fields, tokens, character settings
- **`Chat_Session`** - Individual conversation sessions with time tracking and topic associations
- **`Topic`** - User-created topics that can be associated with chat sessions
- **`Message`** - Individual messages within chat sessions
- **`Log`** - System logs for session tracking and debugging

### AI Agent System (api/agents/)
The conversation system is built with a modular agent architecture:
- **`conversation_agent.py`** - Main facade orchestrating the conversation system
- **`moment_manager.py`** - Handles conversation moments and AI interactions
- **`handlers/`** - Utility classes for conversation, logging, topic management, time tracking
- **`models/conversation_models.py`** - Pydantic models for conversation state management

### Real-time Communication
- WebSocket consumers in `api/consumers.py` handle real-time chat
- Uses Django Channels with in-memory channel layers
- WebSocket routing defined in `api/routing.py`
- Authentication via JWT tokens passed in WebSocket query params

### Data Security
- Sensitive user data (emails, chat content, topics) encrypted using custom `EncryptedField` classes
- Encryption key stored in environment variable `ENCRYPTION_KEY`
- JWT authentication for API endpoints
- CORS configuration for frontend integration

## Development Commands

### Environment Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Apply database migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run development server
python manage.py runserver

# Run with WebSocket support (recommended)
daphne -b 0.0.0.0 -p 8000 django_project.asgi:application
```

### Database Operations
```bash
# Create migrations for model changes
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Access Django shell
python manage.py shell

# Dump database (PostgreSQL)
python scripts/dump.py
```

### Utility Scripts
- **`scripts/clean_cache.py`** - Clear application caches
- **`scripts/migrate_to_postgres.py`** - Database migration utilities
- **`scripts/analyze_libraries.py`** - Analyze project dependencies

## Environment Variables

### Required
- `ANTHROPIC_API_KEY` - Anthropic Claude API access
- `XAI_API_KEY` - XAI Grok API access
- `OPENAI_API_KEY` - OpenAI API access
- `PINECONE_API_KEY` - Pinecone vector database
- `PINECONE_INDEX_NAME` - Pinecone index name
- `ENCRYPTION_KEY` - Field-level encryption key
- `DATABASE_URL` - PostgreSQL connection string
- `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET` - Payment processing

### Database (PostgreSQL)
- `PGDATABASE`, `PGUSER`, `PGPASSWORD`, `PGHOST`, `PGPORT`

### Email Configuration
- `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`
- `DEFAULT_FROM_EMAIL`

## API Integration Patterns

### WebSocket Authentication
```python
# Extract JWT token from WebSocket query params
query_string = self.scope['query_string'].decode()
params = parse_qs(query_string)
token = params.get('token', [None])[0]
```

### AI Model Usage
```python
# Initialize AI model (currently using XAI Grok)
ai_model = init_chat_model(
    model="xai:grok-3-mini-fast-beta",
    temperature=0.7,
    reasoning_effort="high"
)
```

### Topic and Session Management
- Topics can be associated with chat sessions through `SessionTopic` many-to-many relationship
- Sessions track conversation state, time limits, and generate summaries
- Logs are attached to sessions for debugging and conversation flow tracking

## Testing

The project uses Django's built-in testing framework. Test files are located in each app directory:
- `accounts/tests.py`
- `api/tests.py`
- `app/tests.py`
- `blog/tests.py`
- `payments/tests.py`

```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test app
python manage.py test api
```

## Key Integrations

### Vector Database (Pinecone)
- Used for semantic search and conversation context retrieval
- Configuration in `api/utilities/pinecone.py`
- Embedding generation via OpenAI or HuggingFace models

### LangChain Integration
- Framework for AI agent interactions
- Custom conversation chains and memory management
- Integration with multiple LLM providers (Anthropic, XAI, OpenAI)

### Stripe Payments
- Subscription management for premium features
- Webhook handling for payment events
- User token allocation based on subscription status

## Common Patterns

### Encrypted Data Handling
```python
# All sensitive user data should use encrypted fields
class MyModel(models.Model):
    sensitive_data = EncryptedTextField(max_length=500)
    user_email = EncryptedEmailField(max_length=100)
```

### Async Database Operations
```python
# Use database_sync_to_async for database operations in async contexts
@database_sync_to_async
def get_user_profile(user_id):
    return User.objects.get(pk=user_id).profile
```

### WebSocket Message Broadcasting
```python
# Send messages to WebSocket groups
await self.channel_layer.group_send(
    self.room_group_name,
    {
        'type': 'chat_message',
        'message': message_data
    }
)
```