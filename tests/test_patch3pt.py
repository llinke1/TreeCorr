# Copyright (c) 2003-2019 by Mike Jarvis
#
# TreeCorr is free software: redistribution and use in source and binary forms,
# with or without modification, are permitted provided that the following
# conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions, and the disclaimer given in the accompanying LICENSE
#    file.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions, and the disclaimer given in the documentation
#    and/or other materials provided with the distribution.

from __future__ import print_function
import numpy as np
import os
import coord
import time
import fitsio
import treecorr

from test_helper import assert_raises, do_pickle, timer, get_from_wiki, CaptureLog, clear_save

def generate_shear_field(nside, nhalo, rng=None):
    # We do something completely different here than we did for 2pt patch tests.
    # A straight Gaussian field with a given power spectrum has no significant 3pt power,
    # so it's not a great choice for simulating a field for 3pt tests.
    # Instead we place N SIS "halos" randomly in the grid.
    # Then we translate that to a shear field via FFT.

    if rng is None:
        rng = np.random.RandomState()

    # Generate x,y values for the real-space field
    x,y = np.meshgrid(np.linspace(0.,1000.,nside), np.linspace(0.,1000.,nside))

    # Fill the kappa values with SIS halo profiles.
    xc = rng.uniform(0,1000, size=nhalo)
    yc = rng.uniform(0,1000, size=nhalo)
    scale = rng.uniform(20,100, size=nhalo)
    mass = rng.uniform(0.01, 0.05, size=nhalo)
    dx = x.ravel()[:,np.newaxis]-xc[np.newaxis,:]
    dy = y.ravel()[:,np.newaxis]-yc[np.newaxis,:]
    dx[dx==0] = 1  # Avoid division by zero.
    dy[dy==0] = 1
    dx /= scale
    dy /= scale
    rsq = dx**2 + dy**2
    r = rsq**0.5
    k = mass / r  # "Mass" here is really just a dimensionless normalization propto mass.
    kappa = np.sum(k, axis=1).reshape(x.shape)

    # gamma_t = kappa for SIS.
    g = -k * (dx + 1j*dy)**2 / rsq
    gamma = np.sum(g, axis=1).reshape(x.shape)

    x = x.ravel()
    y = y.ravel()
    gamma = gamma.ravel()
    kappa = kappa.ravel()

    # Randomize the positions a little.
    dx = 1000/nside
    x += rng.uniform(-dx/2,dx/2,len(x))
    y += rng.uniform(-dx/2,dx/2,len(x))

    return x, y, np.real(gamma), np.imag(gamma), kappa


