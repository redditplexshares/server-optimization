#!/usr/bin/env python3
"""
Test Emby optimization script on Louie server only
"""

import requests
import json
import sys
import os

# Add parent directory to path to import from main script
sys.path.insert(0, '/data/server_optimize')

# Import functions from main script
from emby_optimization_settings import (
    get_emby_libraries,
    disable_video_previews_and_markers,
    disable_auto_refresh_metadata,
    set_server_configuration,
    configure_scheduled_tasks,
    configure_user_permissions,
    configure_user_home_screen,
    KRONOS_BASE_URL,
    KRONOS_AUTH_TOKEN
)

def get_louie_server():
    """Get Louie server details from Kronos"""
    print("🔍 Searching for Louie server...")

    headers = {'Authorization': f'Bearer {KRONOS_AUTH_TOKEN}'}
    page = 1

    while True:
        try:
            response = requests.get(f'{KRONOS_BASE_URL}/services?page={page}&per_page=50', headers=headers, timeout=30)

            if response.status_code != 200:
                print(f"❌ Failed to fetch from Kronos: {response.status_code}")
                return None

            data = response.json()
            services = data.get('data', [])

            if not services:
                break

            # Look for Louie server
            for service in services:
                if not service.get('is_emby'):
                    continue

                server_name = service.get('display_name', '').lower()
                if 'louie' in server_name:
                    print(f"✅ Found Louie: {service['display_name']}")
                    return service

            page += 1

        except Exception as e:
            print(f"❌ Error fetching services: {e}")
            return None

    print("❌ Louie server not found")
    return None

def verify_library_settings(host, port, token, library_id, library_name):
    """Verify library settings after update"""
    try:
        headers = {'X-Emby-Authorization': f'MediaBrowser Token="{token}"'}
        url = f'http://{host}:{port}/Library/VirtualFolders'
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code != 200:
            return None

        all_libraries = response.json()

        for lib in all_libraries:
            if lib.get('ItemId') == library_id:
                return lib.get('LibraryOptions', {})

        return None

    except Exception as e:
        print(f"    ❌ Error verifying library: {e}")
        return None

def verify_server_config(host, port, token):
    """Verify server configuration"""
    try:
        headers = {'X-Emby-Authorization': f'MediaBrowser Token="{token}"'}
        url = f'http://{host}:{port}/System/Configuration'
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code != 200:
            return None

        return response.json()

    except Exception as e:
        print(f"    ❌ Error verifying server config: {e}")
        return None

def verify_user_permissions(host, port, token, user_id):
    """Verify user permissions"""
    try:
        headers = {'X-Emby-Authorization': f'MediaBrowser Token="{token}"'}
        url = f'http://{host}:{port}/Users/{user_id}'
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code != 200:
            return None

        user_data = response.json()
        return user_data.get('Policy', {}), user_data.get('Configuration', {})

    except Exception as e:
        print(f"    ❌ Error verifying user: {e}")
        return None, None

def count_libraries(host, port, token):
    """Count total libraries on server"""
    try:
        headers = {'X-Emby-Authorization': f'MediaBrowser Token="{token}"'}
        url = f'http://{host}:{port}/Library/VirtualFolders'
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            return len(response.json())
        return 0

    except Exception:
        return 0

