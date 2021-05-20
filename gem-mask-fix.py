#!/usr/bin/env python3
import urllib.request
import sys
import os
import re
from datetime import datetime

ictd_url = "http://sbfictd01.cl.gemini.edu/ChangeRequestGMOScassette.php"
# files_dir = "/net/export/icarus/gemini/GEM8.6/gmos/gmos/data/"
files_dir = "./test_files/"
msk_file = "msk.lut"
masks_file = "masks.lut"
msk_path = files_dir + msk_file
masks_path = files_dir + masks_file
len_nb = 31 # This is the len of chars used by name and barcode in file (smh)
len_gap2 = 9 # This is the len of the chars of the second gap in file (smfh)
len_bar = 8 # smfh
len_n_max = len_nb - len_bar + 1 # smfh

# Custom error for when the name of the barcode is too long for the file (smh)
class NameTooLongError(ValueError):
    pass

# Custom error for when the name of the barcode is too long for the file (smh)
class ICTDPageError(ValueError):
    pass

# Get the content from the ICTD site
try:
    ictd_resp = urllib.request.urlopen(ictd_url)
    ictd_content = [l.decode('utf-8').strip('\n')
                    for l in ictd_resp.readlines()
                    if l.decode('utf-8').strip('\n')]
except URLError as e:
    print(e)
    sys.exit(f"There was a problem accessing {ictd_url}")

cassette_tables = {} # Dictionary for cassette data
# Flags for site content filtering
cassette_flag = False
tr_flag = False
# Column number
i = 1

# Filter the contents of the ICTD webpage
for l in ictd_content:
    # Check for the begginning of a cassette table
    l_filt = re.search(r'Cassette ([123])', l)
    # Check if a cassette table has already been found
    if l_filt and cassette_flag:
        cassette_flag = False
    if not(l_filt) and not(cassette_flag):
        continue
    # Cassette table found
    if not(cassette_flag):
        cassette_no = l_filt.group(1)
        # Initialize cassette dictionary
        cassette_tables['c'+cassette_no] = {}
        cassette_flag = True
        continue
    # Check for the end of the cassette tables section and stop search
    l_filt = re.search(r'END OUTPUT',l)
    if l_filt:
        break
    # Find a slot with a mask
    l_filt = re.search(r'>[0-9]<',l)
    if not(l_filt) and not(tr_flag):
        continue
    if not(tr_flag):
        tr_flag = True
        continue
    # Check for the mask name and serial number
    l_filt = re.findall(r'<TD>([^<]+)</TD>',l)
    if l_filt and tr_flag:
        # Add barcode dict entry for mask name
        cassette_tables['c'+cassette_no][l_filt[1]] = l_filt[0]
        tr_flag = False

if not(cassette_tables):
    raise ICTDPageError(
        'No data was obtained from ICTD page. Webpage format may have changed'
    )

cassette_tables['c1']['42069666'] = 'The beast'
cassette_tables['c3']['99999999'] = 'Que wa te paso a ti'

# Read msk.lut and generate a list with installed masks
try:
    with open(msk_path, 'r') as f:
        msk_dict = {m.split('\t')[2].strip('\n'):m.split('\t')[0]
                    for m in f.readlines()}
except FileNotFoundError as e:
    print(e)
    sys.exit(f"File {msk_file} doesn't exist")
installed_masks = set(msk_dict.keys())

# Read masks.lut and generate a list with known masks
try:
    with open(masks_path, 'r') as f:
        known_masks = {re.search(r'\b[0-9]{8,}\b', l).group(0)
                        for l in f.readlines()
                        if re.search(r'\b[0-9]{8,}\b', l)}
except FileNotFoundError as e:
    print(e)
    sys.exit(f"File {masks_file} doesn't exist")

# Generate list of barcodes not referenced in masks.lut
unknown_masks = list(installed_masks.difference(known_masks))
if not(unknown_masks):
    sys.exit("There are no unknown masks installed")

file_lines = []
for m in unknown_masks:
    # Most of this code is to format the entry into masks.lut (smh)
    cn = 'c' + msk_dict[m]
    try:
        name = cassette_tables[cn][m]
    except KeyError:
        print(f"Error: No information available for {m} barcode in ICTD")
    else:
        if len(name) > len_n_max:
            raise NameTooLongError(
                f"The name: {name} is too long to be written in {masks_file}"
            )
        len_gap1 = len_nb - len(name + m)
        file_lines.append(name + ' ' * len_gap1 + m + ' ' * len_gap2 + '0\n')

# Set string with current date to generate backup copy of masks.lut
curr_date = datetime.strftime(datetime.now(), "%Y%m%d")
try:
    os.system(f"cp {masks_path} {masks_path}.{curr_date}")
except OSError as e:
    print(e)
    sys.exit(f"There was an error copying {masks_file}")


print(f"Updating {masks_file} ...")
try:
    with open(masks_path, 'a') as f:
        for fl in file_lines:
            print(f"Adding line: {fl}")
            f.write(fl)
except FileNotFoundError as e:
    print(e)
    sys.exit(f"File {masks_file} doesn't exist")

