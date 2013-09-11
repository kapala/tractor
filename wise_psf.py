if __name__ == '__main__':
    import matplotlib
    matplotlib.use('Agg')

import sys
import os

import pylab as plt
import numpy as np
from astrometry.util.fits import *
from astrometry.util.file import *
from astrometry.util.plotutils import *

import tractor
from tractor import *
from tractor.sdss import *
from tractor.sdss_galaxy import *
from tractor.emfit import em_fit_2d
from tractor.fitpsf import em_init_params

from tractor.psfex import *


class WisePSF(VaryingGaussianPSF):
    def __init__(self, band, savedfn=None, ngrid=11):
        '''
        band: integer 1-4
        '''
        assert(band in [1,2,3,4])
        S = 1016
        # W4 images are binned on-board 2x2
        if band == 4:
            S /= 2
        self.band = band

        self.ngrid = ngrid
        
        super(WisePSF, self).__init__(S, S, nx=self.ngrid, ny=self.ngrid)

        if savedfn:
            T = fits_table(savedfn)
            pp = T.data
            (NP,NY,NX) = pp.shape
            pp2 = np.zeros((NY,NX,NP))
            for i in range(NP):
                pp2[:,:,i] = pp[i,:,:]
            XX = np.linspace(0, S-1, NX)
            YY = np.linspace(0, S-1, NY)
            self.fitSavedData(pp2, XX, YY)

    def instantiateAt(self, x, y):
        '''
        This is used during fitting.  When used afterwards, you just
        want to use the getPointSourcePatch() and similar methods
        defined in the parent class.
        '''
        # clip to nearest grid point...
        dx = (self.W - 1) / float(self.ngrid - 1)
        gx = dx * int(np.round(x / dx))
        gy = dx * int(np.round(y / dx))

        fn = 'wise-psf/wise-psf-w%i-%.1f-%.1f.fits' % (self.band, gx, gy)
        if not os.path.exists(fn):
            '''
            module load idl
            module load idlutils
            export WISE_DATA=$(pwd)/wise-psf/etc
            '''
            fullfn = os.path.abspath(fn)
            idlcmd = ("mwrfits, wise_psf_cutout(%.1f, %.1f, band=%i, allsky=1), '%s'" % 
                      (gx, gy, self.band, fullfn))
            print 'IDL command:', idlcmd
            idl = os.path.join(os.environ['IDL_DIR'], 'bin', 'idl')
            cmd = 'cd wise-psf/pro; echo "%s" | %s' % (idlcmd, idl)
            print 'Command:', cmd
            os.system(cmd)

        print 'Reading', fn
        psf = pyfits.open(fn)[0].data
        return psf


if __name__ == '__main__':

    # How to load 'em...
    # w = WisePSF(1, savedfn='w1psffit.fits')
    # print 'Instantiate...'
    # im = w.getPointSourcePatch(50., 50.)
    # print im.shape
    # plt.clf()
    # plt.imshow(im.patch, interpolation='nearest', origin='lower')
    # plt.savefig('w1.png')
    # sys.exit(0)


    import fitsio

    for band in [1,2,3,4]:

        H,W = 1016,1016
        nx,ny = 11,11
        if band == 4:
            H /= 2
            W /= 2
        YY = np.linspace(0, H, ny)
        XX = np.linspace(0, W, nx)


        psfsum = 0.
        for y in YY:
            for x in XX:
                # clip to nearest grid point...
                dx = (W - 1) / float(nx - 1)
                dy = (H - 1) / float(ny - 1)
                gx = dx * int(np.round(x / dx))
                gy = dy * int(np.round(y / dy))

                fn = 'wise-psf/wise-psf-w%i-%.1f-%.1f.fits' % (band, gx, gy)
                I = fitsio.read(fn)
                psfsum = psfsum + I
        psfsum /= psfsum.sum()

        psf = GaussianMixturePSF.fromStamp(psfsum)
        #fn = 'wise-psf-avg-w%i.fits' % band
        fn = 'wise-psf-avg.fits'
        #fitsio.write(fn, psf, clobber=True)
        #print 'Wrote', fn        
        T = fits_table()
        T.amp = psf.mog.amp
        T.mean = psf.mog.mean
        T.var = psf.mog.var
        append = (band > 1)
        T.writeto(fn, append=append)

    sys.exit(0)

    
    # Fit
    for band in [1,2,3,4]:
        pfn = 'w%i.pickle' % band
        if os.path.exists(pfn):
            print 'Reading', pfn
            w = unpickle_from_file(pfn)
        else:
            w = WisePSF(band)
            w.savesplinedata = True
            w.ensureFit()
            pickle_to_file(w, pfn)

        print 'Fit data:', w.splinedata
        T = tabledata()
        (pp,xx,yy) = w.splinedata
        (NY,NX,NP) = pp.shape
        pp2 = np.zeros((NP,NY,NX))
        for i in range(NP):
            pp2[i,:,:] = pp[:,:,i]

        T.data = pp2
        T.writeto('w%ipsffit.fits' % band)


