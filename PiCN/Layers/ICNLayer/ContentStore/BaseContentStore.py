"""Abstract BaseContentStore for usage in BasicICNLayer"""

import abc
import multiprocessing
import time
from typing import List

from PiCN.Packets import Content, Name


class ContentStoreEntry(object):
    """Entry of the content store"""
    def __init__(self, content: Content, static: bool=False):
        self._content: Content = content
        self._static: bool = static
        self._timestamp = time.time()

    @property
    def content(self):
        return self._content

    @content.setter
    def content(self, content):
        self._content = content

    @property
    def static(self):
        return self._static

    @static.setter
    def static(self, static):
        self._static = static

    @property
    def timestamp(self):
        return self._timestamp

    @timestamp.setter
    def timestamp(self, timestamp):
        self._timestamp = timestamp

    def __eq__(self, other):
        return self._content == other._content

class BaseContentStore(object):
    """Abstract BaseContentStore for usage in BasicICNLayer"""
    def __init__(self, manager: multiprocessing.Manager):
        self._manager = manager
        self._container: List[ContentStoreEntry] = self._manager.list()

    @abc.abstractclassmethod
    def add_content_object(self, content: Content, static: bool=False):
        """check if there is already a content object stored, otherewise store it in the container"""

    @abc.abstractclassmethod
    def find_content_object(self, name: Name) -> ContentStoreEntry:
        """check if there is a matching content object"""

    @abc.abstractclassmethod
    def remove_content_object(self, name: Name):
        """Remove a content object from CS"""

    @abc.abstractclassmethod
    def update_timestamp(self, cs_entry: ContentStoreEntry):
        """Update Timestamp of a ContentStoreEntry"""

    @property
    def container(self):
        return self._container

    @container.setter
    def container(self, container):
        self._container = container

    @property
    def manager(self):
        return self._manager

    @manager.setter
    def manager(self, manager: multiprocessing.Manager):
        self._manager = manager