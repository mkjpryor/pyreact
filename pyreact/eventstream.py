"""
This module contains the event stream (and associated observer) implementation

Event streams emit values at discrete points in time - they have no concept
of a current value

Observers are used to perform side effects in response to events

Observers are always on the edge of the graph, and guaranteed to be called
only once per propagation wave, regardless of how many event streams they
are dependent on

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

from pyutil import result

from pyreact.core import Emitter, Reactor, Propagator
from pyreact import util


class EventStream(Emitter):
    """
    Base type for event streams
    """
    
    def observe(self, on_value = util.nothing, on_error = util.throw):
        """
        Register the given functions to be called when an event is emitted
        
        on_value is called when a new value is emitted
        on_error is called when an error is emitted
        
        Returns the Observer created to call the functions
        """
        return Observer(self, on_value, on_error)


class EventSource(EventStream):
    """
    Event stream implementation that is a source of events, which are specifically
    emitted using emit (or <<)
    """
    
    @property
    def level(self):
        # Event sources are always at the root of the graph
        return 0
    
    def emit(self, value, propagator = Propagator.instance()):
        """
        Propagates the given value through the data-flow graph
        """
        propagator.propagate(self, result.Success(value))
    
    def __lshift__(self, value):
        """
        Syntactic sugar for self.emit
        
        Returns this event source to allow for chained 'pushes'
        """
        self.emit(value)
        return self
        

class Observer(Reactor):
    """
    Observers are used for performing side effects in response to events
    
    They are guaranteed to be executed only once per propagation wave
    """
    
    def __init__(self, events, on_value = util.nothing, on_error = util.throw):
        super(Observer, self).__init__()
        self.__on_value = on_value
        self.__on_error = on_error
        events.link_child(self, keep_alive = True)
        
    @property
    def level(self):
        # Observers are always on the edge of the graph, so return Inf
        return float('inf')
    
    def ping(self, incoming):
        # When pinged, just call the relevant action depending on whether
        # we received a success or a failure
        try:
            res = next((r for (e, r) in incoming if e in self.parents))
        except StopIteration:
            # If the ping was not from our parent, there is nothing to do
            return set()
        if res.success:
            self.__on_value(res.result)
        else:
            self.__on_error(res.error)
        return set()  # There is nothing to propagate
