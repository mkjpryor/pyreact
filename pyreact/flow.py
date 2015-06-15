"""
This module contains the implementation of the flow syntax for creating
event streams and signals
  
@author: Matt Pryor <mkjpryor@gmail.com>
"""

from pyutil import result

from pyreact.eventstream import EventStream as BaseEventStream
from pyreact.core import Reactor, Emitter


class EventStream(BaseEventStream, Reactor):
    """
    Event stream implementation that allows new event streams
    to be built from generator expressions yielding other event
    streams
    """
    
    def __init__(self, body):
        """
        Creates a new flow event stream with the given body
        
        body should be a generator expression that yields event streams,
        and should except this object as its single argument
        """
        BaseEventStream.__init__(self)
        Reactor.__init__(self)
        # Storage for the result to emit, if any
        self.__to_emit = None
        # Invoke the body once with this object to get our coroutine
        self.__gen = body(self)
        # Bind to the yielded emitter, if there is one
        try:
            e = self.__gen.send(None)
            e.link_child(self)
        except (GeneratorExit, StopIteration):
            # Ignore normal generator exceptions, but raise any others
            pass
    
    def ping(self, incoming):
        # Get the result associated with our current parent
        try:
            prev, res = next((i for i in incoming if i[0] in self.parents))
        except StopIteration:
            # If the ping was not from our parent, there is nothing to do
            return set()
        
        # Resume the generator with the result, and get the next emitter to bind to
        try:
            if res.success:
                fut = self.__gen.send(res.result)
            else:
                fut = self.__gen.throw(res.error)
            # Check if we need to bind to the new emitter, or whether it is the same as
            # the old one
            if prev is not fut:
                prev.unlink_child(self)
                fut.link_child(self)
        except Exception as err:
            # If the generator throws any exceptions, we want to unbind from the previous emitter
            prev.unlink_child(self)
            # If it is not a normal generator exception, we want to emit it as a failure
            if not isinstance(err, GeneratorExit) and not isinstance(err, StopIteration):
                self.__to_emit = result.Failure(err)
            
        # If we have anything to emit, emit it to our children
        if self.__to_emit is not None:
            val, self.__to_emit = self.__to_emit, None
            return { (c, val) for c in self.children }
        else:
            return set()
    
    def __lshift__(self, value):
        """
        Emits the given value at the next opportunity
        """
        self.__to_emit = result.Success(value)
        return self
    