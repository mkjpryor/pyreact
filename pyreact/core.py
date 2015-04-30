"""
This module contains the core of pyreact, i.e. the portion that is responsible for
maintaining the data-flow graph and propagating updates through it

Unless explicitly told otherwise, emitters maintain only weak references to their
children, so a child can be garbage collected if the only references to it are held
by emitters

In contrast, reactors maintain hard references to their parents, so an emitter
can only be garbage collected if there are no direct references to it and it has
no children

Inspiration comes from:

  * scala.rx (https://github.com/lihaoyi/scala.rx)
  * Knockout (http://knockoutjs.com/)
  * Bacon.js (https://baconjs.github.io/)
  
@author: Matt Pryor <mkjpryor@gmail.com>
"""

import itertools
import abc
import weakref


class Node(object):
    """
    A node in the data-flow graph
    """
    
    __metaclass__ = abc.ABCMeta
    
    @abc.abstractproperty
    def level(self):
        """
        The level of the node in the data-flow graph
        """
        pass
    
    
class Emitter(Node):
    """
    A node that emits pings to its children
    
    Emitters maintain only weak references to their children, allowing a child to
    be garbage collected when the emitter holds the only reference to it 
    """
    
    # The set of hard references to children
    __hard_refs = set()
    
    # The set of weak references to children
    __weak_refs = set()
    
    def __compact_weak_refs(self):
        """
        Removes dead references from __weak_refs and returns the new set
        """
        self.__weak_refs = { ref for ref in self.__weak_refs if ref() is not None }
        return self.__weak_refs
        
    @property
    def children(self):
        """
        The set of reactors that are dependent on this emitter
        """
        # Combine the hard refs and weak refs into one set
        # Return a frozenset so that it can't be messed about with
        return frozenset(self.__hard_refs | { ref() for ref in self.__compact_weak_refs() })
    
    def link_child(self, reactor, keep_alive = False):
        """
        Creates an edge in the data-flow graph between this emitter and the given reactor
        """
        # If we already have a reference to the reactor, there is nothing to do
        if reactor in self.__hard_refs:
            return
        for ref in self.__compact_weak_refs():
            if ref() == reactor:
                return
        # Otherwise, add an edge between this emitter and the reactor
        if keep_alive:
            self.__hard_refs.add(reactor)
        else:
            self.__weak_refs.add(weakref.ref(reactor))
        reactor.link_parent(self)
        
    def unlink_child(self, reactor):
        """
        Removes any edge in the data-flow graph between this emitter and the given reactor
        """
        # If we have the reactor as a hard ref, that is easy
        if reactor in self.__hard_refs:
            self.__hard_refs.discard(reactor)
            reactor.unlink_parent(self)
            return
        # Checking if we have a weak ref is more involved
        found = None
        for ref in self.__compact_weak_refs():
            if ref() == reactor:
                found = ref
                break
        if found:
            self.__weak_refs.discard(found)
            reactor.unlink_parent(self)
        
        
class Reactor(Node):
    """
    A node that reacts to pings from its parents
    """
    
    # The set of parents
    __parents = set()
    
    @property
    def parents(self):
        """
        The set of emitters which this reactor is dependent on
        """
        return frozenset(self.__parents)
    
    def link_parent(self, emitter):
        """
        Creates an edge in the data-flow graph between this reactor and the given emitter
        """
        if emitter not in self.__parents:
            self.__parents.add(emitter)
            # Make sure we are linked as a child to the emitter
            emitter.link_child(self)
    
    def unlink_parent(self, emitter):
        """
        Removes any edge in the data-flow graph between this reactor and the given emitter
        """
        if emitter in self.__parents:
            self.__parents.discard(emitter)
            # Make sure we are also unlinked from the parent
            emitter.unlink_child(self)
    
    @abc.abstractmethod
    def ping(self, incoming):
        """
        Pings this reactor, causing it to react
        
        incoming is a set of emitters
        
        Returns the set of reactors to which changes should be propagated
        """
        pass
    
    def dispose(self):
        """
        Manually destroys all edges to the reactor to allow garbage collection
        """
        for p in self.parents():
            self.unlink_parent(p)


class Propagator(object):
    """
    Propagates changes through the data-flow graph using a breadth-first method
    
    ping should be called exactly once for each affected reactor in the data-flow graph
    """
    
    def propagate(self, source):
        """
        Propagates changes to source through the object graph
        """
        # Get a set of (emitter, reactor) tuples for the given emitter
        pings = { (source, r) for r in source.children }
        while len(pings) != 0:
            # Split the pings into those that will happen now and those that will
            # happen later based on the level of the reactors
            min_level = min((r.level for (_, r) in pings))
            now = { p for p in pings if p[1].level == min_level }
            pings -= now
            # Group the pings to be done now by reactor
            for (r, ps) in itertools.groupby(now, lambda p: p[1]):
                # Cause the reactor to react to the pings
                #   Remove the reactor from the pings before passing them
                todo = r.ping({ e for (e, _) in ps })
                # If the reactor is also an emitter, add the returned pings
                # to the list for next time
                if isinstance(r, Emitter):
                    pings |= { (r, r_next) for r_next in todo }

    @classmethod
    def instance(cls):
        """
        Gets an instance of the propagator
        """
        if not hasattr(cls, "__instance"):
            cls.__instance = Propagator()
        return cls.__instance
