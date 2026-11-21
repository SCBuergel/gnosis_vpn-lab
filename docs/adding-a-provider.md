# Adding a cloud provider

The lab needs very little from a cloud, and all of it is behind the `Provider` protocol in
[`vpnlab/providers/__init__.py`](../vpnlab/providers/__init__.py). Everything else (SSH, installs,
funding, verification) is provider-independent and works on any Ubuntu 24.04 machine with root SSH.

## What a provider must do

| Method | Contract |
| --- | --- |
| `create(name, tag, ssh_public_key)` | Create one machine named `<tag>-<name>` that carries the tag and accepts root SSH with the key, without any interactive step. It must install the packages in `digitalocean.PACKAGES`, enable `chrony`, and create `/var/lib/vpn-lab-ready` when first boot is done. Return a `Machine`. |
| `list(tag)` | Return every machine with the tag, with current public and private IPv4 addresses. |
| `delete(machine, tag)` | Delete one machine. Refuse a machine that does not carry the tag. A machine that is already gone is not an error. |
| `hourly_price()` | USD per machine-hour, or `None`. |

Network requirements the provider must satisfy:

- **Public IPv4 on every machine.** The relays announce it on chain.
- **Inbound UDP and TCP 9091 on the relays**, and inbound SSH (TCP 22) from the operator.
  DigitalOcean droplets have no firewall by default; a provider with default-deny rules must open these.
- **A private network shared by all five machines.** The CLI reaches the client through the first
  relay's private address, because the VPN's killswitch cuts SSH from public addresses.
- **The exit's uplink interface is assumed to be `eth0`** in
  [`remote/exit-wg-hooks.sh`](../remote/exit-wg-hooks.sh). Change it there if the image names it differently.

## Steps

1. Add `vpnlab/providers/<name>.py` with a class implementing the four methods and a
   `from_settings(settings)` constructor. `digitalocean.py` is about 100 lines and a good model.
2. Register it in `PROVIDERS` in `vpnlab/providers/__init__.py`.
3. Add a `[providers.<name>]` section to `lab.toml` with whatever the class needs (credentials file,
   region, machine size, image) and set `[lab] provider = "<name>"`.
4. Add a test for the mapping from the provider's machine description to `Machine`, like
   `test_digitalocean_droplet_becomes_a_machine`.

## Notes for AWS

Not implemented. What an AWS provider would need, from the cost comparison in
[research.md](research.md) (Addendum A):

- **Instance:** `c6a.xlarge` (4 vCPU, 8 GB) is the nearest match to DigitalOcean's `c-4`.
- **Extras that DigitalOcean includes:** a security group opening 22 and 9091, a public IPv4 per
  instance (billed hourly), a gp3 root volume of about 30 GB, and a subnet all instances share.
- **Tagging:** tag instances at launch (`TagSpecifications`) and filter on that tag in `list`.
- **First boot:** the same cloud-init user data works; Ubuntu AMIs log in as `ubuntu`, so either
  enable root SSH in the user data or make the SSH user a provider setting in `vpnlab/ssh.py`.
- **Quota:** five machines need 20 vCPUs; new accounts often start below that.
