import os
from dotenv import load_dotenv
from openai import OpenAI
from langfuse import get_client
from datetime import datetime
import importlib.metadata
import time

# Load environment variables
load_dotenv()
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
langfuse = get_client()


def create_session_metadata(session_id, user_id, turn_number, total_turns):
    """Create metadata for session tracking"""
    return {
        "session_id": session_id,
        "user_id": user_id,
        "turn_number": turn_number,
        "total_turns": total_turns,
        "timestamp": datetime.now().isoformat(),
    }


def create_turn_metadata(session_id, user_id, turn_number, model, temperature, max_tokens):
    """Create metadata for individual turn tracking"""
    return {
        "session_id": session_id,
        "user_id": user_id,
        "turn_number": turn_number,
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "timestamp": datetime.now().isoformat(),
    }


def chat_turn(prompt, conversation_history, session_id, user_id, turn_number, model="gpt-3.5-turbo", temperature=0.7, max_tokens=150):
    """Execute a single chat turn with tracking"""
    turn_metadata = create_turn_metadata(session_id, user_id, turn_number, model, temperature, max_tokens)

    with (langfuse.start_as_current_generation(
            name=f"chat_turn_{turn_number}",
            model=model, input={"prompt": prompt, "conversation_context": len(conversation_history)},
            metadata=turn_metadata)
    as generation):
        # Build messages with conversation history
        messages = [{"role": "system", "content": "You are a helpful assistant. Keep responses concise but informative."}]
        messages.extend(conversation_history)
        messages.append({"role": "user", "content": prompt})

        response = openai_client.chat.completions.create(
            model=model,
            messages=messages,  # type: ignore
            temperature=temperature,
            max_tokens=max_tokens
        )

        response_text = response.choices[0].message.content

        # Update generation with response and usage
        if generation is not None:
            generation.update(
                output=response_text,
                usage={
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            )

        return response_text


def simulate_conversation_session(user_id, session_id, conversation_turns, model="gpt-3.5-turbo"):
    """Simulate a complete conversation session with multiple turns"""
    session_metadata = create_session_metadata(session_id, user_id, 0, len(conversation_turns))

    # Create a session-level span to group all turns
    with langfuse.start_as_current_span(
            name=f"conversation_session_{session_id}",
            input={"user_id": user_id, "session_id": session_id},
            metadata=session_metadata,
    ) as session_span:

        conversation_history = []
        print(f"\nStarting conversation session: {session_id} (User: {user_id})")
        print("-" * 60)

        for turn_num, user_prompt in enumerate(conversation_turns, 1):
            print(f"\nTurn {turn_num}/{len(conversation_turns)}")
            print(f" {user_id}: {user_prompt}")

            try:
                # Execute the chat turn
                bot_response = chat_turn(
                    prompt=user_prompt,
                    conversation_history=conversation_history,
                    session_id=session_id,
                    user_id=user_id,
                    turn_number=turn_num,
                    model=model,
                    temperature=0.7 + turn_num * 0.05,  # Slightly vary temperature per turn
                    max_tokens=150
                )

                print(f" LLM Response: {bot_response}")

                # Add to conversation history for context in next turns
                conversation_history.append({"role": "user", "content": user_prompt})
                conversation_history.append({"role": "assistant", "content": bot_response})

                # Add small delay between turns to simulate real conversation
                time.sleep(1)

            except Exception as e:
                print(f" Error in turn {turn_num}: {e}")

        # Update session span with final summary
        if session_span is not None:
            session_span.update(
                output={
                    "total_turns": len(conversation_turns),
                    "conversation_completed": True,
                    "final_context_length": len(conversation_history)
                }
            )

        print(f"\n Session {session_id} completed ({len(conversation_turns)} turns)")
        return conversation_history


def main():
    """Run multiple conversation sessions"""
    print()
    print("-" * 60)
    print("Multi-User Conversation Tracking with Langfuse")
    print("-" * 60)
    print()

    # Define multiple users and their conversation scenarios
    conversation_scenarios = {
        "nishant_tomar": {
            "session_1": [
                "Hi! Can you explain what machine learning is?",
                "That's interesting. How is it different from traditional programming?",
                "Can you give me a simple example of a machine learning application?",
                "Thanks! That was very helpful."
            ]
        },
        "megha_singh": {
            "session_1": [
                "I'm planning a trip to Japan. Any recommendations?",
                "What's the best time of year to visit?",
                "What about food? Any must-try dishes?",
            ],
            "session_2": [
                "Hey, I'm back! I went to Japan and it was amazing!",
                "The ramen was incredible. Do you know any good ramen recipes?",
                "Perfect, I'll try making it at home!"
            ]
        },
        "rajat_rajput": {
            "session_1": [
                "I'm learning Python. Can you help me understand loops?",
                "What's the difference between for loops and while loops?",
                "Can you show me a simple example?",
                "Great! How about list comprehensions?",
                "This is really helpful, thanks!"
            ]
        }
    }

    # Process all conversation scenarios
    for user_id, sessions in conversation_scenarios.items():
        for session_id, turns in sessions.items():
            full_session_id = f"{user_id}_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            simulate_conversation_session(
                user_id=user_id,
                session_id=full_session_id,
                conversation_turns=turns,
                model="gpt-3.5-turbo"
            )

            # Brief pause between sessions
            time.sleep(2)

    # Ensure all data is sent to Langfuse
    langfuse.flush()
    print(f"\n All conversation sessions completed!")
    print(f" Check your Langfuse dashboard to view:")
    print(f"   - Session-level traces (grouped conversations)")
    print(f"   - Turn-level generations (individual chat exchanges)")
    print(f"   - Filter by user_id, session_id, or turn_number")
    print(f"   - View conversation history and context evolution")


if __name__ == "__main__":
    main()