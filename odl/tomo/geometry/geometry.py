# Copyright 2014, 2015 The ODL development group
#
# This file is part of ODL.
#
# ODL is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# ODL is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with ODL.  If not, see <http://www.gnu.org/licenses/>.

"""Geometry base class."""

# Imports for common Python 2/3 codebase
from __future__ import print_function, division, absolute_import
from abc import ABCMeta, abstractmethod, abstractproperty
from future import standard_library
standard_library.install_aliases()
from builtins import object, super

# External
import numpy as np

# Internal
from odl.util.utility import with_metaclass
from odl.discr.grid import RegularGrid, TensorGrid
from odl.set.domain import IntervalProd

__all__ = ('Geometry', 'DivergentBeamGeometry', 'AxisOrientedGeometry')


class Geometry(with_metaclass(ABCMeta, object)):

    """Abstract geometry class.

    A geometry is described by

    * a detector,
    * a set of detector motion parameters,
    * a function mapping motion parameters to the location of a
      reference point (e.g. the center of the detector surface),
    * a rotation applied to the detector surface, depending on the motion
      parameters,
    * a mapping from the motion and surface parameters to the detector pixel
      direction to the source,
    * optionally a mapping from the motion parameters to the source position
    """

    def __init__(self, ndim):
        """Initialize a new instance.

        Parameters
        ----------
        ndim : `int`
           The number of dimensions of the geometry
        """
        self._ndim = ndim
        self._implementation_cache = {}

    @abstractproperty
    def motion_params(self):
        """The motion parameters given as an `IntervalProd`."""

    @abstractproperty
    def detector(self):
        """The detector representation."""

    @abstractmethod
    def det_refpoint(self, mpar):
        """The detector reference point function.

        Parameters
        ----------
        mpar : element of motion parameters
            Motion parameter for which to calculate the detector
            reference point

        Returns
        -------
        point : `numpy.ndarray`, shape (`ndim`,)
            The reference point, an `ndim`-dimensional vector
        """

    @abstractmethod
    def rotation_matrix(self, mpar):
        """The detector rotation function for calculating the detector
        reference position.

        Parameters
        ----------
        mpar : element of motion parameters `motion_params`
            Motion parameter for which to calculate the detector
            reference rotation

        Returns
        -------
        rot : `numpy.ndarray`, shape (`ndim`, `ndim`)
            The rotation matrix mapping the standard basis vectors in
            the fixed ("lab") coordinate system to the basis vectors of
            the local coordinate system of the detector reference point,
            expressed in the fixed system.
        """

    def det_to_src(self, mpar, dpar, normalized=True):
        """Vector pointing from a detector location to the source.

        A function of the motion and detector parameters.

        Parameters
        ----------
        mpar : element of motion parameters `motion_params`
            Motion parameter at which to evaluate
        dpar : element of detector parameters `det_params`
            Detector parameter at which to evaluate
        normalized : `bool`, optional
            If `True`, return a normalized (unit) vector. Default: `True`

        Returns
        -------
        vec : `numpy.ndarray`, shape (`ndim`,)
            (Unit) vector pointing from the detector to the source
        """
        raise NotImplementedError

    def det_point_position(self, mpar, dpar):
        """The detector point position function.

        Parameters
        ----------
        mpar : element of motion parameters `motion_params`
            Motion parameter at which to evaluate
        dpar : element of detector parameters `det_params`
            Detector parameter at which to evaluate

        Returns
        -------
        pos : `numpy.ndarray`, shape (`ndim`,)
            The source position, a `ndim`-dimensional vector
        """

        # TODO: check and write test
        return np.asarray(
            (self.det_refpoint(mpar) +
             self.rotation_matrix(mpar).dot(self.detector.surface(dpar))))

    @property
    def ndim(self):
        """The number of dimensions of the geometry."""
        return self._ndim

    @property
    def implementation_cache(self):
        """Dict where computed implementations of this geometry can be saved.

        Intended for reuse of computations. Implementations that use this
        storage should take care to use a sufficiently unique name.

        Returns
        -------
        implementations : `dict`
        """
        return self._implementation_cache

    @property
    def motion_grid(self):
        """A sampling grid for `motion_params`."""
        return None

    @property
    def has_motion_sampling(self):
        """Whether there is a `motion_grid` or not."""
        return self.motion_grid is not None

    @property
    def det_params(self):
        """The detector parameters."""
        return self.detector.params

    @property
    def det_grid(self):
        """A sampling grid for `det_params`."""
        return self.detector.param_grid

    @property
    def has_det_sampling(self):
        """Whether there is a `det_grid` or not."""
        return self.det_grid is not None

    @property
    def params(self):
        """Joined motion and detector parameters.

        Returns an `IntervalProduct` with the motion parameters inserted
        before the detector parameters.
        """
        return self.motion_params.append(self.det_params)

    @property
    def grid(self):
        """Joined sampling grid for motion and detector parameters."""
        if (isinstance(self.motion_grid, RegularGrid) and
                isinstance(self.det_grid, RegularGrid)):
            grid = self.motion_grid
        else:
            grid = TensorGrid(*self.motion_grid.coord_vectors)
        return grid.append(self.det_grid)