@timer
def test_kkk_jk():
    # Test jackknife and other covariance estimates for kkk correlations.
    # Note: This test takes a while!
    # The main version I think is a pretty decent test of the code correctness.
    # It shows that bootstrap in particular easily gets to within 50% of the right variance.
    # Sometimes within 20%, but because of the randomness there, it varies a bit.
    # Jackknife isn't much worse.  Just a little below 50%.  But still pretty good.
    # Sample and Marked are not great for this test.  I think they will work ok when the
    # triangles of interest are mostly within single patches, but that's not the case we
    # have here, and it would take a lot more points to get to that regime.  So the
    # accuracy tests for those two are pretty loose.

    if __name__ == '__main__':
        # This setup takes about 740 sec to run.
        nside = 200
        nhalo = 1000
        nsource = 10000
        npatch = 64
        tol_factor = 1
    elif False:
        # This setup takes about 180 sec to run.
        nside = 100
        nhalo = 500
        nsource = 2000
        npatch = 32
        tol_factor = 2
    elif False:
        # This setup takes about 51 sec to run.
        nside = 100
        nhalo = 100
        nsource = 1000
        npatch = 16
        tol_factor = 8
    else:
        # This setup takes about 14 sec to run.
        # So we use this one for regular unit test runs.
        # It's pretty terrible in terms of testing the accuracy, but it works for code coverage.
        # But whenever actually working on this part of the code, definitely need to switch
        # to one of the above setups.  Preferably run the name==main version to get a good
        # test of the code correctness.
        nside = 100
        nhalo = 50
        nsource = 500
        npatch = 8
        tol_factor = 10

    file_name = 'data/test_kkk_jk_{}.npz'.format(nsource)
    print(file_name)
    if not os.path.isfile(file_name):
        nruns = 1000
        all_kkks = []
        for run in range(nruns):
            x, y, _, _, k = generate_shear_field(nside, nhalo)
            print(run,': ',np.mean(k),np.std(k))
            indx = np.random.choice(range(len(x)),nsource,replace=False)
            cat = treecorr.Catalog(x=x[indx], y=y[indx], k=k[indx])
            kkk = treecorr.KKKCorrelation(nbins=3, min_sep=30., max_sep=100.,
                                           min_u=0.9, max_u=1.0, nubins=1,
                                           min_v=0.0, max_v=0.1, nvbins=1)
            kkk.process(cat)
            print(kkk.ntri.ravel().tolist())
            print(kkk.zeta.ravel().tolist())
            all_kkks.append(kkk)
        mean_kkk = np.mean([kkk.zeta.ravel() for kkk in all_kkks], axis=0)
        var_kkk = np.var([kkk.zeta.ravel() for kkk in all_kkks], axis=0)

        np.savez(file_name, all_kkk=np.array([kkk.zeta.ravel() for kkk in all_kkks]),
                 mean_kkk=mean_kkk, var_kkk=var_kkk)

    data = np.load(file_name)
    mean_kkk = data['mean_kkk']
    var_kkk = data['var_kkk']
    print('mean = ',mean_kkk)
    print('var = ',var_kkk)

    rng = np.random.RandomState(12345)
    x, y, _, _, k = generate_shear_field(nside, nhalo, rng)
    indx = rng.choice(range(len(x)),nsource,replace=False)
    cat = treecorr.Catalog(x=x[indx], y=y[indx], k=k[indx])
    kkk = treecorr.KKKCorrelation(nbins=3, min_sep=30., max_sep=100.,
                                  min_u=0.9, max_u=1.0, nubins=1,
                                  min_v=0.0, max_v=0.1, nvbins=1, rng=rng)
    kkk.process(cat)
    print(kkk.ntri.ravel())
    print(kkk.zeta.ravel())
    print(kkk.varzeta.ravel())

    kkkp = kkk.copy()
    catp = treecorr.Catalog(x=x[indx], y=y[indx], k=k[indx], npatch=npatch)

    # Do the same thing with patches.
    kkkp.process(catp)
    print('with patches:')
    print(kkkp.ntri.ravel())
    print(kkkp.zeta.ravel())
    print(kkkp.varzeta.ravel())

    np.testing.assert_allclose(kkkp.ntri, kkk.ntri, rtol=0.05 * tol_factor)
    np.testing.assert_allclose(kkkp.zeta, kkk.zeta, rtol=0.1 * tol_factor, atol=1e-3 * tol_factor)
    np.testing.assert_allclose(kkkp.varzeta, kkk.varzeta, rtol=0.05 * tol_factor)

    print('jackknife:')
    cov = kkkp.estimate_cov('jackknife')
    print(np.diagonal(cov))
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_kkk))))
    np.testing.assert_allclose(np.diagonal(cov), var_kkk, rtol=0.6 * tol_factor)
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_kkk), atol=0.5*tol_factor)

    # Both sample and marked are pretty bad for this case.  I think because we have
    # a lot of triangles that cross regions, and these methods don't handle that as well
    # as jackknife or bootstrap.  But it's possible there is a better version of the triple
    # selection that would work better, and I just haven't found it.
    # (I tried a few other plausible choices, but they were even worse.)
    print('sample:')
    cov = kkkp.estimate_cov('sample')
    print(np.diagonal(cov))
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_kkk))))
    np.testing.assert_allclose(np.diagonal(cov), var_kkk, rtol=0.7 * tol_factor)
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_kkk), atol=1.1*tol_factor)

    print('marked:')
    cov = kkkp.estimate_cov('marked_bootstrap')
    print(np.diagonal(cov))
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_kkk))))
    np.testing.assert_allclose(np.diagonal(cov), var_kkk, rtol=0.7 * tol_factor)
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_kkk), atol=1.1*tol_factor)

    # As for 2pt, bootstrap seems to be pretty reliably the best estimator out of these.
    # However, because it's random, it can occasionally come out even slightly worse than jackknife.
    # So the test tolerance is the same as jackknife, even though the typical performance is
    # quite a bit better usually.
    print('bootstrap:')
    cov = kkkp.estimate_cov('bootstrap')
    print(np.diagonal(cov))
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_kkk))))
    np.testing.assert_allclose(np.diagonal(cov), var_kkk, rtol=0.5 * tol_factor)
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_kkk), atol=0.4*tol_factor)

    # Now as a cross correlation with all 3 using the same patch catalog.
    print('with 3 patched catalogs:')
    kkkp.process(catp, catp, catp)
    print(kkkp.zeta.ravel())
    np.testing.assert_allclose(kkkp.zeta, kkk.zeta, rtol=0.1 * tol_factor, atol=1e-3 * tol_factor)

    print('jackknife:')
    cov = kkkp.estimate_cov('jackknife')
    print(np.diagonal(cov))
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_kkk))))
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_kkk), atol=0.5*tol_factor)

    print('sample:')
    cov = kkkp.estimate_cov('sample')
    print(np.diagonal(cov))
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_kkk))))
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_kkk), atol=1.1*tol_factor)

    print('marked:')
    cov = kkkp.estimate_cov('marked_bootstrap')
    print(np.diagonal(cov))
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_kkk))))
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_kkk), atol=1.2*tol_factor)

    print('bootstrap:')
    cov = kkkp.estimate_cov('bootstrap')
    print(np.diagonal(cov))
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_kkk))))
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_kkk), atol=0.7*tol_factor)

    # Repeat this test with different combinations of patch with non-patch catalogs:
    # All the methods work best when the patches are used for all 3 catalogs.  But there
    # are probably cases where this kind of cross correlation with only some catalogs having
    # patches could be desired.  So this mostly just checks that the code runs properly.

    # Patch on 1 only:
    print('with patches on 1 only:')
    kkkp.process(catp, cat)
    print(kkkp.zeta.ravel())
    np.testing.assert_allclose(kkkp.zeta, kkk.zeta, rtol=0.1 * tol_factor, atol=1e-3 * tol_factor)

    print('jackknife:')
    cov = kkkp.estimate_cov('jackknife')
    print(np.diagonal(cov))
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_kkk))))
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_kkk), atol=1.2*tol_factor)

    print('sample:')
    cov = kkkp.estimate_cov('sample')
    print(np.diagonal(cov))
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_kkk))))
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_kkk), atol=1.2*tol_factor)

    print('marked:')
    cov = kkkp.estimate_cov('marked_bootstrap')
    print(np.diagonal(cov))
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_kkk))))
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_kkk), atol=1.2*tol_factor)

    print('bootstrap:')
    cov = kkkp.estimate_cov('bootstrap')
    print(np.diagonal(cov))
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_kkk))))
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_kkk), atol=1.3*tol_factor)

    # Patch on 2 only:
    print('with patches on 2 only:')
    kkkp.process(cat, catp, cat)
    print(kkkp.zeta.ravel())
    np.testing.assert_allclose(kkkp.zeta, kkk.zeta, rtol=0.1 * tol_factor, atol=1e-3 * tol_factor)

    print('jackknife:')
    cov = kkkp.estimate_cov('jackknife')
    print(np.diagonal(cov))
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_kkk))))
    np.testing.assert_allclose(np.diagonal(cov), var_kkk, rtol=0.9 * tol_factor)
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_kkk), atol=1.2*tol_factor)

    print('sample:')
    cov = kkkp.estimate_cov('sample')
    print(np.diagonal(cov))
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_kkk))))
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_kkk), atol=1.2*tol_factor)

    print('marked:')
    cov = kkkp.estimate_cov('marked_bootstrap')
    print(np.diagonal(cov))
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_kkk))))
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_kkk), atol=1.2*tol_factor)

    print('bootstrap:')
    cov = kkkp.estimate_cov('bootstrap')
    print(np.diagonal(cov))
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_kkk))))
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_kkk), atol=1.2*tol_factor)

    # Patch on 3 only:
    print('with patches on 3 only:')
    kkkp.process(cat, cat, catp)
    print(kkkp.zeta.ravel())
    np.testing.assert_allclose(kkkp.zeta, kkk.zeta, rtol=0.1 * tol_factor, atol=1e-3 * tol_factor)

    print('jackknife:')
    cov = kkkp.estimate_cov('jackknife')
    print(np.diagonal(cov))
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_kkk))))
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_kkk), atol=1.2*tol_factor)

    print('sample:')
    cov = kkkp.estimate_cov('sample')
    print(np.diagonal(cov))
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_kkk))))
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_kkk), atol=1.2*tol_factor)

    print('marked:')
    cov = kkkp.estimate_cov('marked_bootstrap')
    print(np.diagonal(cov))
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_kkk))))
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_kkk), atol=1.2*tol_factor)

    print('bootstrap:')
    cov = kkkp.estimate_cov('bootstrap')
    print(np.diagonal(cov))
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_kkk))))
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_kkk), atol=1.3*tol_factor)

    # Patch on 1,2
    print('with patches on 1,2:')
    kkkp.process(catp, catp, cat)
    print(kkkp.zeta.ravel())
    np.testing.assert_allclose(kkkp.zeta, kkk.zeta, rtol=0.1 * tol_factor, atol=1e-3 * tol_factor)

    print('jackknife:')
    cov = kkkp.estimate_cov('jackknife')
    print(np.diagonal(cov))
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_kkk))))
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_kkk), atol=0.4*tol_factor)

    print('sample:')
    cov = kkkp.estimate_cov('sample')
    print(np.diagonal(cov))
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_kkk))))
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_kkk), atol=1.1*tol_factor)

    print('marked:')
    cov = kkkp.estimate_cov('marked_bootstrap')
    print(np.diagonal(cov))
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_kkk))))
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_kkk), atol=1.2*tol_factor)

    print('bootstrap:')
    cov = kkkp.estimate_cov('bootstrap')
    print(np.diagonal(cov))
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_kkk))))
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_kkk), atol=0.4*tol_factor)

    # Patch on 2,3
    print('with patches on 2,3:')
    kkkp.process(cat, catp)
    print(kkkp.zeta.ravel())
    np.testing.assert_allclose(kkkp.zeta, kkk.zeta, rtol=0.1 * tol_factor, atol=1e-3 * tol_factor)

    print('jackknife:')
    cov = kkkp.estimate_cov('jackknife')
    print(np.diagonal(cov))
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_kkk))))
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_kkk), atol=0.4*tol_factor)

    print('sample:')
    cov = kkkp.estimate_cov('sample')
    print(np.diagonal(cov))
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_kkk))))
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_kkk), atol=1.1*tol_factor)

    print('marked:')
    cov = kkkp.estimate_cov('marked_bootstrap')
    print(np.diagonal(cov))
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_kkk))))
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_kkk), atol=1.1*tol_factor)

    print('bootstrap:')
    cov = kkkp.estimate_cov('bootstrap')
    print(np.diagonal(cov))
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_kkk))))
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_kkk), atol=0.4*tol_factor)

    # Patch on 1,3
    print('with patches on 1,3:')
    kkkp.process(catp, cat, catp)
    print(kkkp.zeta.ravel())
    np.testing.assert_allclose(kkkp.zeta, kkk.zeta, rtol=0.1 * tol_factor, atol=1e-3 * tol_factor)

    print('jackknife:')
    cov = kkkp.estimate_cov('jackknife')
    print(np.diagonal(cov))
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_kkk))))
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_kkk), atol=0.4*tol_factor)

    print('sample:')
    cov = kkkp.estimate_cov('sample')
    print(np.diagonal(cov))
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_kkk))))
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_kkk), atol=1.1*tol_factor)

    print('marked:')
    cov = kkkp.estimate_cov('marked_bootstrap')
    print(np.diagonal(cov))
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_kkk))))
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_kkk), atol=1.3*tol_factor)

    print('bootstrap:')
    cov = kkkp.estimate_cov('bootstrap')
    print(np.diagonal(cov))
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_kkk))))
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_kkk), atol=0.4*tol_factor)

    # Finally a set (with all patches) using the KKKCrossCorrelation class.
    kkkc = treecorr.KKKCrossCorrelation(nbins=3, min_sep=30., max_sep=100.,
                                        min_u=0.9, max_u=1.0, nubins=1,
                                        min_v=0.0, max_v=0.1, nvbins=1, rng=rng)
    print('CrossCorrelation:')
    kkkc.process(catp, catp, catp)
    for k1 in kkkc._all:
        print(k1.ntri.ravel())
        print(k1.zeta.ravel())
        print(k1.varzeta.ravel())

        np.testing.assert_allclose(k1.ntri, kkk.ntri, rtol=0.05 * tol_factor)
        np.testing.assert_allclose(k1.zeta, kkk.zeta, rtol=0.1 * tol_factor, atol=1e-3 * tol_factor)
        np.testing.assert_allclose(k1.varzeta, kkk.varzeta, rtol=0.05 * tol_factor)

    print('jackknife:')
    cov = kkkc.estimate_cov('jackknife')
    print(np.diagonal(cov))
    for i in range(6):
        v = np.diagonal(cov)[i*6:(i+1)*6]
        print('max log(ratio) = ',np.max(np.abs(np.log(v)-np.log(var_kkk))))
        np.testing.assert_allclose(np.log(v), np.log(var_kkk), atol=0.5*tol_factor)

    print('sample:')
    cov = kkkc.estimate_cov('sample')
    print(np.diagonal(cov))
    for i in range(6):
        v = np.diagonal(cov)[i*6:(i+1)*6]
        print('max log(ratio) = ',np.max(np.abs(np.log(v)-np.log(var_kkk))))
        np.testing.assert_allclose(np.log(v), np.log(var_kkk), atol=1.1*tol_factor)

    print('marked:')
    cov = kkkc.estimate_cov('marked_bootstrap')
    print(np.diagonal(cov))
    for i in range(6):
        v = np.diagonal(cov)[i*6:(i+1)*6]
        print('max log(ratio) = ',np.max(np.abs(np.log(v)-np.log(var_kkk))))
        np.testing.assert_allclose(np.log(v), np.log(var_kkk), atol=1.2*tol_factor)

    print('bootstrap:')
    cov = kkkc.estimate_cov('bootstrap')
    print(np.diagonal(cov))
    for i in range(6):
        v = np.diagonal(cov)[i*6:(i+1)*6]
        print('max log(ratio) = ',np.max(np.abs(np.log(v)-np.log(var_kkk))))
        np.testing.assert_allclose(np.log(v), np.log(var_kkk), atol=0.4*tol_factor)

    # All catalogs need to have the same number of patches
    catq = treecorr.Catalog(x=x[indx], y=y[indx], k=k[indx], npatch=2*npatch)
    with assert_raises(RuntimeError):
        kkkp.process(catp, catq)
    with assert_raises(RuntimeError):
        kkkp.process(catp, catq, catq)
    with assert_raises(RuntimeError):
        kkkp.process(catq, catp, catq)
    with assert_raises(RuntimeError):
        kkkp.process(catq, catq, catp)

