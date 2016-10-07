#!/usr/bin/env python

import numpy as np
import re
import matplotlib.pyplot as plt
import sys
from numpy.linalg import norm

# PN modules from pyDis package
sys.path.append('/home/richard/code_bases/dislocator2/')
from pyDis.pn import pn_1D as pn1
from pyDis.pn import pn_2D as pn2
from pyDis.pn import fit_gsf as fg
from pyDis.pn import peierls_barrier as pb
from pyDis.pn import energy_coeff as coeff
from pyDis.atomic import aniso

def control_file(filename):
    '''Opens the control file <filename> for a PN simulation and constructs a 
    dictionary containing the (unformatted) values for all necessary simulation
    parameters.
    '''
    
    sim_parameters = dict()
    lines = []
    input_style = re.compile('\s*(?P<par>.+)\s*=\s*[\'"]?(?P<value>[^\'"]*)[\'"]?\s*;')

    with open(filename) as f:
        for line in f:
            temp = line.strip()
            # handle the line
            if temp.startswith('#'): # comment
                continue
            if temp.startswith('&'): # check to see if <line> starts a namelist
                card_name = re.search('&(?P<name>\w+)\s+{', temp).group('name')
                sim_parameters[card_name] = dict()
                in_namelist = True
                continue
            if in_namelist:
                if '};;' in temp: # end of namelist
                    in_namelist = False
                    continue
                elif not(temp.strip()):
                    # empty line
                    continue
                # else
                inp = re.search(input_style, temp)
                sim_parameters[card_name][inp.group('par').strip()] = \
                                                    inp.group('value')

    return sim_parameters
    
def from_mapping(top_dict, namelist, card):
    '''Generates a value for <top_dict[namelist][card]> from a provided 
    functional form.
    '''
    
    map_form = re.compile('\s*map\s+(?P<namelist>[^\s]+)\s*>\s*(?P<val>.+):' +
               '\s*(?P<var>\w+)\s*-\>\s*(?P<expr>.*)')
               
    in_str = top_dict[namelist][card]
    found_map = re.search(map_form, in_str)
    
    # construct the mapping from <val> -> <var>
    new_func = 'lambda %s: %s' % (found_map.group('var'),
                                  found_map.group('expr'))
    input_value = top_dict[found_map.group('namelist')][found_map.group('val')]
    
    # evaluate function using the provided value
    val = eval('({})({})'.format(new_func, input_value))
    top_dict[namelist][card] = val
    return

    
def change_type(top_dict, namelist, card, new_type):
    '''Converts the string in the specified <card> in <namelist> to the required 
    type.
    '''
    
    try:
        top_dict[namelist][card] = new_type(top_dict[namelist][card])
    except ValueError:
        # test to see if np.e or np.pi in input
        if 'np.pi' in top_dict[namelist][card] or 'np.e' in top_dict[namelist][card]:
            top_dict[namelist][card] = eval(top_dict[namelist][card])

    return
    
def change_or_map(param_dict, namelist, card, new_type):
    '''Decides whether the value in <param_dict[namelist][card]> can be converted
    directly to a bool or numerical type (ie. int, float, or complex) or whether the
    provided value is a mapping involving some other parameter.
    '''

    # check that value is defined
    try:
        x = param_dict[namelist][card]
    except KeyError:
        # not defined -> go to default value
        raise ValueError

    if 'map' in  param_dict[namelist][card]:
        # provided value is a mapping
        from_mapping(param_dict, namelist, card)
    else:
        # convert to <new_type>
        change_type(param_dict, namelist, card, new_type)
        
    return
    
def to_bool(in_str):
    '''Routine to convert <in_str>, which may take the values "True" or "False", 
    a boolean (needed because bool("False") == True)
    '''
    
    bool_vals = {"True":True, "False":False}
    
    try:
        new_value = bool_vals[in_str]
    except KeyError:
        raise ValueError("{} is not a boolean value.".format(in_str))
        
    return new_value
    
def to_vector(in_str):
    '''Converts <in_str>, which is a list of numbers, in an array with elements
    of type float.
    '''
    
    new_vec = []
    for x in re.finditer('-?\d+\.?\d*', in_str):
        new_vec.append(float(x.group()))
    
    return np.array(new_vec)

