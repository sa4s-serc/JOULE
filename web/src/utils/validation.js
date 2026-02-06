/**
 * Validation utilities for the HEDGE web interface
 */

/**
 * Validate Python code syntax (basic check)
 */
export const validatePythonCode = (code) => {
  const errors = [];
  
  if (!code || code.trim().length === 0) {
    errors.push('Code cannot be empty');
    return { isValid: false, errors };
  }

  // Basic syntax checks
  const lines = code.split('\n');
  let indentLevel = 0;
  let inFunction = false;
  
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const lineNum = i + 1;
    
    // Skip empty lines and comments
    if (line.trim() === '' || line.trim().startsWith('#')) {
      continue;
    }
    
    // Check for basic Python syntax
    if (line.includes('def ') && !line.includes(':') && !line.trim().endsWith('\\')) {
      errors.push(`Line ${lineNum}: Function definition missing colon`);
    }
    
    // Check for 'if' statements but exclude inline if expressions
    const trimmedLine = line.trim();
    if (trimmedLine.startsWith('if ') && !line.includes(':') && !line.includes('else') && !line.trim().endsWith('\\')) {
      errors.push(`Line ${lineNum}: If statement missing colon`);
    }
    
    // Check for 'for' loops but exclude list/dict/set comprehensions
    // Comprehensions have 'for' inside brackets/parens, not at statement level
    if (trimmedLine.startsWith('for ') && !line.includes(':') && !line.trim().endsWith('\\')) {
      errors.push(`Line ${lineNum}: For loop missing colon`);
    }
    
    // Check for 'while' loops at statement level
    if (trimmedLine.startsWith('while ') && !line.includes(':') && !line.trim().endsWith('\\')) {
      errors.push(`Line ${lineNum}: While loop missing colon`);
    }
    
    // Check for unmatched parentheses (basic)
    const openParens = (line.match(/\(/g) || []).length;
    const closeParens = (line.match(/\)/g) || []).length;
    if (openParens !== closeParens) {
      errors.push(`Line ${lineNum}: Unmatched parentheses`);
    }
  }
  
  return {
    isValid: errors.length === 0,
    errors
  };
};

/**
 * Validate test code
 */
export const validateTestCode = (code) => {
  const errors = [];
  
  if (!code || code.trim().length === 0) {
    errors.push('Test code cannot be empty');
    return { isValid: false, errors };
  }
  
  // Check if it contains at least one test function
  if (!code.includes('def test_') && !code.includes('assert')) {
    errors.push('Test code should contain at least one test function or assertion');
  }
  
  // Basic Python validation
  const pythonValidation = validatePythonCode(code);
  errors.push(...pythonValidation.errors);
  
  return {
    isValid: errors.length === 0,
    errors
  };
};

/**
 * Validate optimization configuration
 */
export const validateOptimizationConfig = (config) => {
  const errors = [];
  
  if (config.generations < 1 || config.generations > 100) {
    errors.push('Generations must be between 1 and 100');
  }
  
  if (config.population_size < 2 || config.population_size > 50) {
    errors.push('Population size must be between 2 and 50');
  }
  
  if (!['micro', 'standard', 'advanced'].includes(config.level)) {
    errors.push('Level must be one of: micro, standard, advanced');
  }
  
  return {
    isValid: errors.length === 0,
    errors
  };
};

/**
 * Validate allowed imports
 */
export const validateAllowedImports = (importsString) => {
  const errors = [];
  
  if (!importsString) {
    return { isValid: true, errors: [] };
  }
  
  const imports = importsString.split(',').map(i => i.trim()).filter(i => i);
  
  for (const imp of imports) {
    // Basic validation - no spaces, valid Python identifier
    if (!/^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)*$/.test(imp)) {
      errors.push(`Invalid import: ${imp}`);
    }
  }
  
  return {
    isValid: errors.length === 0,
    errors
  };
};