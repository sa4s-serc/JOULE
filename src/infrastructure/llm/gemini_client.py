"""
Gemini LLM Client Implementation

This module provides a client for interacting with Google's Gemini API
for semantic code analysis and mutation suggestions.
"""

import os
from typing import List, Optional, Dict, Any

try:
    import google.generativeai as genai
    from google.generativeai.types import GenerateContentResponse
except ImportError:
    genai = None
    GenerateContentResponse = None


class GeminiClient:
    """
    Client for Google's Gemini API.
    
    Provides interface for semantic code analysis and mutation suggestions
    to be used by higher-level mutators in the HEDGE system.
    """

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash"):
        """
        Initialize Gemini client.
        
        Args:
            api_key: Google API key (if None, tries to get from environment)
            model_name: Name of the Gemini model to use
        """
        if genai is None:
            raise ImportError(
                "google-generativeai package is required. Install with: "
                "pip install google-generativeai"
            )
            
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Gemini API key is required. Set GEMINI_API_KEY environment variable "
                "or pass api_key parameter"
            )
            
        self.model_name = model_name
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(model_name)
        
    def analyze_code(self, code: str, prompt: str) -> Optional[str]:
        """
        Analyze code using Gemini.
        
        Args:
            code: Code to analyze
            prompt: Analysis prompt
            
        Returns:
            Analysis result or None if failed
        """
        try:
            full_prompt = f"{prompt}\n\nCode:\n{code}"
            response: GenerateContentResponse = self.model.generate_content(full_prompt)
            return response.text if response.text else None
        except Exception as e:
            print(f"Gemini API error: {e}")
            return None
            
    def suggest_mutations(self, code: str, context: str = "") -> List[Dict[str, Any]]:
        """
        Suggest code mutations using Gemini.
        
        Args:
            code: Code to mutate
            context: Additional context about the code
            
        Returns:
            List of mutation suggestions
        """
        prompt = f"""
        Analyze the following code and suggest optimizations or improvements.
        Focus on performance, readability, and best practices.
        
        Context: {context}
        
        Provide suggestions in JSON format:
        {{
            "suggestions": [
                {{
                    "type": "optimization_type",
                    "description": "What to change",
                    "confidence": 0.8,
                    "code_change": "specific change description"
                }}
            ]
        }}
        """
        
        try:
            result = self.analyze_code(code, prompt)
            if result:
                # Parse JSON response (simplified - in production would use proper JSON parsing)
                import json
                parsed = json.loads(result)
                return parsed.get("suggestions", [])
        except Exception as e:
            print(f"Error parsing Gemini response: {e}")
            
        return []
        
    def is_available(self) -> bool:
        """Check if Gemini API is available."""
        try:
            # Simple test call
            response = self.model.generate_content("test")
            return True
        except:
            return False

    def complete(self, prompt: str) -> str:
        """
        Complete a text prompt using Gemini.
        
        Args:
            prompt: The prompt to complete
            
        Returns:
            The completed text response
        """
        try:
            response: GenerateContentResponse = self.model.generate_content(prompt)
            return response.text if response.text else ""
        except Exception as e:
            print(f"Gemini completion error: {e}")
            return ""
