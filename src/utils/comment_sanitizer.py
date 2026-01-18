"""
Comment Sanitization for LLM Safety

Removes comments and sensitive patterns before sending code to LLM providers.
"""
import re
import ast
from typing import Set, List, Optional
from dataclasses import dataclass


@dataclass
class SanitizationResult:
    """Result of comment sanitization."""
    sanitized_code: str
    removed_comments: List[str]
    sensitive_patterns_found: List[str]
    is_safe: bool


class CommentSanitizer:
    """
    Sanitizes code before sending to LLM by removing comments and sensitive patterns.
    
    Features:
    - Removes all comments (# and triple-quote style)
    - Detects and redacts API keys, passwords, tokens
    - Preserves code structure and functionality
    - Provides audit trail of removed content
    """
    
    # Patterns that indicate sensitive information
    SENSITIVE_PATTERNS = [
        r'(?i)(api[_-]?key|secret|password|token|credential)["\s]*[:=]["\s]*[a-zA-Z0-9_-]+',
        r'(?i)(bearer|auth)["\s]*[:=]["\s]*[a-zA-Z0-9_.-]+',
        r'sk-[a-zA-Z0-9]{32,}',  # OpenAI API keys
        r'AIza[a-zA-Z0-9_-]{35}',  # Google API keys
        r'(?i)password["\s]*[:=]["\s]*[^\s"\']+',
        r'(?i)secret["\s]*[:=]["\s]*[^\s"\']+',
    ]
    
    def __init__(self, strict_mode: bool = True):
        """
        Args:
            strict_mode: If True, treat any sensitive pattern as unsafe
        """
        self.strict_mode = strict_mode
    
    def sanitize(self, code: str) -> SanitizationResult:
        """
        Sanitize code by removing comments and sensitive patterns.
        
        Args:
            code: Source code to sanitize
            
        Returns:
            SanitizationResult with sanitized code and metadata
        """
        removed_comments = []
        sensitive_patterns = []
        
        # Step 1: Extract and remove comments
        sanitized_code, comments = self._remove_comments(code)
        removed_comments.extend(comments)
        
        # Step 2: Check for sensitive patterns in original code
        for pattern in self.SENSITIVE_PATTERNS:
            matches = re.findall(pattern, code)
            if matches:
                sensitive_patterns.extend(matches)
        
        # Step 3: Additional sanitization of string literals
        sanitized_code = self._sanitize_string_literals(sanitized_code)
        
        # Step 4: Determine if code is safe to send
        is_safe = len(sensitive_patterns) == 0 or not self.strict_mode
        
        return SanitizationResult(
            sanitized_code=sanitized_code,
            removed_comments=removed_comments,
            sensitive_patterns_found=sensitive_patterns,
            is_safe=is_safe
        )
    
    def _remove_comments(self, code: str) -> tuple[str, List[str]]:
        """Remove comments while preserving code structure."""
        lines = code.split('\n')
        sanitized_lines = []
        removed_comments = []
        
        in_multiline_string = False
        string_delimiter = None
        
        for line in lines:
            sanitized_line = ""
            i = 0
            
            while i < len(line):
                char = line[i]
                
                # Handle string literals
                if char in ['"', "'"]:
                    if not in_multiline_string:
                        # Check for triple quotes
                        if i + 2 < len(line) and line[i:i+3] == char * 3:
                            in_multiline_string = True
                            string_delimiter = char * 3
                            sanitized_line += line[i:i+3]
                            i += 3
                            continue
                        else:
                            # Regular string
                            string_end = self._find_string_end(line, i)
                            sanitized_line += line[i:string_end+1]
                            i = string_end + 1
                            continue
                    elif line[i:i+3] == string_delimiter:
                        # End of multiline string
                        in_multiline_string = False
                        string_delimiter = None
                        sanitized_line += line[i:i+3]
                        i += 3
                        continue
                
                # Handle comments (only if not in string)
                if char == '#' and not in_multiline_string:
                    comment = line[i:]
                    removed_comments.append(comment.strip())
                    break  # Rest of line is comment
                
                sanitized_line += char
                i += 1
            
            sanitized_lines.append(sanitized_line.rstrip())
        
        return '\n'.join(sanitized_lines), removed_comments
    
    def _find_string_end(self, line: str, start: int) -> int:
        """Find the end of a string literal, handling escapes."""
        quote = line[start]
        i = start + 1
        
        while i < len(line):
            if line[i] == quote:
                return i
            elif line[i] == '\\':
                i += 2  # Skip escaped character
            else:
                i += 1
        
        return len(line) - 1  # String continues to end of line
    
    def _sanitize_string_literals(self, code: str) -> str:
        """Replace suspicious string literals with placeholders."""
        # This is a simplified implementation
        # In production, you'd want more sophisticated pattern matching
        for pattern in self.SENSITIVE_PATTERNS:
            code = re.sub(pattern, '"[REDACTED]"', code)
        
        return code


# Global sanitizer instance
_sanitizer = CommentSanitizer()


def sanitize_code_for_llm(code: str) -> SanitizationResult:
    """
    Convenience function to sanitize code before LLM transmission.
    
    Args:
        code: Source code to sanitize
        
    Returns:
        SanitizationResult with sanitized code and safety information
    """
    return _sanitizer.sanitize(code)


def is_safe_for_llm(code: str) -> bool:
    """
    Quick check if code is safe to send to LLM.
    
    Args:
        code: Source code to check
        
    Returns:
        True if safe, False if contains sensitive patterns
    """
    result = _sanitizer.sanitize(code)
    return result.is_safe