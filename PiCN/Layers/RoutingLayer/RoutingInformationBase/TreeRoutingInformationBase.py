
from typing import List, Tuple, Dict, Iterator

from datetime import datetime

from PiCN.Layers.ICNLayer.ForwardingInformationBase import BaseForwardingInformationBase, ForwardingInformationBaseEntry
from PiCN.Layers.RoutingLayer.RoutingInformationBase.BaseRoutingInformationBase import BaseRoutingInformationBase
from PiCN.Packets import Name


class _RIBTreeNode(object):

    def __init__(self, nc: bytes = None, collapse_reduce_to_shortest: bool = True):
        """
        :param nc: Name component represented by this node
        """
        self._collapse_shortest: bool = collapse_reduce_to_shortest
        # Reference to parent node
        self._parent: _RIBTreeNode = None
        # Children nodes
        self._children: Dict[bytes, _RIBTreeNode] = {}
        # Name component represented by this node
        self._nc: bytes = nc
        #                           fid        dist  timeout
        self._distance_vector: Dict[int, Tuple[int, datetime]] = {}

    def insert(self, name: Name, fid: int, distance: int, timeout: datetime=None):
        """
        Insert a new route into the RIB tree. This function can only be used on the root node.
        :param name: The ICN name of the route
        :param fid: The face ID  of the route
        :param distance: The distance of the route
        :param timeout: The timestamp after which to consider the route
        :raise ValueError: If not called on the root node
        """
        if self._parent is not None:
            raise ValueError('New RIB entries can only be inserted starting at the root node.')
        node = self
        comps = name.components
        # Find the deepest node with a common prefix to the to-be-inserted name
        while len(comps) > 0 and comps[0] in node._children.keys():
            node = node._children[comps[0]]
            comps = comps[1:]
        # For each remaining name component in the to-be-inserted name, create a new tree node
        while len(comps) > 0:
            child = _RIBTreeNode(comps[0], self._collapse_shortest)
            node._add_child(child)
            comps = comps[1:]
            node = child
        # Create a distance vector entry for the deepest node
        node._distance_vector[fid] = distance, timeout

    def collapse(self) -> List[Tuple[List[bytes], int, int, datetime]]:
        """
        Collapse the RIB information to a longest prefix representation for insertion into a FIB
        :return: Longest prefix representation
        """
        result: List[Tuple[List[bytes], int, int, datetime]] = []
        # Special treatment of the root node
        nclist = [self._nc] if self._nc is not None else []
        # If there are no children, simply add an entry for the own name
        if len(self._children) == 0:
            if len(self._distance_vector) > 0:
                if self._collapse_shortest:
                    result.append((list(nclist),) + self._get_best_fid())
                else:
                    for (fid, (dist, timeout)) in self._distance_vector.items():
                        result.append((list(nclist), fid, dist, timeout))
        else:
            # Call collapse() recursively on each child
            ch_res: List[Tuple[List[bytes], int, int, datetime]] = []
            for child in self._children.values():
                ch_res += child.collapse()
            # Add own name component to the name of each entry in the children's results
            if self._nc is not None:
                [c[0].insert(0, self._nc) for c in ch_res]
            # If there is an explicit distance vector entry for the node itself, add it to the children's results
            if len(self._distance_vector) > 0:
                if self._collapse_shortest:
                    ch_res.append((list(nclist),) + self._get_best_fid())
                else:
                    for (fid, (dist, timeout)) in self._distance_vector.items():
                        ch_res.append((list(nclist), fid, dist, timeout))
            # Collect the number of distinct face IDs
            subfids = set()
            for c in ch_res:
                subfids.add(c[1])
            # If there is only one face in the results, reduce the entries to a single prefix entry with the own name
            if len(subfids) == 1 and len(ch_res) > 1:
                sf = subfids.pop()
                dist, timeout = min([(c[2], c[3]) for c in ch_res if c[1] == sf])
                result.append((list(nclist), sf, dist, timeout))
            else:
                # If there is more than one face in the results, don't collapse the entries to a prefix entry
                for c in ch_res:
                    result.append(c)
        return result

    def ageing(self, now: datetime):
        """
        Remove outdated entries from the RIB.
        :param now: Reference time
        """
        # Recursively call ageing on all children
        for child in list(self._children.values()):
            child.ageing(now)
        # Remove all outdated distance vector entries
        todelete: List[int] = list()
        for (fid, (_, timeout)) in self._distance_vector.items():
            if timeout is not None and timeout <= now:
                todelete.append(fid)
        for fid in todelete:
            del self._distance_vector[fid]
        # Delete the node from the tree if it has no children and no distance vector entries left
        if self._parent is not None and len(self._distance_vector) == 0 and len(self._children) == 0:
            del self._parent._children[self._nc]
            self._parent = None

    def _add_child(self, child: '_RIBTreeNode'):
        """
        Add a child node to this node.
        :param child: The child to add
        :raise ValueError: If the node already has a parent
        """
        if child._parent is not None:
            raise ValueError(f'The node {child.__repr__()} already has a parent({child._parent.__repr__()}).')
        self._children[child._nc] = child
        child._parent = self

    def _get_best_fid(self) -> Tuple[int, int, datetime]:
        """
        Get the ID of the face with the minimal path to this name.
        :return: Face ID for the minimal distance path
        """
        (fid, (dist, timeout)) = min(self._distance_vector.items(), key=lambda x: x[1][0])
        return fid, dist, timeout

    def pretty_print(self, depth=0) -> str:
        """
        Create a pretty-print representation of the node and its children.
        """
        s = ''
        myname = self._nc.decode('utf-8') if self._nc is not None else '/'
        s += f'{"│ " * (depth-1)}├╴{myname}: {self._distance_vector}\n'
        for child in self._children.values():
            s += f'│ {child.pretty_print(depth + 1)}'
        return s

    def __repr__(self):
        if self._nc is None:
            return f'<_RIBTreeNode / ({len(self._distance_vector)} entries) at {id(self)}>'
        node: _RIBTreeNode = self
        comp: List[bytes] = []
        while node._nc is not None:
            comp.insert(0, node._nc)
            node = node._parent
        return f'<_RIBTreeNode {Name(comp)} ({len(self._distance_vector)} entries) at {id(self)}>'