@timer
def test_ggg_jk():
    # Test jackknife and other covariance estimates for ggg correlations.

    if __name__ == '__main__':
        # This setup takes about 450 sec to run.
        nside = 200
        nhalo = 500
        nsource = 5000
        npatch = 32
        tol_factor = 1
    elif False:
        # This setup takes about 150 sec to run.
        nside = 100
        nhalo = 300
        nsource = 2000
        npatch = 16
        tol_factor = 2
    elif False:
        # This setup takes about 40 sec to run.
        nside = 100
        nhalo = 100
        nsource = 1000
        npatch = 16
        tol_factor = 4
    else:
        # This setup takes about 11 sec to run.
        # It also doesn't require much looser tolerance than the longest one.
        # Partly this is due to that already not being a very tight test, but for whatever
        # reason, this test doesn't seem to get much worse for the noisier data vectors.
        nside = 100
        nhalo = 50
        nsource = 500
        npatch = 8
        tol_factor = 5

    # I couldn't figure out a way to get reasonable S/N in the shear field.  I thought doing
    # discrete halos would give some significant 3pt shear pattern, at least for equilateral
    # triangles, but the signal here is still consistent with zero.  :(
    # The point is the variance, which is still calculated ok, but I would have rathered
    # have something with S/N > 0.

    # For these tests, I set up the binning to just accumulate all roughly equilateral triangles
    # in a small separation range.  The binning always uses two bins for each to get + and - v
    # bins.  So this function averages these two values to produce 1 value for each gamma.
    f = lambda g: np.array([np.mean(g.gam0), np.mean(g.gam1), np.mean(g.gam2), np.mean(g.gam3)])

    file_name = 'data/test_ggg_jk_{}.npz'.format(nsource)
    print(file_name)
    if not os.path.isfile(file_name):
        nruns = 1000
        all_gggs = []
        for run in range(nruns):
            x, y, g1, g2, _ = generate_shear_field(nside, nhalo)
            # For some reason std(g2) is coming out about 1.5x larger than std(g1).
            # Probably a sign of some error in the generate function, but I don't see it.
            # For this purpose I think it doesn't really matter, but it's a bit odd. ¯\_(ツ)_/¯
            print(run,': ',np.mean(g1),np.std(g1),np.mean(g2),np.std(g2))
            indx = np.random.choice(range(len(x)),nsource,replace=False)
            cat = treecorr.Catalog(x=x[indx], y=y[indx], g1=g1[indx], g2=g2[indx])
            ggg = treecorr.GGGCorrelation(nbins=1, min_sep=20., max_sep=40.,
                                           min_u=0.6, max_u=1.0, nubins=1,
                                           min_v=0.0, max_v=0.6, nvbins=1)
            ggg.process(cat)
            print(ggg.ntri.ravel())
            print(f(ggg))
            all_gggs.append(ggg)
        all_ggg = np.array([f(ggg) for ggg in all_gggs])
        mean_ggg = np.mean(all_ggg, axis=0)
        var_ggg = np.var(all_ggg, axis=0)
        np.savez(file_name, mean_ggg=mean_ggg, var_ggg=var_ggg)

    data = np.load(file_name)
    mean_ggg = data['mean_ggg']
    var_ggg = data['var_ggg']
    print('mean = ',mean_ggg)
    print('var = ',var_ggg)

    rng = np.random.RandomState(12345)
    x, y, g1, g2, _ = generate_shear_field(nside, nhalo, rng)
    indx = rng.choice(range(len(x)),nsource,replace=False)
    cat = treecorr.Catalog(x=x[indx], y=y[indx], g1=g1[indx], g2=g2[indx])
    ggg = treecorr.GGGCorrelation(nbins=1, min_sep=20., max_sep=40.,
                                  min_u=0.6, max_u=1.0, nubins=1,
                                  min_v=0.0, max_v=0.6, nvbins=1, rng=rng)
    ggg.process(cat)
    print(ggg.ntri.ravel())
    print(ggg.gam0.ravel())
    print(ggg.gam1.ravel())
    print(ggg.gam2.ravel())
    print(ggg.gam3.ravel())

    gggp = ggg.copy()
    catp = treecorr.Catalog(x=x[indx], y=y[indx], g1=g1[indx], g2=g2[indx], npatch=npatch)

    # Do the same thing with patches.
    gggp.process(catp)
    print('with patches:')
    print(gggp.ntri.ravel())
    print(gggp.vargam0.ravel())
    print(gggp.vargam1.ravel())
    print(gggp.vargam2.ravel())
    print(gggp.vargam3.ravel())
    print(gggp.gam0.ravel())
    print(gggp.gam1.ravel())
    print(gggp.gam2.ravel())
    print(gggp.gam3.ravel())

    np.testing.assert_allclose(gggp.ntri, ggg.ntri, rtol=0.05 * tol_factor)
    np.testing.assert_allclose(gggp.gam0, ggg.gam0, rtol=0.1 * tol_factor, atol=1e-3 * tol_factor)
    np.testing.assert_allclose(gggp.gam1, ggg.gam1, rtol=0.1 * tol_factor, atol=1e-3 * tol_factor)
    np.testing.assert_allclose(gggp.gam2, ggg.gam2, rtol=0.1 * tol_factor, atol=1e-3 * tol_factor)
    np.testing.assert_allclose(gggp.gam3, ggg.gam3, rtol=0.1 * tol_factor, atol=1e-3 * tol_factor)
    np.testing.assert_allclose(gggp.vargam0, ggg.vargam0, rtol=0.05 * tol_factor)
    np.testing.assert_allclose(gggp.vargam1, ggg.vargam1, rtol=0.05 * tol_factor)
    np.testing.assert_allclose(gggp.vargam2, ggg.vargam2, rtol=0.05 * tol_factor)
    np.testing.assert_allclose(gggp.vargam3, ggg.vargam3, rtol=0.05 * tol_factor)

    # Unlike KKK, sample and marked are actually the best ones.  Not by a huge amount, but
    # interesting.  I suspect this is just a consequence of the S/N of this test being so low
    # that it doesn't matter all that much which covariance estimator is used.  If this is right,
    # then bootstrap is probably still the best estimator for cases with reasonable S/N.  But that
    # would require way more points than I want to do for a unit test.
    print('jackknife:')
    cov = gggp.estimate_cov('jackknife', func=f)
    print(np.diagonal(cov).real)
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_ggg))))
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_ggg), atol=0.7*tol_factor)

    print('sample:')
    cov = gggp.estimate_cov('sample', func=f)
    print(np.diagonal(cov).real)
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_ggg))))
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_ggg), atol=0.6*tol_factor)

    print('marked:')
    cov = gggp.estimate_cov('marked_bootstrap', func=f)
    print(np.diagonal(cov).real)
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_ggg))))
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_ggg), atol=0.6*tol_factor)

    print('bootstrap:')
    cov = gggp.estimate_cov('bootstrap', func=f)
    print(np.diagonal(cov).real)
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_ggg))))
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_ggg), atol=0.7*tol_factor)

    # Now as a cross correlation with all 3 using the same patch catalog.
    print('with 3 patched catalogs:')
    gggp.process(catp, catp, catp)
    print(gggp.gam0.ravel())
    np.testing.assert_allclose(gggp.gam0, ggg.gam0, rtol=0.1 * tol_factor, atol=1e-3 * tol_factor)
    np.testing.assert_allclose(gggp.gam1, ggg.gam1, rtol=0.1 * tol_factor, atol=1e-3 * tol_factor)
    np.testing.assert_allclose(gggp.gam2, ggg.gam2, rtol=0.1 * tol_factor, atol=1e-3 * tol_factor)
    np.testing.assert_allclose(gggp.gam3, ggg.gam3, rtol=0.1 * tol_factor, atol=1e-3 * tol_factor)

    print('jackknife:')
    cov = gggp.estimate_cov('jackknife', func=f)
    print(np.diagonal(cov).real)
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_ggg))))
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_ggg), atol=0.7*tol_factor)

    print('sample:')
    cov = gggp.estimate_cov('sample', func=f)
    print(np.diagonal(cov).real)
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_ggg))))
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_ggg), atol=0.7*tol_factor)

    print('marked:')
    cov = gggp.estimate_cov('marked_bootstrap', func=f)
    print(np.diagonal(cov).real)
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_ggg))))
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_ggg), atol=0.8*tol_factor)

    print('bootstrap:')
    cov = gggp.estimate_cov('bootstrap', func=f)
    print(np.diagonal(cov).real)
    print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_ggg))))
    np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_ggg), atol=0.8*tol_factor)

    # The separate patch/non-patch combinations aren't that interesting, so skip them
    # for GGG unless running from main.
    if __name__ == '__main__':
        # Patch on 1 only:
        print('with patches on 1 only:')
        gggp.process(catp, cat)

        print('jackknife:')
        cov = gggp.estimate_cov('jackknife', func=f)
        print(np.diagonal(cov).real)
        print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_ggg))))
        np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_ggg), atol=0.7*tol_factor)

        print('sample:')
        cov = gggp.estimate_cov('sample', func=f)
        print(np.diagonal(cov).real)
        print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_ggg))))
        np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_ggg), atol=0.7*tol_factor)

        print('marked:')
        cov = gggp.estimate_cov('marked_bootstrap', func=f)
        print(np.diagonal(cov).real)
        print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_ggg))))
        np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_ggg), atol=0.8*tol_factor)

        print('bootstrap:')
        cov = gggp.estimate_cov('bootstrap', func=f)
        print(np.diagonal(cov).real)
        print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_ggg))))
        np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_ggg), atol=0.8*tol_factor)

        # Patch on 2 only:
        print('with patches on 2 only:')
        gggp.process(cat, catp, cat)

        print('jackknife:')
        cov = gggp.estimate_cov('jackknife', func=f)
        print(np.diagonal(cov).real)
        print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_ggg))))
        np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_ggg), atol=0.7*tol_factor)

        print('sample:')
        cov = gggp.estimate_cov('sample', func=f)
        print(np.diagonal(cov).real)
        print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_ggg))))
        np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_ggg), atol=0.7*tol_factor)

        print('marked:')
        cov = gggp.estimate_cov('marked_bootstrap', func=f)
        print(np.diagonal(cov).real)
        print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_ggg))))
        np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_ggg), atol=0.8*tol_factor)

        print('bootstrap:')
        cov = gggp.estimate_cov('bootstrap', func=f)
        print(np.diagonal(cov).real)
        print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_ggg))))
        np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_ggg), atol=0.8*tol_factor)

        # Patch on 3 only:
        print('with patches on 3 only:')
        gggp.process(cat, cat, catp)

        print('jackknife:')
        cov = gggp.estimate_cov('jackknife', func=f)
        print(np.diagonal(cov).real)
        print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_ggg))))
        np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_ggg), atol=0.7*tol_factor)

        print('sample:')
        cov = gggp.estimate_cov('sample', func=f)
        print(np.diagonal(cov).real)
        print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_ggg))))
        np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_ggg), atol=0.7*tol_factor)

        print('marked:')
        cov = gggp.estimate_cov('marked_bootstrap', func=f)
        print(np.diagonal(cov).real)
        print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_ggg))))
        np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_ggg), atol=0.8*tol_factor)

        print('bootstrap:')
        cov = gggp.estimate_cov('bootstrap', func=f)
        print(np.diagonal(cov).real)
        print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_ggg))))
        np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_ggg), atol=0.8*tol_factor)

        # Patch on 1,2
        print('with patches on 1,2:')
        gggp.process(catp, catp, cat)

        print('jackknife:')
        cov = gggp.estimate_cov('jackknife', func=f)
        print(np.diagonal(cov).real)
        print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_ggg))))
        np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_ggg), atol=0.7*tol_factor)

        print('sample:')
        cov = gggp.estimate_cov('sample', func=f)
        print(np.diagonal(cov).real)
        print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_ggg))))
        np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_ggg), atol=0.7*tol_factor)

        print('marked:')
        cov = gggp.estimate_cov('marked_bootstrap', func=f)
        print(np.diagonal(cov).real)
        print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_ggg))))
        np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_ggg), atol=0.7*tol_factor)

        print('bootstrap:')
        cov = gggp.estimate_cov('bootstrap', func=f)
        print(np.diagonal(cov).real)
        print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_ggg))))
        np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_ggg), atol=0.8*tol_factor)

        # Patch on 2,3
        print('with patches on 2,3:')
        gggp.process(cat, catp)

        print('jackknife:')
        cov = gggp.estimate_cov('jackknife', func=f)
        print(np.diagonal(cov).real)
        print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_ggg))))
        np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_ggg), atol=0.7*tol_factor)

        print('sample:')
        cov = gggp.estimate_cov('sample', func=f)
        print(np.diagonal(cov).real)
        print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_ggg))))
        np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_ggg), atol=0.7*tol_factor)

        print('marked:')
        cov = gggp.estimate_cov('marked_bootstrap', func=f)
        print(np.diagonal(cov).real)
        print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_ggg))))
        np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_ggg), atol=0.7*tol_factor)

        print('bootstrap:')
        cov = gggp.estimate_cov('bootstrap', func=f)
        print(np.diagonal(cov).real)
        print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_ggg))))
        np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_ggg), atol=0.8*tol_factor)

        # Patch on 1,3
        print('with patches on 1,3:')
        gggp.process(catp, cat, catp)

        print('jackknife:')
        cov = gggp.estimate_cov('jackknife', func=f)
        print(np.diagonal(cov).real)
        print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_ggg))))
        np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_ggg), atol=0.7*tol_factor)

        print('sample:')
        cov = gggp.estimate_cov('sample', func=f)
        print(np.diagonal(cov).real)
        print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_ggg))))
        np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_ggg), atol=0.7*tol_factor)

        print('marked:')
        cov = gggp.estimate_cov('marked_bootstrap', func=f)
        print(np.diagonal(cov).real)
        print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_ggg))))
        np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_ggg), atol=0.7*tol_factor)

        print('bootstrap:')
        cov = gggp.estimate_cov('bootstrap', func=f)
        print(np.diagonal(cov).real)
        print('max log(ratio) = ',np.max(np.abs(np.log(np.diagonal(cov))-np.log(var_ggg))))
        np.testing.assert_allclose(np.log(np.diagonal(cov)), np.log(var_ggg), atol=0.8*tol_factor)

    # Finally a set (with all patches) using the GGGCrossCorrelation class.
    gggc = treecorr.GGGCrossCorrelation(nbins=1, min_sep=20., max_sep=40.,
                                        min_u=0.6, max_u=1.0, nubins=1,
                                        min_v=0.0, max_v=0.6, nvbins=1, rng=rng)
    print('CrossCorrelation:')
    gggc.process(catp, catp, catp)
    for g in gggc._all:
        print(g.ntri.ravel())
        print(g.gam0.ravel())
        print(g.vargam0.ravel())

        np.testing.assert_allclose(g.ntri, ggg.ntri, rtol=0.05 * tol_factor)
        np.testing.assert_allclose(g.gam0, ggg.gam0, rtol=0.1 * tol_factor, atol=1e-3 * tol_factor)
        np.testing.assert_allclose(g.vargam0, ggg.vargam0, rtol=0.05 * tol_factor)
        np.testing.assert_allclose(g.gam1, ggg.gam1, rtol=0.1 * tol_factor, atol=1e-3 * tol_factor)
        np.testing.assert_allclose(g.vargam1, ggg.vargam1, rtol=0.05 * tol_factor)
        np.testing.assert_allclose(g.gam2, ggg.gam2, rtol=0.1 * tol_factor, atol=1e-3 * tol_factor)
        np.testing.assert_allclose(g.vargam2, ggg.vargam2, rtol=0.05 * tol_factor)
        np.testing.assert_allclose(g.gam3, ggg.gam3, rtol=0.1 * tol_factor, atol=1e-3 * tol_factor)
        np.testing.assert_allclose(g.vargam3, ggg.vargam3, rtol=0.05 * tol_factor)

    fc = lambda gggc: np.concatenate([
            [np.mean(g.gam0), np.mean(g.gam1), np.mean(g.gam2), np.mean(g.gam3)]
            for g in gggc._all])

    print('jackknife:')
    cov = gggc.estimate_cov('jackknife', func=fc)
    print(np.diagonal(cov).real)
    for i in range(6):
        v = np.diagonal(cov)[i*4:(i+1)*4]
        print('max log(ratio) = ',np.max(np.abs(np.log(v)-np.log(var_ggg))))
        np.testing.assert_allclose(np.log(v), np.log(var_ggg), atol=0.7*tol_factor)

    print('sample:')
    cov = gggc.estimate_cov('sample', func=fc)
    print(np.diagonal(cov).real)
    for i in range(6):
        v = np.diagonal(cov)[i*4:(i+1)*4]
        print('max log(ratio) = ',np.max(np.abs(np.log(v)-np.log(var_ggg))))
        np.testing.assert_allclose(np.log(v), np.log(var_ggg), atol=0.8*tol_factor)

    print('marked:')
    cov = gggc.estimate_cov('marked_bootstrap', func=fc)
    print(np.diagonal(cov).real)
    for i in range(6):
        v = np.diagonal(cov)[i*4:(i+1)*4]
        print('max log(ratio) = ',np.max(np.abs(np.log(v)-np.log(var_ggg))))
        np.testing.assert_allclose(np.log(v), np.log(var_ggg), atol=0.9*tol_factor)

    print('bootstrap:')
    cov = gggc.estimate_cov('bootstrap', func=fc)
    print(np.diagonal(cov).real)
    for i in range(6):
        v = np.diagonal(cov)[i*4:(i+1)*4]
        print('max log(ratio) = ',np.max(np.abs(np.log(v)-np.log(var_ggg))))
        np.testing.assert_allclose(np.log(v), np.log(var_ggg), atol=0.9*tol_factor)


