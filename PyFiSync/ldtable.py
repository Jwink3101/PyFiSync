#!/usr/bin/env python
from __future__ import unicode_literals

__version__ = "20180628"
__author__ = "Justin Winokur"

import copy
from collections import defaultdict
import time
import types


class ldtable(object):
    def __init__(self, items=None, attributes=None, default_attribute=None,
                 exclude_attributes=None, indexObjects=False):
        """
        ldtable:
        Create an in-memeory single table DB from a list of dictionaries that 
        may be queried by any specified attribute.

        This is useful since, once created, lookup/query/"in" checks are
        O(1), Creation is still O(N)

        Note: Unless an entry is changed with update(), it must be reindexed

        Inputs:
        --------
        items  [ *empty* ] (list)
            List of dictionaries with each attribute

        attributes [None] (list, None)
            Either a list of attributes to index, or if specified as None
            (default) it will add every attribute of every item and assign
            missing ones to be `default_attribute` (unless excluded)
        
            NOTE: If attributes is set, you may still add items with extra
                  attributes. They just won't be indexed.
                  Or use add_attribute()
        
        exclude_attributes [ *empty* ] (list)
            Attributes that shouldn't ever be added even if attributes=None
            for dynamic addition of attributes.
        
        default_attribute [None] (*any*)
            Default attribute to assign if `attributes=None` and it is missing.
            If the specified object is callable, it will call it (for example,
            `default_attribute=list` will make it an empty list), Otherwise,
            it will set it to whatever value is specified.
        
        Options: (These may be changed later too)
        --------
        indexObjects: [False]
            If True, will automatically take any object and use its
            __dict__ as the dict.
            
            Note
                * Changing to False after adding an object will cause issues.
                * Does not support __slots__ since they are immutable
            
        Multiple Values per attribute
        -----------------------------
        A "row" can have multiple values per attribute as follows:
            
            {'attribute':[val1,val2,val3]}
            
        and can be queried for any (or all) values.
        
        Additional Opperations:
        ----------------------
        This supports index-lookup with a dictionary as well as
        a python `in` check and lookup by a dictionary
        
        The code will allow you to edit/delete/update multiple items at once
        (just like a standard database). Use with caution.

        Tips:
        ------
        * You can simply dump the DB with JSON using the DB.items()
          and then reload it with a new DB
        
        * There is also an attribute called `_index` which can be used to
          query by index.

        """
        
        # Handle inputs
        if items is None:
            items = list()

        if exclude_attributes is None:
            exclude_attributes = list()
        self.indexObjects = indexObjects


        self.attributes = attributes # Will be reset in first add
        self._is_attr_None = attributes is None
        self.default_attribute = default_attribute
        self.exclude_attributes = exclude_attributes

        self.N = 0 # Will keep track
        self._list = []

        self._empty = _emptyList()
        self._ix = set()

        # Add the items
        for item in items:
            self.add(item)
        
        self._i = 0 # Counter for iterator if not called with iteritems
        
        self._time = time.time()
    
        # Edge case: No items
        if self.attributes is None:
            self.attributes = []
        
    def add(self,item):
        """
        Add an item or items to the DB
        """
        if isinstance(item,(list,tuple,types.GeneratorType)):
            for it in item:
                self.add(it)
            return
        
        # handle other object types
        item0 = item
        item = self._convert2dict(item)
        
        if self.N == 0:
            attributes = self.attributes
            if attributes is None:
                attributes = list(item.keys())

            self.attributes = [attrib for attrib in attributes \
                                if attrib not in self.exclude_attributes] # Make a copy
            

            # Set up the lookup
            self._lookup = {attribute:defaultdict(list) for attribute in self.attributes}
        
        ix = len(self._list) # The length will be 1+ the last ix so do not change this

        if self._is_attr_None: # Set to None which means we add all
            for attrib in item.keys():
                if attrib in self.exclude_attributes:
                    continue
                if attrib not in self.attributes:
                    self.add_attribute(attrib,self.default_attribute)
        # Add built in ones
        for attrib in self.attributes:
            if attrib not in item:
                if hasattr(self.default_attribute, '__call__'):
                    item[attrib] = self.default_attribute()
                else:
                    item[attrib] = self.default_attribute
                    
            value = item[attrib]
            self._append(attrib,value,ix)

        # Finally add it
        self._list.append(item0)
        self.N += 1
        self._ix.add(ix)

    def query(self,*A,**K):
        """
        Query the value for attribute. Will always an iterator. Use
        `list(DB.query())` to return a list
        
        Usage
        -----
        
        Any combination of the following will works
        
        Keywords: Only check equality
                   
        >>> DB.query(attrib=val)
        >>> DB.query(attrib1=val1,attrib2=val2)  # Match both
        
        >>> DB.query({'attrib':val})
        >>> DB.query({'attrib1':val1,'attrib2':val2}) # Match Both
                                      
        Query Objects (DB.Q, DB.Qobj)
        
        >>> DB.query(DB.Q.attrib == val)
        >>> DB.query( (DB.Q.attrib1 == val1) &  (DB.Q.attrib1 == val2) )  # Parentheses are important!
        >>> DB.query( (DB.Q.attrib1 == val1) &  (DB.Q.attrib1 != val2))
                                   
        """
        ixs = self._ixs(*A,**K)
        for ix in ixs:
            yield self._list[ix]
    
    def query_one(self,*A,**K):
        """
        Return a single item from a query. See "query" for more details.
        
        Returns None if nothing matches
        """
        try:
            return next(self.query(*A,**K))
        except StopIteration:
            return None

    def count(self,*A,**K):
        """
        Return the number of matched rows for a given query. See "query" for
        details on query construction
        """
        return len(self._ixs(*A,**K))
    
    def isin(self,*A,**K):
        """
        Check if there is at least one item that matches the given query
        
        see query() for usage
        """

        return len(self._ixs(*A,**K))>0

    def reindex(self,*args):
        """
        Reindex the dictionary for specified attributes (or all)
        
        Usage
        -----
        
        >>> DB.reindex()                # All
        >>> DB.reindex('attrib')        # Reindex 'attrib'
        >>> DB.reindex('attrib1','attrib2') # Multiple
        
        See Also
        --------
            update() method which does not require reindexing
        """
        if len(args) == 0:
            attributes = self.attributes
            
            # Just an extra check (and makes a copy)
            attributes = [attr for attr in attributes \
                        if attr not in self.exclude_attributes]
        else:
            attributes = args
            if any(a in self.exclude_attributes for a in args):
                raise ValueError('Cannot reindex an excluded attribute')

        for attribute in attributes:
            self._lookup[attribute] = defaultdict(list) # Reset
        
        for ix,item in enumerate(self._list):
            if item is None: continue
            item = self._convert2dict(item)
            for attrib in attributes:
                value = item[attrib]
                self._append(attrib,value,ix)
    
    def update(self,*args,**queryKWs):
        """
        Update an entry without needing to reindex the DB (or a specific
        attribute)
        
        Usage:
        ------
        
        >>> DB.update(updated_dict, query_dict_or_Qobj, query_attrib1=val1,...)
        >>> DB.update(updated_dict, query_attrib1=val1,...)
        
        Inputs:
        -------
        
        updated_dict : Dictionary with which to update the entry. This is
                       done using the typical dict().update() construct to
                       overwrite it
        
        query_dict_or_Qobj
                     : Either the dictionary used in the query or a Qobj that
                       defines a more advanced query
        
        query_attrib1=val1
                     : Additional (or sole) query attributes
    
        Notes:
        ------
            * Updating an item requires a deletion in a list that has length n
              equal to the number of items matching an attribute. This is O(n).
              However changing the entry directly and reindexing is O(N) where
              N is the size of the DB. If many items are changing and you do not
              need to query them in between, it *may* be faster to directly
              update the item and reindex
        """
        
        if len(args) == 1:
            updated_dict = args[0]
            query = {}
        elif len(args) == 2:
            updated_dict,query = args
        else:
            raise ValueError('Incorrect number of inputs. See documentation')
        
        updated_dict = self._convert2dict(updated_dict)
        if not isinstance(updated_dict,dict):
            raise ValueError('Must specify updated values as a dictionary')
        
        query = self._convert2dict(query)
        if isinstance(query,Qobj):
            ixs = self._ixs(query,**queryKWs)
        elif isinstance(query,dict):
            queryKWs.update(query)
            ixs = self._ixs(**queryKWs)
        else:
            raise ValueError('Unrecognized query {:s}. Must be a dict or Qobj',format(type(query)))
        
        if len(ixs) == 0:
            raise ValueError('Query did not match any results')
        
        for ix in ixs:
            # Get original item
            item = self._list[ix]
            item = self._convert2dict(item)
            
            # Allow the update to also include non DB attributes.
            # The intersection will eliminate any exclude_attributes
            attributes = set(updated_dict.keys()).intersection(self.attributes)
            
            for attrib in attributes: # Only loop over the updated attribs
                # get old value
                value = item[attrib]
                
                # Remove any ix matching it
                self._remove(attrib,value,ix)
                
                # Get new value
                value = updated_dict[attrib]
                
                # Add ix to any new value
                self._append(attrib,value,ix)
                
            # Update the item
            item.update(updated_dict)
        
        return
        
    def add_attribute(self,attribute,*default):
        """
        Add an attribute to the index attributes.

        Usage
        -----
        >>> DB.add_attribute('new_attrib') # Will raise an error if *any*
                                           # items don't have 'new_attrib'
        >>> DB.add_attribute('new_attrib',default)
                                           # Set any missing to the default
        
        If the `default` is callable, it will call it instead. (such as `list`
        to add an empty list)
        
        """
        if attribute in self.exclude_attributes:
            raise ValueError("Can't add exclude_attributes")
        
        attrib = attribute
        if not hasattr(self,'_lookup'):
            self._lookup = {}
        self._lookup[attribute] = defaultdict(list)

        set_default = False
        if len(default) >0:
            set_default = True
            default = default[0]

        for ix,item in enumerate(self._list):
            if item is None: continue
            item = self._convert2dict(item)
            try:
                value = item[attribute]
                self._append(attrib,value,ix)
            except KeyError as KE:
                if set_default:
                    if hasattr(default, '__call__'):
                        item[attribute] = default()
                    else:
                        item[attribute] = default
                else:
                    raise KeyError("Attribute {:s} not found".format(attrib))

                value = item[attribute]
                self._append(attrib,value,ix)

        self.attributes.append(attribute)

    def remove(self,*A,**K):
        """
        Remove item that matches a given attribute or dict. See query() for
        input specification


        DB Options:
        This is set at instantiation but can be changed directly
        -----------
        
        """
        ixs = list(self._ixs(*A,**K))

        if len(ixs) == 0:
            raise ValueError('No matching items')

        items = []

        for ix in ixs[:]: # Must remove it from everything.
            # not sure what is happening, but it seems that I need to make a copy
            # since Python is doing something strange here...

            item = self._list[ix]
            item = self._convert2dict(item)

            for attrib in self.attributes:
                value = item[attrib]
                self._remove(attrib,value,ix)
                
            # Remove it from the list by setting to None. Do not reshuffle
            # the indices. A None check will be performed elsewhere
            self._list[ix] = None
            self._ix.difference_update([ix])
            self.N -= 1
    
    def items(self):
        """
        Return a list of items.
        """
        for item in self._list:
            if item is None:
                continue
            yield item
            
    @property
    def Qobj(self):
        """
        Query object already loaded with the DB
        
            DB.Qobj <==> DB.Q <==> Qobj(DB)
        """
        return Qobj(self)
    Q = Qobj
    
    def _convert2dict(self,obj):
        """
        Convert objects to a regular dictionary for the sake of indexing
        
        Also return Qobjs untouched since they may be used in queries too
        
        If it not an Qobj or dict, it will try to get it's __dict__ and if
        that doesn't work, will just return it
        """
        if isinstance(obj,Qobj):
            return obj
        
        if isinstance(obj,dict): # Also accounts for OrderedDicts or ...
            return obj           # ... anything that inherits dict
        
        if self.indexObjects and hasattr(obj,'__dict__'):
            return obj.__dict__
            
        return obj
        
    
    def _ixs(self,*args,**kwords):
        """
        Get the inde(x/ies) of matching information
        """
        if not hasattr(self,'_lookup') or self.N==0: # It may be empty
            return []
 
        # Make the entire kwords be lists with default of []. Edge case of
        # multiple items
        for key,val in kwords.items():
            if not isinstance(val,list):
                kwords[key] = [val]
        kwords = defaultdict(list,kwords)
        
        Q = Qobj(self) # Empty object
        for arg in args:
            arg = self._convert2dict(arg) # handle other object types
            if isinstance(arg,Qobj):
                Q = Q & arg # Will add these conditions. If Q is empty, will just be arg
                continue
            if isinstance(arg,dict):
                for key,val in arg.items(): # Add it rather than update in case it is already specified
                    kwords[key].append(val)
            else:
                raise ValueError('unrecognized input of type {:s}'.format(str(type(arg))))
        
        # Construct a query for kwords
        for key,value in kwords.items():
            if isinstance(value,list) and len(value) == 0:
                value = [self._empty]
            for val in _makelist(value):
                Qtmp = Qobj(self)
                Qtmp._attr = key
                Q = Q & (Qtmp == val)

        ixs = Q._ixs
        # Ensure one match
        if ixs is None:
            ixs = []
        return list(ixs)
        
    
    def _index(self,ix):
        """
        Return ix if it hasn't been deleted
        """
        try:
            item = self._list[ix]
        except IndexError:
            return []
        
        if item is None:
            return []
        
        return [ix]
    
    def _append(self,attrib,value,ix):
        """
        Add to the lookup and update the modify time
        """
        # Final check but we should be guarded from this
        if attrib in self.exclude_attributes:
            print('BAD! Should guard against this in public methods!')
            raise ValueError('Cannot reindex an excluded attribute')
        
        valueL = _makelist(value)
        for val in valueL:
            self._lookup[attrib][val].append(ix)
        if len(valueL) == 0:
            self._lookup[attrib][self._empty].append(ix) # empty list
        self._time = time.time()
    
    def _remove(self,attrib,value,ix):
        """
        Remove from the lookup and update the modify time
        """
        valueL = _makelist(value)
        for val in valueL:
            try:
                self._lookup[attrib][val].remove(ix)
            except ValueError:
                raise ValueError('Item not found in internal lookup. May need to first call reindex()')
        if len(valueL) == 0:
            self._lookup[attrib][self._empty].remove(ix) # empty list
    
        self._time = time.time()
    
    def __contains__(self,check_diff):
        check_diff = self._convert2dict(check_diff)
        if not ( isinstance(check_diff,dict) or isinstance(check_diff,Qobj)):
            raise ValueError('Python `in` queries should be a of {attribute:value} or Qobj')
        return self.isin(check_diff)

    def __len__(self):
        return self.N

    def __getitem__(self,item):
        item = self._convert2dict(item)
        if isinstance(item,dict) or isinstance(item,Qobj):
            return self.query_one(item)
        elif isinstance(item,int): # numbered item
            if self._list[item] is not None:
                return self._list[item]
            else:
                raise ValueError("Index has been deleted")
        else:
            raise ValueError("Must specify DB[{'attribute':val}] or DB[index]'")
    __call__ = query
    
    def __iter__(self):
        return self

    def __next__(self):
        while self._i < len(self._list):
            self._i += 1 # Increment it but then search back
            if self._list[self._i-1] is not None:
                return self._list[self._i-1]
        raise StopIteration()
    next = __next__ # For compatability
    
    
