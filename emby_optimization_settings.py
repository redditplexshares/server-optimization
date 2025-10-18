#!/usr/bin/env python3
"""
Emby Server Optimization Settings
- Disable video preview thumbnails and markers
- Disable auto refresh metadata
- Apply to all libraries except xxx libraries
"""

import requests
import json
import argparse
import os
import time
from datetime import datetime

# Configuration
KRONOS_BASE_URL = 'https://yellow-sky-1850.kronosapp.io/api/v1'
KRONOS_AUTH_TOKEN = '21|p9U7DSWgUGO0H7Y8v0I2QCAS6yXbtW9QvuClubA1c4fcef82'
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1419407731890192514/KvdnuYY54MTdF8wPbCQeLADvkszg-nbnveMBPoag3qKLa9YpY8TzDSP6lzz90-je1oF5"

# Server optimization cache directory
CACHE_DIR = '/data/server_optimize'
EMBY_TOKEN_CACHE_FILE = '/data/server_optimize/emby_tokens.json'
EMBY_PROCESSED_SERVERS_FILE = '/data/server_optimize/emby_processed.txt'

def get_emby_services():
    """Get all Emby services from Kronos with retry mechanism"""
    headers = {'Authorization': f'Bearer {KRONOS_AUTH_TOKEN}'}
    all_services = []
    page = 1
    retry_delay = 5  # Start with 5 seconds
    max_retries = 3

    print(f"🔄 Fetching services from Kronos API...")

    while True:
        retry_count = 0
        while retry_count < max_retries:
            try:
                response = requests.get(f'{KRONOS_BASE_URL}/services?page={page}&per_page=100', headers=headers, timeout=30)

                if response.status_code == 429:
                    retry_count += 1
                    if retry_count < max_retries:
                        print(f"⚠️ Rate limited, waiting {retry_delay} seconds before retry {retry_count}/{max_retries}...")
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                        continue
                    else:
                        print(f"❌ Rate limited after {max_retries} retries, using {len(all_services)} services already fetched")
                        break  # Exit to filtering

                elif response.status_code != 200:
                    print(f"❌ Kronos API error: {response.status_code}")
                    if response.text:
                        print(f"Response: {response.text[:200]}")
                    return all_services if all_services else []

                if not response.text.strip():
                    print(f"❌ Empty response from Kronos API")
                    return all_services if all_services else []

                data = response.json()
                services = data.get('data', [])
                if not services:
                    break

                all_services.extend(services)
                print(f"📊 Page {page}: Retrieved {len(services)} services")
                page += 1

                # Reset retry delay on success
                retry_delay = 5
                time.sleep(2)  # Delay between successful requests
                break  # Break out of retry loop

            except requests.exceptions.JSONDecodeError as e:
                print(f"❌ JSON decode error from Kronos API: {e}")
                print(f"Response text: {response.text[:500] if 'response' in locals() else 'No response'}")
                return all_services if all_services else []
            except Exception as e:
                print(f"❌ Error getting services from Kronos: {e}")
                return all_services if all_services else []

        # If we exhausted retries, break out of main loop
        if retry_count >= max_retries:
            break

    print(f"📊 Retrieved {len(all_services)} total services from Kronos")

    # Filter Emby services
    emby_services = [s for s in all_services if s.get('is_emby')]
    print(f"📊 Found {len(emby_services)} Emby services")
    return emby_services

def get_emby_libraries(host, port, token):
    """Get all libraries from Emby server"""
    try:
        headers = {'X-Emby-Token': token}
        url = f'http://{host}:{port}/emby/Library/VirtualFolders'

        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"    ❌ Failed to get libraries: {response.status_code}")
            return []

    except Exception as e:
        print(f"    ❌ Error getting libraries: {e}")
        return []