@timer
def test_brute_jk():
    # With bin_slop = 0, the jackknife calculation from patches should match a
    # brute force calcaulation where we literally remove one patch at a time to make
    # the vectors.
    if __name__ == '__main__':
        nside = 100
        nhalo = 100
        nsource = 500
        npatch = 16
        rand_factor = 5
    else:
        nside = 100
        nhalo = 100
        nsource = 300
        npatch = 8
        rand_factor = 5

    rng = np.random.RandomState(8675309)
    x, y, g1, g2, k = generate_shear_field(nside, nhalo)
    # randomize positions slightly, since with grid, can get v=0 exactly, which is ambiguous
    # as to +- sign for v.  So complicates verification of equal results.
    x += rng.normal(0,0.01,len(x))
    y += rng.normal(0,0.01,len(y))

    indx = rng.choice(range(len(x)),nsource,replace=False)
    source_cat_nopatch = treecorr.Catalog(x=x[indx], y=y[indx],
                                          g1=g1[indx], g2=g2[indx], k=k[indx])
    source_cat = treecorr.Catalog(x=x[indx], y=y[indx],
                                  g1=g1[indx], g2=g2[indx], k=k[indx],
                                  npatch=npatch)
    print('source_cat patches = ',np.unique(source_cat.patch))
    print('len = ',source_cat.nobj, source_cat.ntot)
    assert source_cat.nobj == nsource

    # Start with KKK, since relatively simple.
    kkk1 = treecorr.KKKCorrelation(nbins=3, min_sep=30., max_sep=100., brute=True,
                                   min_u=0.8, max_u=1.0, nubins=1,
                                   min_v=0., max_v=0.2, nvbins=1)
    kkk1.process(source_cat_nopatch)

    kkk = treecorr.KKKCorrelation(nbins=3, min_sep=30., max_sep=100., brute=True,
                                  min_u=0.8, max_u=1.0, nubins=1,
                                  min_v=0., max_v=0.2, nvbins=1,
                                  var_method='jackknife')
    kkk.process(source_cat)
    np.testing.assert_allclose(kkk.zeta, kkk1.zeta)

    kkk_zeta_list = []
    for i in range(npatch):
        source_cat1 = treecorr.Catalog(x=source_cat.x[source_cat.patch != i],
                                       y=source_cat.y[source_cat.patch != i],
                                       k=source_cat.k[source_cat.patch != i],
                                       g1=source_cat.g1[source_cat.patch != i],
                                       g2=source_cat.g2[source_cat.patch != i])
        kkk1 = treecorr.KKKCorrelation(nbins=3, min_sep=30., max_sep=100., brute=True,
                                       min_u=0.8, max_u=1.0, nubins=1,
                                       min_v=0., max_v=0.2, nvbins=1)
        kkk1.process(source_cat1)
        print('zeta = ',kkk1.zeta.ravel())
        kkk_zeta_list.append(kkk1.zeta.ravel())

    kkk_zeta_list = np.array(kkk_zeta_list)
    cov = np.cov(kkk_zeta_list.T, bias=True) * (len(kkk_zeta_list)-1)
    varzeta = np.diagonal(np.cov(kkk_zeta_list.T, bias=True)) * (len(kkk_zeta_list)-1)
    print('KKK: treecorr jackknife varzeta = ',kkk.varzeta.ravel())
    print('KKK: direct jackknife varzeta = ',varzeta)
    np.testing.assert_allclose(kkk.varzeta.ravel(), varzeta)

    # Now GGG
    ggg1 = treecorr.GGGCorrelation(nbins=3, min_sep=30., max_sep=100., brute=True,
                                   min_u=0.8, max_u=1.0, nubins=1,
                                   min_v=0., max_v=0.2, nvbins=1)
    ggg1.process(source_cat_nopatch)

    ggg = treecorr.GGGCorrelation(nbins=3, min_sep=30., max_sep=100., brute=True,
                                  min_u=0.8, max_u=1.0, nubins=1,
                                  min_v=0., max_v=0.2, nvbins=1,
                                  var_method='jackknife')
    ggg.process(source_cat)
    np.testing.assert_allclose(ggg.gam0, ggg1.gam0)
    np.testing.assert_allclose(ggg.gam1, ggg1.gam1)
    np.testing.assert_allclose(ggg.gam2, ggg1.gam2)
    np.testing.assert_allclose(ggg.gam3, ggg1.gam3)

    ggg_gam0_list = []
    ggg_gam1_list = []
    ggg_gam2_list = []
    ggg_gam3_list = []
    ggg_map3_list = []
    for i in range(npatch):
        source_cat1 = treecorr.Catalog(x=source_cat.x[source_cat.patch != i],
                                       y=source_cat.y[source_cat.patch != i],
                                       k=source_cat.k[source_cat.patch != i],
                                       g1=source_cat.g1[source_cat.patch != i],
                                       g2=source_cat.g2[source_cat.patch != i])
        ggg1 = treecorr.GGGCorrelation(nbins=3, min_sep=30., max_sep=100., brute=True,
                                       min_u=0.8, max_u=1.0, nubins=1,
                                       min_v=0., max_v=0.2, nvbins=1)
        ggg1.process(source_cat1)
        ggg_gam0_list.append(ggg1.gam0.ravel())
        ggg_gam1_list.append(ggg1.gam1.ravel())
        ggg_gam2_list.append(ggg1.gam2.ravel())
        ggg_gam3_list.append(ggg1.gam3.ravel())
        ggg_map3_list.append(ggg1.calculateMap3()[0])

    ggg_gam0_list = np.array(ggg_gam0_list)
    vargam0 = np.diagonal(np.cov(ggg_gam0_list.T, bias=True)) * (len(ggg_gam0_list)-1)
    print('GG: treecorr jackknife vargam0 = ',ggg.vargam0.ravel())
    print('GG: direct jackknife vargam0 = ',vargam0)
    np.testing.assert_allclose(ggg.vargam0.ravel(), vargam0)
    ggg_gam1_list = np.array(ggg_gam1_list)
    vargam1 = np.diagonal(np.cov(ggg_gam1_list.T, bias=True)) * (len(ggg_gam1_list)-1)
    print('GG: treecorr jackknife vargam1 = ',ggg.vargam1.ravel())
    print('GG: direct jackknife vargam1 = ',vargam1)
    np.testing.assert_allclose(ggg.vargam1.ravel(), vargam1)
    ggg_gam2_list = np.array(ggg_gam2_list)
    vargam2 = np.diagonal(np.cov(ggg_gam2_list.T, bias=True)) * (len(ggg_gam2_list)-1)
    print('GG: treecorr jackknife vargam2 = ',ggg.vargam2.ravel())
    print('GG: direct jackknife vargam2 = ',vargam2)
    np.testing.assert_allclose(ggg.vargam2.ravel(), vargam2)
    ggg_gam3_list = np.array(ggg_gam3_list)
    vargam3 = np.diagonal(np.cov(ggg_gam3_list.T, bias=True)) * (len(ggg_gam3_list)-1)
    print('GG: treecorr jackknife vargam3 = ',ggg.vargam3.ravel())
    print('GG: direct jackknife vargam3 = ',vargam3)
    np.testing.assert_allclose(ggg.vargam3.ravel(), vargam3)

    ggg_map3_list = np.array(ggg_map3_list)
    varmap3 = np.diagonal(np.cov(ggg_map3_list.T, bias=True)) * (len(ggg_map3_list)-1)
    covmap3 = treecorr.estimate_multi_cov([ggg], 'jackknife',
                                          lambda corrs: corrs[0].calculateMap3()[0])
    print('GG: treecorr jackknife varmap3 = ',np.diagonal(covmap3))
    print('GG: direct jackknife varmap3 = ',varmap3)
    np.testing.assert_allclose(np.diagonal(covmap3), varmap3)

    return
    # Finally, test NN, which is complicated, since several different combinations of randoms.
    # 1. (DD-RR)/RR
    # 2. (DD-2DR+RR)/RR
    # 3. (DD-2RD+RR)/RR
    # 4. (DD-DR-RD+RR)/RR

    rand_source_cat = treecorr.Catalog(x=rng.uniform(0,1000,nsource*rand_factor),
                                       y=rng.uniform(0,1000,nsource*rand_factor),
                                       patch_centers=source_cat.patch_centers)
    print('rand_source_cat patches = ',np.unique(rand_source_cat.patch))
    print('len = ',rand_source_cat.nobj, rand_source_cat.ntot)

    dd = treecorr.NNCorrelation(bin_size=0.3, min_sep=10., max_sep=30., bin_slop=0,
                                var_method='jackknife')
    dd.process(lens_cat, source_cat)
    rr = treecorr.NNCorrelation(bin_size=0.3, min_sep=10., max_sep=30., bin_slop=0,
                                var_method='jackknife')
    rr.process(rand_lens_cat, rand_source_cat)
    rd = treecorr.NNCorrelation(bin_size=0.3, min_sep=10., max_sep=30., bin_slop=0,
                                var_method='jackknife')
    rd.process(rand_lens_cat, source_cat)
    dr = treecorr.NNCorrelation(bin_size=0.3, min_sep=10., max_sep=30., bin_slop=0,
                                var_method='jackknife')
    dr.process(lens_cat, rand_source_cat)

    # Now do this using brute force calculation.
    xi1_list = []
    xi2_list = []
    xi3_list = []
    xi4_list = []
    for i in range(npatch):
        lens_cat1 = treecorr.Catalog(x=lens_cat.x[lens_cat.patch != i],
                                     y=lens_cat.y[lens_cat.patch != i])
        source_cat1 = treecorr.Catalog(x=source_cat.x[source_cat.patch != i],
                                       y=source_cat.y[source_cat.patch != i])
        rand_lens_cat1 = treecorr.Catalog(x=rand_lens_cat.x[rand_lens_cat.patch != i],
                                          y=rand_lens_cat.y[rand_lens_cat.patch != i])
        rand_source_cat1 = treecorr.Catalog(x=rand_source_cat.x[rand_source_cat.patch != i],
                                            y=rand_source_cat.y[rand_source_cat.patch != i])
        dd1 = treecorr.NNCorrelation(bin_size=0.3, min_sep=10., max_sep=30., bin_slop=0)
        dd1.process(lens_cat1, source_cat1)
        rr1 = treecorr.NNCorrelation(bin_size=0.3, min_sep=10., max_sep=30., bin_slop=0)
        rr1.process(rand_lens_cat1, rand_source_cat1)
        rd1 = treecorr.NNCorrelation(bin_size=0.3, min_sep=10., max_sep=30., bin_slop=0)
        rd1.process(rand_lens_cat1, source_cat1)
        dr1 = treecorr.NNCorrelation(bin_size=0.3, min_sep=10., max_sep=30., bin_slop=0)
        dr1.process(lens_cat1, rand_source_cat1)
        xi1_list.append(dd1.calculateXi(rr1)[0])
        xi2_list.append(dd1.calculateXi(rr1,dr=dr1)[0])
        xi3_list.append(dd1.calculateXi(rr1,rd=rd1)[0])
        xi4_list.append(dd1.calculateXi(rr1,dr=dr1,rd=rd1)[0])

    print('(DD-RR)/RR')
    xi1_list = np.array(xi1_list)
    xi1, varxi1 = dd.calculateXi(rr)
    varxi = np.diagonal(np.cov(xi1_list.T, bias=True)) * (len(xi1_list)-1)
    print('treecorr jackknife varxi = ',varxi1)
    print('direct jackknife varxi = ',varxi)
    np.testing.assert_allclose(dd.varxi, varxi)

    print('(DD-2DR+RR)/RR')
    xi2_list = np.array(xi2_list)
    xi2, varxi2 = dd.calculateXi(rr, dr=dr)
    varxi = np.diagonal(np.cov(xi2_list.T, bias=True)) * (len(xi2_list)-1)
    print('treecorr jackknife varxi = ',varxi2)
    print('direct jackknife varxi = ',varxi)
    np.testing.assert_allclose(dd.varxi, varxi)

    print('(DD-2RD+RR)/RR')
    xi3_list = np.array(xi3_list)
    xi3, varxi3 = dd.calculateXi(rr, rd=rd)
    varxi = np.diagonal(np.cov(xi3_list.T, bias=True)) * (len(xi3_list)-1)
    print('treecorr jackknife varxi = ',varxi3)
    print('direct jackknife varxi = ',varxi)
    np.testing.assert_allclose(dd.varxi, varxi)

    print('(DD-DR-RD+RR)/RR')
    xi4_list = np.array(xi4_list)
    xi4, varxi4 = dd.calculateXi(rr, rd=rd, dr=dr)
    varxi = np.diagonal(np.cov(xi4_list.T, bias=True)) * (len(xi4_list)-1)
    print('treecorr jackknife varxi = ',varxi4)
    print('direct jackknife varxi = ',varxi)
    np.testing.assert_allclose(dd.varxi, varxi)