class DivergentBeamGeometry(Geometry):

    """Abstract n-dimensional divergent beam geometry.

    A divergent beam geometry is characterized by a source and an
    (n-1)-dimensional detector moving in space according to a 1d motion
    parameter.

    Special cases include fanbeam in 2d and conebeam in 3d.
    """

    def __init__(self, ndim, angle_intvl, detector, agrid=None):
        """Initialize a new instance.

        Parameters
        ----------
        ndim : int
            number of dimensions of geometry
        angle_intvl : 1-dim. `IntervalProd`
            Admissible angles
        detector : `Detector`
            The detector to use
        agrid : `TensorGrid`, optional
            Optional discretization of the ``angle_intvl``
        """
        if not (isinstance(angle_intvl, IntervalProd) and
                angle_intvl.ndim == 1):
            raise TypeError('angle parameters {!r} are not an interval.'
                            ''.format(angle_intvl))
        self._motion_params = angle_intvl
        self._motion_grid = agrid
        self._detector = detector

        if agrid is not None:
            if not isinstance(agrid, TensorGrid):
                raise TypeError('angle grid {!r} is not a `TensorGrid` '
                                'instance.'.format(agrid))
            if not angle_intvl.contains_set(agrid):
                raise ValueError('angular grid {} not contained in angle '
                                 'interval {}.'.format(agrid, angle_intvl))

        super().__init__(ndim=ndim)

    @property
    def motion_params(self):
        """Motion parameters of this geometry."""
        return self._motion_params

    @property
    def motion_grid(self):
        """Sampling grid for this geometry's motion parameters."""
        return self._motion_grid

    @property
    def detector(self):
        """Detector of this geometry."""
        return self._detector

    @abstractmethod
    def src_position(self, mpar):
        """The source position function.

        Parameters
        ----------
        mpar : element of motion parameters `motion_params`
            Motion parameter for which to calculate the source position

        Returns
        -------
        pos : `numpy.ndarray`, shape (`ndim`,)
            The source position, a `ndim`-dimensional vector
        """

    def det_to_src(self, mpar, dpar, normalized=True):
        """Vector pointing from a detector location to the source.

        A function of the motion and detector parameters.

        The default implementation uses the `det_point_position` and
        `src_position` functions. Implementations can override this, for
        example if no source position is given.

        Parameters
        ----------
        mpar : element of motion parameters `motion_params`
            Motion parameter at which to evaluate
        dpar : element of detector parameters `det_params`
            Detector parameter at which to evaluate
        normalized : `bool`, optional
            If `True`, return a normalized (unit) vector.

        Returns
        -------
        vec : `numpy.ndarray`, shape (`ndim`,)
            (Unit) vector pointing from the detector to the source
        """

        if mpar not in self.motion_params:
            raise ValueError('mpar {} is not in the valid range {}.'
                             ''.format(mpar, self.motion_params))
        if dpar not in self.det_params:
            raise ValueError('detector parameter {} is not in the valid '
                             'range {}.'.format(dpar, self.det_params))

        vec = self.src_position(mpar) - self.det_point_position(mpar, dpar)

        if normalized:
            # axis = -1 allows this to be vectorized
            vec /= np.linalg.norm(vec, axis=-1)

        return vec


class AxisOrientedGeometry(object):
    """Mixin class for 3d geometries oriented according to an axis."""

    def __init__(self, axis):
        """Initialize a new instance.

        Parameters
        ----------
        axis : 3-element array, optional
            Fixed rotation axis defined by a 3-element vector
        """

        self._axis = np.asarray(axis, dtype=float) / np.linalg.norm(axis)

        if self.axis.shape != (3,):
            raise ValueError('axis {!r} not a 3 element array-like'
                             ''.format(axis))

    @property
    def axis(self):
        """The normalized axis of rotation.

        Returns
        -------
        axis : `numpy.ndarray`, shape (3,)
            The normalized rotation axis
        """
        return self._axis

    def rotation_matrix(self, angle):
        """The detector rotation function.

        Returns the matrix for rotating a vector in 3d by an angle ``angle``
        about the rotation axis given by the property `axis` according to
        the right hand rule.

        The matrix is computed according to
        `Rodrigues' rotation formula
        <https://en.wikipedia.org/wiki/Rodrigues'_rotation_formula>`_.

        Parameters
        ----------
        angle : `float`
            The motion parameter given in radian. It must be
            contained in this geometry's `motion_params`.

        Returns
        -------
        rot_mat : `numpy.ndarray`, shape ``(3, 3)``
            The rotation matrix mapping the standard basis vectors in
            the fixed ("lab") coordinate system to the basis vectors of
            the local coordinate system of the detector reference point,
            expressed in the fixed system.
        """

        angle = float(angle)
        if angle not in self.motion_params:
            raise ValueError('angle {} is not in the valid range {}.'
                             ''.format(angle, self.motion_params))

        axis = self.axis

        cross_mat = np.array([[0, -axis[2], axis[1]],
                              [axis[2], 0, -axis[0]],
                              [-axis[1], axis[0], 0]])
        dy_mat = np.outer(axis, axis)
        id_mat = np.eye(3)
        cos_ang = np.cos(angle)
        sin_ang = np.sin(angle)

        return cos_ang * id_mat + (1. - cos_ang) * dy_mat + sin_ang * cross_mat
