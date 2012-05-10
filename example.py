#!/usr/bin/env python

import sys
import os
import argparse
import mpc1000

def title(s):
    border = '=' * 40
    out = (border, s, border)
    return '\n'.join(out)

def parse_arguments(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'infile',
        nargs='?',
        type=argparse.FileType('rb'),
        help='MPC 1000 program (default: default pgm data)')
    parser.add_argument(
        '-o',
        dest='outfile',
        metavar='FILE',
        type=argparse.FileType('wb'),
        help="write modified pgm to FILE")
    return parser.parse_args(argv)

def main(args):
    # Load data from file or use default pgm data
    if args.infile:
        pgm_data = args.infile.read()
        args.infile.close()
    else:
        pgm_data = mpc1000.DEFAULT_PGM_DATA
    
    # Create Program object form data
    pgm = mpc1000.Program(pgm_data)
    
    # Print program's intial values
    print title('Initial Values')
    print pgm
    print
    
    # Modify program
    pad = pgm.pads[0]
    sample = pad.samples[0]
    sample.sample_name = 'Example'

    # Print program's new values
    print title('New Values')
    print pgm
    print
    
    # Write modified program to outfile
    if args.outfile:
        pgm_data = pgm.data
        args.outfile.write(pgm_data)
        args.outfile.close()
    
    return 0

if __name__ == '__main__':
    args = parse_arguments()
    status = main(args)
    sys.exit(status)