def _makelist(input):
    if isinstance(input,list):
        return input
    return [input]

class _emptyList(object):
    def __init__(self):
        pass
    def __hash__(self):
        return 9999999999999
    def __eq__(self,other):
        return isinstance(other,list) and len(other)==0
        
class Qobj(object):
    """
    Query objects. This works by returning an updated *copy* of the object
    whenever it is acted upon
    
    Calling
        * Q.attribute sets attribute and returns a copy
        * Q.attribute == val (or any other comparison) set the index of elements
        * Q1 & Q1 or other boolean perform set operations
        
    Useful Methods:
        _filter : (or just `filter` if not an attribute): Apply a filter
                  to the DB
    """
    def __init__(self,DB,ixs=None,attr=None):
        self._DB = DB
        self._ixs = ixs
        self._attr = attr
        
        self._time = time.time()
        
    
    def _valid(self):
        if self._time < self._DB._time:
            raise ValueError('This query object is out of date from the DB. Create a new one')
    
    def _filter(self,filter_func):
        """
        
        If 'filter' is NOT an attribute of the DB, this can be called
        with 'filter' instead of '_filter'
        
        Apply a filter to the data that returns True if it matches and False
        otherwise
        
        Note that filters are O(N)
        """
        self._valid() # Actually, these would still work but still check
        ixs = set()
        for ix,item in enumerate(self._DB._list): # loop all
            item = self._DB._convert2dict(item)
            if item is None:
                continue
            if filter_func(item):
                ixs.add(ix)
        self._ixs = ixs
        return self.copy()
         
            
    # Comparisons
    def __eq__(self,value):
        self._valid()
        
        if self._DB.N == 0:
            self._ixs = set()
            return self.copy()
        
        first_set = True
        for val in _makelist(value): # Account for list inputs
            if self._attr == '_index':
                if first_set:
                    ixs = set(self._DB._index(val))
                    first_set = False
                else:
                    ixs = ixs.intersection(self._DB._index(val))
                continue
            if self._attr not in self._DB.attributes:
                raise KeyError("'{:s}' is not an attribute".format(self._attr))
                
            ixs_at = self._DB._lookup[self._attr][val]
            if first_set:
                ixs = set(ixs_at)
                first_set = False
            else:
                ixs = ixs.intersection(ixs_at)
        
        self._ixs = ixs
        return self.copy()
     
    def __ne__(self,value):
        self._ixs = self._DB._ix - (self == value)._ixs
        return self.copy()
    
    def __lt__(self,value):
        self._valid() # Actually, these would still work but still check
        ixs = set()
        for ix,item in enumerate(self._DB._list): # loop all
            item = self._DB._convert2dict(item)
            if item is None:
                continue
            for ival in _makelist(item[self._attr]):
                if ival < value:
                    ixs.add(ix)
        self._ixs = ixs
        return self.copy()

    def __le__(self,value):
        self._valid() # Actually, these would still work but still check
        ixs = set()
        for ix,item in enumerate(self._DB._list): # loop all
            item = self._DB._convert2dict(item)
            if item is None:
                continue
            if item[self._attr] <= value:
                ixs.add(ix)
        self._ixs = ixs
        return self.copy()
        
    def __gt__(self,value):
        self._valid() # Actually, these would still work but still check
        ixs = set()
        for ix,item in enumerate(self._DB._list): # loop all
            item = self._DB._convert2dict(item)
            if item is None:
                continue
            if item[self._attr] > value:
                ixs.add(ix)
        self._ixs = ixs
        return self.copy()
    
    def __ge__(self,value):
        self._valid() # Actually, these would still work but still check
        ixs = set()
        for ix,item in enumerate(self._DB._list): # loop all
            item = self._DB._convert2dict(item)
            if item is None:
                continue
            if item[self._attr] >= value:
                ixs.add(ix)
        self._ixs = ixs
        return self.copy()
    
    # Logic
    def __and__(self,Q2):
        if self._ixs == None:  # An empty object and another will just return other
            return Q2
        self._ixs.intersection_update(Q2._ixs)
        return self.copy()
    def __or__(self,Q2):
        self._ixs.update(Q2._ixs)
        return self.copy()
    def __invert__(self):
        self._ixs = self._DB._ix - self._ixs
        return self.copy()
    
    def __getattr__(self,attr):
        if attr == 'filter' and 'filter' not in self._DB.attributes:
            return self._filter
        self._attr = attr
        return self.copy()
    
    def copy(self):
        new = Qobj(self._DB,ixs=self._ixs,attr=self._attr)
        # Reset the time
        new._time = self._time
        return new
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