@timer
def test_finalize_false():

    nside = 100
    nsource = 80
    nhalo = 100
    npatch = 16

    # Make three independent data sets
    rng = np.random.RandomState(8675309)
    x_1, y_1, g1_1, g2_1, k_1 = generate_shear_field(nside, nhalo)
    indx = rng.choice(range(len(x_1)),nsource,replace=False)
    x_1 = x_1[indx]
    y_1 = y_1[indx]
    g1_1 = g1_1[indx]
    g2_1 = g2_1[indx]
    k_1 = k_1[indx]
    x_1 += rng.normal(0,0.01,nsource)
    y_1 += rng.normal(0,0.01,nsource)
    x_2, y_2, g1_2, g2_2, k_2 = generate_shear_field(nside, nhalo)
    indx = rng.choice(range(len(x_2)),nsource,replace=False)
    x_2 = x_2[indx]
    y_2 = y_2[indx]
    g1_2 = g1_2[indx]
    g2_2 = g2_2[indx]
    k_2 = k_2[indx]
    x_2 += rng.normal(0,0.01,nsource)
    y_2 += rng.normal(0,0.01,nsource)
    x_3, y_3, g1_3, g2_3, k_3 = generate_shear_field(nside, nhalo)
    indx = rng.choice(range(len(x_3)),nsource,replace=False)
    x_3 = x_3[indx]
    y_3 = y_3[indx]
    g1_3 = g1_3[indx]
    g2_3 = g2_3[indx]
    k_3 = k_3[indx]
    x_3 += rng.normal(0,0.01,nsource)
    y_3 += rng.normal(0,0.01,nsource)

    # Make a single catalog with all three together
    cat = treecorr.Catalog(x=np.concatenate([x_1, x_2, x_3]),
                           y=np.concatenate([y_1, y_2, y_3]),
                           g1=np.concatenate([g1_1, g1_2, g1_3]),
                           g2=np.concatenate([g2_1, g2_2, g2_3]),
                           k=np.concatenate([k_1, k_2, k_3]),
                           npatch=npatch)

    # Now the three separately, using the same patch centers
    cat1 = treecorr.Catalog(x=x_1, y=y_1, g1=g1_1, g2=g2_1, k=k_1, patch_centers=cat.patch_centers)
    cat2 = treecorr.Catalog(x=x_2, y=y_2, g1=g1_2, g2=g2_2, k=k_2, patch_centers=cat.patch_centers)
    cat3 = treecorr.Catalog(x=x_3, y=y_3, g1=g1_3, g2=g2_3, k=k_3, patch_centers=cat.patch_centers)

    np.testing.assert_array_equal(cat1.patch, cat.patch[0:nsource])
    np.testing.assert_array_equal(cat2.patch, cat.patch[nsource:2*nsource])
    np.testing.assert_array_equal(cat3.patch, cat.patch[2*nsource:3*nsource])

    # KKK auto
    kkk1 = treecorr.KKKCorrelation(nbins=3, min_sep=30., max_sep=100., brute=True,
                                   min_u=0.8, max_u=1.0, nubins=1,
                                   min_v=0., max_v=0.2, nvbins=1)
    kkk1.process(cat)

    kkk2 = treecorr.KKKCorrelation(nbins=3, min_sep=30., max_sep=100., brute=True,
                                   min_u=0.8, max_u=1.0, nubins=1,
                                   min_v=0., max_v=0.2, nvbins=1)
    kkk2.process(cat1, initialize=True, finalize=False)
    kkk2.process(cat2, initialize=False, finalize=False)
    kkk2.process(cat3, initialize=False, finalize=False)
    kkk2.process(cat1, cat2, initialize=False, finalize=False)
    kkk2.process(cat1, cat3, initialize=False, finalize=False)
    kkk2.process(cat2, cat1, initialize=False, finalize=False)
    kkk2.process(cat2, cat3, initialize=False, finalize=False)
    kkk2.process(cat3, cat1, initialize=False, finalize=False)
    kkk2.process(cat3, cat2, initialize=False, finalize=False)
    kkk2.process(cat1, cat2, cat3, initialize=False, finalize=True)

    np.testing.assert_allclose(kkk1.ntri, kkk2.ntri)
    np.testing.assert_allclose(kkk1.weight, kkk2.weight)
    np.testing.assert_allclose(kkk1.meand1, kkk2.meand1)
    np.testing.assert_allclose(kkk1.meand2, kkk2.meand2)
    np.testing.assert_allclose(kkk1.meand3, kkk2.meand3)
    np.testing.assert_allclose(kkk1.zeta, kkk2.zeta)

    # KKK cross12
    cat23 = treecorr.Catalog(x=np.concatenate([x_2, x_3]),
                             y=np.concatenate([y_2, y_3]),
                             g1=np.concatenate([g1_2, g1_3]),
                             g2=np.concatenate([g2_2, g2_3]),
                             k=np.concatenate([k_2, k_3]),
                             patch_centers=cat.patch_centers)
    np.testing.assert_array_equal(cat23.patch, cat.patch[nsource:3*nsource])

    kkk1.process(cat1, cat23)
    kkk2.process(cat1, cat2, initialize=True, finalize=False)
    kkk2.process(cat1, cat3, initialize=False, finalize=False)
    kkk2.process(cat1, cat2, cat3, initialize=False, finalize=True)

    np.testing.assert_allclose(kkk1.ntri, kkk2.ntri)
    np.testing.assert_allclose(kkk1.weight, kkk2.weight)
    np.testing.assert_allclose(kkk1.meand1, kkk2.meand1)
    np.testing.assert_allclose(kkk1.meand2, kkk2.meand2)
    np.testing.assert_allclose(kkk1.meand3, kkk2.meand3)
    np.testing.assert_allclose(kkk1.zeta, kkk2.zeta)

    # KKKCross cross12
    kkkc1 = treecorr.KKKCrossCorrelation(nbins=3, min_sep=30., max_sep=100., brute=True,
                                         min_u=0.8, max_u=1.0, nubins=1,
                                         min_v=0., max_v=0.2, nvbins=1)
    kkkc1.process(cat1, cat23)

    kkkc2 = treecorr.KKKCrossCorrelation(nbins=3, min_sep=30., max_sep=100., brute=True,
                                         min_u=0.8, max_u=1.0, nubins=1,
                                         min_v=0., max_v=0.2, nvbins=1)
    kkkc2.process(cat1, cat2, initialize=True, finalize=False)
    kkkc2.process(cat1, cat3, initialize=False, finalize=False)
    kkkc2.process(cat1, cat2, cat3, initialize=False, finalize=True)

    for perm in ['k1k2k3', 'k1k3k2', 'k2k1k3', 'k2k3k1', 'k3k1k2', 'k3k2k1']:
        kkk1 = getattr(kkkc1, perm)
        kkk2 = getattr(kkkc2, perm)
        np.testing.assert_allclose(kkk1.ntri, kkk2.ntri)
        np.testing.assert_allclose(kkk1.weight, kkk2.weight)
        np.testing.assert_allclose(kkk1.meand1, kkk2.meand1)
        np.testing.assert_allclose(kkk1.meand2, kkk2.meand2)
        np.testing.assert_allclose(kkk1.meand3, kkk2.meand3)
        np.testing.assert_allclose(kkk1.zeta, kkk2.zeta)

    # KKK cross
    kkk1.process(cat, cat2, cat3)
    kkk2.process(cat1, cat2, cat3, initialize=True, finalize=False)
    kkk2.process(cat2, cat2, cat3, initialize=False, finalize=False)
    kkk2.process(cat3, cat2, cat3, initialize=False, finalize=True)

    np.testing.assert_allclose(kkk1.ntri, kkk2.ntri)
    np.testing.assert_allclose(kkk1.weight, kkk2.weight)
    np.testing.assert_allclose(kkk1.meand1, kkk2.meand1)
    np.testing.assert_allclose(kkk1.meand2, kkk2.meand2)
    np.testing.assert_allclose(kkk1.meand3, kkk2.meand3)
    np.testing.assert_allclose(kkk1.zeta, kkk2.zeta)

    # KKKCross cross
    kkkc1.process(cat, cat2, cat3)
    kkkc2.process(cat1, cat2, cat3, initialize=True, finalize=False)
    kkkc2.process(cat2, cat2, cat3, initialize=False, finalize=False)
    kkkc2.process(cat3, cat2, cat3, initialize=False, finalize=True)

    for perm in ['k1k2k3', 'k1k3k2', 'k2k1k3', 'k2k3k1', 'k3k1k2', 'k3k2k1']:
        kkk1 = getattr(kkkc1, perm)
        kkk2 = getattr(kkkc2, perm)
        np.testing.assert_allclose(kkk1.ntri, kkk2.ntri)
        np.testing.assert_allclose(kkk1.weight, kkk2.weight)
        np.testing.assert_allclose(kkk1.meand1, kkk2.meand1)
        np.testing.assert_allclose(kkk1.meand2, kkk2.meand2)
        np.testing.assert_allclose(kkk1.meand3, kkk2.meand3)
        np.testing.assert_allclose(kkk1.zeta, kkk2.zeta)

    # GGG auto
    ggg1 = treecorr.GGGCorrelation(nbins=3, min_sep=30., max_sep=100., brute=True,
                                   min_u=0.8, max_u=1.0, nubins=1,
                                   min_v=0., max_v=0.2, nvbins=1)
    ggg1.process(cat)

    ggg2 = treecorr.GGGCorrelation(nbins=3, min_sep=30., max_sep=100., brute=True,
                                   min_u=0.8, max_u=1.0, nubins=1,
                                   min_v=0., max_v=0.2, nvbins=1)
    ggg2.process(cat1, initialize=True, finalize=False)
    ggg2.process(cat2, initialize=False, finalize=False)
    ggg2.process(cat3, initialize=False, finalize=False)
    ggg2.process(cat1, cat2, initialize=False, finalize=False)
    ggg2.process(cat1, cat3, initialize=False, finalize=False)
    ggg2.process(cat2, cat1, initialize=False, finalize=False)
    ggg2.process(cat2, cat3, initialize=False, finalize=False)
    ggg2.process(cat3, cat1, initialize=False, finalize=False)
    ggg2.process(cat3, cat2, initialize=False, finalize=False)
    ggg2.process(cat1, cat2, cat3, initialize=False, finalize=True)

    np.testing.assert_allclose(ggg1.ntri, ggg2.ntri)
    np.testing.assert_allclose(ggg1.weight, ggg2.weight)
    np.testing.assert_allclose(ggg1.meand1, ggg2.meand1)
    np.testing.assert_allclose(ggg1.meand2, ggg2.meand2)
    np.testing.assert_allclose(ggg1.meand3, ggg2.meand3)
    np.testing.assert_allclose(ggg1.gam0, ggg2.gam0)
    np.testing.assert_allclose(ggg1.gam1, ggg2.gam1)
    np.testing.assert_allclose(ggg1.gam2, ggg2.gam2)
    np.testing.assert_allclose(ggg1.gam3, ggg2.gam3)

    # GGG cross12
    cat23 = treecorr.Catalog(x=np.concatenate([x_2, x_3]),
                             y=np.concatenate([y_2, y_3]),
                             g1=np.concatenate([g1_2, g1_3]),
                             g2=np.concatenate([g2_2, g2_3]),
                             k=np.concatenate([k_2, k_3]),
                             patch_centers=cat.patch_centers)
    np.testing.assert_array_equal(cat23.patch, cat.patch[nsource:3*nsource])

    ggg1.process(cat1, cat23)
    ggg2.process(cat1, cat2, initialize=True, finalize=False)
    ggg2.process(cat1, cat3, initialize=False, finalize=False)
    ggg2.process(cat1, cat2, cat3, initialize=False, finalize=True)

    np.testing.assert_allclose(ggg1.ntri, ggg2.ntri)
    np.testing.assert_allclose(ggg1.weight, ggg2.weight)
    np.testing.assert_allclose(ggg1.meand1, ggg2.meand1)
    np.testing.assert_allclose(ggg1.meand2, ggg2.meand2)
    np.testing.assert_allclose(ggg1.meand3, ggg2.meand3)
    np.testing.assert_allclose(ggg1.gam0, ggg2.gam0)
    np.testing.assert_allclose(ggg1.gam1, ggg2.gam1)
    np.testing.assert_allclose(ggg1.gam2, ggg2.gam2)
    np.testing.assert_allclose(ggg1.gam3, ggg2.gam3)

    # GGGCross cross12
    gggc1 = treecorr.GGGCrossCorrelation(nbins=3, min_sep=30., max_sep=100., brute=True,
                                         min_u=0.8, max_u=1.0, nubins=1,
                                         min_v=0., max_v=0.2, nvbins=1)
    gggc1.process(cat1, cat23)

    gggc2 = treecorr.GGGCrossCorrelation(nbins=3, min_sep=30., max_sep=100., brute=True,
                                         min_u=0.8, max_u=1.0, nubins=1,
                                         min_v=0., max_v=0.2, nvbins=1)
    gggc2.process(cat1, cat2, initialize=True, finalize=False)
    gggc2.process(cat1, cat3, initialize=False, finalize=False)
    gggc2.process(cat1, cat2, cat3, initialize=False, finalize=True)

    for perm in ['g1g2g3', 'g1g3g2', 'g2g1g3', 'g2g3g1', 'g3g1g2', 'g3g2g1']:
        ggg1 = getattr(gggc1, perm)
        ggg2 = getattr(gggc2, perm)
        np.testing.assert_allclose(ggg1.ntri, ggg2.ntri)
        np.testing.assert_allclose(ggg1.weight, ggg2.weight)
        np.testing.assert_allclose(ggg1.meand1, ggg2.meand1)
        np.testing.assert_allclose(ggg1.meand2, ggg2.meand2)
        np.testing.assert_allclose(ggg1.meand3, ggg2.meand3)
        np.testing.assert_allclose(ggg1.gam0, ggg2.gam0)
        np.testing.assert_allclose(ggg1.gam1, ggg2.gam1)
        np.testing.assert_allclose(ggg1.gam2, ggg2.gam2)
        np.testing.assert_allclose(ggg1.gam3, ggg2.gam3)

    # GGG cross
    ggg1.process(cat, cat2, cat3)
    ggg2.process(cat1, cat2, cat3, initialize=True, finalize=False)
    ggg2.process(cat2, cat2, cat3, initialize=False, finalize=False)
    ggg2.process(cat3, cat2, cat3, initialize=False, finalize=True)

    np.testing.assert_allclose(ggg1.ntri, ggg2.ntri)
    np.testing.assert_allclose(ggg1.weight, ggg2.weight)
    np.testing.assert_allclose(ggg1.meand1, ggg2.meand1)
    np.testing.assert_allclose(ggg1.meand2, ggg2.meand2)
    np.testing.assert_allclose(ggg1.meand3, ggg2.meand3)
    np.testing.assert_allclose(ggg1.gam0, ggg2.gam0)
    np.testing.assert_allclose(ggg1.gam1, ggg2.gam1)
    np.testing.assert_allclose(ggg1.gam2, ggg2.gam2)
    np.testing.assert_allclose(ggg1.gam3, ggg2.gam3)

    # GGGCross cross
    gggc1.process(cat, cat2, cat3)
    gggc2.process(cat1, cat2, cat3, initialize=True, finalize=False)
    gggc2.process(cat2, cat2, cat3, initialize=False, finalize=False)
    gggc2.process(cat3, cat2, cat3, initialize=False, finalize=True)

    for perm in ['g1g2g3', 'g1g3g2', 'g2g1g3', 'g2g3g1', 'g3g1g2', 'g3g2g1']:
        ggg1 = getattr(gggc1, perm)
        ggg2 = getattr(gggc2, perm)
        np.testing.assert_allclose(ggg1.ntri, ggg2.ntri)
        np.testing.assert_allclose(ggg1.weight, ggg2.weight)
        np.testing.assert_allclose(ggg1.meand1, ggg2.meand1)
        np.testing.assert_allclose(ggg1.meand2, ggg2.meand2)
        np.testing.assert_allclose(ggg1.meand3, ggg2.meand3)
        np.testing.assert_allclose(ggg1.gam0, ggg2.gam0)
        np.testing.assert_allclose(ggg1.gam1, ggg2.gam1)
        np.testing.assert_allclose(ggg1.gam2, ggg2.gam2)
        np.testing.assert_allclose(ggg1.gam3, ggg2.gam3)