def handle_pn_control(param_dict):
    '''handle each possible card in turn. If default value is <None>, the card is 
    considered "mission critical" and the program will abort if a value is not 
    provided.
    
    TO DO: List defining control parameters
    '''

    # cards for the <&control> namelist 
    control_cards = (('gsf_file', {'default':None, 'type':str}),
                     ('output', {'default':'pyDisPN.out', 'type':str}),
                     ('title_line', {'default':'Peierls-Nabarro model', 'type':str}),
                     ('n_iter', {'default':1, 'type':int}),
                     ('dimensions', {'default':2, 'type':int}),
                     ('max_x', {'default':100, 'type':int}),
                     ('n_funcs', {'default':np.nan, 'type':int}),
                     ('disl_type', {'default':'edge', 'type':str}),
                     ('use_sym', {'default':True, 'type':to_bool}),
                     ('plot', {'default':False, 'type':to_bool}),
                     ('plot_name', {'default':'pn_plot.tif', 'type':str}),
                     ('plot_both', {'default':False, 'type':to_bool}),
                     ('record', {'default':True, 'type':to_bool}),
                     ('nplanes', {'default':30, 'type':int}),
                     ('noisy', {'default': False, 'type': to_bool}),
                     ('parameters', {'default':np.array([]), 'type':to_vector})
                   )

    # cards for the <&struc> namelist. Need to find some way to incorporate 
    # anisotropic elasticity
    struc_cards = (('a', {'default':None, 'type':float}),
                   ('b', {'default':'map struc > a: x -> x', 'type':float}),
                   ('burgers', {'default':'map struc > a: x -> x', 'type':float}),
                   ('spacing', {'default':'map struc > a: x -> x', 'type':float}),
                  )
                  
    # cards for the &elast namelist. <k_para> and <k_norm> allow the user to 
    # supply predetermined elastic coefficients for the systems parallel and 
    # perpendicular to the Burgers vector
    elast_cards = (('bulk', {'default':None, 'type':float}),
                   ('shear', {'default':None, 'type':float}),
                   ('poisson', {'default':None, 'type':float}),
                   ('k_parallel', {'default':None, 'type':float}),
                   ('k_normal', {'default':np.nan, 'type':float}),
                   ('cij', {'default':None, 'type':aniso.readCij}),
                   ('b_edge', {'default':np.array([1., 0., 0.]), 'type':to_vector}),
                   ('b_screw', {'default':np.array([0., 0., 1.]), 'type':to_vector}),
                   ('normal', {'default':np.array([0., 1., 0.]), 'type':to_vector}),
                   ('in_gpa', {'default':True, 'type':to_bool})
                  )

    # cards for the <&surface> namelist. Where dimensions == 1 but the gsf 
    # file is two-dimensional (ie. a gamma surface), <map_ux> corresponds to the 
    # gamma line direction. If <dimensions> == 2, <map_ux> (<max_uy>) is the
    # direction of the edge (screw) component of the displacement. 
    surf_cards = (('x_length', {'default':'map struc > a: x -> x', 'type':float}),
                  ('y_length', {'default':'map struc > b: x -> x', 'type':float}),
                  ('angle', {'default':np.pi/2, 'type':float}),
                  ('map_ux', {'default':'remap: (ux, uy) -> ux', 'type':str}),
                  ('map_uy', {'default':'remap: (ux, uy) -> uy', 'type':str}),
                  ('gamma_shift', {'default':0., 'type':float}),
                  ('has_vacuum', {'default':False, 'type':to_bool}),
                  ('do_fourier', {'default':False, 'type':to_bool}),
                  ('fourier_N', {'default':2, 'type': int})
                 )

    # cards for the <&properties> namelist
    prop_cards = (('max_rho', {'default':False, 'type':to_bool}),
                  ('width', {'default':False, 'type':to_bool}),
                 )
    
    # cards for the <&stress> namelist
    stress_cards = (('calculate_stress', {'default':True, 'type':to_bool}),
                    ('dtau', {'default':0.0005, 'type':float}),
                    ('use_GPa', {'default':True, 'type':to_bool}),
                    ('threshold', {'default':0.5, 'type':float})
                   )
    
    # list of valid namelists 
    namelists = ['control', 'struc', 'elast', 'surface', 'properties', 'stress']
    # check that all namelists were in the control file and add them as keys
    # (with empty dicts as values) in the control dictionary
    for name in namelists:
        if name not in param_dict.keys():
            param_dict[name] = dict()

    # handle the input namelists, except for the elasticity namelist, which
    # requires special handling.
    for i, cards in enumerate([control_cards, struc_cards, elast_cards, surf_cards, 
                                                        prop_cards, stress_cards]):
        if namelists[i] == 'elast':
            # handle the elastic parameters later
            continue
        # else    
        for var in cards:
            try:
                change_or_map(param_dict, namelists[i], var[0], var[1]['type'])
            except ValueError:
                default_val = var[1]['default']
                # test to see if variable is "mission-critical" using None != None
                if default_val is None:
                    raise ValueError("No value supplied for mission-critical" +
                                                 " variable {}.".format(var[0]))
                else:
                    param_dict[namelists[i]][var[0]] = default_val
                    # if <default_val> is a mapping, needs to be evaluated
                    if type(default_val) == str and 'map' in default_val:
                        from_mapping(param_dict, namelists[i], var[0])
                        
    # extract values from the &elast namelist
    for var in elast_cards:
        try:
            change_or_map(param_dict, 'elast', var[0], var[1]['type'])
        except ValueError:
            param_dict['elast'][var[0]] = var[1]['default']
                                         
    # test to make sure that all of the parameters required for one of isotropic
    # or anisotropic elasticity have been supplied. Should we also test to see
    # which function to use when calculating the energy coefficients?
    if not (param_dict['elast']['k_parallel'] is None):
        param_dict['elast']['coefficients'] = 'specific'
    elif not (param_dict['elast']['cij'] is None):
        # if an elastic constants tensor is given, use anisotropic elasticity
        param_dict['elast']['coefficients'] = 'aniso'
    elif param_dict['elast']['shear'] != None:
        # test to see if another isotropic elastic property has been provided. 
        # Preference poisson's ratio over bulk modulus, if both have been provided
        if param_dict['elast']['poisson']  != None:
            param_dict['elast']['coefficients'] = 'iso_nu'
        elif param_dict['elast']['bulk'] != None:
            param_dict['elast']['coefficients'] = 'iso_bulk'
        else:
            raise AttributeError("No elastic properties have been provided.")
    else:
        raise AttributeError("No elastic properties have been provided.")
            
    return

