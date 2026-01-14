
def formal_calculation(x, y):
    """
    Formal example showcasing:
    1. Constant Folding: 10 * 30 * 2
    2. Dead Code: i = 0 that is never used, or if False block
    3. Unused variables
    4. Simple arithmetic simplification
    """
    # Constant folding candidate
    a = 10 * 30 * 2
    
    # Dead code candidate
    unused_var = 999
    
    # Simple simplification
    result = x + 0
    result = result * 1
    
    if False:
        print("This will never run")
        result += 1000
        
    # Another constant folding
    b = a + 40
    
    return result + b + (y * 0)
