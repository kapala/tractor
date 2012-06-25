# Copyright 2011 David W. Hogg and Dustin Lang.  All rights reserved.

if __name__ == '__main__':
	import matplotlib
	matplotlib.use('Agg')
	import pylab as plt
	import matplotlib.cm as cm
import numpy as np
import scipy.spatial.distance as scp

# magic arrays, generated by running optimize_mixture_profiles.py:
# (note optimize_mixture_profiles.py now lives in Hogg's TheTractor github repo)
exp_amp = np.array([  2.34853813e-03,   3.07995260e-02,   2.23364214e-01,
		      1.17949102e+00,   4.33873750e+00,   5.99820770e+00])
exp_var = np.array([  1.20078965e-03,   8.84526493e-03,   3.91463084e-02,
		      1.39976817e-01,   4.60962500e-01,   1.50159566e+00])
exp_amp /= np.sum(exp_amp)

dev_amp = np.array([  4.26347652e-02,   2.40127183e-01,   6.85907632e-01,   1.51937350e+00,
		      2.83627243e+00,   4.46467501e+00,   5.72440830e+00,   5.60989349e+00])
dev_var = np.array([  2.23759216e-04,   1.00220099e-03,   4.18731126e-03,   1.69432589e-02,
		      6.84850479e-02,   2.87207080e-01,   1.33320254e+00,   8.40215071e+00])
dev_amp /= np.sum(dev_amp)

def get_exp_mixture():
	return MixtureOfGaussians(exp_amp, np.zeros((exp_amp.size, 2)), exp_var)

def get_dev_mixture():
	return MixtureOfGaussians(dev_amp, np.zeros((dev_amp.size, 2)), dev_var)

