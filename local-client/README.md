# Run the lab's client on your own machine

These files set up a Gnosis VPN client on your machine exactly like the lab's client: same package
(gnosisvpn 1.1.0), same configuration, the lab exit pinned, and payment channels only to the three lab
relays. You then run the same connect-and-download test and check from your own log that only the lab
relays carried the session.

They belong to the lab deployment of 2026-11-21. The lab's machines are deleted on
**2026-11-23 22:30 UTC**; after that the exit and relays in `config.toml` no longer exist.

## What you need

- A Debian or Ubuntu machine (x86-64 or arm64) where you have root. I have only run this on
  Ubuntu 24.04. The package also exists for macOS, but its paths differ and nothing here was tested there.
- About **120.4 wxHOPR and 0.005 xDAI** on Gnosis Chain for the new client. Of that, 10 wxHOPR is the
  one-time fee to register the node, 45 goes into three channels (15 per relay) and 35.35 into the
  payment pool. Each connection then pays the exit 5.94 wxHOPR up front.
- `curl`, `jq`, `python3`.

Know before you start:

- **Connecting routes all traffic of the machine through the VPN** and installs a killswitch that
  drops everything else, including incoming SSH from public addresses. Run this at the machine, or
  over a private network. Private address ranges stay reachable.
- The funds end up in a Safe that only this client's key controls. Back the key up (step 4) before
  you send anything.

## Files

| File | Goes to | Purpose |
| --- | --- | --- |
| `config.toml` | `/etc/gnosisvpn/config.toml` | The lab client's configuration: pinned exit, relay allowlist |
| `lab-log.env` | `/etc/gnosisvpn/lab-log.env` | Log filter: the path planner at debug level, needed for the check in step 8 |
| `10-lab-log.conf` | `/etc/systemd/system/gnosisvpn.service.d/` | Makes the service read `lab-log.env` |
| `connect-stall-test.py` | anywhere | The measurement: connect, download at once, time every interruption |
| `check-paths.py` | anywhere | Reads your client's log and checks that only the lab relays were used |

## Steps

Run them from the folder that holds these files.

### 1. Install the pinned package

```bash
curl -fsSL https://download.vpn.gnosis.eth.limo/linux/install.sh -o install.sh
echo "59add2768da0ab42073978dfebf75b677b986a9fb4f7e59e1390a62587db506b  install.sh" | sha256sum -c -
sudo bash install.sh --channel=stable --network=piz-palu-prod

curl -fsSL -o gnosisvpn_1.1.0_amd64.deb \
  https://download.gnosisvpn.io/linux/apt/pool/main/g/gnosisvpn/gnosisvpn_1.1.0_amd64.deb
echo "c944e294c408916d21a62e29262af52d5f0f66fe6715056d33c1f407559d7712  gnosisvpn_1.1.0_amd64.deb" | sha256sum -c -
sudo GNOSISVPN_NETWORK=piz-palu-prod GNOSISVPN_HOPR_BLOKLI_URL=https://blokli.piz-palu.gnosisvpn.io \
  apt-get install -y --allow-downgrades -o Dpkg::Options::=--force-confold ./gnosisvpn_1.1.0_amd64.deb
gnosis_vpn-ctl --version        # must print 1.1.0
```

Both `sha256sum` lines must print `OK`. The hashes are for the installer as served on 2026-11-21 and
for the amd64 package; on arm64 take the arm64 package and skip its hash line.

### 2. Put the lab configuration in place

The package links `config.toml` to its own preset; replace the link with the lab's file.

```bash
sudo rm -f /etc/gnosisvpn/config.toml
sudo install -m 644 config.toml /etc/gnosisvpn/config.toml
sudo install -m 644 lab-log.env /etc/gnosisvpn/lab-log.env
sudo mkdir -p /etc/systemd/system/gnosisvpn.service.d
sudo install -m 644 10-lab-log.conf /etc/systemd/system/gnosisvpn.service.d/10-lab-log.conf
sudo systemctl daemon-reload
sudo systemctl restart gnosisvpn
```

### 3. Start the client and read what it asks for

The worker runs under your own user, not root.

```bash
gnosis_vpn-ctl start-client 30m
sleep 20
gnosis_vpn-ctl -o json status | jq '.data.run_mode'
```

You should see `"type": "preparing_safe"`, a `node_address`, and a `balance_recommendation`. With this
configuration the lab client asked for 120.35 wxHOPR (`wxhopr` is in wei: 120350000000927277980) and
0.005 xDAI. A much larger wxHOPR figure means `config.toml` was not picked up.