class TreeRoutingInformationBase(BaseRoutingInformationBase):
    """
    Implementation of a Routing Information Base that uses a tree structure for internal storage.
    """

    def __init__(self, shortest_only: bool = True):
        """
        :param shortest_only: Whether to only add the shortest route to the FIB, or to add all routes.
        """
        super().__init__(shortest_only)
        self._tree: _RIBTreeNode = _RIBTreeNode(collapse_reduce_to_shortest=shortest_only)

    def ageing(self):
        """
        Remove outdated entries from the RIB.
        """
        self._tree.ageing(datetime.utcnow())

    def insert(self, name: Name, fid: int, distance: int, timeout: datetime = None):
        """
        Insert a new route into the RIB.
        :param name: The ICN name of the route
        :param fid: The face ID  of the route
        :param distance: The distance of the route
        :param timeout: The timestamp after which to consider the route
        :return:
        """
        self._tree.insert(name, fid, distance, timeout)

    def build_fib(self) -> List[ForwardingInformationBaseEntry]:
        """
        Construct FIB entries from the RIB data, and insert them into the passed FIB object.
        All previous entries in the FIB will be deleted.
        :param fib: The FIB to fill with routes.
        """
        # Clear all previous FIB entries
        # Add the longest prefix representation entries to the FIB
        fib: List[ForwardingInformationBaseEntry] = list()
        for name, fid, dist, timeout in self:
            fib.append(ForwardingInformationBaseEntry(name, fid, static=False))
        return fib

    def __iter__(self) -> Iterator[Tuple[Name, int, int, datetime]]:
        collapsed: List[Tuple[List[bytes], int, int, datetime]] = self._tree.collapse()
        for name, fid, dist, timeout in collapsed:
            yield (Name(name), fid, dist, timeout)

    def entries(self) -> List[Tuple[Name, int, int, datetime]]:
        return [(Name(name), fid, dist, timeout) for name, fid, dist, timeout in self._tree.collapse()]

    def __len__(self):
        return len(self._tree.collapse())
