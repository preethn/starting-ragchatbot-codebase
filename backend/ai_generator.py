import anthropic
from typing import List, Optional


class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""

    MAX_TOOL_ROUNDS = 2

    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to a comprehensive search tool for course information.

Search Tool Usage:
- Use the search tool **only** for questions about specific course content or detailed educational materials
- **Two searches per query maximum** — use a second search only when the first result is genuinely insufficient
- After receiving search results, you MUST always write a response — never produce an empty reply
- Synthesize search results into accurate, fact-based responses, even if the results are partial
- If search yields no results, state this clearly without offering alternatives

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without searching
- **Course-specific questions**: Search first, then answer
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, search explanations, or question-type analysis
 - Do not mention "based on the search results"
 - Do not say you need to do more searches — answer from what you have


All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""

    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

        self.base_params = {"model": self.model, "temperature": 0, "max_tokens": 800}

    def generate_response(
        self,
        query: str,
        conversation_history: Optional[str] = None,
        tools: Optional[List] = None,
        tool_manager=None,
    ) -> str:
        """
        Generate AI response with optional tool usage and conversation context.
        Supports up to MAX_TOOL_ROUNDS sequential tool-calling rounds.
        """

        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        messages = [{"role": "user", "content": query}]

        api_params = {
            **self.base_params,
            "messages": messages,
            "system": system_content,
        }

        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}

        response = self.client.messages.create(**api_params)

        round_count = 0
        while (
            response.stop_reason == "tool_use"
            and tool_manager
            and round_count < self.MAX_TOOL_ROUNDS
        ):
            try:
                messages = self._execute_tool_round(response, messages, tool_manager)
            except Exception:
                break

            round_count += 1

            if round_count < self.MAX_TOOL_ROUNDS:
                # More rounds possible — keep tools available so Claude can search again
                next_params = {
                    **self.base_params,
                    "messages": messages,
                    "system": system_content,
                    "tools": tools,
                    "tool_choice": {"type": "auto"},
                }
            else:
                # Rounds exhausted — strip tools to force a prose response
                next_params = {
                    **self.base_params,
                    "messages": messages,
                    "system": system_content,
                }

            response = self.client.messages.create(**next_params)

        # If Claude stopped without tool_use, return this response directly
        return response.content[0].text

    def _execute_tool_round(self, response, messages: List, tool_manager) -> List:
        """
        Execute all tool calls in a response and append results to the message list.
        Returns the updated message list.
        Raises on tool execution failure so the caller can exit the loop.
        """
        messages = messages.copy()

        # Append Claude's tool-use turn
        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for content_block in response.content:
            if content_block.type == "tool_use":
                tool_result = tool_manager.execute_tool(
                    content_block.name, **content_block.input
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": content_block.id,
                        "content": tool_result,
                    }
                )

        messages.append(
            {
                "role": "user",
                "content": tool_results
                + [
                    {
                        "type": "text",
                        "text": "Now provide your response based on the search results above.",
                    }
                ],
            }
        )

        return messages