The worker stops itself 30 minutes after the last `gnosis_vpn-ctl` command (not counting `info` and
`ping`); `start-client 30m` starts it again.

### 4. Back up the client's key

```bash
mkdir -m 700 -p ~/gnosisvpn-key-backup
cp -p ~/.local/share/gnosisvpn/networks/piz-palu-prod/hopr.id \
      ~/.local/share/gnosisvpn/networks/piz-palu-prod/hopr.pass ~/gnosisvpn-key-backup/
```

Copy that folder somewhere off the machine too. Without these two files the funds cannot be recovered.

### 5. Fund the node address

Send the recommended wxHOPR (plus a little margin, for example 120.4) and 0.006 xDAI on Gnosis Chain
to the **`node_address`** from step 3. Do not send to a Safe address: the client creates its own Safe
from what arrives at the node address. wxHOPR is `0xD4fdec44DB9D44B8f2b6d529620f9C0C7066A2c1`.

### 6. Wait until the lab exit is routable

```bash
watch -n 10 "gnosis_vpn-ctl -o json status | jq -c '{mode: .data.run_mode.type, lab: [.data.destinations[] | select(.destination.id==\"lab\") | .route_health.state.type][0]}'"
```

It goes through `deploying_safe` and `warmup` to `running`; then `lab` turns `routable`. In the lab
this took about 3 minutes after funding. Then check the channels:

```bash
gnosis_vpn-ctl -o json balance | jq -r '.data.channels_out[].address'
```

Exactly these three must be listed, and nothing else:

```
0xc8e2fAF5B2D4afd01f5CA86666f04045199926cD   relay1
0x826d7d57A992eDe72e0dA79176E4cF3731a7f0DC   relay2
0x6bc768EA0e3F0F42042718A70d0984842fe32A52   relay3
```

### 7. Run the test

Same measurement as in the lab: it issues `connect lab`, starts a 100 MB download the moment the client
is connected, samples the download every 0.1 s, and prints one JSON object. Run it as your own user.

```bash
python3 connect-stall-test.py "$USER" lab https://fsn1-speed.hetzner.com/100MB.bin | tee iteration-1.json
jq '{connect_seconds, download, stalls, stalled_seconds}' iteration-1.json
gnosis_vpn-ctl disconnect
```

For three iterations, as in the lab, repeat with `iteration-2.json` and `iteration-3.json`, waiting
about 30 seconds after each `disconnect`. Every connection costs 5.94 wxHOPR from the client's pool.

While connected, `curl -4 https://api.ipify.org` must print the lab exit's public address.

### 8. Check that only the lab relays were used

```bash
python3 check-paths.py
```

It reads today's worker log (`~/.local/state/gnosisvpn/worker.log.<date>`, UTC date) and must end with
`RESULT: only the lab relays appear in every path to and from the lab exit`. A foreign relay, or no
planner lines at all, makes it fail. If you ran the test before midnight UTC and check after, pass the
log file as an argument.

Note what this does and does not show: all relayed, paid traffic of the session goes through the three
relays. Like the lab client, your client still keeps direct connections to the other nodes of the
network and sends them unpaid probe packets.

### 9. Send back the results

Send me `iteration-*.json` and the output of `check-paths.py`, and say what kind of line the machine is
on. I will record the run under `results/` next to the lab's own numbers.

## What the lab measured, for comparison

Client, relays and exit all in one data centre, three iterations:

| | Lab client |
| --- | --- |
| `connect` issued until connected | 5.1 to 6.4 s |
| Download runs before it stops | about 17 s (after 13.3 MB) |
| Interruption | 13.2 to 16.6 s |
| 100 MB download, total | about 77 s |
| Rate once it flows | 23 to 28 Mbit/s, later about 12 Mbit/s |

## Afterwards

- `gnosis_vpn-ctl disconnect` and `gnosis_vpn-ctl stop-client` end the session and the worker.
- To go back to the stock configuration: `sudo ln -sf /etc/gnosisvpn/config-piz-palu-prod.toml
  /etc/gnosisvpn/config.toml`, remove the two log files from step 2, and restart the service.
- Getting the funds back is manual: close the three channels, wait 300 seconds, then move the wxHOPR
  out of the client's Safe with a Safe transaction signed by the backed-up key. Ask me and I will do
  it with you; it is not automated.