class MixtureOfGaussians():

	# symmetrize is an unnecessary step in principle, but in practice?
	def __init__(self, amp, mean, var):
		self.amp = np.array(amp).astype(float)
		self.mean = np.atleast_2d(np.array(mean)).astype(float)
		(self.K, self.D) = self.mean.shape
		self.set_var(var)
		self.symmetrize()
		#self.test()

	def __str__(self):
		result = "MixtureOfGaussians instance"
		result += " with %d components in %d dimensions:\n" % (self.K, self.D)
		result += " amp	 = %s\n" % self.amp.__str__()
		result += " mean = %s\n" % self.mean.__str__()
		result += " var	 = %s\n" % self.var.__str__()
		return result

	def set_var(self, var):
		if var.size == self.K:
			self.var = np.zeros((self.K, self.D, self.D))
			for d in range(self.D):
				self.var[:,d,d] = var
		else:
			# atleast_3d makes bizarre choices about which axes to expand...
			#self.var = np.atleast_3d(np.array(var))
			#print 'var', self.var.shape
			self.var = np.array(var).astype(float)
	def symmetrize(self):
		for i in range(self.D):
			for j in range(i):
				tmpij = 0.5 * (self.var[:,i,j] + self.var[:,j,i])
				self.var[:,i,j] = tmpij
				self.var[:,j,i] = tmpij

	# very harsh testing, and expensive
	def test(self):
		assert(self.amp.shape == (self.K, ))
		assert(self.mean.shape == (self.K, self.D))
		assert(self.var.shape == (self.K, self.D, self.D))
		for k in range(self.K):
			thisvar = self.var[k]
			assert(np.sum(thisvar.T - thisvar) == 0.)
			assert(np.linalg.det(thisvar) >= 0.)

	def copy(self):
		return MixtureOfGaussians(self.amp, self.mean, self.var)

	def normalize(self):
		self.amp /= np.sum(self.amp)

	def extend(self, other):
		assert(self.D == other.D)
		self.K = self.K + other.K
		self.amp = np.append(self.amp, other.amp)
		self.mean = np.reshape(np.append(self.mean, other.mean), (self.K, self.D))
		self.var = np.reshape(np.append(self.var, other.var), (self.K, self.D, self.D))
		self.test

	def apply_affine(self, shift, scale):
		'''
		shift: D-vector offset
		scale: DxD-matrix transformation
		'''
		assert(shift.shape == (self.D,))
		assert(scale.shape == (self.D, self.D))
		newmean = self.mean + shift
		newvar = self.var.copy()
		for k in range(self.K):
			newvar[k,:,:] = np.dot(scale.T, np.dot(self.var[k,:,:], scale))
		return MixtureOfGaussians(self.amp, newmean, newvar)

	# dstn: should this be called "correlate"?
	def convolve(self, other):
		assert(self.D == other.D)
		newK = self.K * other.K
		D = self.D
		newamp = np.zeros((newK))
		newmean = np.zeros((newK, D))
		newvar = np.zeros((newK, D, D))
		newk = 0
		for k in range(other.K):
			nextnewk = newk + self.K
			newamp[newk:nextnewk] = self.amp * other.amp[k]
			newmean[newk:nextnewk,:] = self.mean + other.mean[k]
			newvar[newk:nextnewk,:,:] = self.var + other.var[k]
			newk = nextnewk
		return MixtureOfGaussians(newamp, newmean, newvar)

	# ideally pos is a numpy array shape (N, self.D)
	# returns a numpy array shape (N)
	# may fail for self.D == 1
	# loopy
	def evaluate_3(self, pos):
		if pos.size == self.D:
			pos = np.reshape(pos, (1, self.D))
		(N, D) = pos.shape
		assert(self.D == D)
		twopitotheD = (2.*np.pi)**self.D
		result = np.zeros(N)
		for k in range(self.K):
			# pos is (N, D)
			# mean[k] is (D,)
			dpos = pos - self.mean[k]
			dsq = np.sum(dpos * np.dot(dpos, np.linalg.inv(self.var[k])), axis=1)
			I = (dsq < 700)
			result[I] += (self.amp[k] / np.sqrt(twopitotheD * np.linalg.det(self.var[k]))) * np.exp(-0.5 * dsq[I])
		return result

	def evaluate_1(self, pos):
		if pos.size == self.D:
			pos = np.reshape(pos, (1, self.D))
		(N, D) = pos.shape
		assert(self.D == D)
		twopitotheD = (2.*np.pi)**self.D
		result = np.zeros(N)
		for k in range(self.K):
			dsq = scp.cdist(pos, self.mean[np.newaxis, k], 'mahalanobis', VI=np.linalg.inv(self.var[k]))[:,0]**2
			I = (dsq < 700)
			result[I] += (self.amp[k] / np.sqrt(twopitotheD * np.linalg.det(self.var[k]))) * np.exp(-0.5 * dsq[I])
		return result

	def evaluate_2(self, pos):
		from mix import c_gauss_2d
		if pos.size == self.D:
			pos = np.reshape(pos, (1, self.D))
		(N, D) = pos.shape
		assert(self.D == D)
		result = np.zeros(N)
		rtn = c_gauss_2d(pos, self.amp, self.mean, self.var, result)
		if rtn == -1:
			raise RuntimeError('c_gauss_2d failed')
		x, y = meshgrid()
		return result

	def evaluate_grid_dstn(self, xlo, xhi, ylo, yhi):
		from mix import c_gauss_2d_grid
		assert(self.D == 2)
		NX = int(round(xhi - xlo - 1))
		NY = int(round(yhi - ylo - 1))
		result = np.zeros((NY, NX))
		rtn = c_gauss_2d_grid(xlo, 1., NX, ylo, 1., NY, self.amp, self.mean,
							  self.var, result)
		if rtn == -1:
			raise RuntimeError('c_gauss_2d_grid failed')
		return result

	def evaluate_grid_hogg(self, xlo, xhi, ylo, yhi):
		assert(self.D == 2)
		xy = np.array(np.meshgrid(range(xlo, xhi), range(ylo, yhi)))
		D, nx, ny = xy.shape
		xy = xy.reshape((D, nx * ny)).T
		result = self.evaluate_1(xy)
		return result.reshape((nx, ny))

	evaluate = evaluate_2
	#evaluate_grid = evaluate_grid_hogg
	evaluate_grid = evaluate_grid_dstn

# input: a mixture, a 2d array of x,y minimum values, and a 2d array of x,y maximum values
# output: a patch
def mixture_to_patch(mixture, posmin, posmax):
	return mixture.evaluate_grid(int(posmin[0]), int(posmax[0]),
								 int(posmin[1]), int(posmax[1]))
'''
	xl = np.arange(posmin[0], posmax[0], 1.)
	nx = xl.size
	yl = np.arange(posmin[1], posmax[1], 1.)
	ny = yl.size
	x, y = np.meshgrid(xl, yl)
	pos = np.transpose(np.array([np.ravel(x), np.ravel(y)]))
	return np.reshape(mixture.evaluate(pos), (ny, nx))
'''

def model_to_patch(model, scale, posmin, posmax):
	xl = np.arange(posmin[0], posmax[0]+1., 1.)
	nx = xl.size
	yl = np.arange(posmin[1], posmax[1]+1., 1.)
	ny = yl.size
	x, y = np.meshgrid(xl, yl)
	dist = np.sqrt(np.ravel(x)**2 + np.ravel(y)**2)
	if model == 'exp':
		return np.reshape(np.exp(-1. * (dist / scale)), (ny, nx))
	if model == 'dev':
		return np.reshape(np.exp(-1. * (dist / scale)**0.25), (ny, nx))
	else:
		return 0.

