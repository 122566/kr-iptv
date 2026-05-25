#!/usr/bin/env python3
import subprocess
import sys
import os
import re
import time
from datetime import datetime

SOURCES = [
    "https://iptv-org.github.io/iptv/countries/kr.m3u",
    "https://iptv-org.github.io/iptv/languages/kor.m3u",
]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
M3U_FILE = os.path.join(SCRIPT_DIR, "kr_live.m3u")
LOG_FILE = os.path.join(SCRIPT_DIR, "update.log")

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def fetch_m3u(url):
    try:
        result = subprocess.run(
            ["curl", "-s", "-L", "--connect-timeout", "15", "--max-time", "30", url],
            capture_output=True, text=True, timeout=35
        )
        return result.stdout
    except Exception as e:
        log(f"  Failed to fetch {url}: {e}")
        return ""

def parse_m3u(content):
    channels = []
    current_extinf = ""
    current_extras = []
    
    for line in content.strip().split('\n'):
        line = line.strip()
        if line.startswith('#EXTM3U'):
            continue
        elif line.startswith('#EXTINF:'):
            current_extinf = line
            current_extras = []
        elif line.startswith('#EXTVLCOPT:'):
            current_extras.append(line)
        elif line.startswith('http'):
            channels.append({
                'extinf': current_extinf,
                'extras': current_extras[:],
                'url': line
            })
            current_extinf = ""
            current_extras = []
    return channels

def check_url(url, idx):
    tmpfile = os.path.join(SCRIPT_DIR, f"_check_{idx}.tmp")
    try:
        result = subprocess.run(
            ['curl', '-s', '-o', tmpfile, '-w', '%{http_code}',
             '--connect-timeout', '10', '--max-time', '15', '-L', url],
            capture_output=True, text=True, timeout=20
        )
        http_code = result.stdout.strip()
    except subprocess.TimeoutExpired:
        http_code = '000'
    except Exception:
        http_code = '000'
    
    valid = False
    if http_code in ('200', '206'):
        try:
            with open(tmpfile, 'r', encoding='utf-8', errors='ignore') as f:
                for _ in range(5):
                    fl = f.readline().strip()
                    if fl.startswith('#EXTM3U') or fl.startswith('#EXT-X') or fl.startswith('#EXTINF'):
                        valid = True
                        break
        except:
            pass
    
    try:
        os.remove(tmpfile)
    except:
        pass
    
    return http_code, valid

def generate_m3u(channels):
    with open(M3U_FILE, 'w', encoding='utf-8') as f:
        f.write("#EXTM3U\n")
        f.write(f"# Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC\n")
        f.write(f"# Channels: {len(channels)}\n")
        for ch in channels:
            f.write(ch['extinf'] + '\n')
            f.write('#EXTVLCOPT:network-caching=10000\n')
            f.write('#EXTVLCOPT:http-reconnect=true\n')
            f.write('#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36\n')
            for extra in ch['extras']:
                f.write(extra + '\n')
            f.write(ch['url'] + '\n')

def main():
    log("=" * 60)
    log("Starting Korea IPTV M3U update")
    log("=" * 60)
    
    all_channels = []
    seen_urls = set()
    
    for src in SOURCES:
        log(f"Fetching: {src}")
        content = fetch_m3u(src)
        if not content:
            continue
        channels = parse_m3u(content)
        log(f"  Parsed {len(channels)} channels")
        for ch in channels:
            if ch['url'] not in seen_urls:
                seen_urls.add(ch['url'])
                all_channels.append(ch)
    
    log(f"Total unique channels: {len(all_channels)}")
    log("Testing channels...")
    
    playable = []
    down = []
    
    for i, ch in enumerate(all_channels):
        extinf = ch['extinf']
        last_comma = extinf.rfind(',')
        name = extinf[last_comma+1:].strip() if last_comma != -1 else f"Channel {i+1}"
        
        http_code, valid = check_url(ch['url'], i)
        
        if http_code in ('200', '206') and valid:
            playable.append(ch)
            status = "OK"
        else:
            down.append(ch)
            status = "DOWN"
        
        log(f"  [{i+1}/{len(all_channels)}] {name[:45]:45s} {status} (HTTP {http_code})")
    
    log(f"\nPlayable: {len(playable)} | Down: {len(down)}")
    
    generate_m3u(playable)
    log(f"Generated: {M3U_FILE}")
    log("Update complete!")

if __name__ == "__main__":
    main()