def print_control(control_dict, print_types=True):
    '''Print the values of each card in the namelists in <control_dict>
    including, optionally, their types. Useful mainly as a debugging tool
    if adding new cards (or namelists).
    '''
    
    for key in control_dict:
        print "### Namelist: {} ###\n".format(key.upper())
        for key1 in control_dict[key]:
            print "CARD: {}".format(key1)
            print "VALUE: {}".format(control_dict[key][key1])
            
            if print_types:
                print "TYPE: {}\n".format(type(control_dict[key][key1]))
            else:
                print "\n"
    
    return 
    
class PNSim(object):
    # handles the control file for a PN simulation in <pyDis>
    
    def __init__(self, filename):
        self.sim = control_file(filename)
        handle_pn_control(self.sim)
        
        # functions to access values in namelists easily
        self.control = lambda card: self.sim['control'][card]
        self.struc = lambda card: self.sim['struc'][card]
        self.elast = lambda card: self.sim['elast'][card]
        self.surf = lambda card: self.sim['surface'][card]
        self.prop = lambda card: self.sim['properties'][card]
        self.stress = lambda card: self.sim['stress'][card]

        # calculate the energy coefficients
        if self.elast('coefficients') == 'specific':          
            self.K = coeff.predefined(self.elast('k_parallel'), self.elast('k_normal'),
                                                using_atomic=not(self.elast('in_gpa')))
        elif self.elast('coefficients') == 'aniso':
            self.K = coeff.anisotropic_K(self.elast('cij'),
                                         self.elast('b_edge'),
                                         self.elast('b_screw'),
                                         self.elast('normal'),
                                         using_atomic=not(self.elast('in_gpa'))
                                        )
        elif self.elast('coefficients') == 'iso_nu':
            self.K = coeff.isotropic_nu(self.elast('poisson'), self.elast('shear'),
                                             using_atomic=not(self.elast('in_gpa')))
        elif self.elast('coefficients') == 'iso_bulk':
            self.K = coeff.isotropic_K(self.elast('bulk'), self.elast('shear'),
                                           using_atomic=not(self.elast('in_gpa')))
                                           

        # if restricting calculation to one component of displacement, extract
        # the appropriate energy coefficient.    
        if self.control('dimensions') == 1:
            # store a copy of the edge and screw energy coefficients
            self.K_store = self.K
            if self.control('disl_type').lower() == 'edge':
                self.K = self.K[0]
            else:
                # for the moment, default to shear
                self.K = self.K[1]
        
        # construct the gamma surface/gamma line
        if self.control('noisy'):
            print("Constructing gamma surface/line")
        self.construct_gsf()
        
        # calculate fit parameters and energy of the dislocation
        if self.control('noisy'):
            print("Relaxing dislocation core structure.")
             
        self.run_sim()
        
        if self.control('noisy'):
            print("Core relaxation complete.")
        
        # do post-processing and/or plotting, if requested by the user
        if self.control('noisy'):
            print('Doing post-processing.')       
        self.post_processing()
        
        # calculate Peierls stress and Peierls barrier, if requested
        if self.control('noisy'):
            print('Calculating Peierls stress.')
            
        self.peierls()
        
        if self.control('noisy'):
            print('Peierls stress calculated.')

        # write results to ouput
        self.write_output()
        
    def run_sim(self):
        '''Calculates an optimum(ish) dislocation structure.
        '''
        
        # check to see if the user has provided parameters specifying a trial
        # disregistry profile (in the order A x0 c).
        if len(self.control('parameters')) != 0:
            # use supplied parameters and perform only a single energy minimization
            inpar = self.control('parameters')
            niter = 1
        else:
            # no parameters -> tell program that it should generate a trial 
            # configuration
            inpar = None
            niter = self.control('n_iter')
            
        if self.control('dimensions') == 1:
            # calculate dislocation energy and disregistry profile
            self.E, self.par = pn1.run_monte1d(
                                               niter,
                                               self.control('n_funcs'),
                                               self.K,
                                               max_x=self.control('max_x'),
                                               energy_function=self.gsf,
                                               use_sym=self.control('use_sym'),
                                               b=self.struc('burgers'),
                                               spacing=self.struc('spacing'),
                                               noisy=self.control('noisy'),
                                               params=inpar
                                              ) # Done Monte Carlo 1D
        elif self.control('dimensions') == 2:
            self.E, self.par = pn2.run_monte2d(
                                               niter,
                                               self.control('n_funcs'),
                                               self.control('disl_type'),
                                               self.K, 
                                               max_x=self.control('max_x'),
                                               energy_function=self.gsf,
                                               use_sym=self.control('use_sym'),
                                               b=self.struc('burgers'),
                                               spacing=self.struc('spacing'),
                                               noisy=self.control('noisy'),
                                               params=inpar
                                              ) # Done Monte Carlo 2D              
                                                            
        return
                                
    def construct_gsf(self):
    
        gsf_grid, self.units = fg.read_numerical_gsf(self.control('gsf_file'))

        # determine which fitting function to use from the shape of <gsf_grid>
        # original test was self.control("dimensions")
        n_columns = np.shape(gsf_grid)[-1]
        if n_columns == 2:
            self.gsf = fg.spline_fit1d(gsf_grid, self.surf('x_length'), 
                                                 self.surf('y_length'),
                                                 angle=self.surf('angle'),
                                                 units=self.units,
                                                 hasvac=self.surf('has_vacuum'),
                                                 do_fourier_fit=self.surf('do_fourier'),
                                                 n_order=self.surf('fourier_N'))
        elif n_columns == 3: # 2-dimensional misfit function
            # fit the gamma surface
            if self.control('dimensions') == 2:
                base_func = fg.spline_fit2d(gsf_grid, self.surf('x_length'), 
                                                      self.surf('y_length'),
                                                   angle=self.surf('angle'),
                                                           units=self.units,
                                             hasvac=self.surf('has_vacuum'),
                                     do_fourier_fit=self.surf('do_fourier'),
                                             n_order=self.surf('fourier_N'))
                                                  
                self.gsf = fg.new_gsf(base_func, self.surf('map_ux'), self.surf('map_uy'))
                                             
            elif self.control('dimensions') == 1: 
                # begin by performing a spline fit to the surface 
                base_func = fg.spline_fit2d(gsf_grid, self.surf('x_length'), 
                                                      self.surf('y_length'),
                                                   angle=self.surf('angle'),
                                                           units=self.units,
                                             hasvac=self.surf('has_vacuum'),
                                                       do_fourier_fit=False)
                
                # remap input so that x and y correspond to ux and uy                                       
                temp_gsf = fg.new_gsf(base_func, self.surf('map_ux'), self.surf('map_uy'))
                
                # project out the dislocation parallel component
                # determine which axis to use (0/x if edge, 1/y if screw)
                if self.control('disl_type') == 'edge':
                    use_axis = 0
                elif self.control('disl_type') == 'screw':
                    use_axis = 1
                    
                temp_1d = fg.projection(temp_gsf, self.surf('gamma_shift'), use_axis)
                
                # set the correct periodicity
                temp_1d2 = lambda x: temp_1d(x % self.struc('burgers'))
                
                if self.surf('do_fourier'):
                    # fit a fourier series to <temp_1d2>.
                    self.gsf = fg.gline_fourier(temp_1d, self.surf('fourier_N'),
                                                           self.struc('burgers'))
                else:
                    self.gsf = temp_1d2
        else:
            raise ValueError("GSF grid has invalid number of dimensions")

        return
                            
    def post_processing(self):
        '''Calculate the displacement field and dislocation density, record these
        values in appropriate output files, plot them (if requested to by the
        user), and then calculate the dislocation height and width.
        '''
        
        if (self.control('plot') or self.prop('max_rho') or self.prop('width') or
                                                        self.control('record')):
                                                        
            if self.control('record'):
                # open output files for the disregistry and dislocation density
                outstreamu = open('disreg.{}'.format(self.control('output')), 'w')
                outstreamrho = open('rho.{}'.format(self.control('output')), 'w')
                
            # lattice points
            r = self.struc('spacing')*np.arange(-self.control('max_x'), self.control('max_x'))
            
            # calculate misfit profile and dislocation density and write to output
            # files
            if self.control('dimensions') == 1:
                self.ux = pn1.get_u1d(self.par, self.struc('burgers'), 
                                   self.struc('spacing'), self.control('max_x')) 
                
                # record disregistry and dislocation density
                if self.control('record'):
                    # header for output files
                    outstreamu.write('# r (\AA) u (\AA)\n')
                    outstreamrho.write('# r (\AA) rho\n')
                    
                    # record values of rho and u at each lattice point
                    rho = pn1.rho(self.ux, r) 
                    for i in range(len(r)):
                        outstreamu.write('{:.3f} {:.6f}\n'.format(r[i], self.ux[i]))
                        if i != 0:
                            # rho not defined for first lattice plane
                            # Record at intervals between lattice planes
                            ri = 0.5*(r[i]+r[i-1])
                            outstreamrho.write('{:.3f} {:.6f}\n'.format(ri, rho[i-1]))
                        
                    outstreamu.close()
                    outstreamrho.close()
                    
            elif self.control('dimensions') == 2:
                self.ux, self.uy = pn2.get_u2d(self.par, self.struc('burgers'),
                                    self.struc('spacing'), self.control('max_x'),
                                                      self.control('disl_type'))
                
                # record both components of disregistry and dislocation density
                if self.control('record'):
                    # header lines
                    outstreamu.write('# r (\AA) ux (\AA) uy (\AA)\n')
                    outstreamrho.write('# r (\AA) rhox  rhoy\n')
                    
                    # record values of u and rho at each lattice point
                    rhox = pn1.rho(self.ux, r)
                    rhoy = pn1.rho(self.uy, r)
                    for i in range(len(r)):
                        outstreamu.write('{:.3f} {:.6f} {:.6f}\n'.format(r[i], self.ux[i],
                                                                              self.uy[i]))
                        if i != 0:
                            # as above, rho not defined for first lattice plane.
                            # Record at intervals between lattice planes
                            ri = 0.5*(r[i]+r[i-1])
                            outstreamrho.write('{:.3f} {:.6f} {:.6f}\n'.format(ri, 
                                                                rhox[i-1], rhoy[i-1]))
                        
                    outstreamu.close()
                    outstreamrho.close()
                             
            # create plot of dislocation density and misfit profile
            if self.control('plot'):   
                if self.control('dimensions') == 1:
                    self.fig, self.ax = pn1.plot_both(self.ux, r, self.struc('burgers'),
                                                        self.struc('spacing'), 
                                                        nplanes=self.control('nplanes'))
                    plt.savefig(self.control('plot_name'))
                    plt.close()             
                elif self.control('plot_both'): # dimension == 2
                    self.fig, self.ax = pn1.plot_both(self.ux, r, self.struc('burgers'),
                                                               self.struc('spacing'), 
                                                        nplanes=self.control('nplanes'))
                    plt.savefig('edge.' + self.control('plot_name'))
                    plt.close()
                    self.fig, self.ax = pn1.plot_both(self.uy, r, self.struc('burgers'),
                                                               self.struc('spacing'), 
                                                        nplanes=self.control('nplanes'))
                    plt.savefig('screw.' + self.control('plot_name'))
                    plt.close()
                else: # dimensions == 2
                    if self.control('disl_type') in 'edge':
                        self.fig, self.ax = pn1.plot_both(self.ux, r, self.struc('burgers'),
                                                               self.struc('spacing'), 
                                                        nplanes=self.control('nplanes'))
                    else: # screw
                        self.fig, self.ax = pn1.plot_both(self.uy, r, self.struc('burgers'),
                                                               self.struc('spacing'), 
                                                        nplanes=self.control('nplanes'))
                    plt.savefig(self.control('plot_name'))
                    plt.close()
                
            # calculate dislocation width and height
            if (self.control('disl_type') in 'edge' 
                or self.control('dimensions') == 1):
                self.rho = pn1.rho(self.ux, r)
            else: # screw
                self.rho = pn1.rho(self.uy, r)
            
            self.dis_width = pn1.dislocation_width(self.rho, r)
            self.max_density = pn1.max_rho(self.rho, self.struc('spacing'))
        return
            
    def peierls(self):
        '''Calculate the Peierls stress for the lowest-energy dislocation.
        '''

        if not self.stress('calculate_stress'):
            pass
        else:
            self.taup, self.taup_av = pb.taup(
                                              self.par, 
                                              self.control('max_x'), 
                                              self.gsf,
                                              self.K, 
                                              self.struc('burgers'), 
                                              self.struc('spacing'),
                                              self.control('dimensions'), 
                                              self.control('disl_type'),
                                              dtau=self.stress('dtau'), 
                                              in_GPa=self.stress('use_GPa'),
                                              thr=self.stress('threshold')
                                             )
                                                           
            # calculate average and direction-dependent Peierls barriers
            self.wp_av = pb.peierls_barrier(self.taup_av, self.struc('burgers'),
                                                  in_GPa=self.stress('use_GPa'))
                                                  
            self.wp = [pb.peierls_barrier(taup, self.struc('burgers'),
                                        in_GPa=self.stress('use_GPa'))
                                                for taup in self.taup]
                                                     
        return
        
    def write_output(self):
        '''Write the results of the PN calculation to the specified output file 
        (<control('output')>)
        '''
        
        outstream = open(self.control('output'), 'w')
        
        # write front matter
        boiler_plate = 'Peierls-Nabarro calculation with pyDis - a Python' + \
                       ' interface for atomistic modelling of dislocations\n'                       
        outstream.write(boiler_plate)
        outstream.write('{}\n\n'.format(self.control('title_line')))
        
        # write parameters used in the simulation
        outstream.write('SIMULATION PARAMETERS:\n')
        outstream.write('Dimensions: {}\n'.format(self.control('dimensions')))
        outstream.write('Dislocation type: {}\n'.format(self.control('disl_type')))
        outstream.write('Burgers vector: {:.3f} ang.\n'.format(self.struc('burgers')))
        outstream.write('Interlayer spacing: {:.3f} ang.\n'.format(self.struc('spacing')))
        outstream.write('Number of iterations: {}\n'.format(self.control('n_iter')))
        outstream.write('Number of atomic planes used: {}\n'.format(2*self.control('max_x')+1))
        
        # energy coefficients -> only write relevant coefficient if 1D
        if self.control('dimensions') == 2:
            outstream.write('Edge energy coefficient: {:.3f} eV/ang.\n'.format(self.K[0]))
            outstream.write('Screw energy coefficient: {:.3f} eV/ang.\n'.format(self.K[1]))
        else: # dimensions == 1
            outstream.write('Edge energy coefficient: {:.3f} eV/ang.\n'.format(self.K_store[0]))
            outstream.write('Screw energy coefficient: {:.3f} eV/ang.\n'.format(self.K_store[1]))
            
        outstream.write('\n\n')
        
        # write fit parameters
        outstream.write('Fit parameters: \n')
        
        # needed in case user set input <parameters> manually
        N = len(self.par)/3
        
        if self.control('dimensions') == 2:
            # write parameters for the edge component of displacement
            outstream.write('----X1----\n')
            
            outstream.write('A\n')
            for A in self.par[:N/2]:
                outstream.write('{:.3f} '.format(A))
            outstream.write('\n')
            
            outstream.write('x0\n')
            for x0 in self.par[N:N+N/2]:
                outstream.write('{:.3f} '.format(x0))
            outstream.write('\n')
            
            outstream.write('c\n')
            for c in self.par[2*N:2*N+N/2]:
                outstream.write('{:.3f} '.format(c))
            outstream.write('\n')

            # write parameters for screw component of displacement
            outstream.write('----X2----\n')
            
            outstream.write('A\n')
            for A in self.par[N/2:N]:
                outstream.write('{:.3f} '.format(A))
            outstream.write('\n')
            
            outstream.write('x0\n')
            for x0 in self.par[N+N/2:2*N]:
                outstream.write('{:.3f} '.format(x0))
            outstream.write('\n')
            
            outstream.write('c\n')
            for c in self.par[2*N+N/2:]:
                outstream.write('{:.3f} '.format(c))
            outstream.write('\n')

        elif self.control('dimensions') == 1:
            outstream.write('----X----\n')

            outstream.write('A\n')
            for A in self.par[:N]:
                outstream.write('{:.3f} '.format(A))
            outstream.write('\n')
            
            outstream.write('x0\n')
            for x0 in self.par[N:2*N]:
                outstream.write('{:.3f} '.format(x0))
            outstream.write('\n')
            
            outstream.write('c\n')
            for c in self.par[2*N:]:
                outstream.write('{:.3f} '.format(c))
            outstream.write('\n')
        
        outstream.write('\n\n')
        
        # write results
        outstream.write('Results:\n')
        outstream.write('E = {:.3f} eV\n'.format(self.E))
        if self.stress('calculate_stress'):
            if self.stress('use_GPa'):
                units = 'GPa'
                outstream.write('Minimum Peierls stress = {:.3f} {}\n'.format(
                                                         self.taup[0], units))
                outstream.write('Maximum Peierls stress = {:.3f} {}\n'.format(
                                                         self.taup[1], units))
                outstream.write('Average Peierls stress = {:.3f} {}\n'.format(
                                                         self.taup_av, units))
            else:
                units = 'eV/ang.^3'
                outstream.write('Minimum Peierls stress = {:.6f} {}\n'.format( 
                                                          self.taup[0], units))
                outstream.write('Maximum Peierls stress = {:.6f} {}\n'.format(
                                                          self.taup[1], units))
                outstream.write('Average Peierls stress = {:.6f} {}\n'.format(
                                                          self.taup_av, units))
                                                    
            outstream.write('Peierls barrier: {:.3f} eV/Ang\n'.format(self.wp_av))
            
        if self.prop('max_rho'):
            outstream.write('Maximum density: {:.3f}\n'.format(self.max_density))
        if self.prop('width'):
            outstream.write('Dislocation width: {:.3f} ang.\n'.format(abs(self.dis_width)))
            
        outstream.write('\n\n**Finished**')
        outstream.close()
        return
        
def main(filename):
    new_sim = PNSim(filename)
    
if __name__ == "__main__":
    main(sys.argv[1])