def disable_video_previews_and_markers(host, port, token, library_id, library_name):
    """Disable video preview generation and chapter markers for a library"""
    try:
        headers = {
            'X-Emby-Token': token,
            'Content-Type': 'application/json'
        }

        # Get current library configuration using correct endpoint
        url = f'http://{host}:{port}/emby/Library/VirtualFolders?name={library_name}'
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code != 200:
            print(f"    ❌ Failed to get library config for {library_name}")
            return False

        config_array = response.json()
        if not config_array or not isinstance(config_array, list):
            print(f"    ❌ Invalid config response for {library_name}")
            return False

        config = config_array[0]  # VirtualFolders returns array with one item
        if 'LibraryOptions' not in config:
            print(f"    ❌ No LibraryOptions found for {library_name}")
            return False

        lib_options = config['LibraryOptions']
        changes_made = 0

        # Disable chapter image extraction during scan
        if lib_options.get('ExtractChapterImagesDuringLibraryScan', True):
            lib_options['ExtractChapterImagesDuringLibraryScan'] = False
            changes_made += 1
            print(f"    📑 Disabled chapter image extraction for {library_name}")

        # Disable chapter image extraction
        if lib_options.get('EnableChapterImageExtraction', True):
            lib_options['EnableChapterImageExtraction'] = False
            changes_made += 1
            print(f"    🖼️ Disabled chapter image extraction for {library_name}")

        # Disable marker detection during library scan
        if lib_options.get('EnableMarkerDetectionDuringLibraryScan', True):
            lib_options['EnableMarkerDetectionDuringLibraryScan'] = False
            changes_made += 1
            print(f"    📍 Disabled marker detection during scan for {library_name}")

        # Disable marker detection
        if lib_options.get('EnableMarkerDetection', True):
            lib_options['EnableMarkerDetection'] = False
            changes_made += 1
            print(f"    🚫 Disabled marker detection for {library_name}")

        # Always update the config to ensure API is called every time
        config['LibraryOptions'] = lib_options

        # Update library options using library ID to avoid creating duplicates
        # POST the full config object, not just lib_options
        post_url = f'http://{host}:{port}/emby/Library/VirtualFolders/LibraryOptions?id={library_id}'
        post_response = requests.post(post_url, headers=headers, json=config, timeout=15)

        if post_response.status_code in [200, 204]:
            if changes_made > 0:
                print(f"    ✅ Applied {changes_made} video settings changes to {library_name}")
            else:
                print(f"    ✅ Video settings verified/updated for {library_name}")
            return changes_made > 0  # Return True only if actual changes were made
        else:
            print(f"    ❌ Failed to apply video settings to {library_name}: {post_response.status_code}")
            return False

    except Exception as e:
        print(f"    ❌ Error setting video options for {library_name}: {e}")
        return False

def disable_auto_refresh_metadata(host, port, token, library_id, library_name):
    """Disable automatic metadata refresh for a library"""
    try:
        headers = {
            'X-Emby-Token': token,
            'Content-Type': 'application/json'
        }

        # Get current library configuration using correct endpoint
        url = f'http://{host}:{port}/emby/Library/VirtualFolders?name={library_name}'
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code != 200:
            print(f"    ❌ Failed to get library config for {library_name}")
            return False

        config_array = response.json()
        if not config_array or not isinstance(config_array, list):
            print(f"    ❌ Invalid config response for {library_name}")
            return False

        config = config_array[0]  # VirtualFolders returns array with one item
        if 'LibraryOptions' not in config:
            print(f"    ❌ No LibraryOptions found for {library_name}")
            return False

        lib_options = config['LibraryOptions']
        changes_made = 0

        # Disable automatic metadata refresh (if the setting exists)
        if lib_options.get('AutomaticRefreshIntervalDays', 0) != 0:
            lib_options['AutomaticRefreshIntervalDays'] = 0
            changes_made += 1
            print(f"    🔄 Disabled auto metadata refresh for {library_name}")

        # Disable real-time monitoring (but keep it enabled for xxx libraries)
        if 'xxx' not in library_name.lower():
            if lib_options.get('EnableRealtimeMonitor', True):
                lib_options['EnableRealtimeMonitor'] = False
                changes_made += 1
                print(f"    👁️ Disabled realtime monitoring for {library_name}")
        else:
            print(f"    ℹ️ Keeping realtime monitoring enabled for xxx library: {library_name}")

        # Disable automatic collection imports (reduces metadata processing)
        if lib_options.get('ImportCollections', True):
            lib_options['ImportCollections'] = False
            changes_made += 1
            print(f"    📦 Disabled automatic collection imports for {library_name}")

        # Always update the config to ensure API is called every time
        config['LibraryOptions'] = lib_options

        # Update library options using library ID to avoid creating duplicates
        # POST the full config object, not just lib_options
        post_url = f'http://{host}:{port}/emby/Library/VirtualFolders/LibraryOptions?id={library_id}'
        post_response = requests.post(post_url, headers=headers, json=config, timeout=15)

        if post_response.status_code in [200, 204]:
            if changes_made > 0:
                print(f"    ✅ Applied {changes_made} metadata settings changes to {library_name}")
            else:
                print(f"    ✅ Metadata settings verified/updated for {library_name}")
            return changes_made > 0  # Return True only if actual changes were made
        else:
            print(f"    ❌ Failed to apply metadata settings to {library_name}: {post_response.status_code}")
            return False

    except Exception as e:
        print(f"    ❌ Error setting metadata options for {library_name}: {e}")
        return False