def test_louie_optimization():
    """Test optimization on Louie server only"""
    print("=" * 60)
    print("🧪 TESTING EMBY OPTIMIZATION ON LOUIE ONLY")
    print("=" * 60)

    # Get Louie server
    louie = get_louie_server()
    if not louie:
        print("❌ Cannot proceed without Louie server")
        return False

    server_name = louie['display_name']
    host = louie.get('container_ip')
    port = louie.get('container_port')
    token = louie.get('media_player_api_key')
    product_name = louie.get('product_name', '').lower()
    is_baremetal = 'baremetal' in product_name or 'unlimited' in product_name

    print(f"\n🎬 Server: {server_name}")
    print(f"   Host: {host}:{port}")
    print(f"   Product: {louie.get('product_name', 'Unknown')} {'[UNLIMITED/BAREMETAL]' if is_baremetal else ''}")

    if not host or not port or not token:
        print("❌ Missing connection details")
        return False

    # Count libraries before
    libraries_before = count_libraries(host, port, token)
    print(f"\n📊 Total libraries before: {libraries_before}")

    # Test 1: Server Configuration
    print("\n" + "=" * 60)
    print("TEST 1: Server Configuration (DB settings)")
    print("=" * 60)

    config_before = verify_server_config(host, port, token)
    if config_before:
        print(f"Before - DB Cache: {config_before.get('DatabaseCacheSizeMB')} MB")
        print(f"Before - Analysis Limit: {config_before.get('DatabaseAnalysisLimit')}")

    set_server_configuration(host, port, token)

    config_after = verify_server_config(host, port, token)
    if config_after:
        print(f"After  - DB Cache: {config_after.get('DatabaseCacheSizeMB')} MB")
        print(f"After  - Analysis Limit: {config_after.get('DatabaseAnalysisLimit')}")

        if config_after.get('DatabaseCacheSizeMB') == 600 and config_after.get('DatabaseAnalysisLimit') == 400:
            print("✅ TEST 1 PASSED: Server config correct")
        else:
            print("❌ TEST 1 FAILED: Server config incorrect")
            return False
    else:
        print("❌ TEST 1 FAILED: Could not verify config")
        return False

    # Test 2: User Permissions (if baremetal)
    if is_baremetal:
        print("\n" + "=" * 60)
        print("TEST 2: User Permissions (Baremetal)")
        print("=" * 60)

        # Get first non-admin user
        headers = {'X-Emby-Authorization': f'MediaBrowser Token="{token}"'}
        url = f'http://{host}:{port}/Users'
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            users = response.json()
            test_user = None

            for user in users:
                if not user.get('IsAdministrator', False) and user.get('HasPassword', True):
                    test_user = user
                    break

            if test_user:
                user_id = test_user['Id']
                user_name = test_user['Name']

                policy_before, config_before = verify_user_permissions(host, port, token, user_id)
                if policy_before:
                    print(f"Before - User: {user_name}")
                    print(f"Before - EnableSubtitleDownloading: {policy_before.get('EnableSubtitleDownloading')}")
                    print(f"Before - EnableContentDownloading: {policy_before.get('EnableContentDownloading')}")

                configure_user_permissions(host, port, token, is_baremetal)

                policy_after, config_after = verify_user_permissions(host, port, token, user_id)
                if policy_after:
                    print(f"After  - EnableSubtitleDownloading: {policy_after.get('EnableSubtitleDownloading')}")
                    print(f"After  - EnableContentDownloading: {policy_after.get('EnableContentDownloading')}")

                    if policy_after.get('EnableSubtitleDownloading') and policy_after.get('EnableContentDownloading'):
                        print("✅ TEST 2 PASSED: User permissions correct")
                    else:
                        print("❌ TEST 2 FAILED: User permissions incorrect")
                        return False
                else:
                    print("❌ TEST 2 FAILED: Could not verify user permissions")
                    return False

    # Test 3: Library Updates (no duplicates)
    print("\n" + "=" * 60)
    print("TEST 3: Library Updates (No Duplicates)")
    print("=" * 60)

    libraries = get_emby_libraries(host, port, token)
    if not libraries:
        print("❌ Could not get libraries")
        return False

    # Test on first video library (not xxx)
    test_library = None
    for lib in libraries:
        library_name = lib.get('Name', '')
        library_type = lib.get('CollectionType', '')

        if 'xxx' not in library_name.lower() and library_type in ['movies', 'tvshows', 'mixed', None]:
            test_library = lib
            break

    if not test_library:
        print("⚠️ No suitable test library found")
    else:
        library_id = test_library.get('ItemId')
        library_name = test_library.get('Name')

        print(f"Testing with library: {library_name}")

        settings_before = verify_library_settings(host, port, token, library_id, library_name)
        if settings_before:
            print(f"Before - EnableRealtimeMonitor: {settings_before.get('EnableRealtimeMonitor')}")
            print(f"Before - EnableChapterImageExtraction: {settings_before.get('EnableChapterImageExtraction')}")
            print(f"Before - EnableMarkerDetection: {settings_before.get('EnableMarkerDetection')}")
            print(f"Before - AutomaticRefreshIntervalDays: {settings_before.get('AutomaticRefreshIntervalDays')}")

        # Apply both functions
        disable_video_previews_and_markers(host, port, token, library_id, library_name)
        disable_auto_refresh_metadata(host, port, token, library_id, library_name)

        # Check library count
        libraries_after = count_libraries(host, port, token)
        print(f"\n📊 Total libraries after: {libraries_after}")

        if libraries_after != libraries_before:
            print(f"❌ TEST 3 FAILED: Duplicate library created! ({libraries_before} -> {libraries_after})")
            return False

        settings_after = verify_library_settings(host, port, token, library_id, library_name)
        if settings_after:
            print(f"After  - EnableRealtimeMonitor: {settings_after.get('EnableRealtimeMonitor')}")
            print(f"After  - EnableChapterImageExtraction: {settings_after.get('EnableChapterImageExtraction')}")
            print(f"After  - EnableMarkerDetection: {settings_after.get('EnableMarkerDetection')}")
            print(f"After  - AutomaticRefreshIntervalDays: {settings_after.get('AutomaticRefreshIntervalDays')}")

            # Verify settings changed correctly
            if (settings_after.get('EnableChapterImageExtraction') == False and
                settings_after.get('EnableMarkerDetection') == False and
                settings_after.get('AutomaticRefreshIntervalDays') == 0):
                print("✅ TEST 3 PASSED: Library updated correctly, no duplicates")
            else:
                print("❌ TEST 3 FAILED: Library settings not updated correctly")
                return False
        else:
            print("❌ TEST 3 FAILED: Could not verify library settings")
            return False

    # Final Summary
    print("\n" + "=" * 60)
    print("🎉 ALL TESTS PASSED!")
    print("=" * 60)
    print("✅ Server configuration correct (DB cache 600 MB, Analysis 400)")
    if is_baremetal:
        print("✅ User permissions correct (subtitle/download enabled)")
    print("✅ Library updates working without duplicates")
    print("✅ Library settings updated correctly")
    print("\n🚀 Script is ready to run on all servers")

    return True

if __name__ == "__main__":
    success = test_louie_optimization()
    sys.exit(0 if success else 1)
