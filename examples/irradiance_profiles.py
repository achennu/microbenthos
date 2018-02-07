import logging
logger = logging.getLogger('microbenthos')
logger.setLevel(20)
from logutils.colorize import ColorizingStreamHandler
logger.addHandler(ColorizingStreamHandler())
from microbenthos import SedimentDBLDomain, Irradiance

from scipy.stats import norm
from fipy import PhysicalField, Variable
from matplotlib import pyplot as plt


domain = SedimentDBLDomain()

DEPTHS = domain.depths.numericValue / 1e-6

Irrad = Irradiance()
print('Created {}'.format(Irrad))


Irrad.create_channel('par', 16.1)
print('Added channel: {}'.format(Irrad))
# now the PAR channel appears

Irrad.domain = domain

Irrad.setup()
print('Domain variables: {}'.format(domain.VARS))
# Now the par channel is setup

for chname, channel in Irrad.channels.iteritems():
    print('Channel {}: {}'.format(chname, channel))

# First observe the surface value over daylength time
CLOCKTIME = Variable(0, 's')
dT = PhysicalField(15, 'min')
plt.plot(CLOCKTIME.numericValue/3600.0, Irrad.surface_irrad.numericValue, 'ro')

for i in range(30*60/15):

    CLOCKTIME.value = CLOCKTIME() + dT
    Irrad.on_time_updated(CLOCKTIME)

    plt.plot(CLOCKTIME.inUnitsOf('h').value, Irrad.surface_irrad.numericValue, 'ro')

plt.xlabel('Clocktime (h)')
plt.ylabel('Surface irrad (%)')
plt.show(block=False)

# Add a dependence on a biomass value for the attenuation

bmass = domain.create_var('biomass1', value=0, unit='mg/cm**3')
bmass.value = 0.25 * norm.pdf(domain.mesh.x(), loc=domain.mesh.x[20], scale=domain.distances[3])
kappa1 = Variable(25.3, 'cm**2/g', name='kappa1')
kappa2 = Variable(55.5, 'cm**2/g', name='kappa2')

par = Irrad.channels['par']
par.add_attenuation_source('biomass1', kappa1)
print('Added attenuation: {}'.format(par))

bmass2 = domain.create_var('biomass2', value=0, unit='mg/cm**3')
bmass2.value =  norm.pdf(domain.mesh.x(), loc=domain.mesh.x[24], scale=domain.distances[3]*3)
nir = Irrad.create_channel('nir', 10.2, k_mods=[('biomass1', kappa2), ('biomass2', kappa1)])

print('Irrad is now: {}'.format(Irrad))
print('NIR: {}'.format(Irrad.channels['nir']))

fig, (ax1, ax2) = plt.subplots(ncols=2, figsize=(8,8), sharey=True)
plt.axes(ax1)
plt.plot(bmass.numericValue, DEPTHS, 'r', label='biomass1')
plt.plot(bmass2.numericValue, DEPTHS, 'g', label='biomass1')
plt.ylim(*plt.ylim()[::-1])
plt.legend()
plt.ylabel('Depth (um)')
plt.xlabel('Biomass')

plt.twiny()
plt.plot(par.attenuation_profile, DEPTHS, 'k--', label='par_atten')
plt.plot(nir.attenuation_profile, DEPTHS, 'k:', label='nir_atten')
plt.xscale('log')
plt.xlabel('Attenuation')
plt.legend()


# CLOCKTIME.value = Irrad.clocktime_zenith
Irrad.on_time_updated(Irrad.zenith_time)


plt.axes(ax2)
plt.plot(par.intensities.numericValue, DEPTHS, 'k--', label='par')
plt.plot(nir.intensities.numericValue, DEPTHS, 'k:', label='nir')
plt.axhline()
# plt.xscale('log')
plt.legend()
plt.xlabel('Intensities')

plt.show()
# create some plots




# TIMES = []
# INTENSITIES = []
#
# TIMES.append(CLOCKTIME.numericValue)
# INTENSITIES.append(Irrad.surface_irrad.numericValue)
#
# for i in range(50):
#     CLOCKTIME.value = CLOCKTIME.value + dT
#     print('CLOCKTIME NOW: {}'.format(CLOCKTIME))
#     Irrad.on_time_updated(CLOCKTIME)
#
#     TIMES.append(float(CLOCKTIME().numericValue))
#     INTENSITIES.append(float(Irrad.surface_irrad()))
#
#
# TIMES = np.array(TIMES)
# INTENSITIES = np.array(INTENSITIES)
#
# print(TIMES[:5])
# print(INTENSITIES[:5])
# plt.plot(TIMES/3600, INTENSITIES, 'ro')
plt.show()

