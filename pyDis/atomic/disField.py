#!/usr/bin/env python

import numpy as np
import numpy.linalg as L

import matplotlib.pyplot as plt

def plotDisplacementFieldXY(fieldType, b, figureName, Sij=0.3):
    '''Produces a heat-map of the x and y components of displacement field 
    for the specified dislocation/disclination field types. For convenience, 
    we set the Frank/Burgers vector equal to 1. The plot is then saved to 
    file <figureName>.
    '''
    
    # define the maximum value of x and y,  and the grid spacing to use
    coordMin = 50
    dCoord = 0.1
    
    # create an even grid of x and y points out to 10|b|
    x, y = np.mgrid[-coordMin:coordMin:dCoord, -coordMin:coordMin:dCoord]
    
    # initialise arrays to hold the x and y components of displacement
    ux = []
    uy = []
    
    # calculate components of displacement at each points on the generated
    # xy grid
    gridSize = int(2.*coordMin/dCoord)
    for i in range(gridSize):
        # create temporary arrays to hold displacement along a row
        tempx = []
        tempy = []       
        for j in range(gridSize):
            # calculate displacement field and extract x and y components
            u = fieldType(np.array([x[i, j], y[i, j]]), b, np.array([0., 0.]), Sij)
            tempx.append(u[0])
            tempy.append(u[1])
                       
        ux.append(tempx)
        uy.append(tempy)
            
    ux = np.array(np.transpose(ux))
    uy = np.array(np.transpose(uy))
    
    plt.figure(figsize=(12, 5))
    
    # plot x component
    plt.subplot(121)
    plt.imshow(ux, extent=(-coordMin, coordMin, -coordMin, coordMin))
    plt.colorbar()
    plt.title(r'$u_{x}$', size=16)
    
    # plot y component
    plt.subplot(122)
    plt.imshow(uy, extent=(-coordMin, coordMin, -coordMin, coordMin))
    plt.colorbar()
    plt.title(r'$u_{y}$', size=16)
    
    plt.savefig(figureName)
    
    return
    
def plotDisplacementFieldZ(fieldType, b, figureName, Sij=0.3):
    '''Produces a heat-map of the z component of the displacement field 
    for the specified dislocation/disclination field types. For convenience, 
    we set the Frank/Burgers vector equal to 1. Mostly useful for screw 
    dislocations. The plot is then saved to file <figureName>.
    '''  
    
        # define the maximum value of x and y,  and the grid spacing to use
    coordMin = 10
    dCoord = 0.05
    
    # create an even grid of x and y points out to 10|b|
    x, y = np.mgrid[-coordMin:coordMin:dCoord, -coordMin:coordMin:dCoord]
    
    # initialise array to hold displacement
    uz = []
    
    # calculate components of displacement at each points on the generated
    # xy grid
    gridSize = int(2.*coordMin/dCoord)
    for i in range(gridSize):
        # create temporary array to hold displacement along a row
        temp = []
        for j in range(gridSize):
            # calculate displacement field and extract x and y components
            u = fieldType(np.array([x[i, j], y[i, j]]), b, np.array([0., 0.]), Sij)
            temp.append(u[2])
            
        uz.append(temp)
            
    uz = np.array(uz)
    
    plt.figure(figsize=(5, 5))
    
    # plot z component
    plt.imshow(uz, extent=(-coordMin, coordMin, -coordMin, coordMin))
    plt.colorbar()
    plt.title(r'$u_{z}$', size=16)
    
    plt.savefig(figureName)  

def isotropicScrewField(x1, b, x0, dummySij=0):
    '''Calculates displacement field for an isotropic dislocation at 
    point x (where the dislocation is at point x0,  and assumed to lie 
    parallel to the z-axis). 
    '''
    
    # NOTE: need to generalize sign for arb. orientation (currently only works
    # when b = [0, 0, +/-1])
    bs = L.norm(b)*np.sign(b[-1])
    # calculate x and y components of radial vector between point and 
    # dislocation line.
    dx = x1[0]-x0[0]
    dy = x1[1]-x0[1]
    
    # calculate the angle phi
    phi = np.arctan2(dy, dx)
    
    # z component of displacement field (ux and uy identically 0)
    uz = bs/(2*np.pi) * phi
    
    # construct displacement vector
    u = np.array([0., 0., uz])
    return u
    
