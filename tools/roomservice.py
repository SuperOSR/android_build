#!/usr/bin/env python
# Copyright (C) 2012 The CyanogenMod Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import sys
import urllib2
import json
import re
from xml.etree import ElementTree

product = sys.argv[1];

if len(sys.argv) > 2:
    depsonly = sys.argv[2]
else:
    depsonly = None

try:
    device = product[product.index("_") + 1:]
except:
    device = product

if not depsonly:
    print "Device %s not found. Attempting to retrieve device repository:" % device

repositories = []

local_manifests = r'.repo/local_manifests'
if not os.path.exists(local_manifests): os.makedirs(local_manifests)

def exists_in_tree(lm, repository):
    for child in lm.getchildren():
        if child.attrib['name'].endswith(repository):
            return True
    return False

# in-place prettyprint formatter
def indent(elem, level=0):
    i = "\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent(elem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

def get_from_manifest(devicename):
    try:
        lm = ElementTree.parse(".repo/local_manifests/local_manifest.xml")
        lm = lm.getroot()
    except:
        lm = ElementTree.Element("manifest")

    for localpath in lm.findall("project"):
        if re.search("android_device_.*_%s$" % device, localpath.get("name")):
            return localpath.get("path")

    # Devices originally from AOSP are in the main manifest...
    try:
        mm = ElementTree.parse(".repo/manifest.xml")
        mm = mm.getroot()
    except:
        mm = ElementTree.Element("manifest")

    for localpath in mm.findall("project"):
        if re.search("android_device_.*_%s$" % device, localpath.get("name")):
            return localpath.get("path")

    return None

def get_project_from_path_in_manifest(target_path):
    try:
        mm = ElementTree.parse(".repo/manifest.xml")
        mm = mm.getroot()
    except:
        mm = ElementTree.Element("manifest")

    for project in mm.findall("project"):
        if project.get("path") == target_path:
            return project

    return None

def get_from_device_manifest(devicename):
    try:
        dm = ElementTree.parse("android/devices.xml")
        dm = dm.getroot()
    except:
        dm = ElementTree.Element("manifest")

    for localpath in dm.findall("project"):
        if re.search("android_device_.*_%s$" % device, localpath.get("name")):
            return localpath

    return None

def is_in_manifest(projectname):
    try:
        lm = ElementTree.parse(".repo/local_manifests/local_manifest.xml")
        lm = lm.getroot()
    except:
        lm = ElementTree.Element("manifest")

    for localpath in lm.findall("project"):
        if localpath.get("name") == projectname:
            return 1

    return None

def add_to_manifest(repositories, fallback_branch = None):
    try:
        mm = ElementTree.parse(".repo/local_manifests/local_manifest.xml")
        mm = mm.getroot()
    except:
        mm = ElementTree.Element("manifest")

    # Local Manifest
    try:
        lm = ElementTree.parse(".repo/local_manifests/local_manifest.xml")
        lm = lm.getroot()
    except:
        lm = ElementTree.Element("manifest")

    for repository in repositories:
        repo_name = repository['repository']
        repo_target = repository['target_path']
        mmproj = get_project_from_path_in_manifest(repo_target)
        if mmproj != None:
            print 'Found %s already defined in main manifest as %s' % (repo_target, mmproj.get("name"))
            print 'Adding remove-project: %s -> %s' % (mmproj.get("name"), repo_target)
            project = ElementTree.Element("remove-project", attrib = { "path": repo_target,
                "remote": "github", "name": mmproj.get("name"), "revision": "jb43" })

            if mmproj.get('remote') != None:
                project.set('remote',mmproj.get('remote'))

            if mmproj.get('revision') != None:
                project.set('revision',mmproj.get('revision'))

            lm.append(project)

        if exists_in_tree(lm, repo_name):
            print '%s already exists' % (repo_name)
            continue

        print 'Adding dependency: %s -> %s' % (repo_name, repo_target)
        project = ElementTree.Element("project", attrib = { "path": repo_target,
            "remote": "github", "name": repo_name, "revision": "jb43" })

        if 'branch' in repository:
            project.set('revision',repository['branch'])
        elif fallback_branch:
            print("Using fallback branch %s for %s" % (fallback_branch, repo_name))
            project.set('revision', fallback_branch)
        else:
            print("Using default branch for %s" % repo_name)

        lm.append(project)

    indent(lm, 0)
    raw_xml = ElementTree.tostring(lm)
    raw_xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + raw_xml

    f = open('.repo/local_manifests/local_manifest.xml', 'w')
    f.write(raw_xml)
    f.close()

