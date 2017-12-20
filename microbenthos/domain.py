"""
Module that defines the microbial mat domain and related environmental parameters
"""

import logging

from fipy import PhysicalField, CellVariable, Variable
from fipy.meshes.uniformGrid1D import UniformGrid1D


class SedimentDBLDomain(object):
    """
    Class for the MicromatModelBase that defines the mesh for the domain, which includes a
    sediment column of atleast 10 cells and an optional Diffusive boundary layer column.

    Note: The domain dimensions are converted into SI units (meters) for the creation of the mesh,
    so that the model equations and parameters can all work on a common dimension system.
    """

    def __init__(self, cell_size = 0.1, sediment_length = 10, dbl_length = 1, porosity = 0.6):
        """
        Create a model domain that defines a sediment column and a diffusive boundary layer
        column on top of it. The mesh parameters should be supplied.

        If the mesh dimensions are given as :class:`PhysicalField` then they are converted into
        meters. If plain numbers (float) are given, then they are interpreted as being in units
        of mm.

        Args:
            cell_size: The size of a cell (default: 100 micron)
            sediment_length: The length of the sediment column (default: 1 cm)
            dbl_length: The length of the DBL (default: 1 mm)
            porosity: The porosity value for the sediment column

        """
        self.logger = logging.getLogger(__name__)
        self.VARS = {}
        self.mesh = None
        self.sediment_Ncells = self.DBL_Ncells = None

        self.cell_size = PhysicalField(cell_size, 'mm')
        self.sediment_length = PhysicalField(sediment_length, 'mm')
        self.DBL_length = PhysicalField(dbl_length, 'mm')

        assert self.sediment_length.numericValue > 0, "Sediment length should be positive"
        assert self.DBL_length.numericValue >= 0, "DBL length should be positive or zero"

        assert (self.sediment_length / self.cell_size) >= 10, \
            "Sediment length {} too small for cell size {}".format(
                self.sediment_length, self.cell_size
                )

        self.sediment_Ncells = int(self.sediment_length / self.cell_size)
        self.DBL_Ncells = int(self.DBL_length / self.cell_size)
        self.domain_Ncells = self.sediment_Ncells + self.DBL_Ncells

        self.sediment_length = self.sediment_Ncells * self.cell_size
        self.DBL_length = self.sediment_interface = self.DBL_Ncells * self.cell_size
        self.domain_length = self.sediment_length + self.DBL_length

        self.idx_surface = self.DBL_Ncells

        self.create_mesh()
        self.set_porosity(float(porosity))

    def __str__(self):
        return 'Domain(mesh={}, sed={}, DBL={})'.format(self.mesh, self.sediment_Ncells,
                                                        self.DBL_Ncells)

    def __repr__(self):
        return 'SedimentDBLDomain(cell_size={:.2}, sed_length={:.2}, dbl_length={:.2})'.format(
            self.cell_size.value, self.sediment_length.value, self.DBL_length.value
            )

    def __getitem__(self, item):
        return self.VARS[item]

    def create_mesh(self):
        """
        Create the mesh for the domain
        """

        self.logger.info('Creating UniformGrid1D with {} sediment and {} DBL cells of {}'.format(
            self.sediment_Ncells, self.DBL_Ncells, self.cell_size
            ))
        self.mesh = UniformGrid1D(dx=self.cell_size.numericValue,
                                  nx=self.domain_Ncells,
                                  )
        self.logger.debug('Created domain mesh: {}'.format(self.mesh))
        self.distances = Variable(value=self.mesh.scaledCellDistances[:-1], unit='m')
        Z = self.mesh.x()
        Z = Z - Z[self.idx_surface]
        self.depths_um = Z * 1e6 # in micrometers, with 0 at surface

    def create_var(self, vname, vtype = 'cell', **kwargs):
        """
        Create a variable on the domain.

         If the vtype is `'cell'` then the :class:`CellVariable` is created on the mesh. If vtype is
         `'basic'`, then a normal :class:`Variable` is created.

        Args:
            vname (str): The name identifier for the variable
            vtype (str): Whether to create a `'cell'` or a `'basic'` variable
            **kwargs: passed to the call to :class:`CellVariable`

        Returns:
            The created variable
        """

        self.logger.info('Creating {} variable {!r}'.format(vtype, vname))
        if not self.mesh:
            raise RuntimeError('Cannot create cell variable without mesh!')

        if vname in self.VARS:
            # self.logger.warning('Variable {} already exists. Over-writing with new'.format(vname))
            raise RuntimeError('Variable {} already exists!'.format(vname))

        if kwargs.get('name') is None:
            kwargs['name'] = str(vname)

        if kwargs.get('value') is None:
            self.logger.debug('Cannot set {} to None. Setting to zero instead!'.format(vname))
            kwargs['value'] = 0.0

        self.logger.debug('domain var params: {}'.format(kwargs))
        if vtype == 'cell':
            var = CellVariable(mesh=self.mesh, **kwargs)
        elif vtype == 'basic':
            var = Variable(**kwargs)

        self.logger.debug('Created variable {}: {} shape: {} unit: {}'.format(vname, repr(var), var.shape, var.unit))
        self.VARS[vname] = var
        return var

    def var_in_sediment(self, vname):
        """
        Convenience method to get the value of domain variable in the sediment
        Args:
            vname: Name of the variable

        Returns:
            Slice of the variable in the sediment

        """
        return self.VARS[vname][self.idx_surface:]

    def var_in_DBL(self, vname):
        """
        Convenience method to get the value of domain variable in the DBL

        Args:
            vname: Name of the variable

        Returns:
            Slice of the variable in the DBL

        """
        return self.VARS[vname][:self.idx_surface]

    def set_porosity(self, porosity):
        """
        Set the porosity for the sediment region. The DBL porosity is set to 1.0

        Args:
            porosity: A value for porosity between 0 and 1

        Returns:
            The instance of the porosity variable

        """
        if not (0.1 < porosity < 0.9):
            raise ValueError(
                'Sediment porosity={} should be between (0.1, 0.9)'.format(porosity))

        P = self.VARS.get('porosity')
        if P is None:
            P = self.create_var('porosity', vtype='basic', value=[1.0]*self.domain_Ncells)


        self.sediment_porosity = float(porosity)
        P[:self.idx_surface] = 1.0
        P[self.idx_surface:] = self.sediment_porosity
        self.logger.info('Set sediment porosity to {} and DBL porosity to 1.0'.format(
            self.sediment_porosity))
        return P
