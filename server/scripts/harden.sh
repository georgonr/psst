#!/usr/bin/env bash
# Hardening servera podľa bežného štandardu (volá ho deploy.sh; dá sa spustiť aj samostatne, idempotentné).
#
#   sudo scripts/harden.sh
#
#  - admin používateľ so SSH kľúčom a sudo (ak sa nasadzuje ako root: vytvorí "psst" s kľúčmi roota)
#  - SSH: len kľúčom, root login vypnutý — LEN ak má admin aspoň jeden SSH kľúč (inak by ste sa zamkli)
#  - UFW: povolené len 22/tcp, 80/tcp, 443/tcp, 7881/tcp (LiveKit ICE/TCP), 7882/udp (médiá), 3478/udp (TURN)
#  - fail2ban (sshd), automatické bezpečnostné aktualizácie (unattended-upgrades)
# Pozn.: porty publikované Dockerom obchádzajú UFW — compose.yml preto publikuje verejne len 80, 443,
# 7881/tcp, 7882/udp a 3478/udp; Synapse a MAS admin API sú len na 127.0.0.1.
set -euo pipefail
log()  { printf '\033[1;34m[harden]\033[0m %s\n' "$*" >&2; }
warn() { printf '\033[1;33m[harden] VAROVANIE:\033[0m %s\n' "$*" >&2; }
[ "$(id -u)" = 0 ] || { echo "spustite cez sudo"; exit 1; }
[ -f /etc/debian_version ] || { warn "hardening podporuje Debian/Ubuntu — preskakujem"; exit 0; }
export DEBIAN_FRONTEND=noninteractive

log "balíky: ufw, fail2ban, unattended-upgrades"
apt-get update -qq
apt-get install -y -qq ufw fail2ban unattended-upgrades apt-listchanges >/dev/null

# ------------------------------------------------------------------ admin používateľ
ADMIN="${SUDO_USER:-}"
if [ -z "$ADMIN" ] || [ "$ADMIN" = root ]; then
  ADMIN=psst
  if ! id "$ADMIN" >/dev/null 2>&1; then
    log "vytváram admin používateľa '$ADMIN' (SSH kľúče prevezme od roota)"
    useradd -m -s /bin/bash -G sudo "$ADMIN"
  fi
  if [ -s /root/.ssh/authorized_keys ]; then
    install -d -m 700 -o "$ADMIN" -g "$ADMIN" "/home/$ADMIN/.ssh"
    touch "/home/$ADMIN/.ssh/authorized_keys"
    # doplní kľúče roota (bez duplikátov)
    sort -u "/home/$ADMIN/.ssh/authorized_keys" /root/.ssh/authorized_keys | grep -v '^\s*$' \
      | grep -v 'command=' > "/home/$ADMIN/.ssh/authorized_keys.new" || true
    mv "/home/$ADMIN/.ssh/authorized_keys.new" "/home/$ADMIN/.ssh/authorized_keys"
    chown "$ADMIN:$ADMIN" "/home/$ADMIN/.ssh/authorized_keys"; chmod 600 "/home/$ADMIN/.ssh/authorized_keys"
  fi
  # bez hesla (prihlásenie len kľúčom) → sudo bez hesla
  echo "$ADMIN ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/90-psst-admin; chmod 440 /etc/sudoers.d/90-psst-admin
  visudo -cq
fi
ADMIN_HOME="$(getent passwd "$ADMIN" | cut -d: -f6)"
KEYS="$(grep -cE '^(ssh-|ecdsa-|sk-)' "$ADMIN_HOME/.ssh/authorized_keys" 2>/dev/null || true)"

# ------------------------------------------------------------------ SSH
if [ "${KEYS:-0}" -ge 1 ]; then
  log "SSH: len kľúčom, root login vypnutý (admin: $ADMIN, kľúčov: $KEYS)"
  cat > /etc/ssh/sshd_config.d/10-psst.conf <<'SSH'
# PSST hardening (scripts/harden.sh) — prvá zhoda vyhráva, preto 10-
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
PubkeyAuthentication yes
PermitEmptyPasswords no
MaxAuthTries 3
LoginGraceTime 30
X11Forwarding no
AllowAgentForwarding no
SSH
  if sshd -t; then systemctl reload ssh 2>/dev/null || systemctl reload sshd 2>/dev/null || true
  else warn "sshd -t zlyhal — mažem PSST SSH konfiguráciu"; rm -f /etc/ssh/sshd_config.d/10-psst.conf; fi
else
  warn "používateľ $ADMIN nemá SSH kľúč → SSH heslá a root login NECHÁVAM zapnuté (inak by ste sa zamkli)."
  warn "Pridajte kľúč do $ADMIN_HOME/.ssh/authorized_keys a spustite scripts/harden.sh znova."
fi

# ------------------------------------------------------------------ UFW
log "UFW: deny incoming; povolené 22/tcp (limit), 80/tcp, 443/tcp, 7881/tcp, 7882/udp, 3478/udp"
ufw --force default deny incoming >/dev/null
ufw --force default allow outgoing >/dev/null
ufw limit 22/tcp comment 'SSH' >/dev/null
ufw allow 80/tcp comment "HTTP (Let's Encrypt, presmerovanie)" >/dev/null
ufw allow 443/tcp comment 'HTTPS + TURN/TLS' >/dev/null
ufw allow 7881/tcp comment 'LiveKit ICE/TCP' >/dev/null
ufw allow 7882/udp comment 'LiveKit media' >/dev/null
ufw allow 3478/udp comment 'TURN/UDP (coturn)' >/dev/null
# nginx (Docker sieť 172.30.0.0/24) → coturn v host sieti (TURN/TLS na 443 ukončený v nginx)
ufw allow from 172.30.0.0/24 to any port 3478 proto tcp comment 'nginx → coturn' >/dev/null
ufw --force enable >/dev/null

# ------------------------------------------------------------------ fail2ban
log "fail2ban: sshd jail"
cat > /etc/fail2ban/jail.d/psst.local <<'F2B'
[DEFAULT]
bantime = 1h
findtime = 10m
maxretry = 5
backend = systemd

[sshd]
enabled = true
F2B
systemctl enable --now fail2ban >/dev/null 2>&1 || true
systemctl restart fail2ban >/dev/null 2>&1 || true

# ------------------------------------------------------------------ automatické aktualizácie
log "unattended-upgrades: bezpečnostné aktualizácie denne, reštart (ak treba) o 04:30"
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'APT'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
APT
cat > /etc/apt/apt.conf.d/52psst-unattended <<'APT'
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "04:30";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
APT
systemctl enable --now unattended-upgrades >/dev/null 2>&1 || true

log "hotovo (admin: $ADMIN). Prihlasujte sa: ssh $ADMIN@<IP>"