def functional_test_circular_mixtures():
	exp_mixture = MixtureOfGaussians(exp_amp, np.zeros((exp_amp.size, 2)), exp_var)
	dev_mixture = MixtureOfGaussians(dev_amp, np.zeros((dev_amp.size, 2)), dev_var)
	pos = np.random.uniform(-5.,5.,size=(24,2))
	exp_eva = exp_mixture.evaluate(pos)
	dev_eva = dev_mixture.evaluate(pos)
	(N, D) = pos.shape
	for n in range(N):
		print '(%+6.3f %+6.3f) exp: %+8.5f' % (pos[n,0], pos[n,1], exp_eva[n] - np.exp(-1. * np.sqrt(np.sum(pos[n] * pos[n]))))
		print '(%+6.3f %+6.3f) dev: %+8.5f' % (pos[n,0], pos[n,1], dev_eva[n] - np.exp(-1. * np.sqrt(np.sum(pos[n] * pos[n]))**0.25))

def functional_test_patch_maker(fn, psf=None):
	scale = 30.
	posmin = np.array([-3, -5]) * scale
	posmax = np.array([1, 1]) * scale
	exp_mixture = MixtureOfGaussians(exp_amp*scale*scale, np.zeros((exp_amp.size, 2)), exp_var*scale*scale)

	# Works! exp_mixture.apply_affine(np.array([10,-30]), np.eye(2))
	S = np.array([[1,0],[0,0.5]])
	print 'Det', np.linalg.det(S)
	S /= np.sqrt(np.linalg.det(S))
	print 'Det', np.linalg.det(S)
	r = np.deg2rad(30.)
	cr = np.cos(r)
	sr = np.sin(r)
	S = np.dot(S, np.array([[cr, sr],[-sr, cr]]))
	print 'Det', np.linalg.det(S)
	exp_mixture = exp_mixture.apply_affine(np.array([10,-30]), S)

	if psf is not None:
		exp_mixture = exp_mixture.convolve(psf)
	exp_mix_patch = mixture_to_patch(exp_mixture, posmin, posmax)
	exp_patch = model_to_patch('exp', scale, posmin, posmax)
	dev_mixture = MixtureOfGaussians(dev_amp*scale*scale, np.zeros((dev_amp.size, 2)), dev_var*scale*scale)
	if psf is not None:
		dev_mixture = dev_mixture.convolve(psf)
	dev_mix_patch = mixture_to_patch(dev_mixture, posmin, posmax)
	dev_patch = model_to_patch('dev', scale, posmin, posmax)
	cmap = cm.gray
	vmin = -0.5
	vmax = 1.0
	factor = 100.
	plt.clf()
	plt.subplot(231)
	plt.imshow(exp_mix_patch, interpolation='nearest', origin='lower', cmap=cmap, vmin=vmin, vmax=vmax)
	plt.colorbar()
	plt.subplot(232)
	plt.imshow(exp_patch, interpolation='nearest', origin='lower', cmap=cmap, vmin=vmin, vmax=vmax)
	plt.colorbar()
	plt.subplot(233)
	plt.imshow(exp_mix_patch - exp_patch, interpolation='nearest', origin='lower', cmap=cmap, vmin=-1./factor, vmax=1./factor)
	plt.colorbar()
	plt.subplot(234)
	plt.imshow(dev_mix_patch, interpolation='nearest', origin='lower', cmap=cmap, vmin=vmin, vmax=vmax)
	plt.colorbar()
	plt.subplot(235)
	plt.imshow(dev_patch, interpolation='nearest', origin='lower', cmap=cmap, vmin=vmin, vmax=vmax)
	plt.colorbar()
	plt.subplot(236)
	plt.imshow(dev_mix_patch - dev_patch, interpolation='nearest', origin='lower', cmap=cmap, vmin=-1./factor, vmax=1./factor)
	plt.colorbar()
	plt.savefig(fn)

if __name__ == '__main__':
	# functional_test_circular_mixtures()
	psfamp = np.array([0.7,0.2,0.1])
	psfmean = np.zeros((3,2))
	psfvar = np.zeros((3,2,2))
	psfvar[0,0,0] = 1.2**2
	psfvar[0,1,1] = psfvar[0,0,0]
	psfvar[1,0,0] = 2.4**2
	psfvar[1,1,1] = psfvar[1,0,0]
	psfvar[2,0,0] = 3.6**2
	psfvar[2,1,1] = psfvar[2,0,0]
	psf = MixtureOfGaussians(psfamp, psfmean, psfvar)
	functional_test_patch_maker('test_patch.png')
	functional_test_patch_maker('test_psf_patch.png', psf=psf)
