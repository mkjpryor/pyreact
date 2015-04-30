"""
This module is responsible for the automatic dependency tracking
  
@author: Matt Pryor <mkjpryor@gmail.com>
"""


# The stack of callables
__stack = []
# The current callable
__current = None


def begin(callback):
    """
    Start a new tracking frame over the top of the current one
    
    The given callback will be called with the dependency whenever
    a dependency is registered
    """
    global __current, __stack
    if __current is not None:
        __stack.append(__current)
    __current = callback
    
    
def end():
    """
    Ends the current tracking frame and restores the previous frame
    """
    global __current, __stack
    __current = None
    if __stack:
        __current = __stack.pop()
        
        
def register_dependency(dep):
    """
    Registers dep as a dependency in the current frame
    """
    global __current
    if __current:
        __current(dep)
