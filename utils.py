import contextlib
import hashlib
import os
import shutil
import subprocess
from getpass import getpass
import github

CURRENT_REPO_NAME = "fingolfin/distribution-scripts"
# Initialized by initialize_github
GITHUB_INSTANCE = None
CURRENT_REPO = None

# print notices in green
def notice(msg):
    print("\033[32m" + msg + "\033[0m")

# print warnings in yellow
def warning(msg):
    print("\033[33m" + msg + "\033[0m")

# print error in red and exit
def error(msg):
    print("\033[31m" + msg + "\033[0m")
    raise UserWarning("error in GAP release script")

def verify_command_available(cmd):
    if shutil.which(cmd) == None:
        error(f"the '{cmd}' command was not found, please install it")
    # TODO: do the analog of this in ReleaseTools bash script:
    # command -v curl >/dev/null 2>&1 ||
    #     error "the 'curl' command was not found, please install it"

def verify_git_repo():
    res = subprocess.run(["git", "--git-dir=.git", "rev-parse"], stderr = subprocess.DEVNULL)
    if res.returncode != 0:
        error("current directory is not a git root directory")

# check for uncommitted changes
def verify_git_clean():
    res = subprocess.run(["git", "update-index", "--refresh"])
    if res.returncode == 0:
        res = subprocess.run(["git", "diff-index", "--quiet", "HEAD", "--"])
    if res.returncode != 0:
        error("uncommitted changes detected")

# from https://code.activestate.com/recipes/576620-changedirectory-context-manager/
@contextlib.contextmanager
def working_directory(path):
    """A context manager which changes the working directory to the given
    path, and then changes it back to its previous value on exit.

    """
    prev_cwd = os.getcwd()
    os.chdir(path)
    yield
    os.chdir(prev_cwd)

# helper for extracting values of variables set in the GAP Makefiles.rules
def get_makefile_var(var):
    res = subprocess.run(["make", f"print-{var}"], check=True, capture_output=True)
    kv = res.stdout.decode('ascii').strip().split('=')
    assert len(kv) == 2
    assert kv[0] == var
    return kv[1]

# compute the sha256 checkum of a file
def sha256file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        # Read and update hash string value in blocks of 4K
        for data in iter(lambda: f.read(4096), b""):
            h.update(data)
        return h.hexdigest()

# download file at the given URL to path `dst`
# TODO: check at startup if `curl is present`
def download(url, dst):
    res = subprocess.run(["curl", "-L", "-C", "-", "-o", dst, url])
    if res.returncode != 0:
        error('failed downloading ' + url)

# Returns a boolean
def check_whether_git_tag_exists(tag):
    subprocess.run(["git", "fetch", "--tags"])
    res = subprocess.run(["git", "tag", "-l"],
                         capture_output=True,
                         text=True,
                         check=True)
    tags = res.stdout.split('\n')
    for s in tags:
        if tag == s:
            return True
    return False

# Returns a boolean
def check_whether_github_release_exists(tag):
    if CURRENT_REPO == None:
        print("CURRENT_REPO is not initialized. Call initialize_github first")
    releases = CURRENT_REPO.get_releases()
    for release in releases:
        if release.tag_name == tag:
            return True
    return False

# sets the global variables GITHUB_INSTANCE and CURRENT_REPO
# If no token is provided, this uses the value of the environment variable
# GITHUB_TOKEN.
def initialize_github(token=None):
    global GITHUB_INSTANCE, CURRENT_REPO
    if GITHUB_INSTANCE != None or CURRENT_REPO != None:
        error("Global variables GITHUB_INSTANCE and CURRENT_REPO "
              + " are already initialized.")
    if token == None and "GITHUB_TOKEN" in os.environ:
        token = os.environ["GITHUB_TOKEN"]
    if token == None:
        error("Error: no access token found or provided")
    g = github.Github(token)
    try:
        g.get_user().name
    except github.GithubException:
        error("Error: the access token may be incorrect")
    GITHUB_INSTANCE = g
    CURRENT_REPO = GITHUB_INSTANCE.get_repo(CURRENT_REPO_NAME)
