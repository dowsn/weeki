
This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Weeki is a Django-based conversational AI application that enables users to have structured conversations with AI agents. The application features real-time chat via WebSockets, topic management, user profiles, and integrations with various AI providers (Anthropic, XAI, OpenAI) and vector databases (Pinecone).


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

## Project File References

### Key Files to Review
- **`@app/models.py`**: Core data models for the application, defining database schema and relationships
- **`@api/consumers.py`**: WebSocket consumer handling real-time communication and message routing
- **`@api/agents/main/conversation_agent.py`**: Primary agent for managing conversation flow and interactions
- **`@api/agents/main/moment_manager.py`**: Manages conversation moments and interaction states
- **`@api/agents/models/conversation_models.py`**: Pydantic models for structuring conversation data
- **`@api/agents/graph/graph_conversation.py`**: Graph-based conversation management and context tracking
- **`@api/agents/handlers/topic_manager.py`**: Handles topic creation, association, and management
- **`@api/views.py`**: REST API views for handling HTTP requests
- **`@api/urls.py`**: URL routing configuration for API endpoints
- **`@api/agents/handlers/time_manager.py`**: Manages time-related aspects of conversations
- **`@api/agents/handlers/session_manager.py`**: Handles chat session lifecycle and metadata
- **`@api/agents/handlers/pinecone_manager.py`**: Manages vector database interactions for semantic search
- **`@api/agents/handlers/log_manager.py`**: Logging and tracking system interactions