def set_server_configuration(host, port, token):
    """Set server-wide configuration settings"""
    try:
        headers = {
            'X-Emby-Token': token,
            'Content-Type': 'application/json'
        }

        # Get current server configuration
        url = f'http://{host}:{port}/emby/System/Configuration'
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code != 200:
            print(f"    ❌ Failed to get server configuration")
            return False

        config = response.json()

        changes_made = 0

        # Set DB cache size to 600 MB (using correct Emby field name)
        if config.get('DatabaseCacheSizeMB', 0) != 600:
            config['DatabaseCacheSizeMB'] = 600
            changes_made += 1
            print(f"    💾 Set DB cache size to 600 MB")

        # Set analysis row limit to 400 (using correct Emby field name)
        if config.get('DatabaseAnalysisLimit', 0) != 400:
            config['DatabaseAnalysisLimit'] = 400
            changes_made += 1
            print(f"    📊 Set analysis row limit to 400")

        # Disable UPnP/DLNA (reduces network scanning overhead)
        if config.get('EnableUPnP', True):
            config['EnableUPnP'] = False
            changes_made += 1
            print(f"    🌐 Disabled UPnP/DLNA discovery")

        # Always update the config to ensure API is called every time
        url = f'http://{host}:{port}/emby/System/Configuration'
        response = requests.post(url, headers=headers, json=config, timeout=10)

        if response.status_code in [200, 204]:
            if changes_made > 0:
                print(f"    ✅ Applied {changes_made} server configuration changes")
            else:
                print(f"    ✅ Server configuration verified/updated")
            return changes_made > 0  # Return True only if actual changes were made
        else:
            print(f"    ❌ Failed to apply server configuration: {response.status_code}")
            return False

    except Exception as e:
        print(f"    ❌ Error setting server configuration: {e}")
        return False

def configure_transcoding_settings(host, port, token):
    """Configure transcoding/encoding settings for efficiency"""
    try:
        headers = {
            'X-Emby-Token': token,
            'Content-Type': 'application/json'
        }

        # Get current encoding configuration
        url = f'http://{host}:{port}/emby/System/Configuration/encoding'
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code != 200:
            print(f"    ❌ Failed to get encoding configuration")
            return False

        config = response.json()
        changes_made = 0

        # Enable transcoding throttling (reduces CPU usage during streaming)
        if not config.get('EnableThrottling', False):
            config['EnableThrottling'] = True
            changes_made += 1
            print(f"    ⚡ Enabled transcoding throttling")

        # Always update the config to ensure API is called every time
        url = f'http://{host}:{port}/emby/System/Configuration/encoding'
        response = requests.post(url, headers=headers, json=config, timeout=10)

        if response.status_code in [200, 204]:
            if changes_made > 0:
                print(f"    ✅ Applied {changes_made} transcoding configuration change(s)")
            else:
                print(f"    ✅ Transcoding configuration verified/updated")
            return changes_made > 0
        else:
            print(f"    ❌ Failed to apply transcoding configuration: {response.status_code}")
            return False

    except Exception as e:
        print(f"    ❌ Error setting transcoding configuration: {e}")
        return False

