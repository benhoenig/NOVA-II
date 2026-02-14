#!/usr/bin/env python3
"""
LLM utility module for NOVA II.

Handles interactions with OpenAI and Anthropic APIs.
"""

import os
import sys
import json
from enum import Enum
from typing import Optional, Dict, Any, List, Union

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Try imports
try:
    from openai import OpenAI, OpenAIError
except ImportError:
    OpenAI = None

try:
    from anthropic import Anthropic, AnthropicError
except ImportError:
    Anthropic = None

class LLMProvider(Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AUTO = "auto"

class LLMClient:
    def __init__(self):
        self.openai_client = None
        self.anthropic_client = None
        
        # Initialize OpenAI
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key and OpenAI:
            try:
                self.openai_client = OpenAI(api_key=openai_key)
            except Exception as e:
                print(f"Warning: Failed to initialize OpenAI client: {e}")

        # Initialize Anthropic
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key and Anthropic:
            try:
                self.anthropic_client = Anthropic(api_key=anthropic_key)
            except Exception as e:
                print(f"Warning: Failed to initialize Anthropic client: {e}")
        
        if not self.openai_client and not self.anthropic_client:
            # Don't throw here, just warn. Let the specific methods fail if called.
            pass

    def generate_text(self, 
                     prompt: str, 
                     system_prompt: str = "You are a helpful AI assistant.",
                     provider: LLMProvider = LLMProvider.AUTO,
                     model: str = None) -> Optional[str]:
        """Generate text from LLM."""
        
        # Determine initial provider
        selected_provider = self._select_provider(provider)
        result = None
        
        if selected_provider == LLMProvider.ANTHROPIC:
            result = self._generate_anthropic(prompt, system_prompt, model)
            # Fallback to OpenAI if failed and AUTO was requested
            if result is None and provider == LLMProvider.AUTO and self.openai_client:
                print("⚠️ Anthropic failed, falling back to OpenAI...")
                result = self._generate_openai(prompt, system_prompt)
                
        elif selected_provider == LLMProvider.OPENAI:
            result = self._generate_openai(prompt, system_prompt, model)
            # Fallback to Anthropic if failed and AUTO was requested
            if result is None and provider == LLMProvider.AUTO and self.anthropic_client:
                print("⚠️ OpenAI failed, falling back to Anthropic...")
                result = self._generate_anthropic(prompt, system_prompt)
        
        if result is None:
             print("❌ All LLM providers failed.")
             
        return result

    def generate_json(self, 
                     prompt: str, 
                     system_prompt: str = "You are a helpful AI assistant that outputs JSON.",
                     provider: LLMProvider = LLMProvider.AUTO,
                     model: str = None) -> Optional[Dict[str, Any]]:
        """Generate JSON from LLM."""
        
        # Force JSON instruction
        system_prompt += "\nIMPORTANT: Return ONLY valid JSON."
        
        text = self.generate_text(prompt, system_prompt, provider, model)
        if not text:
            return None
            
        # Clean up markdown
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
            
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}")
            print(f"Raw output: {text}")
            return None

    def _select_provider(self, requested: LLMProvider) -> LLMProvider:
        if requested != LLMProvider.AUTO:
            if requested == LLMProvider.ANTHROPIC and self.anthropic_client:
                return LLMProvider.ANTHROPIC
            if requested == LLMProvider.OPENAI and self.openai_client:
                return LLMProvider.OPENAI
        
        # Auto selection (preference logic)
        if self.anthropic_client:
            return LLMProvider.ANTHROPIC
        if self.openai_client:
            return LLMProvider.OPENAI
            
        return None

    def _generate_anthropic(self, prompt: str, system: str, model: str = None) -> Optional[str]:
        if not self.anthropic_client:
            return None
            
        try:
            # Default model
            model = model or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
            print(f"🤖 Using Anthropic ({model})...")
            
            message = self.anthropic_client.messages.create(
                model=model,
                max_tokens=4000,
                system=system,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return message.content[0].text
        except Exception as e:
            print(f"Anthropic generation error: {e}")
            return None

    def _generate_openai(self, prompt: str, system: str, model: str = None) -> Optional[str]:
        if not self.openai_client:
            return None
            
        try:
            # Default model
            model = model or os.getenv("OPENAI_MODEL", "gpt-4o")
            print(f"🤖 Using OpenAI ({model})...")
            
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"OpenAI generation error: {e}")
            return None

def main():
    """Test function."""
    client = LLMClient()
    print("Testing LLM generation...")
    response = client.generate_text("Say 'Hello NOVA'!", provider=LLMProvider.AUTO)
    print(f"Response: {response}")

if __name__ == "__main__":
    main()
