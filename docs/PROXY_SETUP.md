# Proxy Setup Guide

To avoid rate limits when fetching large batches of tickers, `equiquant` supports proxy rotation. This guide explains how to set up your own proxies using Oracle Cloud (or any VPS) and Tailscale.

## Option 1: Standard Proxy (Tinyproxy)

This is the most lightweight method for a standard VPS.

### 1. Install Tinyproxy
On your Linux server:
```bash
sudo apt update
sudo apt install tinyproxy -y
```

### 2. Configure Access
Edit `/etc/tinyproxy/tinyproxy.conf`:
```bash
sudo nano /etc/tinyproxy/tinyproxy.conf
```
Add your local IP to the allow list:
```text
Allow 127.0.0.1
Allow <YOUR_HOME_IP>
```

### 3. Open Firewall
Ensure port `8888` is open in your VPS provider's dashboard (e.g., Oracle Cloud Security Lists).

### 4. Usage
Add to your `.env`:
```text
PROXIES=http://<SERVER_IP>:8888
```

---

## Option 2: Tailscale Exit Nodes (Secure & Easy)

If you use Tailscale, you don't need to open any ports to the public internet.

### 1. Set up the Oracle Machine as an Exit Node
On the Oracle machine:
```bash
# Advertise as an exit node
sudo tailscale up --advertise-exit-node
```
In the **Tailscale Admin Console**, find the machine, click "Edit Route Settings," and check **"Exit Node"**.

### 2. Set up a Proxy on the Oracle Machine
Even with Tailscale, you still need a "Proxy Server" (like Tinyproxy) running on that machine to send specific HTTP requests through it, OR you can route your *entire* local traffic through it.

#### To use it specifically for `equiquant` without routing all your PC traffic:
1. Install Tinyproxy on the Oracle machine (as shown in Option 1).
2. Instead of allowing your Home IP, allow the **Tailscale IP range**:
   ```text
   # In /etc/tinyproxy/tinyproxy.conf
   Allow 100.64.0.0/10
   ```
3. Use the **Tailscale IP** of the Oracle machine in your `.env`:
   ```text
   PROXIES=http://100.x.y.z:8888
   ```

**Benefits of Tailscale:**
- No need to open ports in Oracle Cloud.
- Traffic is encrypted.
- No need to update "Allow" lists if your Home IP changes.

---

## Multiple Proxies
You can rotate through multiple servers by comma-separating them:
```text
PROXIES=http://ip1:8888,http://ip2:8888,http://ip3:8888
```
The `ProxyManager` will switch to the next proxy in the list for every batch of tickers.