def configure_scheduled_tasks(host, port, token, is_baremetal):
    """Configure scheduled task settings for media library scanning"""
    try:
        headers = {
            'X-Emby-Token': token,
            'Content-Type': 'application/json'
        }

        # Get current scheduled tasks
        url = f'http://{host}:{port}/emby/ScheduledTasks'
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code != 200:
            print(f"    ❌ Failed to get scheduled tasks")
            return False

        tasks = response.json()

        changes_made = 0

        # Find media library scan task and video preview task
        for task in tasks:
            task_name = task.get('Name', '').lower()
            task_id = task.get('Id', '')

            # Disable video preview thumbnail extraction task
            if 'video preview' in task_name or task.get('Key') == 'RefreshChapterImages':
                print(f"    🎬 Found task: {task.get('Name')}")
                triggers = task.get('Triggers', [])
                if len(triggers) > 0:
                    # Remove all triggers to disable the task
                    url = f'http://{host}:{port}/emby/ScheduledTasks/{task_id}/Triggers'
                    response = requests.post(url, headers=headers, json=[], timeout=10)
                    if response.status_code in [200, 204]:
                        print(f"    ✅ Disabled video preview thumbnail extraction task")
                        changes_made += 1
                    else:
                        print(f"    ❌ Failed to disable video preview task: {response.status_code}")
                else:
                    print(f"    ✅ Video preview task already disabled")

            # Configure media library scan interval
            elif 'scan media library' in task_name or 'library scan' in task_name:
                print(f"    📅 Found task: {task.get('Name')}")

                if is_baremetal:
                    print(f"    🏗️ Unlimited/Baremetal server - keeping default scan schedule")
                    continue

                # For non-baremetal servers, set scan interval to 3+ hours
                current_interval = task.get('IntervalTicks', 0)
                # 3 hours = 3 * 60 * 60 * 10000000 ticks (100-nanosecond intervals)
                three_hours_ticks = 3 * 60 * 60 * 10000000

                if current_interval < three_hours_ticks:
                    # Update the task configuration
                    task_update = {
                        'IntervalTicks': three_hours_ticks,  # 3 hours minimum
                        'IsEnabled': True
                    }

                    url = f'http://{host}:{port}/emby/ScheduledTasks/{task_id}'
                    response = requests.post(url, headers=headers, json=task_update, timeout=10)

                    if response.status_code in [200, 204]:
                        print(f"    ✅ Set media library scan to 3+ hours")
                        changes_made += 1
                    else:
                        print(f"    ❌ Failed to update scan interval: {response.status_code}")
                else:
                    print(f"    ✅ Scan interval already 3+ hours")

        return changes_made > 0

    except Exception as e:
        print(f"    ❌ Error configuring scheduled tasks: {e}")
        return False

