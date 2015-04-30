"""
This module contains utility functions for use with pyreact
  
@author: Matt Pryor <mkjpryor@gmail.com>
"""


def nothing(*args, **kwargs):
    """
    Takes any number of arguments, does nothing with them and returns nothing
    """
    pass


def throw(e):
    """
    Takes an exception and raises it
    """
    raise e
