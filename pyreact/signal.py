"""
This module contains the signal (and associated observer) implementation

Signals represent values that vary with time, but always have the concept
of a current value

Observers are used to perform side effects due to changes in signals

Observers are always on the edge of the graph, and guaranteed to be called
only once all signals have reached their final state

Observers are linked to their parents with hard links in both directions, 
which means that anonymous observers can be created without having to
worry about keeping references
In the case where you end up with an observer and its parent signal(s) forming
a cycle of hard references with no references from the outside, the Python
GC should recognise this and collect them all
If not, the observer can be explicitly freed using o.dispose(), which will
then allow the parent signal(s) to be collected
  
@author: Matt Pryor <mkjpryor@gmail.com>
"""

import abc

from pyutil import result

from pyreact.core import Reactor, Emitter, Propagator
from pyreact import tracking, util


class Signal(Emitter):
    """
    Base type for signals
    """
    
    def apply(self):
        """
        Gets the current value of this signal, while also registering a dependency
        """
        # This is the same as now, but just registers a dependency with the tracking
        tracking.register_dependency(self)
        return self.now
    
    @property
    @abc.abstractmethod
    def now(self):
        """
        Gets the current value of this signal, but doesn't register a dependency
        """
        pass
    
    def observe(self, on_value = util.nothing, on_error = util.throw):
        """
        Register the given functions to be called when this signal changes value
        
        on_value is called when the signal changes to a new value
        on_error is called when the signal changes to an error
        
        Returns the Observer created to call the functions
        """
        def action():
            try:
                on_value(self())
            except Exception as e:
                on_error(e)
        return Observer(action)
    
    def to_result(self):
        """
        Returns the current state of this signal as a result (i.e. a success or failure)
        """
        try:
            return result.Success(self.now)
        except Exception as e:
            return result.Failure(e)
    
    def __call__(self):
        """
        Syntactic sugar for self.apply
        """
        return self.apply()


class Val(Signal):
    """
    Signal type for a constant value
    """
    
    def __init__(self, value):
        super(Val, self).__init__()
        self.__value = value
        
    @property
    def level(self):
        # Constant values are always at the root
        return 0
    
    @property
    def now(self):
        return self.__value
    
    
class Var(Signal):
    """
    Signal type for a value that can be changed
    """
    
    def __init__(self, initial):
        super(Var, self).__init__()
        self.__current = initial
        
    @property
    def level(self):
        # Variables are always at the root
        return 0
        
    @property
    def now(self):
        return self.__current
    
    def update(self, new_value, propagator = Propagator.instance()):
        """
        Updates the current value of this signal to the new value and propagates
        the change through the data-flow graph
        """
        
        if new_value != self.__current:
            self.__current = new_value
            # Propagate the update
            propagator.propagate(self, result.Success(self.__current))
            
    def __lshift__(self, new_value):
        """
        Syntactic sugar for self.update
        
        Returns this signal to allow for chained 'pushes'
        """
        self.update(new_value)
        return self
        
        
class Computed(Signal, Reactor):
    """
    Signal type for a signal whose value is computed from the values of other
    signals
    """
    
    def __init__(self, calc):
        Signal.__init__(self)
        Reactor.__init__(self)
        self.__calc = calc
        # Our state is a Result (Success or Failure) representing the current
        # state of our underlying computation
        self.__state = self.__recalculate()
        
    @property
    def now(self):
        # If the state is an error, this will raise it
        return self.__state.result
    
    def ping(self, incoming):
        # Recalculate our state
        new_state = self.__recalculate()
        # If our state hasn't changed, there is nothing to propagate
        if new_state == self.__state: return set()
        # Otherwise, propagate the change to our children
        self.__state = new_state
        return { (c, self.__state) for c in self.children }

    def __recalculate(self):
        # Link ourself to our dependencies as we go
        tracking.begin(lambda dep: dep.link_child(self))
        # If an error occurs during the calculation, we want to store it
        r = None
        try:
            r = result.Success(self.__calc())
        except Exception as e:
            r = result.Failure(e)
        finally:
            tracking.end()
        return r


class Observer(Reactor):
    """
    Observers are used for performing side effects in response to changes in signals
    
    They are guaranteed to be executed once per propagation wave, once the values of
    all signals are settled down
    """
    
    def __init__(self, action):
        super(Observer, self).__init__()
        self.__action = action
        self.__do_action()  # Call the action for the initial values, and
                            # to establish dependencies  
        
    @property
    def level(self):
        # Observers are always on the edge of the graph, so return Inf
        return float('inf')
    
    def ping(self, incoming):
        self.__do_action()  # When pinged, we just call our action
        return set()  # There is nothing to propagate
    
    def __do_action(self):
        # We want to register dependencies as we go, so we get called again
        tracking.begin(lambda dep: dep.link_child(self, keep_alive = True))
        try:
            self.__action()
        finally:
            tracking.end()
