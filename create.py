''' This script must be executed by Python3 '''

import sys
from datetime import date
import lxc
import os
import tarfile
import shutil
import utils
import re

lxc_config_template = "config-template"
lxc_mac_prefix = "00:16:3e:c8:6a:"
lxc_ipv4_prefix = "10.0.3."
lxc_ipv4_mask = "24"
lxc_arch = "amd64"
lxc_net_if = "lxcbr0"
lxc_root = "/lxc"

current_uid = os.getuid()
if current_uid != 0:
    print("This script must be ran as root or with sudo.")
    sys.exit(1)

arguments = sys.argv
if len(arguments) < 3:
    print("Usage : create.py <name> <template-archive>")
    sys.exit(1)

template_archive = arguments[2]

if not os.path.isfile(template_archive):
    print("Template archive '%s' does not exist." % template_archive)
    sys.exit(1)

if not tarfile.is_tarfile(template_archive):
    print("Template archive '%s' is not a tar file." % template_archive)
    sys.exit(1)

container_name = arguments[1]
lxc_hostname = container_name + ".lxc"
lxc_path = lxc_root + "/" + container_name

if os.path.isdir(lxc_path):
    print("LXC directory '%s' already exists." % lxc_path)
    overwrite = input('Remove existing directory ? y/N')
    if str(overwrite).lower() != 'y':
        print("Aborting.")
        sys.exit(1)
    else:
        shutil.rmtree(lxc_path)

os.mkdir(lxc_path)
print("Extracting template ...")
archive = tarfile.open(template_archive)
archive.extractall(lxc_path)

ipv4_last_bytes = []
hosts = open("/etc/hosts", "r+")
for line in hosts:
    match = re.match(re.escape(lxc_ipv4_prefix) + "([0-9]{1,3})", line)
    if match:
        ipv4_last_bytes.append(match.group(1))

ipv4_last_bytes.sort()
ipv4_last_byte = int(ipv4_last_bytes.pop()) + 1

custom_ipv4_last_byte = input("IPv4 last byte [%d] ? " % ipv4_last_byte)
if str(custom_ipv4_last_byte).isnumeric() and 1 < custom_ipv4_last_byte < 255:
    ipv4_last_byte = custom_ipv4_last_byte

mac_last_group = hex(int(ipv4_last_byte))[2:]

lxc_mac_address = lxc_mac_prefix + mac_last_group
lxc_ipv4 = lxc_ipv4_prefix + str(ipv4_last_byte)
lxc_ipv4_with_mask = lxc_ipv4 + "/" + lxc_ipv4_mask

lxc_config_dir = "/var/lib/lxc/" + container_name
os.mkdir(lxc_config_dir)

config_path = lxc_config_dir + '/config'
shutil.copyfile(lxc_config_template, config_path)
''' TODO: Remove .lxc suffit from LXC name and add it to search domain in resolv.conf '''
utils.replaceAll(config_path, '{{CONTAINER_NAME}}', container_name)
utils.replaceAll(config_path, '{{IPV4}}', lxc_ipv4)
utils.replaceAll(config_path, '{{NET_IF}}', lxc_net_if)
utils.replaceAll(config_path, '{{MAC_ADDRESS}}', lxc_mac_address)
utils.replaceAll(config_path, '{{ARCH}}', lxc_arch)

hosts.write(lxc_ipv4 + " " + lxc_hostname + " # Auto-generated on %s.\n" % date.today())
hosts.close()

lxc_hostname_file = open(lxc_path + "/etc/hostname", "w")
lxc_hostname_file.write(lxc_hostname + "\n")
lxc_hostname_file.close()

lxc_config = open(config_path, 'r+')

autostart = input("Autostart LXC at boot ? ")
if autostart:
    lxc_config.write("\n # Autostarting LXC\nlxc.start.auto = 1\nlxc.start.delay = 5\n")

c = lxc.Container(container_name)

print("Starting container ...")
if not c.start():
    print("Failed to start the container", file=sys.stderr)
    sys.exit(1)

print("Running apt-get update ...")
c.attach_wait(lxc.attach_run_command, ["apt-get", "update"])

print("All done !")