@timer
def test_lowmem():
    # Test using patches to keep the memory usage lower.

    nside = 100
    if __name__ == '__main__':
        nsource = 10000
        nhalo = 100
        npatch = 4
        himem = 7.e5
        lomem = 8.e4
    else:
        nsource = 1000
        nhalo = 100
        npatch = 4
        himem = 1.3e5
        lomem = 8.e4

    rng = np.random.RandomState(8675309)
    x, y, g1, g2, k = generate_shear_field(nside, nhalo)
    indx = rng.choice(range(len(x)),nsource,replace=False)
    x = x[indx]
    y = y[indx]
    g1 = g1[indx]
    g2 = g2[indx]
    k = k[indx]
    x += rng.normal(0,0.01,nsource)
    y += rng.normal(0,0.01,nsource)

    file_name = os.path.join('output','test_lowmem_3pt.fits')
    orig_cat = treecorr.Catalog(x=x, y=y, g1=g1, g2=g2, k=k, npatch=npatch)
    patch_centers = orig_cat.patch_centers
    orig_cat.write(file_name)
    del orig_cat

    try:
        import guppy
        hp = guppy.hpy()
        hp.setrelheap()
    except Exception:
        hp = None

    full_cat = treecorr.Catalog(file_name,
                                x_col='x', y_col='y', g1_col='g1', g2_col='g2', k_col='k',
                                patch_centers=patch_centers)

    kkk = treecorr.KKKCorrelation(nbins=1, min_sep=280., max_sep=300.,
                                  min_u=0.95, max_u=1.0, nubins=1,
                                  min_v=0., max_v=0.05, nvbins=1)

    t0 = time.time()
    s0 = hp.heap().size if hp else 0
    kkk.process(full_cat)
    t1 = time.time()
    s1 = hp.heap().size if hp else 2*himem
    print('regular: ',s1, t1-t0, s1-s0)
    assert s1-s0 > himem  # This version uses a lot of memory.

    ntri1 = kkk.ntri
    zeta1 = kkk.zeta
    full_cat.unload()
    kkk.clear()

    # Remake with save_patch_dir.
    clear_save('test_lowmem_3pt_%03d.fits', npatch)
    save_cat = treecorr.Catalog(file_name,
                                x_col='x', y_col='y', g1_col='g1', g2_col='g2', k_col='k',
                                patch_centers=patch_centers, save_patch_dir='output')

    t0 = time.time()
    s0 = hp.heap().size if hp else 0
    kkk.process(save_cat, low_mem=True, finalize=False)
    t1 = time.time()
    s1 = hp.heap().size if hp else 0
    print('lomem 1: ',s1, t1-t0, s1-s0)
    assert s1-s0 < lomem  # This version uses a lot less memory
    ntri2 = kkk.ntri
    zeta2 = kkk.zeta
    print('ntri1 = ',ntri1)
    print('zeta1 = ',zeta1)
    np.testing.assert_array_equal(ntri2, ntri1)
    np.testing.assert_array_equal(zeta2, zeta1)

    # Check running as a cross-correlation
    save_cat.unload()
    t0 = time.time()
    s0 = hp.heap().size if hp else 0
    kkk.process(save_cat, save_cat, low_mem=True)
    t1 = time.time()
    s1 = hp.heap().size if hp else 0
    print('lomem 2: ',s1, t1-t0, s1-s0)
    assert s1-s0 < lomem
    ntri3 = kkk.ntri
    zeta3 = kkk.zeta
    np.testing.assert_array_equal(ntri3, ntri1)
    np.testing.assert_array_equal(zeta3, zeta1)

    # Check running as a cross-correlation
    save_cat.unload()
    t0 = time.time()
    s0 = hp.heap().size if hp else 0
    kkk.process(save_cat, save_cat, save_cat, low_mem=True)
    t1 = time.time()
    s1 = hp.heap().size if hp else 0
    print('lomem 3: ',s1, t1-t0, s1-s0)
    assert s1-s0 < lomem
    ntri4 = kkk.ntri
    zeta4 = kkk.zeta
    np.testing.assert_array_equal(ntri4, ntri1)
    np.testing.assert_array_equal(zeta4, zeta1)


if __name__ == '__main__':
    test_brute_jk()
    test_finalize_false()
    test_lowmem
