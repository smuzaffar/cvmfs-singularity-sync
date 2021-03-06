#!/usr/bin/env python
"""
Cleanup for Singularity container

Scan the images in the singularity CVMFS.  If an image directory has not been "linked" to for 2 days, 
remove the image directory.

Maintains state in a file in the root singularity directory named .missing_links.json

"""
import glob
import os
import json
import shutil
import argparse
import time
from datetime import datetime, timedelta

# JSON structure:
# {
#   "missing_links": {
#       "/cvmfs/singularity.opensciencegrid.org/.images/7d/ba009871baa50e01d655a80f79728800401bbd0f5e7e18b5055839e713c09f": "<timestamp_last_linked>"
#       ...
#   }
# }

def cleanup(delay=2, test=False,
            singularity_base='/cvmfs/singularity.opensciencegrid.org',
            max_per_cycle=50):
    '''Clean up unlinked singularity images'''
    json_location = os.path.join(singularity_base, '.missing_links.json')
    # Read in the old json, if it exists
    json_missing_links = {}
    try:
        with open(json_location) as json_file:
            json_missing_links = json.load(json_file)['missing_links']
    except (IOError, ValueError):
        # File is missing, unreadable, or damaged
        pass

    # Get all the images in the repo

    # Walk the directory /cvmfs/singularity.opensciencegrid.org/.images/*
    image_dirs = glob.glob(os.path.join(singularity_base, '.images/*/*'))

    # Walk the named image dirs
    named_image_dir = glob.glob(os.path.join(singularity_base, '*/*'))

    # For named image dir, look at the what the symlink points at 
    for named_image in named_image_dir:
        link_target = os.readlink(named_image)
        while link_target in image_dirs:
            image_dirs.remove(link_target)
        # Remove linked image from json (in case link is restored)
        json_missing_links.pop(link_target, None)

    # Now, for each image, see if it's in the json
    for image_dir in image_dirs:
        if image_dir not in json_missing_links:
            # Add it to the json
            print("Newly found missing link: %s" % (image_dir))
            json_missing_links[image_dir] = int(time.time())

    # Loop through the json missing links, removing directories if over the `delay` days
    expiry = datetime.now() - timedelta(days=delay)
    images_removed = 0
    for image_dir, last_linked in json_missing_links.items():
        date_last_linked = datetime.fromtimestamp(last_linked)
        if date_last_linked < expiry:
            # Confirm that we're inside the managed directory
            if not image_dir.startswith(singularity_base):
                continue
            # Remove the directory
            print("Removing missing link: %s" % image_dir)
            if not test:
                try:
                    shutil.rmtree(image_dir)
                    del json_missing_links[image_dir]
                except OSError as e:
                    print("Failed to remove missing link: %s" % e)

            images_removed += 1
            if images_removed >= max_per_cycle:
                print("Reached limit of cleaning %d images. Stopping cleanup cycle." % images_removed)
                break

    # Write out the end json
    with open(json_location, 'w') as json_file:
        json.dump({"missing_links": json_missing_links}, json_file)

def main():
    '''Main function'''
    args = parse_args()
    cleanup(test=args.test)

def parse_args():
    '''Parse CLI options'''
    parser = argparse.ArgumentParser()

    parser.add_argument('--test', action='store_true',
                        help="Don't remove files, but go through the motions of removing them.")
    return parser.parse_args()

if __name__ == "__main__":
    main()
