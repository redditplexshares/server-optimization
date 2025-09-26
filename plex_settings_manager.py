#!/usr/bin/env python3
"""
Plex Server Settings Manager
Check and modify analysis/scanning settings across all Duck Plex servers
"""

import requests
import xml.etree.ElementTree as ET
import argparse
import os
import json
from datetime import datetime

# Configuration
KRONOS_BASE_URL = 'https://yellow-sky-1850.kronosapp.io/api/v1'
KRONOS_AUTH_TOKEN = '21|p9U7DSWgUGO0H7Y8v0I2QCAS6yXbtW9QvuClubA1c4fcef82'
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1419407731890192514/KvdnuYY54MTdF8wPbCQeLADvkszg-nbnveMBPoag3qKLa9YpY8TzDSP6lzz90-je1oF5"

# Server optimization cache directory
CACHE_DIR = '/data/server_optimize'
TOKEN_CACHE_FILE = '/data/server_optimize/plex_tokens.json'
PROCESSED_SERVERS_FILE = '/data/server_optimize/plex_processed.txt'

def load_token_cache():
    """Load cached server tokens from file"""
    try:
        if os.path.exists(TOKEN_CACHE_FILE):
            with open(TOKEN_CACHE_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_token_cache(cache):
    """Save server tokens to cache file"""
    try:
        # Ensure cache directory exists
        os.makedirs(CACHE_DIR, exist_ok=True)

        with open(TOKEN_CACHE_FILE, 'w') as f:
            json.dump(cache, f, indent=2)
    except Exception:
        pass

def get_cached_server_info(service_id, cache):
    """Get cached server info (token, host, port) if available"""
    return cache.get(str(service_id))

def cache_server_info(service_id, host, port, token, cache):
    """Cache server info for future use"""
    cache[str(service_id)] = {
        'host': host,
        'port': port,
        'token': token,
        'cached_at': datetime.now().isoformat()
    }

def test_plex_connection(host, port, token):
    """Test if Plex server is accessible with given token"""
    try:
        url = f'http://{host}:{port}/:/prefs?X-Plex-Token={token}'
        response = requests.get(url, timeout=5)
        return response.status_code == 200
    except Exception:
        return False

def get_all_plex_services():
    """Get all Plex services from Kronos API"""
    headers = {'Authorization': f'Bearer {KRONOS_AUTH_TOKEN}'}
    all_services = []
    page = 1

    while True:
        response = requests.get(
            f'{KRONOS_BASE_URL}/services?page={page}&per_page=100',
            headers=headers
        )
        data = response.json()
        services = data['data']
        if not services:
            break
        all_services.extend(services)
        page += 1

    # Filter all Plex services
    plex_services = []
    for service in all_services:
        if service['is_plex']:
            plex_services.append(service)

    return plex_services

# Plex doesn't need fresh tokens - use existing plex_token from service data

def get_plex_settings(host, port, token):
    """Get Plex server settings"""
    try:
        url = f'http://{host}:{port}/:/prefs?X-Plex-Token={token}'
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            root = ET.fromstring(response.text)
            settings = {}

            for setting in root:
                if setting.tag == 'Setting':
                    settings[setting.get('id')] = {
                        'label': setting.get('label', ''),
                        'value': setting.get('value', ''),
                        'default': setting.get('default', ''),
                        'type': setting.get('type', '')
                    }

            return settings
        return None
    except Exception as e:
        print(f"Error getting settings for {host}:{port} - {e}")
        return None

def set_plex_setting(host, port, token, setting_id, value):
    """Set a Plex server setting"""
    try:
        url = f'http://{host}:{port}/:/prefs?X-Plex-Token={token}'
        data = {setting_id: value}
        response = requests.put(url, data=data, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Error setting {setting_id}={value} on {host}:{port} - {e}")
        return False

def analyze_server_settings():
    """Analyze settings across all servers"""
    print("=" * 80)
    print("PLEX SERVER SETTINGS ANALYSIS")
    print("=" * 80)

    services = get_all_duck_plex_services()

    # Analysis settings we care about
    analysis_settings = [
        'GenerateBIFBehavior',           # Generate video preview thumbnails
        'GenerateIntroMarkerBehavior',   # Generate intro video markers
        'GenerateCreditsMarkerBehavior', # Generate credits video markers
        'GenerateAdMarkerBehavior',      # Generate ad video markers
        'GenerateVADBehavior',           # Generate voice activity data
        'GenerateChapterThumbBehavior',  # Generate chapter thumbnails
        'LoudnessAnalysisBehavior',      # Analyze audio tracks for loudness
        'MusicAnalysisBehavior',         # Analyze audio tracks for sonic features
        'ButlerTaskUpgradeMediaAnalysis', # Upgrade media analysis during maintenance
        'ButlerTaskDeepMediaAnalysis'    # Perform extensive media analysis during maintenance
    ]

    results = []

    for service in services:
        server_name = service['display_name']
        owner = service['user']['name']
        host = service['container_ip']
        port = service['container_port']
        token = service['plex_token']

        print(f"\nChecking: {server_name} ({owner})")

        settings = get_plex_settings(host, port, token)
        if settings:
            server_analysis = {
                'server_name': server_name,
                'owner': owner,
                'host': f"{host}:{port}",
                'settings': {}
            }

            disabled_count = 0
            for setting_id in analysis_settings:
                if setting_id in settings:
                    value = settings[setting_id]['value']
                    default = settings[setting_id]['default']
                    label = settings[setting_id]['label']

                    server_analysis['settings'][setting_id] = {
                        'label': label,
                        'value': value,
                        'default': default,
                        'disabled': value in ['never', '0'] and default not in ['never', '0']
                    }

                    if server_analysis['settings'][setting_id]['disabled']:
                        disabled_count += 1
                        print(f"  ❌ {label}: {value} (default: {default})")
                    else:
                        print(f"  ✅ {label}: {value}")

            server_analysis['disabled_count'] = disabled_count
            results.append(server_analysis)
        else:
            print(f"  ❌ Could not get settings")

    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")

    total_servers = len(results)
    servers_with_disabled = sum(1 for r in results if r['disabled_count'] > 0)

    print(f"Total servers checked: {total_servers}")
    print(f"Servers with disabled analysis features: {servers_with_disabled}")

    # Show servers with most disabled features
    results.sort(key=lambda x: x['disabled_count'], reverse=True)

    print(f"\nServers with disabled analysis features:")
    for result in results:
        if result['disabled_count'] > 0:
            print(f"  {result['server_name']} ({result['owner']}): {result['disabled_count']} disabled")

    return results

def send_discord_notification(message):
    """Send notification to Discord"""
    try:
        # Discord has a 2000 character limit, truncate if needed
        if len(message) > 1900:
            message = message[:1900] + "\n...[Message truncated - too many changes]"

        webhook_data = {
            "username": "Plex Optimization Bot",
            "avatar_url": "https://www.plex.tv/wp-content/themes/plex/assets/img/plex-logo.svg",
            "content": message
        }
        response = requests.post(DISCORD_WEBHOOK_URL, json=webhook_data, timeout=10)
        if response.status_code == 200 or response.status_code == 204:
            print(f"✅ Discord notification sent successfully")
        else:
            print(f"❌ Discord notification failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Discord notification error: {e}")

def reboot_plex_server(service):
    """Reboot Plex server after library changes"""
    try:
        headers = {'Authorization': f'Bearer {KRONOS_AUTH_TOKEN}'}

        # Check if this is a Plex server
        if not service.get('is_plex'):
            print(f"    ❌ Not a Plex server")
            return False

        # Try Plex-specific restart endpoint
        url = f'{KRONOS_BASE_URL}/services/{service["id"]}/plex/restart'
        response = requests.post(url, headers=headers, timeout=30)

        if response.status_code in [200, 202]:
            print(f"    ✅ Plex server reboot initiated for {service['display_name']}")
            return True
        else:
            # Fallback to general service restart
            url = f'{KRONOS_BASE_URL}/services/{service["id"]}'
            data = {"restart_at": "now"}
            response = requests.put(url, headers=headers, json=data, timeout=30)

            if response.status_code in [200, 202]:
                print(f"    ✅ Server reboot initiated for {service['display_name']}")
                return True
            else:
                print(f"    ❌ Reboot failed for {service['display_name']}: {response.status_code}")
                return False

    except Exception as e:
        print(f"    ❌ Reboot error for {service['display_name']}: {e}")
        return False

def is_new_server(service, hours_threshold=72):
    """Check if server is new (created within last X hours)"""
    try:
        created_at = service.get('created_at')
        if created_at:
            from datetime import datetime, timedelta
            created_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            threshold_time = datetime.now() - timedelta(hours=hours_threshold)
            return created_time > threshold_time
    except Exception:
        pass
    return True

def is_server_processed(service_id):
    """Check if server has been processed (stored in local file)"""
    try:
        if os.path.exists(PROCESSED_SERVERS_FILE):
            with open(PROCESSED_SERVERS_FILE, 'r') as f:
                processed_servers = set(line.strip() for line in f.readlines())
                return str(service_id) in processed_servers
    except Exception:
        pass
    return False

def mark_server_processed(service_id, service_name):
    """Mark server as processed in local file"""
    try:
        # Ensure cache directory exists
        os.makedirs(CACHE_DIR, exist_ok=True)

        with open(PROCESSED_SERVERS_FILE, 'a') as f:
            f.write(f"{service_id}\n")
        print(f"    📝 Server {service_id} marked as processed")
    except Exception:
        pass

def optimize_plex_server(service, token_cache):
    """Optimize a single Plex server with library-specific settings"""
    server_name = service['display_name']
    owner = service['user']['name']
    service_id = service.get('id')
    product_name = service.get('product_name', '').lower()
    is_baremetal = 'baremetal' in product_name or 'unlimited' in product_name

    print(f"\n🎬 Optimizing: {server_name} ({owner})")
    print(f"   Product: {service.get('product_name', 'Unknown')} {'[UNLIMITED/BAREMETAL]' if is_baremetal else ''}")

    # Try to get server info from cache first
    cached_info = get_cached_server_info(service_id, token_cache)
    host = None
    port = None
    token = None

    if cached_info:
        host = cached_info['host']
        port = cached_info['port']
        token = cached_info['token']

        print(f"   📁 Using cached connection info: {host}:{port}")

        # Test if cached token still works
        if test_plex_connection(host, port, token):
            print(f"   ✅ Cached token is valid")
        else:
            print(f"   ⚠️ Cached token failed, falling back to API data")
            cached_info = None

    # Fall back to API data if no cache or cache failed
    if not cached_info:
        host = service.get('container_ip')
        port = service.get('container_port')
        token = service.get('plex_token')

        if not token:
            print(f"   ❌ No Plex token available in service data")
            return 0, []

        print(f"   🔄 Using API token: {host}:{port}")

        # Cache the working connection info
        if host and port and token:
            cache_server_info(service_id, host, port, token, token_cache)

    if not host or not port:
        print(f"   ❌ Missing connection details")
        return 0, []

    # Recommended library-specific settings (DISABLE resource-heavy features)
    recommended_settings = {
        'GenerateBIFBehavior': 'never',             # DISABLE video preview thumbnails
        'GenerateIntroMarkerBehavior': 'never',     # DISABLE intro detection
        'GenerateCreditsMarkerBehavior': 'never',   # DISABLE credits detection
        'GenerateAdMarkerBehavior': 'never',        # DISABLE ad detection
        'GenerateVADBehavior': 'never',             # DISABLE voice activity data
        'GenerateChapterThumbBehavior': 'never',    # DISABLE chapter thumbnails
        'LoudnessAnalysisBehavior': 'never',        # DISABLE loudness analysis
        'MusicAnalysisBehavior': 'never',           # DISABLE sonic analysis
        'ButlerTaskUpgradeMediaAnalysis': '0',      # DISABLE media analysis upgrades
        'ButlerTaskDeepMediaAnalysis': '0'          # DISABLE deep media analysis
    }

    settings = get_plex_settings(host, port, token)
    if not settings:
        print(f"   ❌ Could not get server settings")
        return 0, []

    changes_made = 0
    changes_list = []
    detection_changes = 0  # Track detection settings that require reboot

    # 1. Library scan settings (performance critical)
    # Enforce scan interval (≥ 2 hours except baremetals)
    if 'ScheduledLibraryUpdateInterval' in settings:
        current_interval = int(settings['ScheduledLibraryUpdateInterval']['value'])
        hours = current_interval / 3600

        if current_interval < 7200:  # Less than 2 hours
            print(f"    🔄 Changing scan interval: {hours:.1f}h → 2.0h")
            success = set_plex_setting(host, port, token, 'ScheduledLibraryUpdateInterval', '7200')
            if success:
                print(f"    ✅ Scan interval increased to 2 hours")
                changes_made += 1
                changes_list.append(f"Scan interval: {hours:.1f}h → 2.0h")
            else:
                print(f"    ❌ Failed to update scan interval")
        else:
            print(f"    ✅ Scan interval OK: {hours:.1f}h")

    # Disable auto library scanning
    if 'FSEventLibraryUpdatesEnabled' in settings:
        current_value = settings['FSEventLibraryUpdatesEnabled']['value']
        if current_value == '1':
            print(f"    🔄 Changing auto scan: ON → OFF")
            success = set_plex_setting(host, port, token, 'FSEventLibraryUpdatesEnabled', '0')
            if success:
                print(f"    ✅ Auto scan disabled")
                changes_made += 1
                changes_list.append("Auto library scan: Disabled")
            else:
                print(f"    ❌ Failed to disable auto scan")
        else:
            print(f"    ✅ Auto scan already OFF")

    # Enable scanner low priority
    if 'ScannerLowPriority' in settings:
        current_value = settings['ScannerLowPriority']['value']
        if current_value != '1':
            print(f"    🔄 Changing scanner priority: OFF → ON (low priority)")
            success = set_plex_setting(host, port, token, 'ScannerLowPriority', '1')
            if success:
                print(f"    ✅ Scanner low priority enabled")
                changes_made += 1
                changes_list.append("Scanner priority: Low priority enabled")
            else:
                print(f"    ❌ Failed to enable scanner low priority")
        else:
            print(f"    ✅ Scanner low priority already ON")

    # Set transcoder quality to higher speed (NOT higher quality)
    if 'TranscoderQuality' in settings:
        current_value = settings['TranscoderQuality']['value']
        if current_value != '1':  # 1 = Higher Speed
            quality_names = {'0': 'Auto', '1': 'Higher Speed', '2': 'Higher Quality'}
            current_name = quality_names.get(current_value, current_value)
            print(f"    🔄 Changing transcoder: {current_name} → Higher Speed")
            success = set_plex_setting(host, port, token, 'TranscoderQuality', '1')
            if success:
                print(f"    ✅ Transcoder set to higher speed")
                changes_made += 1
                changes_list.append(f"Transcoder: {current_name} → Higher Speed")
            else:
                print(f"    ❌ Failed to update transcoder quality")
        else:
            print(f"    ✅ Transcoder quality already: Higher Speed")

    # 2. Resource-heavy optimization features
    # Settings that require reboot when changed
    reboot_required_settings = {
        'GenerateIntroMarkerBehavior',
        'GenerateCreditsMarkerBehavior',
        'GenerateAdMarkerBehavior'
    }

    for setting_id, recommended_value in recommended_settings.items():
        if setting_id in settings:
            current_value = settings[setting_id]['value']
            label = settings[setting_id]['label']

            # Check if change is needed (disable features that are currently enabled)
            needs_change = current_value != recommended_value and current_value not in ['never', '0']

            if needs_change:
                print(f"    🔄 Changing {label}: {current_value} → {recommended_value}")
                success = set_plex_setting(host, port, token, setting_id, recommended_value)
                if success:
                    print(f"    ✅ Successfully updated {label}")
                    changes_made += 1
                    changes_list.append(f"{label}: {current_value} → {recommended_value}")

                    # Track detection settings (no reboot needed)
                    if setting_id in reboot_required_settings:
                        detection_changes += 1
                else:
                    print(f"    ❌ Failed to update {label}")
            else:
                print(f"    ✅ {label} already optimized ({current_value})")

    # Never reboot servers - changes applied without restart
    if changes_made > 0:
        print(f"    ✅ Settings optimized ({changes_made} changes) - no reboot needed")
    else:
        print(f"    ℹ️ No changes made - server already optimized")

    return changes_made, changes_list

def fix_disabled_settings(new_only=False):
    """Enable recommended analysis settings on servers"""
    mode_text = "NEW SERVERS ONLY" if new_only else "ALL SERVERS"
    print("=" * 80)
    print(f"PLEX SETTINGS OPTIMIZATION - {mode_text}")
    print("=" * 80)
    print("Settings to apply:")
    print("• SET library scan interval ≥ 2 hours")
    print("• DISABLE auto library scanning")
    print("• ENABLE scanner low priority")
    print("• SET transcoder to higher speed (not quality)")
    print("• DISABLE video preview thumbnails (never)")
    print("• DISABLE intro detection (never)")
    print("• DISABLE credits detection (never)")
    print("• DISABLE ad detection (never)")
    print("• DISABLE voice activity data (never)")
    print("• DISABLE chapter thumbnails (never)")
    print("• DISABLE loudness analysis (never)")
    print("• DISABLE sonic analysis (never)")
    print("• DISABLE media analysis upgrades")
    print("• DISABLE deep media analysis")
    print("• Reboot only when library changes made")
    print("=" * 80)

    all_services = get_all_plex_services()

    if not all_services:
        print("❌ No Plex servers found")
        return

    # Filter services based on mode
    if new_only:
        services = []
        for service in all_services:
            service_id = service.get('id')
            service_name = service['display_name']

            if is_new_server(service) or not is_server_processed(service_id):
                services.append(service)
                print(f"   ✅ Including new/unprocessed server: {service_name}")
            else:
                print(f"   ⏭️ Skipping already processed server: {service_name}")
    else:
        services = all_services

    print(f"Processing {len(services)}/{len(all_services)} Plex servers ({mode_text.lower()})")

    # Process each server using the optimize_plex_server function

    if not services:
        print("❌ No Plex servers found")
        return

    print(f"Found {len(services)} Plex servers")

    total_servers = 0
    total_changes = 0
    server_details = []

    # Load token cache
    token_cache = load_token_cache()

    for i, service in enumerate(services, 1):
        print(f"\n[{i}/{len(services)}]", end=" ")
        changes, changes_list = optimize_plex_server(service, token_cache)
        total_changes += changes
        if changes > 0:
            total_servers += 1
            server_details.append({
                'name': service['display_name'],
                'owner': service['user']['name'],
                'changes': changes_list
            })

        # Mark server as processed
        service_id = service.get('id')
        service_name = service['display_name']
        mark_server_processed(service_id, service_name)

    # Save updated token cache
    save_token_cache(token_cache)

    print(f"\n{'='*80}")
    print(f"PLEX OPTIMIZATION SUMMARY")
    print(f"{'='*80}")
    print(f"Servers optimized: {total_servers}/{len(services)}")
    print(f"Total changes applied: {total_changes}")
    print(f"Mode: {mode_text}")

    # Send detailed Discord notification
    if total_changes > 0 or len(services) > 0:
        discord_message = f"🎬 **Plex Optimization Complete** - {mode_text}\n"
        discord_message += f"Servers processed: {len(services)}/{len(all_services)}\n"
        discord_message += f"Servers optimized: {total_servers}\n"
        discord_message += f"Total changes applied: {total_changes}\n\n"

        if server_details:
            # Show only first 3 servers with details to avoid character limit
            servers_to_show = server_details[:3]
            discord_message += f"**Servers optimized (sample):**\n"
            for server_detail in servers_to_show:
                discord_message += f"• **{server_detail['name']}** ({server_detail['owner']}):\n"
                for change in server_detail['changes']:
                    discord_message += f"  - {change}\n"

            if len(server_details) > 3:
                remaining = len(server_details) - 3
                discord_message += f"• ... and {remaining} more servers optimized\n"
            discord_message += f"\n"
        else:
            discord_message += f"**No changes needed** - All processed servers already optimized\n\n"

        discord_message += f"**Settings optimized:**\n"
        discord_message += f"• Library scan interval: ≥2 hours\n"
        discord_message += f"• Auto library scan: DISABLED\n"
        discord_message += f"• Scanner priority: LOW (enabled)\n"
        discord_message += f"• Transcoder quality: Higher Speed\n"
        discord_message += f"• Video thumbnails: DISABLED\n"
        discord_message += f"• Intro/credits/ad detection: DISABLED\n"
        discord_message += f"• Voice activity data: DISABLED\n"
        discord_message += f"• Chapter thumbnails: DISABLED\n"
        discord_message += f"• Audio analysis: DISABLED\n"
        discord_message += f"• Media analysis upgrades: DISABLED\n"
        discord_message += f"• No reboots (library settings unchanged)\n"
        discord_message += f"• Using existing Plex tokens"

        send_discord_notification(discord_message)

def main():
    parser = argparse.ArgumentParser(description='Plex Server Optimization')
    parser.add_argument('--new-only', action='store_true', help='Optimize new servers only')
    parser.add_argument('--all-servers', action='store_true', help='Optimize all servers (full scan)')

    args = parser.parse_args()

    # Default to all servers if no mode specified
    new_only = args.new_only and not args.all_servers

    fix_disabled_settings(new_only=new_only)

if __name__ == "__main__":
    main()