def configure_user_permissions(host, port, token, is_baremetal):
    """Configure user permissions for unlimited/baremetal servers"""
    if not is_baremetal:
        print(f"    ℹ️ Limited server - skipping user permission changes")
        return False

    try:
        headers = {
            'X-Emby-Token': token,
            'Content-Type': 'application/json'
        }

        # Get all users
        url = f'http://{host}:{port}/emby/Users'
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code != 200:
            print(f"    ❌ Failed to get users list")
            return False

        users = response.json()
        print(f"    👥 Found {len(users)} users on unlimited/baremetal server")

        changes_made = 0

        for user in users:
            user_id = user.get('Id', '')
            user_name = user.get('Name', 'Unknown')

            # Skip admin users or system accounts
            if user.get('HasPassword', True) == False or user.get('IsAdministrator', False):
                print(f"    🔒 Skipping admin/system user: {user_name}")
                continue

            print(f"    👤 Configuring permissions for: {user_name}")

            # Get current user data (contains Policy)
            url = f'http://{host}:{port}/emby/Users/{user_id}'
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code != 200:
                print(f"      ❌ Failed to get user data for {user_name}")
                continue

            user_data = response.json()

            if 'Policy' not in user_data:
                print(f"      ❌ No Policy found for {user_name}")
                continue

            policy = user_data['Policy']
            user_changes = 0

            # Enable subtitle downloading
            if not policy.get('EnableSubtitleDownloading', False):
                policy['EnableSubtitleDownloading'] = True
                user_changes += 1
                print(f"      📝 Enabled subtitle downloading for {user_name}")

            # Enable media downloading (including transcoding)
            if not policy.get('EnableContentDownloading', False):
                policy['EnableContentDownloading'] = True
                user_changes += 1
                print(f"      💾 Enabled media downloading for {user_name}")

            # Enable downloading with transcoding
            if not policy.get('EnableContentDownloadingForPhotoAlbums', False):
                policy['EnableContentDownloadingForPhotoAlbums'] = True
                user_changes += 1

            # Ensure user can access all media types for downloading
            if not policy.get('EnableAllDevices', True):
                policy['EnableAllDevices'] = True
                user_changes += 1

            # Apply changes if any were made
            if user_changes > 0:
                # POST only the policy to the correct endpoint
                url = f'http://{host}:{port}/emby/Users/{user_id}/Policy'
                response = requests.post(url, headers=headers, json=policy, timeout=15)

                if response.status_code in [200, 204]:
                    print(f"      ✅ Applied {user_changes} permission changes to {user_name}")
                    changes_made += 1
                else:
                    print(f"      ❌ Failed to update permissions for {user_name}: {response.status_code}")
            else:
                print(f"      ✅ Permissions already configured for {user_name}")

        if changes_made > 0:
            print(f"    🎉 Updated permissions for {changes_made} users on baremetal server")

        return changes_made > 0

    except Exception as e:
        print(f"    ❌ Error configuring user permissions: {e}")
        return False

def configure_user_home_screen(host, port, token, is_baremetal):
    """Configure home screen layout for all users (unlimited/baremetal only)"""
    if not is_baremetal:
        print(f"    ℹ️ Limited server - skipping home screen customization")
        return False

    try:
        headers = {
            'X-Emby-Token': token,
            'Content-Type': 'application/json'
        }

        # Get all users
        url = f'http://{host}:{port}/emby/Users'
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code != 200:
            print(f"    ❌ Failed to get users list for home screen config")
            return False

        users = response.json()
        print(f"    🏠 Configuring home screen for {len(users)} users")

        changes_made = 0

        for user in users:
            user_id = user.get('Id', '')
            user_name = user.get('Name', 'Unknown')

            print(f"    👤 Configuring home screen for: {user_name}")

            # Get current user data (contains Configuration)
            url = f'http://{host}:{port}/emby/Users/{user_id}'
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code != 200:
                print(f"      ❌ Failed to get user data for {user_name}")
                continue

            user_data = response.json()

            if 'Configuration' not in user_data:
                print(f"      ❌ No Configuration found for {user_name}")
                continue

            config = user_data['Configuration']
            user_changes = 0

            # Define home screen sections in order
            home_sections = [
                {
                    "Type": "librarytiles",
                    "Name": "My Media"
                },
                {
                    "Type": "resume",
                    "Name": "Continue Watching"
                },
                {
                    "Type": "latestmedia",
                    "Name": "Latest Media"
                },
                {
                    "Type": "recentlyreleasedmovies",
                    "Name": "Recently Released Movies"
                },
                {
                    "Type": "collections",
                    "Name": "Collections"
                }
            ]

            # Check if home sections need updating
            current_sections = config.get('HomeScreenSections', [])

            # Compare sections
            sections_match = True
            if len(current_sections) != len(home_sections):
                sections_match = False
            else:
                for i, section in enumerate(home_sections):
                    if i >= len(current_sections) or current_sections[i].get('Type') != section['Type']:
                        sections_match = False
                        break

            if not sections_match:
                config['HomeScreenSections'] = home_sections
                user_changes += 1
                print(f"      🏠 Updated home screen layout for {user_name}")
                print(f"        1. My Media")
                print(f"        2. Continue Watching")
                print(f"        3. Latest Media")
                print(f"        4. Recently Released Movies")
                print(f"        5. Collections")

            # Apply changes if any were made
            if user_changes > 0:
                # POST only the configuration to the correct endpoint
                url = f'http://{host}:{port}/emby/Users/{user_id}/Configuration'
                response = requests.post(url, headers=headers, json=config, timeout=15)

                if response.status_code in [200, 204]:
                    print(f"      ✅ Applied home screen changes to {user_name}")
                    changes_made += 1
                else:
                    print(f"      ❌ Failed to update home screen for {user_name}: {response.status_code}")
            else:
                print(f"      ✅ Home screen already configured for {user_name}")

        if changes_made > 0:
            print(f"    🎉 Updated home screen for {changes_made} users")

        return changes_made > 0

    except Exception as e:
        print(f"    ❌ Error configuring home screen: {e}")
        return False