def fetch_dependencies(repo_path, fallback_branch = None):
    print 'Looking for dependencies'

    syncable_repos = []

    dependencies_path = repo_path + '/osr.dependencies'
    if not os.path.exists(dependencies_path):
        print 'No osr.dependencies file in %s' % repo_path
        dependencies_path = repo_path + '/cm.dependencies'

    if os.path.exists(dependencies_path):
        print 'Using %s' % dependencies_path
        dependencies_file = open(dependencies_path, 'r')
        dependencies = json.loads(dependencies_file.read())

        fetch_list = []

        for dependency in dependencies:
            if dependency['repository'] == None or dependency['repository'] == "github": 
                if not "/" in dependency['repository']:
                    dependency['repository'] = "CyanogenMod/%s" % dependency['repository']

            if not is_in_manifest(dependency['repository']):
                fetch_list.append(dependency)
                syncable_repos.append(dependency['target_path'])

        dependencies_file.close()

        if len(fetch_list) > 0:
            print 'Adding dependencies to manifest'
            add_to_manifest(fetch_list, fallback_branch)
    else:
        print 'Dependencies file not found, bailing out.'

    if len(syncable_repos) > 0:
        print 'Syncing dependencies'
        os.system('repo sync %s' % ' '.join(syncable_repos))

def has_branch(branches, revision):
    return revision in [branch['name'] for branch in branches]

if depsonly:
    repo_path = get_from_manifest(device)
    if repo_path:
        fetch_dependencies(repo_path)
    else:
        print "Trying dependencies-only mode on a non-existing device tree?"

    sys.exit()

else:

    obj = get_from_device_manifest(device)
    if obj != None:
        repo_path = obj.get("path")
        repo_name = obj.get("name")

        print "Found repository in devices.xml: %s" % repo_name

        add_to_manifest([{'repository':repo_name,'target_path':repo_path}])

        print "Syncing repository to retrieve project."
        os.system('repo sync %s' % repo_path)
        print "Repository synced!"

        fetch_dependencies(repo_path)
        print "Done"
        sys.exit()

    print "Not found in android/devices.xml (Check and try repo sync android, then rerun lunch)"
    print "Searching at CyanogenMod"
    page = 1
    while not depsonly:
        result = json.loads(urllib2.urlopen("https://api.github.com/users/CyanogenMod/repos?page=%d" % page).read())
        if len(result) == 0:
            break
        for res in result:
            repositories.append(res)
        page = page + 1

    for repository in repositories:
        repo_name = repository['name']
        if repo_name.startswith("android_device_") and repo_name.endswith("_" + device):
            print "Found repository: %s" % repository['name']
            manufacturer = repo_name.replace("android_device_", "").replace("_" + device, "")
            
            default_revision = get_default_revision()
            print("Default revision: %s" % default_revision)
            print("Checking branch info")
            githubreq = urllib.request.Request(repository['branches_url'].replace('{/branch}', ''))
            add_auth(githubreq)
            result = json.loads(urllib.request.urlopen(githubreq).read().decode())

            ## Try tags, too, since that's what releases use
            if not has_branch(result, default_revision):
                githubreq = urllib.request.Request(repository['tags_url'].replace('{/tag}', ''))
                add_auth(githubreq)
                result.extend (json.loads(urllib.request.urlopen(githubreq).read().decode()))
            
            repo_path = "device/%s/%s" % (manufacturer, device)
            adding = {'repository':repo_name,'target_path':repo_path}
            
            fallback_branch = None
            if not has_branch(result, default_revision):
                if os.getenv('ROOMSERVICE_BRANCHES'):
                    fallbacks = list(filter(bool, os.getenv('ROOMSERVICE_BRANCHES').split(' ')))
                    for fallback in fallbacks:
                        if has_branch(result, fallback):
                            print("Using fallback branch: %s" % fallback)
                            fallback_branch = fallback
                            break

                if not fallback_branch:
                    print("Default revision %s not found in %s. Bailing." % (default_revision, repo_name))
                    print("Branches found:")
                    for branch in [branch['name'] for branch in result]:
                        print(branch)
                    print("Use the ROOMSERVICE_BRANCHES environment variable to specify a list of fallback branches.")
                    sys.exit()

            add_to_manifest([adding], fallback_branch)

            print "Syncing repository to retrieve project."
            os.system('repo sync %s' % repo_path)
            print "Repository synced!"

            fetch_dependencies(repo_path, fallback_branch)
            print "Done"
            sys.exit()

print "Repository for %s not found in the CyanogenMod Github repository list. If this is in error, you may need to manually add it to your local_manifest.xml." % device
