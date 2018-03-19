"""
Module that defines the microbenthic domain: sediment + diffusive boundary layer
"""

import logging

from fipy import PhysicalField, CellVariable, Variable, Grid1D
# from fipy.meshes.uniformGrid1D import UniformGrid1D
from fipy.tools import numerix

from ..utils.snapshotters import snapshot_var


class SedimentDBLDomain(object):
    """
    Class that defines the model domain as a sediment column with a diffusive boundary layer.
    """

    def __init__(self, cell_size = 0.1, sediment_length = 10, dbl_length = 1, porosity = 0.6):
        """
        Create a model domain that defines a sediment column and a diffusive boundary layer
        column on top of it. The mesh parameters should be supplied.

        If the mesh dimensions are given as :class:`~fipy.PhysicalField` then they are converted
        into meters. If plain numbers (float) are given, then they are interpreted as being in units
        of mm. Finally, the parameters are all converted to base units (meters) for the creation
        of the mesh, so that the model equations and parameters can all work on a common
        dimension system.

        Args:
            cell_size (float, PhysicalField): The size of a cell (default: 100 micron)
            sediment_length (float): The length of the sediment column in mm (default: 10)
            dbl_length (float): The length of the DBL in mm (default: 1)
            porosity (float): The porosity value for the sediment column (default: 0.6)

        """
        self.logger = logging.getLogger(__name__)

        #: Mapping of names to :class:`CellVariable` instances available on the domain:
        self.VARS = {}

        #: The fipy Mesh instance
        self.mesh = None

        self.sediment_cells = self.DBL_cells = None

        #: the mesh cell size as a PhysicalField
        self.cell_size = PhysicalField(cell_size, 'mm')
        #: the sediment subdomain length as a PhysicalField
        self.sediment_length = PhysicalField(sediment_length, 'mm')
        #: the diffusive boundary layer subdomain length as a PhysicalField
        self.DBL_length = PhysicalField(dbl_length, 'mm')

        assert self.sediment_length.numericValue > 0, "Sediment length should be positive"
        assert self.DBL_length.numericValue >= 0, "DBL length should be positive or zero"

        assert (self.sediment_length / self.cell_size) >= 10, \
            "Sediment length {} too small for cell size {}".format(
                self.sediment_length, self.cell_size
                )

        self.sediment_cells = int(self.sediment_length / self.cell_size)
        self.DBL_cells = int(self.DBL_length / self.cell_size)
        #: total cells in the domain: sediment + DBL
        self.total_cells = self.sediment_cells + self.DBL_cells

        self.sediment_length = self.sediment_cells * self.cell_size
        self.DBL_length = self.sediment_interface = self.DBL_cells * self.cell_size
        self.total_length = self.sediment_length + self.DBL_length

        #: The coordinate index for the sediment surface
        self.idx_surface = self.DBL_cells

        #: An array of the scaled cell distances of the mesh
        self.distances = None

        #: An array of the cell center coordinates, with the 0 set at the sediment surface
        self.depths = None

        self.create_mesh()

        mask = numerix.ones(self.total_cells, dtype='uint8')
        mask[:self.idx_surface] = 0
        #: A variable named "sed_mask" which is 1 in the sediment subdomain
        self.sediment_mask = self.create_var(name='sed_mask', value=1)
        self.sediment_mask.value = mask

        self.set_porosity(float(porosity))

    def __str__(self):
        return 'Domain(mesh={}, sed={}, DBL={})'.format(self.mesh, self.sediment_cells,
                                                        self.DBL_cells)

    def __repr__(self):
        return 'SedimentDBLDomain(cell_size={:.3}, sed_length={:.2}, dbl_length={:.2})'.format(
            self.cell_size.value, self.sediment_length.value, self.DBL_length.value
            )

    def __getitem__(self, item):
        """
        Retrieve from :attr:`.VARS` by item name.
        """
        return self.VARS[item]

    def __contains__(self, item):
        """
        Container test for item in :attr:`.VARS`
        """
        return item in self.VARS

    def create_mesh(self):
        """
        Create the :mod:`fipy` mesh for the domain using :attr:`cell_size` and :attr:`total_cells`.

        The arrays :attr:`depths` and :attr:`distances` are created, which provide the
        coordinates and distances of the mesh cells.
        """

        self.logger.info('Creating UniformGrid1D with {} sediment and {} DBL cells of {}'.format(
            self.sediment_cells, self.DBL_cells, self.cell_size
            ))
        self.mesh = Grid1D(dx=self.cell_size.numericValue,
                           nx=self.total_cells,
                           )
        self.logger.debug('Created domain mesh: {}'.format(self.mesh))

        #: An array of the scaled cell distances of the mesh
        self.distances = Variable(value=self.mesh.scaledCellDistances[:-1], unit='m',
                                  name='distances')
        Z = self.mesh.x()
        Z = Z - Z[self.idx_surface]

        #: An array of the cell center coordinates, with the 0 set at the sediment surface
        self.depths = Variable(Z, unit='m', name='depths')

    def create_var(self, name, store = True, **kwargs):
        """
        Create a variable on the mesh as a :class:`.CellVariable`.

        If a `value` is not supplied, then it is set to 0.0. Before creating the cell variable,
        the value is multiplied with an array of ones of the shape of the domain mesh. This
        ensures that no single-valued options end up creating an improper variable. As a result,
        several types for `value` are valid.

        Args:
            name (str): The name identifier for the variable

            store (bool): If True, then the created variable is stored in :attr:`.VARS`

            value (float, :class:`numpy.ndarray`, PhysicalField): value to set on the variable

            unit (str): The physical units for the variable

            hasOld (bool): Whether the variable maintains the older values, which is required for
                numerical solution through time discretization. This should be set to `True` for the
                variables of the equations that will be solved.

            **kwargs: passed to the call to :meth:`CellVariable.__init__`

        Returns:
            The created variable

        Raises:
            ValueError: If `name` is not a string with len > 0
            ValueError: If value has a shape incompatible with the mesh
            RuntimeError: If domain variable with same name already exists & `store` = True
        """

        self.logger.info('Creating variable {!r}'.format(name))
        if not self.mesh:
            raise RuntimeError('Cannot create cell variable without mesh!')

        if not name:
            raise ValueError('Name must have len > 0')

        if name in self.VARS and store:
            raise RuntimeError('Domain variable {} already exists!'.format(name))

        if kwargs.get('value') is None:
            self.logger.debug('Cannot set {} to None. Setting to zero instead!'.format(name))
            kwargs['value'] = 0.0

        value = kwargs.pop('value')

        if hasattr(value, 'shape'):
            if value.shape not in ((), self.mesh.shape):
                raise ValueError('Value shape {} not compatible for mesh {}'.format(value.shape,
                                                                                    self.mesh.shape))
        unit = kwargs.get('unit')
        if unit and isinstance(value, PhysicalField):
            vunit = str(value.unit.name())
            if vunit != "1":
                # value has units
                self.logger.warning('{!r} value has units {!r}, which will override '
                                    'supplied {}'.format(name, vunit, unit))

        try:
            varr = numerix.ones(self.mesh.shape)
            value = varr * value
        except TypeError:
            self.logger.error('Error creating variable', exc_info=True)
            raise ValueError('Value {} could not be cast numerically'.format(value))

        self.logger.debug('Creating CellVariable {!r} with: {}'.format(name, kwargs))
        var = CellVariable(mesh=self.mesh, name=name, value=value, **kwargs)

        self.logger.debug('Created variable {!r}: shape: {} unit: {}'.format(var,
                                                                             var.shape, var.unit))
        if store:
            self.VARS[name] = var
            self.logger.debug('Stored on domain: {!r}'.format(var))

        return var

    def var_in_sediment(self, vname):
        """
        Convenience method to get the value of domain variable in the sediment

        Args:
            vname (str): Name of the variable

        Returns:
            Slice of the variable in the sediment subdomain

        """
        return self.VARS[vname][self.idx_surface:]

    def var_in_DBL(self, vname):
        """
        Convenience method to get the value of domain variable in the DBL

        Args:
            vname (str): Name of the variable

        Returns:
            Slice of the variable in the DBL subdomain

        """
        return self.VARS[vname][:self.idx_surface]

    def set_porosity(self, porosity):
        """
        Set the porosity for the sediment subdomain. The DBL porosity is set to 1.0. The supplied
        value is set in :attr:`.sediment_porosity`.

        Args:
            porosity (float): A value between 0.1 and 0.9

        Returns:
            The instance of the porosity variable

        """
        if not (0.1 < porosity < 0.9):
            raise ValueError(
                'Sediment porosity={} should be between (0.1, 0.9)'.format(porosity))

        P = self.VARS.get('porosity')
        if P is None:
            self.porosity = P = self.create_var('porosity', value=1.0)
            # self.porosity = P = Variable(float(porosity), name='porOsiTy')
            # self.VARS['porosity'] = P

        self.sediment_porosity = float(porosity)
        P.value[:self.idx_surface] = 1.0
        P.value[self.idx_surface:] = self.sediment_porosity
        self.logger.info('Set sediment porosity to {} and DBL porosity to 1.0'.format(
            self.sediment_porosity))
        return P

    def snapshot(self, base = False):
        """
        Returns a snapshot of the domain's state, with the following structure:

            * depths:
                * "data_static"
                    * (:attr:`.depths`, `dict(unit="m")`)
            * distances:
                * "data_static"
                    * (:attr:`.distances`, `dict(unit="m")`)
            * metadata
                * `cell_size`
                * `sediment_length`
                * `sediment_cells`
                * `DBL_cells`
                * `DBL_length`
                * `total_cells`
                * `total_length`
                * `sediment_porosity`
                * `idx_surface`


        Returns:
            dict

        """
        self.logger.debug('Snapshot: {}'.format(self))
        state = dict()
        meta = state['metadata'] = {}
        meta['cell_size'] = str(self.cell_size)
        meta['sediment_length'] = str(self.sediment_length)
        meta['DBL_length'] = str(self.DBL_length)
        meta['sediment_cells'] = self.sediment_cells
        meta['DBL_cells'] = self.DBL_cells
        meta['total_cells'] = self.total_cells
        meta['total_length'] = str(self.total_length)
        meta['sediment_porosity'] = self.sediment_porosity
        meta['idx_surface'] = self.idx_surface

        state['depths'] = {'data_static': snapshot_var(self.depths, base=base)}
        state['distances'] = {'data_static': snapshot_var(self.distances, base=base)}

        return state

    __getstate__ = snapshot
