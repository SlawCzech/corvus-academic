#!/usr/bin/env bash
# One-time preparation of a fresh Ubuntu 24.04 VPS for Corvus. Run as root,
# or with sudo from the provider's first user (`ubuntu` on OVH):
#
#   scp infra/deploy/setup-server.sh ubuntu@<ip>:
#   ssh ubuntu@<ip> 'sudo bash setup-server.sh'
#
# What it does, in order — each step safe to repeat:
#   1. a `deploy` user with your SSH keys (the sudo caller's, or root's) and
#      the docker group; the account GitHub Actions logs in as;
#   2. SSH by key only — no passwords, no root login (log in as `deploy`
#      and use sudo from now on);
#   3. firewall: 22, 80, 443 in, nothing else;
#   4. automatic security updates;
#   5. Docker (from Docker's own apt repository), gpg, and rclone from rclone.org;
#   6. /srv/corvus, the backup passphrase, and the daily backup at 03:15.
#
# Before running it: make sure you log in with your key, not a password.
# After step 2 a password will no longer get you in.
set -euo pipefail

[ "$(id -u)" -eq 0 ] || { echo "run as root (or with sudo)" >&2; exit 1; }

# Whose keys `deploy` inherits: the user who ran sudo, else root.
if [ -n "${SUDO_USER:-}" ] && [ "$SUDO_USER" != root ]; then
    KEYS="$(getent passwd "$SUDO_USER" | cut -d: -f6)/.ssh/authorized_keys"
else
    KEYS=/root/.ssh/authorized_keys
fi
[ -s "$KEYS" ] || {
    echo "no $KEYS — add your SSH key first (ssh-copy-id), or you will lock yourself out" >&2
    exit 1
}

export DEBIAN_FRONTEND=noninteractive
# Ubuntu's needrestart would otherwise stop and ask which services to restart.
export NEEDRESTART_MODE=a
apt-get update -q
apt-get upgrade -yq

# 1. deploy user
if ! id deploy >/dev/null 2>&1; then
    adduser --disabled-password --gecos "" deploy
fi
install -d -m 700 -o deploy -g deploy /home/deploy/.ssh
install -m 600 -o deploy -g deploy "$KEYS" /home/deploy/.ssh/authorized_keys
echo "deploy ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/deploy
chmod 440 /etc/sudoers.d/deploy

# 2. SSH: keys only
cat > /etc/ssh/sshd_config.d/10-corvus.conf <<'CONF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
CONF
systemctl reload ssh 2>/dev/null || systemctl restart ssh

# 3. firewall. Docker's published ports bypass ufw — which is why the
# production compose publishes nothing but Caddy's 80 and 443.
apt-get install -yq ufw
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp
ufw --force enable

# 4. security updates, applied nightly; reboots at 04:30 when a kernel needs it
apt-get install -yq unattended-upgrades
cat > /etc/apt/apt.conf.d/52corvus-unattended <<'CONF'
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "04:30";
CONF
dpkg-reconfigure -f noninteractive unattended-upgrades

# 5. Docker, gpg, rclone
if ! command -v docker >/dev/null; then
    apt-get install -yq ca-certificates curl
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    # shellcheck disable=SC1091
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update -q
    apt-get install -yq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
usermod -aG docker deploy
# Container logs are otherwise kept forever and fill the disk.
cat > /etc/docker/daemon.json <<'CONF'
{ "log-driver": "json-file", "log-opts": { "max-size": "20m", "max-file": "5" } }
CONF
systemctl restart docker
apt-get install -yq gnupg
# rclone from rclone.org, not Ubuntu's: the archive's 1.60 (2022) answers
# R2 uploads with 501 Not Implemented on the first attempt.
if ! rclone version 2>/dev/null | head -1 | grep -qvE 'v1\.(5|6)[0-9]\.'; then
    apt-get remove -yq rclone >/dev/null 2>&1 || true
    curl -fsSL -o /tmp/rclone.deb https://downloads.rclone.org/rclone-current-linux-amd64.deb
    dpkg -i /tmp/rclone.deb
    rm -f /tmp/rclone.deb
fi

# 6. the app's directory, backup passphrase, daily backup
install -d -m 750 -o deploy -g deploy /srv/corvus /srv/corvus/backups
if [ ! -s /srv/corvus/.backup-passphrase ]; then
    openssl rand -base64 32 > /srv/corvus/.backup-passphrase
    chown deploy:deploy /srv/corvus/.backup-passphrase
    chmod 600 /srv/corvus/.backup-passphrase
    echo
    echo ">>> Backup passphrase — put it in your password manager NOW:"
    cat /srv/corvus/.backup-passphrase
    echo
fi
cat > /etc/cron.d/corvus-backup <<'CONF'
15 3 * * * deploy /srv/corvus/backup.sh >> /srv/corvus/backups/backup.log 2>&1
CONF

echo "setup: done. From now on: ssh deploy@$(hostname -I | awk '{print $1}')"