def reboot_emby_server(service):
    """Reboot Emby server after optimization changes"""
    try:
        headers = {'Authorization': f'Bearer {KRONOS_AUTH_TOKEN}'}

        # Check if this is an Emby server that supports restart
        if not service.get('is_emby'):
            print(f"    ❌ Not an Emby server")
            return False

        # Try Emby-specific restart endpoint (similar to Plex)
        url = f'{KRONOS_BASE_URL}/services/{service["id"]}/emby/restart'
        response = requests.post(url, headers=headers, timeout=30)

        if response.status_code in [200, 202]:
            print(f"    ✅ Emby server reboot initiated for {service['display_name']}")
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

def get_fresh_api_key(service_id, fallback_token=None):
    """Get fresh API key from Kronos for a service with rate limiting and fallback"""
    try:
        # Add small delay to avoid rate limiting
        time.sleep(0.5)

        headers = {'Authorization': f'Bearer {KRONOS_AUTH_TOKEN}'}
        url = f'{KRONOS_BASE_URL}/services/{service_id}'
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            service_data = response.json()
            fresh_token = service_data.get('media_player_api_key')
            if fresh_token:
                return fresh_token
            else:
                print(f"    ⚠️ No API key in Kronos response, using fallback")
                return fallback_token
        elif response.status_code == 429:
            print(f"    ⚠️ Rate limited, using fallback token")
            return fallback_token
        else:
            print(f"    ⚠️ Failed to fetch fresh API key: {response.status_code}, using fallback")
            return fallback_token
    except Exception as e:
        print(f"    ⚠️ Error fetching fresh API key: {e}, using fallback")
        return fallback_token

