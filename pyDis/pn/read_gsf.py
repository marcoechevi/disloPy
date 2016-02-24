#!/usr/bin/env python
from __future__ import print_function

import re
import argparse
import sys

import numpy as np

# dictionary containing regex to match final energies for a variety of codes
energy_lines = {"gulp": re.compile(r"\n\s*Final energy\s+=\s+" +
                                  "(?P<E>-?\d+\.\d+)\s*(?P<units>\w+)\s*\n"),
                "castep": re.compile(r"\n\s*BFGS:\s*Final\s+Enthalpy\s+=\s+" +
                              "(?P<E>-?\d+\.\d+E\+\d+)\s*(?P<units>\w+)\s*\n"),
                "qe": re.compile(r"\n\s*Final energy\s+=\s+(?P<E>-?\d+\.\d+)" +
                                  "\s+(?P<units>\w+)\s*\n")
               }

# regex to match the gnorm of the completed (but not necessarily converged) 
# structure output by a GULP calculation               
get_gnorm = re.compile(r"Final Gnorm\s*=\s*(?P<gnorm>\d+\.\d+)")
               
def command_line_options():
    '''Parse command line options to control extraction of gamma surface.
    '''
    
    options = argparse.ArgumentParser()
    
    options.add_argument("-b", "--base-name", type=str, dest="base_name",
                         default="gsf", help="Base name for GSF calculations")
    options.add_argument("-x", "--x_max", type=int, dest="x_max", default=0,
                                            help="Number of steps along x")
    options.add_argument("-y", "--y_max", type=int, dest="y_max", default=0,
                                            help="Number of steps along y")
    options.add_argument("-p", "--program", type=str, dest="program", default="gulp",
                                     help="Program used to calculate GSF energies")
    options.add_argument("-o", "--output", type=str, dest="out_name", default="gsf.dat",
                                  help="Output file for the gamma surface energies")
    options.add_argument("-s", "--suffix", type=str, dest="suffix", default="out",
                                help="Suffix for ab initio/MM-FF output files")
    options.add_argument("-d", "--dimensions", type=int, choices=[1, 2], default=2,
                             dest='dim', help="Dimensionality of the stacking" +
                          "fault function. 1D corresponds to a gamma-line, 2D to" +
                                            " a gamma-surface.")
    options.add_argument("--indir", action="store_true", default=False,
                         help="Each GSF point is in its own directory")
                                  
    return options
               
def get_gsf_energy(energy_regex, prog, base_name, suffix, i, j=None, indir=False):
    '''Extracts calculated energy from a generalized stacking fault calculation
    using the regular expression <energy_regex> corresponding to the code used
    to calculate the GSF energy.

    Set argument indir to True if mkdir was True in gsf_setup.
    '''
    
    acceptable_gnorm = 0.2
    
    name_format = '{}.{}'.format(base_name, i)
    if j is not None: # gamma surface, need x and y indices
        name_format += '.{}'.format(j)
        
    # check if individual calculations are in their own directories
    if indir:
        filename = '{}/{}.{}'.format(name_format, name_format, suffix)
    else:
        filename = '{}.{}'.format(name_format, suffix)
    print(filename)
    outfile = open(filename)
    output_lines = outfile.read()
    outfile.close()
    matched_energies = re.findall(energy_regex, output_lines)
    
    # flags that we use to see if convergence has failed without resulting in
    # a divergent energy (which would stop GULP).
    gulp_flag_failure = ["Conditions for a minimum have not been satisfied",
                         "Too many failed attempts to optimise"]
    
                    
    if not(matched_energies):
        # match the unconverged energy, and see if the total force is below
        # some acceptance threshold
        #raise AttributeError("Calculation does not have an energy.")
        E = np.nan
        units = None    
    else:
        if prog.lower() == 'gulp':
            if ((gulp_flag_failure[0] in output_lines) or 
                (gulp_flag_failure[1] in output_lines)):
                gnorm = float(get_gnorm.search(output_lines).group("gnorm"))
            else:
                gnorm = 0.
                
            if gnorm < acceptable_gnorm:       
                for match in matched_energies:
                    E = float(match[0])
                    units = match[1]
            else:
                E = np.nan
                units = None
        
    return E, units
        
def main():
    
    if not sys.argv[1:]:
        raise ValueError("Input arguments must be supplied.")
    else:
        options = command_line_options()
        args = options.parse_args()
        
    # determine which regular expression to use to match output energies
    try:
        regex = energy_lines[(args.program).lower()]
    except KeyError:
        print("Invalid program name supplied. Implemented programs are: ")
        for prog in energy_lines.keys():
            print("***{}***".format(prog))
        
    outstream = open("{}".format(args.out_name), "w")    
    
    if args.dim == 1:
        energies = np.zeros(args.x_max+1)
        # handle gamma line
        for i in xrange(args.x_max+1):
            E, units = get_gsf_energy(regex, args.program, args.base_name, 
                                         args.suffix, i, indir=args.indir)
            energies[i] = E
            
        # record the units in which the cell energy is expressed
        outstream.write("# units {}\n".format(units))
            
        # remove any nan values -> should implement as a separate function.
        E_perfect = energies[0]
        for i in range(args.x_max+1):
            if energies[i] != energies[i]:
                # nan value; average values before and after
                energies[i] = 0.5*(energies[(i-1) % (args.x_max+1)]+
                                   energies[(i+1) % (args.x_max+1)])
                                   
                if energies[i] != energies[i]:
                    # gamma line not computed accurately; raise error
                    raise ValueError("Too many NaN values.")
            
            outstream.write("{} {:.6f}\n".format(i, energies[i]))
            
    else: # gamma surface
        energies = np.zeros((args.x_max+1, args.y_max+1))
        # handle gamma surface
        for i in xrange(args.x_max+1):
            for j in xrange(args.y_max+1):
                E, units = get_gsf_energy(regex, args.program, args.base_name, 
                                           args.suffix, i, j, indir=args.indir)
                energies[i, j] = E

        # record energy units used
        outstream.write("# units {}\n".format(units))
        # get rid of nan values -> Should implement this as a separate function
        E_perfect = energies[0, 0]
        for i in xrange(args.x_max+1):
            for j in xrange(args.y_max+1):
                if energies[i, j] != energies[i, j] or (energies[i, j] < E_perfect - 1.):
                    # average neighbouring energies, excluding nan values        
                    approx_energy = 0.
                    num_real = 0 # tracks number of adjacent non-NaNs
                    for signature in [((i+1) % args.x_max, j),
                                      ((i-1) % args.x_max, j),
                                      (i, (j+1) % args.y_max),
                                      (i, (j-1) % args.y_max)]:
                        if energies[signature] !=  energies[signature]:
                            pass
                        elif energies[signature] < E_perfect - 1.:
                            # energy is nonsense -> probably a sign of weird 
                            # interatomic potentials.
                            pass
                        else:
                            approx_energy += energies[signature]
                            num_real += 1

                    if num_real == 0:
                        #raise Exception("Entry (%d, %d) has no real neighbours" 
                        #                                               % (i, j))
                        print("Warning: no real neighbours.")
                        energies[i, j] = -10000
                    else:
                        energies[i, j] = approx_energy/num_real
                    print("({}, {}): {:.2f}".format(i, j, energies[i, j]))
                print(energies[i, j])
                outstream.write("{} {} {:.6f}\n" .format(i, j, energies[i, j]))
                
            # include a space between slices of constant x (for gnuplot)
            outstream.write("\n")
    
    outstream.close()
        
if __name__ == "__main__":
    main()
