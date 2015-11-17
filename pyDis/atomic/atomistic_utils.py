#!/usr/bin/env python
'''A module to hold miscellaneous functions/classes/etc. that are generally

useful (eg. scaling k-point grids and reading input files), but have no obvious
home in any other module and are not substantial enough to form the basis of

their own modules. If you want to implement a minor helper function, this is the

module to do it in.
'''

from __future__ import print_function,division

import crystal as cry

def read_file(filename,path='./', return_str=False):
    '''Reads a file and prepares it for parsing. Has the option to return the

    output as a single string (with newline characters included), which can be
    useful if the structure of the input file makes regex easy (eg. CASTEP, QE)
    '''

    lines = []
    with open('%s%s' % (path, filename)) as input_file:
        for line in input_file:
            temp = line.rstrip()
            if temp:
                lines.append(temp)

    if return_str:
        all_lines = ''
        # stitch all elements of lines together
        for line in lines:
            all_lines += line + '\n'
        lines = all_lines

    return lines

def ceiling(x):
    '''Returns the smallest integer >= x.
    '''

    if abs(int(x) - x) < 1e-12:
        # if x has integer value (note: NOT type), return x
        return float(int(x))
    else:
        return float(int(x + 1.0))

def scale_kpoints(kgrid, sc_dimensions):
    '''Scales the k-point grid to reflect new supercell dimensions.
    '''

    new_grid = []
    for k, dim in zip(kgrid['spacing'], sc_dimensions):
        new_grid.append(max(int(ceiling(k / dim)), 1))

    kgrid['spacing'] = new_grid

def write_kgrid(write_fn, kgrid):
    '''Writes k-point grid.
    '''

    write_fn('%s ' % kgrid['preamble'])
    for k in kgrid['spacing']:
        write_fn(' %d' % k)
    write_fn('\n')
    return

def isiter(x):
    '''Tests to see if x is an iterable object whose class is NOT 
    <Basis> or any class derived from <Basis> (eg. <Crystal>, 
    <TwoRegionCluster>, etc.).
    '''
    
    if isinstance(x, (cry.Basis, cry.Atom)):
        # NOTE: need to implement __getitem__ for <cry.Atom>
        return False
    # else
    try:
        a = iter(x)
        return True
    except TypeError:
        return False

