#!/usr/bin/env python3

""" Borg Backup ID verify """
# (C) Copyright 2025
#
# Written by        : Arno van Amersfoort
# Dependencies      : subprocess, getopt, sys, os
# Python Version    : 3
# Initial date      : February 14, 2025
# Last Modified     : November 10, 2025

import subprocess
import sys
import os
import getopt

MY_VERSION = "1.01a"

def printn_stdout(line):
  """ Print to stdout with linefeed """
  sys.stdout.write(line + "\n")


def printn_stderr(line):
  """ Print to stderr with linefeed """
  sys.stderr.write(line + "\n")


class BorgIdVerify():
  """ Borg check class """

  def __init__(self):
    self._borg_base_path = None
    self._repo = None
    self._file_id_info = []
    self._borg_id_info = []
    self._force_update = False
    self._init = False
    self._dryrun = False

  @staticmethod
  def print_version():
    """ Show program version """
    printn_stdout(f"BorgBackup-ID-Verify v{MY_VERSION} - (C) Copyright 2025 Arno van Amersfoort")
    printn_stdout("")


  @staticmethod
  def print_help():
    """ Show help """
    printn_stdout("Usage: borg-id-verify.py [ options ] [ borg_base_path ]")
    printn_stdout("")
    printn_stdout("[ borg_base_path ]     - Borg repository base path")
    printn_stdout("Options:")
    printn_stdout("--help|-h              - Show (this) help screen")
    printn_stdout("--version              - Show program version")
    printn_stdout("--force|-f             - Force file updating, even when verify fails")
    printn_stdout("--init|-i              - Init new repositories")
    printn_stdout("--repo=[repo]          - Only verify repository [repo]")
    printn_stdout("--dryrun|-n            - Do NOT write any files")
    printn_stdout("")


  def process_commandline(self, argv):
    """ Process command line arguments (if any) """
    try:
      opts, args = getopt.getopt(argv, "hvnfi", ["help", "version", "dryrun", "force", "init", "repo="])
    except getopt.GetoptError as err_msg:
      printn_stderr(f"ERROR: {err_msg}")
      return False

    for option, value in opts:
      if option in ("-h", "/h", "--help"):
        self.print_version()
        self.print_help()
        return ""

      if option in ("-v", "/v", "--version"):
        self.print_version()
        return ""

      if option in ("-n", "--dryrun"):
        self._dryrun = True

      if option in ("-f", "--force"):
        self._force_update = True

      if option in ("-i", "--init"):
        self._init = True

      if option == "--repo":
        self._repo = value.lower()

    # Overwrite data-path?
    if len(args) == 1:
      self._borg_base_path = args[0]
    elif len(args) > 1:
      printn_stderr("ERROR: Multiple non-option arguments are not allowed")
      return False

    return True


  def sanity_check(self):
    """ Sanity check """
    if self._borg_base_path is None:
      printn_stderr("ERROR: Need to specify Borg base path!")
      sys.exit(1)

    if not os.path.isdir(self._borg_base_path):
      printn_stderr(f"ERROR: Borg base path \"{self._borg_base_path}\" does not exist!")
      sys.exit(1)

    return True


  def get_borg_id_info(self, repo_name):
    """ Get ID info from borg using "borg list" """
    self._borg_id_info = []

    try:
      result = subprocess.run(['borg', 'list', repo_name],
                              stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT,
                              env={'BORG_UNKNOWN_UNENCRYPTED_REPO_ACCESS_IS_OK': 'yes', 'BORG_RELOCATED_REPO_ACCESS_IS_OK': 'yes'},
                              check=False)
    except subprocess.CalledProcessError:
      printn_stderr("ERROR: Borg execution failed")
      return False

    if result.returncode != 0:
      printn_stderr(f"ERROR: Borg failed with code {result.returncode}")
      for line in result.stdout.splitlines():
        printn_stderr(line.decode('utf-8'))
      return False

    self._borg_id_info = [ line.decode('utf-8') for line in result.stdout.splitlines() if not line.startswith('Removed stale shared roster lock') ]

    return True


  def read_id_file(self, id_filename):
    """ Read (hash) info from repo info file """
    self._file_id_info = []

    try:
      with open(id_filename, 'r', encoding='ascii') as file_handle:
        self._file_id_info = [ line.strip('\n') for line in file_handle ]
      return True
    except IOError:
      printn_stderr(f"ERROR: Reading Borg-id file {id_filename} failed")
      return False


  def write_id_file(self, id_filename):
    """ Write (hash) info from repo info file """
    try:
      with open(id_filename, 'w', encoding='ascii') as file_handle:
        for line in self._borg_id_info:
          file_handle.write(f"{line}\n")
      return True
    except IOError:
      printn_stderr(f"ERROR: Writing borg-id file {id_filename} failed")
      return False


  def compare_ids(self):
    """ Compare the obtained BORG IDs with the ones stored in file """
    ret = True
    for idx, file_id in enumerate(self._file_id_info):
      if idx >= len(self._borg_id_info):
        printn_stderr(f"ERROR: Reached end of Borg-info before reaching end of ID-file at line {idx + 1}:")
        printn_stderr(f"* File={file_id}")
        ret = False
        break  # No point in continuing
      elif self._borg_id_info[idx] != file_id:
        printn_stderr(f"ERROR: Compare failed at file line {idx + 1}:")
        printn_stderr(f"* File={file_id}")
        printn_stderr(f"* Repo={self._borg_id_info[idx]}")
        ret = False

    return ret


  def check_repos(self):
    """ Check all repositories """
    self.print_version()

    ret_code = 0

    if self._repo is None:
      folders = [f for f in os.listdir(self._borg_base_path) if os.path.isdir(os.path.join(self._borg_base_path, f))]
    else:
      folders = [ self._repo ]

    for folder in folders:
      full_dir = os.path.join(self._borg_base_path, folder)
      id_file = os.path.join(self._borg_base_path, f".{folder}.id")

      printn_stdout(f"* Checking Borg path \"{full_dir}\"...")

      write_file = False

      if not os.path.isfile(id_file):
        if not self._init:
          printn_stderr(f"ERROR: Borg-id file {id_file} does not exist (yet). If this is the first run, use --init")
          printn_stdout("")
          continue
        else:
          printn_stdout(f"WARNING: Borg-id file {id_file} does not exist (yet). Creating one since --init is specified")
          self.get_borg_id_info(full_dir)
          write_file = True
      elif self.read_id_file(id_file) and self.get_borg_id_info(full_dir) and self._file_id_info:
        if self._force_update:
          write_file = True
          printn_stdout("NOTE: --force specified, not verifying IDs")
        else:
          if self.compare_ids():
            if len(self._borg_id_info) != len(self._file_id_info):
              write_file = True
            else:
              write_file = False
              printn_stdout("NOTE: Not updating ID file due to no changes")
          else:
            ret_code = 1
            printn_stderr(f"ERROR: Verification for Borg repository \"{full_dir}\" failed. Not updating ID file!")

      if write_file:
        if self._dryrun:
          printn_stdout("NOTE: Skipping updating ID file due to --dryrun")
        else:
          if os.path.isfile(id_file):
            old_id_file = f"{id_file}.old"
            if os.path.isfile(old_id_file):
              os.remove(old_id_file)
            os.rename(id_file, old_id_file)

          printn_stdout("* Writing (new) ID file...")
          self.write_id_file(id_file)

      printn_stdout("")

    sys.exit(ret_code)


def main(argv):
  """ Main program """
  app = BorgIdVerify()
  if app.process_commandline(argv) and app.sanity_check():
    app.check_repos()


#######################
# Program entry point #
#######################
if __name__ == "__main__":
  main(sys.argv[1:])