def optimize_emby_server(service):
    """Optimize a single Emby server"""
    server_name = service['display_name']
    owner = service['user']['name']
    host = service.get('container_ip')
    port = service.get('container_port')
    service_id = service.get('id')
    product_name = service.get('product_name', '').lower()
    is_baremetal = 'baremetal' in product_name or 'unlimited' in product_name

    # Use existing token from service data
    token = service.get('media_player_api_key')

    if not token:
        print(f"   ❌ No API token available")
        return 0

    print(f"\n🎬 Optimizing: {server_name} ({owner})")
    print(f"   Host: {host}:{port}")
    print(f"   Product: {service.get('product_name', 'Unknown')} {'[UNLIMITED/BAREMETAL]' if is_baremetal else ''}")
    print(f"   🔑 Using cached API token")

    if not host or not port:
        print(f"   ❌ Missing connection details")
        return 0

    # Try to get libraries with existing token
    libraries = get_emby_libraries(host, port, token)

    # If existing token failed, try to get fresh one from Kronos as fallback
    if not libraries:
        print(f"   ⚠️ Token failed, fetching fresh API key from Kronos...")
        token = get_fresh_api_key(service_id, fallback_token=token)
        if token:
            print(f"   ✅ Fresh API key retrieved, retrying...")
            libraries = get_emby_libraries(host, port, token)

    if not libraries:
        print(f"   ❌ Could not get libraries")
        return 0

    print(f"   📚 Found {len(libraries)} libraries")

    total_changes = 0
    server_config_changes = 0

    # First, set server-wide configuration
    if set_server_configuration(host, port, token):
        total_changes += 1
        server_config_changes += 1

    # Configure transcoding/encoding settings
    if configure_transcoding_settings(host, port, token):
        total_changes += 1
        server_config_changes += 1

    # Configure scheduled tasks (scan intervals)
    if configure_scheduled_tasks(host, port, token, is_baremetal):
        total_changes += 1
        server_config_changes += 1

    # Configure user permissions (baremetal only)
    if configure_user_permissions(host, port, token, is_baremetal):
        total_changes += 1
        server_config_changes += 1

    # Configure home screen layout (baremetal only)
    if configure_user_home_screen(host, port, token, is_baremetal):
        total_changes += 1
        server_config_changes += 1

    for library in libraries:
        library_id = library.get('ItemId', '')
        library_name = library.get('Name', 'Unknown')
        library_type = library.get('CollectionType', 'mixed')

        # Skip xxx libraries
        if 'xxx' in library_name.lower():
            print(f"   🚫 Skipping {library_name} (xxx library)")
            continue

        print(f"   📁 Processing: {library_name} ({library_type})")

        # Only process video libraries
        if library_type in ['movies', 'tvshows', 'mixed', None]:
            # Disable video previews and markers
            if disable_video_previews_and_markers(host, port, token, library_id, library_name):
                total_changes += 1

            # Disable auto metadata refresh
            if disable_auto_refresh_metadata(host, port, token, library_id, library_name):
                total_changes += 1
        else:
            print(f"    ℹ️ Skipping {library_name} (not a video library)")

    # Count actual library changes (video/metadata settings)
    library_changes = total_changes - server_config_changes

    # Configuration changes applied without restart
    if library_changes > 0:
        print(f"    ✅ Library settings changed - applied without restart")
    elif server_config_changes > 0:
        print(f"    ✅ Server configuration changed - applied without restart")
    else:
        print(f"    ℹ️ No changes made")

    return total_changes

def send_discord_notification(message):
    """Send notification to Discord"""
    try:
        webhook_data = {
            "username": "Emby Optimization Bot",
            "avatar_url": "https://emby.media/notificationicon.png",
            "content": message
        }
        requests.post(DISCORD_WEBHOOK_URL, json=webhook_data, timeout=10)
    except Exception as e:
        print(f"Discord notification error: {e}")

def is_new_server(service, hours_threshold=72):
    """Check if server is new (created within last X hours)"""
    try:
        # Check if server was created recently based on service data
        # This is a simple check - you might need to adjust based on Kronos API data structure
        created_at = service.get('created_at')
        if created_at:
            from datetime import datetime, timedelta
            created_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            threshold_time = datetime.now() - timedelta(hours=hours_threshold)
            return created_time > threshold_time
    except Exception:
        pass

    # Fallback: consider all servers as "new" if we can't determine age
    # This ensures servers get processed even if creation date is unavailable
    return True

def get_last_optimization_time(service_id):
    """Get last optimization time for a server"""
    try:
        log_file = f"/var/log/emby_optimization_tracking.log"
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                for line in reversed(f.readlines()):
                    if f"service_id:{service_id}:" in line:
                        timestamp = line.split(':', 1)[0]
                        return datetime.fromisoformat(timestamp)
    except Exception:
        pass
    return None

