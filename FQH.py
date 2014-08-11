# Diagonalizing FQH in LLL on a torus. Both single layer & double layer

import itertools
import numpy as np
import scipy as sp
import scipy.sparse.linalg as lin
import pylab

def getBasis0(Ns, N):
# No momentum conservation
    states = [tuple(sorted(list(x))) for x in itertools.combinations(range(Ns), N)] 
    return states

def getBasis(Ns, N):
    sectors =  [ [] for i in range(Ns)]
    for config in itertools.combinations(range(Ns), N):
        k = sum(config)%Ns
        sectors[k].append(config)            
    return sectors

def getBasisDL(Ns, N):
# Ns is the number of orbitals in each layer. There are 2*Ns orbitals in total
# For each orbital there is a layer index, (j, 0) or (j, 1)
# (j, s) is indexed as 2j+s
# N is the total number of electrons
    sectors = [ [] for i in range(Ns)]
    for config in itertools.combinations(range(2*Ns), N):
        k = sum([n//2 for n in config])%Ns
        sectors[k].append(config)            
    return sectors
    
def addp(state, pos):
    state.insert(0, pos)
    state.sort()

def removep(state, pos):
    state.remove(pos)

def fermion_sign(i, j, state):
# 0 <= i, j < Ns
    sgn = 1
    if i < j:
        for n in state:
            if n >= i and n < j:
                sgn = -sgn
    else:
        for n in state:
            if n >= j and n < i:
                sgn = -sgn
        sgn = -sgn
    return sgn
            

def hopping(i, j, bstates, btab):
# c_i^\dag c_j, i != j
    mat = []
    for ind, state in enumerate(bstates):
        if (j in state) and (not (i in state)):
            sgn = fermion_sign(i, j, state)
            nstate = list(state)
            removep(nstate, j)
            addp(nstate, i)
            mat.append([sgn, btab[tuple(nstate)], ind])
    return mat
    
def pairhopping(i1, j1, i2, j2, bstates, btab):
# c_{i1}^\dag c_{j1} c_{i2}^\dag c_{j2}
    mat = []
    for ind, state in enumerate(bstates):
        nstate = list(state)
        if (j2 in nstate) and (not (i2 in nstate)):
            sgn = fermion_sign(i2, j2, state)
            removep(nstate, j2)
            addp(nstate, i2)
            if (j1 in nstate) and (not (i1 in nstate)):
                sgn *= fermion_sign(i1, j1, nstate)
                removep(nstate, j1)
                addp(nstate, i1)
                mat.append([sgn, btab[tuple(nstate)], ind])
    return mat
    

def V(k, m, a, b, Ns):
# a*b=2*pi*Ns
    cutoff = 50
    v = 0
    for nx in range(-cutoff, cutoff+1):
        for ny in range(1,cutoff+1):
            q = np.sqrt((2*np.pi*(Ns*nx+k)/a)**2+(2*np.pi*ny/b)**2)
            v += 2*(1/q)*np.exp(-0.5*(q**2))*np.cos(2*np.pi*m*ny/Ns)
    return v/Ns

def incDL(i, n, Ns):
    return 2*((i//2+n)%Ns) + i%2

def matrixwrap(dim, elems):
    mat = np.zeros((dim, dim))
    for elem in elems:
        mat[elem[1], elem[2]] = elem[0]
    return mat

def sparse_mat_wrap(dim, elems):
    data = np.array([elem[0] for elem in elems])
    row = np.array([elem[1] for elem in elems])
    col = np.array([elem[2] for elem in elems])
    smat = sp.sparse.csr_matrix((data, (row,col)), shape=(dim,dim))
    return smat
    
    
def fqh(Ns, N, a, numE):
#V(k, m) is the pseudo-potential
#Hamiltonian reads 
#\sum_{j=0}^{Ns-1} \sum_{k>|m|}c_{j+k}^\dag c_{j+m}^\dag c_{j+k+m}c_j
    sectors = getBasis(Ns, N)
    spec = []
    #compute matrix elements of the interaction
    vk0 = [ V(i, 0, a, 2*np.pi*Ns/a, Ns) for i in range(Ns//2)]
    vkm = np.zeros((Ns//2, Ns//2))
    for m in range(1, Ns//2):
        for n in range(m+1, Ns//2):
            vkm[n][m] = V(n, m, a, 2*np.pi*Ns/a, Ns)
            
    for k, sector in enumerate(sectors):
        dim = len(sector)
        print "COM momentum:", k
        print "Hilbert space dimension:", dim
        #create a look-up table
        tab = {}
        for ind, state in enumerate(sector):
            tab[tuple(state)] = ind 
        ham = sp.sparse.csr_matrix((dim, dim))
        hamhop = sp.sparse.csr_matrix((dim, dim))        
        #calculate the electrostatic interaction energy, m=0
        mat = []
        for ind, state in enumerate(sector):
            n = [0]*Ns # configuration in layer 1
            for p in state:
                n[p] = 1
            int_energy = 0.0
            for k in range(Ns//2):
                for i in range(Ns):
                    int_energy += vk0[k]*n[i]*n[(i+k)%Ns]
            #print "configuration:", n, int_energy
            mat.append((int_energy, ind, ind))
        ham = ham + sparse_mat_wrap(dim, mat)
        
        print "Finish electrostatic interactions"
        
        #calculate the m=1,2, ..., [Ns/2] hopping term
        for m in range(1,Ns//2):
            for n in range(m+1, Ns//2):
                for i in range(Ns):
                    hopmat = pairhopping((i+m)%Ns, i, (i+n)%Ns, (i+n+m)%Ns, sector, tab)
                    hamhop = vkm[n][m]*sparse_mat_wrap(dim, hopmat)
                    ham = ham + hamhop + hamhop.transpose()
        
        print "Hamiltonian constructed."
        w, v = lin.eigsh(ham,k=numE,which="SA",maxiter=100000)
        print sorted(w)
        spec.append(sorted(w))
    return spec


        
def fqhDL1(Ns, N, a, t):
# double layer FQH, full diagonalization
# Ns: number of orbitals in each layer
# N: number of electrons
# Lx: length of the torus in x direction. Notice that Lx*Ly=2*pi*Ns
# d: separation between the layers. Enter the Das Sarma-Zhang potential
# t: tunneling amplitude between the layers

    sectors = getBasisDL(Ns, N)
    for k, sector in enumerate(sectors):
        print "COM momentum:", k
        #create a look-up table
        tab = {}
        for ind, state in enumerate(sector):
            tab[tuple(state)] = ind 
        dim = len(sector)
        ham = np.zeros((dim, dim))
        hamhop = np.zeros((dim,dim))      
        #calculate the electrostatic interaction energy, m=0
        mat = []
        for ind, state in enumerate(sector):
            n1 = [0]*Ns # configuration in layer 1
            n2 = [0]*Ns # configuration in layer 2
            for p in state:
                if p%2 == 0:
                    n1[p//2] = 1
                else:
                    n2[p//2] = 1
            int_energy = 0.0
            for k in range(Ns//2):
                vk0 = V(k, 0, a, 2*np.pi*Ns/a, Ns)
                for i in range(Ns):
                    int_energy += vk0*n1[i]*n1[(i+k)%Ns] + vk0*n2[i]*n2[(i+k)%Ns]
            mat.append((int_energy, ind, ind))
        ham = ham + matrixwrap(dim, mat)
        
        #calculate the m=1,2, ..., [Ns/2] hopping term
        for m in range(1,Ns//2):
            for k in range(m+1,Ns//2):
                vk1 = V(k, 1, a, 2*np.pi*Ns/a, Ns)
                for i in range(Ns):
                    hopmat = pairhopping(incDL(i, m, Ns), i, incDL(i, k, Ns), incDL(i, k+m, Ns), sector, tab)
                    hamhop = vk1*matrixwrap(dim, hopmat)
                    ham = ham + hamhop + hamhop.transpose()
        
        #calculate inter-layer hopping
        for i in range(Ns):
            hopmat = hopping(2*i, 2*i+1,sector, tab)
            hamhop = -t*matrixwrap(dim, hopmat)
            ham = ham + hamhop + hamhop.transpose()
        
        w = np.linalg.eigvalsh(ham)
        print sorted(w)

        
def fqhDL(Ns, N, a, t, numE, sectors):
# double layer FQHE, using sparse matrices
# Ns: number of orbitals in each layer
# N: number of electrons
# Lx: length of the torus in x direction. Notice that Lx*Ly=2*pi*Ns
# d: separation between the layers. Enter the Das Sarma-Zhang potential
# t: tunneling amplitude between the layers

    spec = []
    
    vk0 = [ V(i, 0, a, 2*np.pi*Ns/a, Ns) for i in range(Ns//2)]
    vkm = np.zeros((Ns//2, Ns//2))
    for m in range(1, Ns//2):
        for n in range(m+1, Ns//2):
            vkm[n][m] = V(n, m, a, 2*np.pi*Ns/a, Ns)
    for k, sector in enumerate(sectors):
        #print "basis:", sector
        dim = len(sector)
        print "COM momentum:", k
        print "Hilbert space dimension:", dim
        #create a look-up table
        tab = {}
        for ind, state in enumerate(sector):
            tab[tuple(state)] = ind 
        ham = sp.sparse.csr_matrix((dim, dim))
        hamhop = sp.sparse.csr_matrix((dim, dim))        
        #calculate the electrostatic interaction energy, m=0
        mat = []
        for ind, state in enumerate(sector):
            n1 = [0]*Ns # configuration in layer 1
            n2 = [0]*Ns # configuration in layer 2
            for p in state:
                if p%2 == 0:
                    n1[p//2] = 1
                else:
                    n2[p//2] = 1
            int_energy = 0.0
            for k in range(Ns//2):
                for i in range(Ns):
                    int_energy += vk0[k]*n1[i]*n1[(i+k)%Ns] + vk0[k]*n2[i]*n2[(i+k)%Ns]
            mat.append((int_energy, ind, ind))
        ham = ham + sparse_mat_wrap(dim, mat)
                
        #calculate the m=1,2, ..., [Ns/2] hopping term
        for m in range(1,Ns//2):
            for n in range(m+1, Ns//2):
                for i in range(2*Ns):
                    hopmat = pairhopping(incDL(i, m, Ns), i, incDL(i, n, Ns), incDL(i, n+m, Ns), sector, tab)
                    hamhop = vkm[n][m]*sparse_mat_wrap(dim, hopmat)
                    ham = ham + hamhop + hamhop.transpose()
        
        #calculate inter-layer hopping
        for i in range(Ns):
            hopmat = hopping(2*i, 2*i+1,sector, tab)
            hamhop = -t*sparse_mat_wrap(dim, hopmat)
            ham = ham + hamhop + hamhop.transpose()
        
        print "Finish Hamiltonian construction."
        w = lin.eigsh(ham,k=numE,which="SA",maxiter=100000,return_eigenvectors=False)
        print sorted(w)
        spec.append(sorted(w))
        return sorted(w)
        #break
    return spec
        
def density(v, Ns, states):
    nexpt = [0]*Ns
    for i in range(Ns):
        for ind, basis in enumerate(states):
            if i in basis:
                n = 1
            else:
                n = 0
            nexpt[i] += n*np.abs(v[ind])**2
    return nexpt
    
def plot_spec(spec):
    momentum = [2*np.pi*i/Ns for i in range(Ns)]
    levels = [[spec[j][i] for j in range(Ns)] for i in range(numE)]
    pylab.figure()
    for i in range(numE):
        pylab.plot(momentum, levels[i],'ro')     
                
if __name__ == "__main__":
    Ns = 6
    N = 2
    numE = 1
    ratio = 1 # a/b = ratio. 
    a = np.sqrt(ratio*2*np.pi*Ns)
    t = 0.02


    #sectors = getBasisDL(Ns, N)

    spec0 = fqh(Ns, N, a, numE)
    
    plot_spec(spec0)
    #spec = fqh(Ns, N, a, numE)

    
    
