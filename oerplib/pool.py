# -*- coding: UTF-8 -*-
"""
"""
import collections

from oerplib import factory, error


class ModelPool(collections.MutableMapping):
    """Manage OSV classes. Each OSV class has an object pool (Factory)
    which manage the corresponding objects.

    """

    def __init__(self, oerp):
        super(ModelPool, self).__init__()
        self.oerp = oerp
        self._factories_by_osv_name = {}
        self._factories_by_osv_class = {}

    def get(self, osv_name, refresh=False):
        """Return a factory which is able to create browsable objects
        corresponding to the OSV name supplied.

        """
        if osv_name not in self._factories_by_osv_name:
            facto = factory.Factory(self.oerp, osv_name)
            self._factories_by_osv_name[osv_name] = facto
            self._factories_by_osv_class[facto.osv['class']] = facto
        elif refresh:
            self._factories_by_osv_name[osv_name] = factory.Factory(self.oerp,
                                                                    osv_name)
        return self._factories_by_osv_name[osv_name]

    def get_by_class(self, osv):
        """Return a factory which is able to create browsable objects
        corresponding to the OSV class supplied.

        """
        return self._factories_by_osv_class[osv]

    def __str__(self):
        """Return string representation of this pool."""
        res = {}
        for osv_name, facto in self._factories_by_osv_name.iteritems():
            res[osv_name] = facto.keys()
        return str(res)

    # ---------------------------- #
    # -- MutableMapping methods -- #
    # ---------------------------- #

    def __delitem__(self, osv_name):
        self._factories_by_osv_name[osv_name].clear()
        del self._factories_by_osv_name[osv_name]
        #raise error.NotAllowedError(u"Operation not supported")

    def __getitem__(self, osv_name):
        return self.get(osv_name)

    def __iter__(self):
        for osv_name in self._factories_by_osv_name:
            yield osv_name

    def __len__(self):
        return len(self._factories_by_osv_name)

    def __setitem__(self, osv_name, value):
        raise error.NotAllowedError(u"Operation not supported")
