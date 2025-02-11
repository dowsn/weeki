from typing import Dict, Optional
from langchain import hub

class PromptManager:
    def __init__(self):
        self.base_prompt = hub.pull("chat_mr_week:02e4c2fd")
        self.onboarding_prompts = {
            0: """As a self-development coach, I'd love to get to know you better. What areas of personal growth interest you the most? Feel free to share your thoughts on topics like career development, relationships, health, mindfulness, or any other areas you'd like to explore.""",
            1: """Thank you for sharing. For each area you mentioned, what specific goals or improvements would you like to work towards? This will help us create more focused and meaningful conversations.""",
            2: """What challenges or obstacles have you faced in these areas before? Understanding these will help me provide better support and strategies.""",
            3: """How do you prefer to learn and grow? For example, do you like practical exercises, deep discussions, reading recommendations, or a mix of approaches?"""
        }

    def build_response_prompt(self, context: Dict) -> str:
        """Builds context-aware prompt for response generation"""
        if context["topic_shift"] and context["potential_topic"]:
            topic_info = f"{context['retrieved_context'].get('topics', [])} | Potential new topic: {context['potential_topic']}"
            user_context = "User is exploring a potential new topic for their development journey"
        else:
            topic_info = str(context['retrieved_context'].get('topics', []))
            user_context = context.get('user_context', '')

        return self.base_prompt.partial(
            username=context['username'],
            topics=topic_info,
            chat_memory=context['conversation'],
            query=context.get('current_query', ''),
            user_context=user_context,
            literature_help=str(context['retrieved_context'].get('logs', []))
        )