.. _tut02:

Chemical reactions
===================

In the previous tutorial :ref:`tut01`, we defined a microbenthic domain and a single variable to
construct a single differential equation. We will now create chemical reactions between two
solutes and study the dynamics and distributions of their variables by solving couple partial
differential equations.

Firstly, we define another diffusive solute hydrogen sulfide :math:`H_2S` under ``environment``.

.. code-block:: yaml

    h2s:
        cls: Variable
        init_params:
            name: h2s
            create:
                hasOld: true
                value: !unit 0.0 mol/m**3

            constraints:
                top: !unit 10.0 mumol/l
                bottom: !unit 1e-3 mol/l

            seed:
                profile: linear

            clip_min: 0.0

    D_h2s:
        cls: Process
        init_params:
            expr:
                formula: porosity * D0_h2s
            params:
                D0_h2s: !unit 0.02 cm**2/h

Respiration
------------

We will now specify reactions that involve the ``oxy`` and ``h2s`` variables, which will be cast
as "source" terms in the differential equations. First we specify that the oxygen within the
sediment is consumed through aerobic respiration in the ``environment``.

.. code-block:: yaml

    aero_respire:
        cls: Process
        init_params:
            expr:
                formula: -Vmax * porosity * sed_mask * saturation(oxy, Km)
            params:
                Vmax: !unit 1.0 mmol/l/h
                Km: &aero_Km !unit 1e-5 mol/l

This specification states that thye respiration process at a rate of ``Vmax``. Since respiration
does not occur within the sediment grains but within the porespaces, we multiply it by
``porosity``, which is defined from the model domain. We want that the reaction occurs only in
the sediment and not in the water column, so we use the variable ``sed_mask``. This
merely selects the region of the domain that is the sediment. Additionally, we specify that the
rate of respiration has a saturation dependence on oxygen, that is the rate of the process slows
down at high enough levels (parameterized by ``Km``) of oxygen. What is the formulation for the
``saturation(oxy, Km)`` function? It can be specified under the ``namespace`` key of the process'
``init_params``. Alternatively, if a formula is to be reused then in a ``formulae``
section of the ``model`` as follows.

.. code-block:: yaml

    formulae:

        saturation:
            vars: [x, Km]
            expr: x / (Km + x)


Abiotic sulfide oxidation
--------------------------

Another process that occurs in sedimentary system is the abiotic oxidation of sulfide. That is
oxygen reacts with hydrogen sulfide in a 2:1 stoichiometry. We can define this process also in
the ``environment``.

.. code-block:: yaml

    abio_sulfoxid:
        cls: Process
        init_params:
            expr:
                formula: porosity * sed_mask * k * oxy * oxy * h2s
            params:
                k: !unit -70.0 1/h/(mmol/l)**2

This reaction process therefore couples the equations of the two variables ``oxy`` and ``h2s``,
that so far had no shared process terms. The definition of this process should therefore appear
in both equations.

The equations for this model will therefore be:

.. code-block:: yaml

    equations:

        oxyEqn:
            transient: [domain.oxy, 1]

            diffusion: [env.D_oxy, 1]

            sources:
                - [env.abio_sulfoxid, 2]

                - [env.aero_respire, 1]

        h2sEqn:

            transient: [domain.h2s, 1]

            diffusion: [env.D_h2s, 1]

            sources:
                - [env.abio_sulfoxid, 1]

Note that the stoichiometry of the sulfide oxidation process is represented by a coefficient of 2
in the oxygen equation, indicating that for each H2S consumed two O2 are consumed by this
process. The definition of the environmental process ``abio_sulfoxid`` enables us to easily
represent the process in multiple equations.

Run it
-------

This creates the equation to solve

.. math::

    \frac{d}{dt} oxy = Doxy \frac{d^{2}}{d z^{2}}  oxy - \frac{Vmax \cdot oxy \cdot porosity
    \cdot sed\_mask} {Km + oxy} + \\
    2 \cdot h2s \cdot k \cdot oxy^{2} \cdot porosity \cdot sed\_mask

    \frac{d}{dt} h2s = Dh2s \frac{d^{2}}{d z^{2}}  h2s + h2s \cdot k \cdot oxy^{2} \cdot porosity
    \cdot sed\_mask


Running the model simulation with::

    microbenthos -v simulate input_definition.yml --plot --show-eqns

should show the equation in the console and open up a graphical view of the model as it is
simulated.

An extracted frame is shown below.

.. image:: model_frame.png



The full :download:`definition file <definition_input.yml>` is:

.. literalinclude:: definition_input.yml
   :language: yaml