def anisotropicScrewField(x1, b, x0, s_ratio=1.):
    '''Calculates displacement field for a screw dislocation in an anisotropic
    material with S44/S55 = <s_ratio>.
    '''
    
    # NOTE: need to generalize sign for arb. orientation (currently only works
    # when b = [0, 0, +/-1])
    bs = L.norm(b)*np.sign(b[-1])
    # calculate x and y components of radial vector between point and 
    # dislocation line.
    dx = x1[0]-x0[0]
    dy = x1[1]-x0[1]
    
    # calculate the angle phi
    prefactor = np.sqrt(s_ratio)
    phi = np.arctan2(prefactor*dy, dx)
    
    # z component of displacement field (ux and uy identically 0)
    uz = bs/(2*np.pi) * phi
    
    # construct displacement vector
    u = np.array([0., 0., uz])
    return u    
    
def isotropicEdgeField(x1, b, x0, Sij=0.3):
    '''Calculate displacement field at point x1 for edge dislocation in
    isotropic medium with Poisson's ration (represented by <Sij> and Burgers
    vector <b>.
    '''
    
    be = L.norm(b)*np.sign(sum(b))
    dx = x1[0]-x0[0]
    dy = x1[1]-x0[1]
    
    # calculate the radius <rho> and angle <phi>
    rho2 = dx**2+dy**2
    phi = np.arctan2(dy, dx)
    
    # Calculate x and y components of displacement field u (uz identically
    # zero.
    coreRadius2 = 1e-10
    if (rho2 < coreRadius2):
        # if the distance from the core is less than <coreRadius>,  assume 
        # no displacment - may have to fix this later
        ux = 0.
        uy = 0.
    else: 
        # calculate displacement normally      
        #ux = be/(4*np.pi*(1-Sij)) * (dx*dy/rho2) + be/(2*np.pi) * phi
        #uy = -(1-2*Sij) * be/(8*np.pi*(1-Sij)) * np.log(rho2) \
             #- be/(8*np.pi*(1-Sij)) * ((dx**2-dy**2)/(rho2))
        ux = be/(4*np.pi*(1-Sij))*(dx*dy/rho2) - be/(2*np.pi)*np.arctan2(dx, dy)
        uy = -(1-2*Sij) * be/(8*np.pi*(1-Sij)) * np.log(rho2/be**2) \
             + be/(8*np.pi*(1-Sij)) * ((dy**2)/(rho2))
    # construct displacement vector       
    u = np.array([ux, uy, 0.])
    return u
    
def isotropicWedgeField(x1, F, x0, Sij=0.3):
    '''Calculate displacement field at point x1 for a wedge disclination with
    Frank vector F centred at x0 with Poissons ratio <Sij>. Use expression in
    deWit (1973) for the displacement field.
    '''
    
    # Calculate magnitude of the Frank vector
    Omega = F[-1]
    
    dx = x1[0]-x0[0]
    dy = x1[1]-x0[1]
    
    # calculate the radius <rho> and angle <phi>
    rho = np.sqrt(dx**2+dy**2)
    phi = np.arctan2(dy, dx)#*(1+th)
        
    # for a wedge disclination oriented along [001],  uz = 0
    coreRadius = 1e-8
    if rho < coreRadius:
        # set displacement at the core to zero
        ux = 0
        uy = 0
    else:
        # calculate displacement normally
        ### NOTE: TEMPORARILY SWITCHING UX AND UY
        #ux = -Omega * (dy*phi/(2*np.pi) - (1-2*Sij)/(4*np.pi*(1-Sij)) * dx
        #      * (np.log(rho) - 1.))
        #uy = Omega * (dx*phi/(2*np.pi) + (1-2*Sij)/(4*np.pi*(1-Sij)) * dy
        #      * (np.log(rho) - 1.))
        ux = -Omega * (dy*phi/(2*np.pi) - (1-2*Sij)/(4*np.pi*(1-Sij)) * dx
              * (np.log(rho) - 1.))
        uy = Omega * (dx*phi/(2*np.pi) + (1-2*Sij)/(4*np.pi*(1-Sij)) * dy
              * (np.log(rho) - 1.))
              
    # construct displacement vector
    u = np.array([ux, uy, 0.])
    return u
    
    

