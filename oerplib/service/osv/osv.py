# -*- coding: UTF-8 -*-
"""Provide the :class:`OSV` class which allow to access dynamically to all
methods proposed by an OSV model of the `OpenERP` server."""

import collections

from oerplib import error
from oerplib.service.osv import fields, browse


class OSV(collections.Mapping):
    """.. versionadded:: 0.5.0

    Represent a data model from the `OpenERP` server.

    .. note::
        This class have to be used through the :func:`oerplib.OERP.get`
        method.

    >>> import oerplib
    >>> oerp = oerplib.OERP('localhost')
    >>> user = oerp.login('admin', 'passwd', 'database')
    >>> user_osv = oerp.get('res.users')
    >>> user_osv
    <oerplib.service.osv.osv.OSV object at 0xb75ba4ac>
    >>> user_osv.name_get(user.id) # Use any methods from the OSV instance
    [[1, 'Administrator']]

    .. warning::

        The only method implemented in this class is ``browse``. Except this
        one, method calls are purely dynamic. As long as you know the signature
        of the OSV method targeted, you will be able to use it
        (see the :ref:`tutorial <tutorials-execute-queries>`).

    """

    fields_reserved = ['id', '__oerp__', '__osv__', '__data__']

    def __init__(self, oerp, osv_name):
        super(OSV, self).__init__()
        self._oerp = oerp
        self._name = osv_name
        self._browse_class = self._generate_browse_class()

    def _browse_generator(self, ids, context=None):
        """Generator used by the
        :func:`browse <oerplib.OERP.service.osv.osv.OSV.browse>` method.

        """
        for o_id in ids:
            yield self.browse(o_id, context)

    def browse(self, ids, context=None):
        """Browse one record or several records (if ``ids`` is a list of IDs)
        according to the model ``osv_name``. The fields and values for such
        objects are generated dynamically.

        >>> oerp.get('res.partner').browse(1)
        browse_record(res.partner, 1)

        >>> [partner.name for partner in oerp.get('res.partner').browse([1, 2])]
        [u'Your Company', u'ASUStek']

        A list of data types used by ``browse_record`` fields are
        available :ref:`here <fields>`.

        :return: a ``browse_record`` instance
        :return: a generator to iterate on ``browse_record`` instances
        :raise: :class:`oerplib.error.RPCError`

        """
        if isinstance(ids, list):
            return self._browse_generator(ids, context)
        else:
            obj = self._browse_class(ids)
            self._refresh(obj, context)
            return obj
            #return self.browse(ids, context)

    def _generate_browse_class(self):
        """Generate a class with all its fields corresponding to
        the OSV name supplied and return them.

        """
        # Retrieve server fields info and generate corresponding local fields
        fields_get = self._oerp.execute(self._name, 'fields_get')
        cls_name = self._name.replace('.', '_')
        if type(cls_name) == unicode:
            cls_name = cls_name.encode('utf-8')
        cls_fields = {}
        for field_name, field_data in fields_get.items():
            if field_name not in OSV.fields_reserved:
                cls_fields[field_name] = fields.generate_field(self,
                                                               field_name,
                                                               field_data)
        # Case where no field 'name' exists, we generate one (which will be
        # in readonly mode) in purpose to be filled with the 'name_get' method
        if 'name' not in cls_fields:
            field_data = {'type': 'text', 'string': 'Name', 'readonly': True}
            cls_fields['name'] = fields.generate_field(self, 'name', field_data)

        cls = type(cls_name, (browse.BrowseRecord,), {})
        cls.__oerp__ = self._oerp
        cls.__osv__ = {'name': self._name, 'columns': cls_fields}
        slots = ['__oerp__', '__osv__', '__dict__', '__data__']
        slots.extend(cls_fields.keys())
        cls.__slots__ = slots
        return cls

    def _write_record(self, obj, context=None):
        """Send values of fields updated to the OpenERP server."""
        obj_data = obj.__data__
        vals = {}
        for field_name in obj_data['fields_updated']:
            if field_name in obj_data['raw_data']:
                field = self._browse_class.__osv__['columns'][field_name]
                field_value = getattr(obj, "_{0}".format(field_name))
                # Many2One fields
                if isinstance(field, fields.Many2OneField):
                    vals[field_name] = field_value and field_value[0]
                # All other fields
                else:
                    vals[field_name] = field_value
        try:
            if self._oerp.config['compatible']:
                res = self.write([obj.id], vals, context)
            else:
                res = self.write([obj.id], vals, context=context)
        except error.Error as exc:
            raise exc
        else:
            # Update raw_data dictionary
            # FIXME: make it optional to avoid a RPC request?
            self._refresh(obj, context)
            return res

    def _refresh(self, obj, context=None):
        """Retrieve field values from OpenERP server.
        May be used to restore the original values
        in the purpose to cancel all changes made.

        """
        context = context or {}
        obj_data = obj.__data__
        obj_data['context'] = context
        # Fill fields with values of the record
        if obj.id:
            if self._oerp.config['compatible']:
                obj_data['raw_data'] = self.read([obj.id], None, context)[0]
            else:
                obj_data['raw_data'] = self.read(
                    [obj.id], None, context=context)[0]
            if obj_data['raw_data'] is False:
                raise error.RPCError(
                    u"There is no '{osv_name}' record with ID {obj_id}.".format(
                        osv_name=obj.__class__.__osv__['name'], obj_id=obj.id))
        # No ID: fields filled with default values
        else:
            if self._oerp.config['compatible']:
                default_get = self.default_get(
                    obj.__osv__['columns'].keys(), context)
            else:
                default_get = self.default_get(
                    obj.__osv__['columns'].keys(), context=context)
            obj_data['raw_data'] = {}
            for field_name in obj.__osv__['columns'].keys():
                obj_data['raw_data'][field_name] = False
            obj_data['raw_data'].update(default_get)
        self._reset(obj)

    def _reset(self, obj):
        """Cancel all changes by restoring field values with original values
        obtained during the last refresh (object instanciation or
        last call to _refresh() method).

        """
        obj_data = obj.__data__
        obj_data['fields_updated'] = []
        # Load fields and their values
        for field in self._browse_class.__osv__['columns'].values():
            if field.name in obj_data['raw_data']:
                setattr(obj, "_{0}".format(field.name),
                        obj_data['raw_data'][field.name])
                setattr(obj.__class__, field.name,
                        field)

    def _unlink_record(self, obj, context=None):
        """Delete the object from the OpenERP server."""
        if self._oerp.config['compatible']:
            return self.unlink([obj.id], context)
        else:
            return self.unlink([obj.id], context=context)

    def __getattr__(self, method):
        """Provide a dynamic access to a RPC method."""
        def rpc_method(*args, **kwargs):
            """Return the result of the RPC request."""
            if self._oerp.config['compatible']:
                if kwargs:
                    raise error.RPCError(
                        u"Named parameters are not supported in "
                        u"compatibility mode")
                result = self._oerp.execute(
                    self._browse_class.__osv__['name'], method, *args)
            else:
                if self._oerp.config['auto_context'] \
                        and 'context' not in kwargs:
                    kwargs['context'] = self._oerp.context
                result = self._oerp.execute_kw(
                    self._browse_class.__osv__['name'], method, args, kwargs)
            return result
        return rpc_method

    def __repr__(self):
        return "Model(%r)" % (self._browse_class.__osv__['name'])

    # ---------------------------- #
    # -- MutableMapping methods -- #
    # ---------------------------- #

    def __getitem__(self, obj_id):
        return self.browse(obj_id)

    def __iter__(self):
        ids = self.search([])
        return self._browse_generator(ids)

    def __len__(self):
        return self._oerp.search(self._browse_class.__osv__['name'], count=True)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