def log_optimization_time(service_id, service_name):
    """Log optimization time for tracking"""
    try:
        timestamp = datetime.now().isoformat()
        log_entry = f"{timestamp}:service_id:{service_id}:{service_name}:optimized\n"
        with open("/var/log/emby_optimization_tracking.log", 'a') as f:
            f.write(log_entry)
    except Exception:
        pass

def optimize_all_emby_servers(new_only=False):
    """Optimize Emby servers based on mode"""
    mode_text = "NEW SERVERS ONLY" if new_only else "ALL SERVERS"
    print(f"🎬 EMBY SERVER OPTIMIZATION - {mode_text}")
    print("=" * 50)
    print("Settings to apply:")
    print("• Set DB cache size to 600 MB")
    print("• Set analysis row limit to 400")
    print("• Scheduled task scan: 3+ hours (unlimited/baremetal exempt)")
    print("• User permissions: Enable subtitle & media downloading (unlimited/baremetal only)")
    print("• Home screen: Custom layout (unlimited/baremetal only)")
    print("  1. My Media  2. Continue Watching  3. Latest Media")
    print("  4. Recently Released Movies  5. Collections")
    print("• Disable video preview thumbnails and markers")
    print("• Disable auto refresh metadata")
    print("• Skip libraries containing 'xxx'")
    print("=" * 50)

    all_services = get_emby_services()

    if not all_services:
        print("❌ No Emby servers found")
        return

    # Filter services based on mode
    if new_only:
        services = []
        for service in all_services:
            service_id = service.get('id')
            service_name = service['display_name']

            # Check if server is new or hasn't been optimized recently
            if is_new_server(service) or get_last_optimization_time(service_id) is None:
                services.append(service)
                print(f"   ✅ Including new/unoptimized server: {service_name}")
            else:
                print(f"   ⏭️ Skipping previously optimized server: {service_name}")
    else:
        services = all_services

    print(f"Processing {len(services)}/{len(all_services)} Emby servers ({mode_text.lower()})")

    total_servers = 0
    total_changes = 0

    for i, service in enumerate(services, 1):
        print(f"\n[{i}/{len(services)}]", end=" ")
        changes = optimize_emby_server(service)
        total_changes += changes
        if changes > 0:
            total_servers += 1

        # Log optimization time for tracking (even if no changes made)
        service_id = service.get('id')
        service_name = service['display_name']
        log_optimization_time(service_id, service_name)

    print(f"\n{'='*50}")
    print(f"EMBY OPTIMIZATION SUMMARY")
    print(f"{'='*50}")
    print(f"Servers optimized: {total_servers}/{len(services)}")
    print(f"Total changes applied: {total_changes}")

    if total_changes > 0:
        send_discord_notification(f"🎬 **Emby Optimization Complete**\n"
                                f"Servers optimized: {total_servers}/{len(services)}\n"
                                f"Changes applied: {total_changes}\n"
                                f"• DB cache size: 600 MB\n"
                                f"• Analysis row limit: 400\n"
                                f"• UPnP/DLNA discovery: Disabled\n"
                                f"• Transcoding throttling: Enabled\n"
                                f"• Collection imports: Disabled\n"
                                f"• Scan intervals: 3+ hours (unlimited/baremetal exempt)\n"
                                f"• User permissions: Subtitle/media downloading (unlimited/baremetal)\n"
                                f"• Home screen: Custom layout (unlimited/baremetal)\n"
                                f"• Video previews/markers disabled\n"
                                f"• Auto metadata refresh disabled\n"
                                f"• Settings applied without restart")

def main():
    parser = argparse.ArgumentParser(description='Emby Server Optimization')
    parser.add_argument('--new-only', action='store_true', help='Optimize new servers only')
    parser.add_argument('--all-servers', action='store_true', help='Optimize all servers (full scan)')

    args = parser.parse_args()

    # Default to all servers if no mode specified
    new_only = args.new_only and not args.all_servers

    optimize_all_emby_servers(new_only=new_only)

if __name__ == "__main__":
    main()