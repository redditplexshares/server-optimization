# Server Optimization Scripts

This directory contains automated optimization scripts for Plex and Emby servers managed through Kronos API.

## Scripts

### 1. Emby Optimization (`emby_optimization_settings.py`)

Automated script that optimizes all Emby servers with the following settings:

#### Features Applied:

**Server-Wide Settings:**
- Sets database cache size to 600 MB (optimized for performance)
- Sets database analysis row limit to 400 (prevents excessive analysis)
- Disables UPnP/DLNA discovery (reduces network scanning overhead)
- Uninstalls DLNA plugin completely (eliminates DLNA server overhead)
- Enables transcoding throttling (reduces CPU usage during streaming)

**Library Settings (all video libraries except 'xxx'):**
- Disables video preview thumbnail generation
- Disables chapter image extraction during scan
- Disables chapter image extraction
- Disables marker detection during scan
- Disables marker detection
- Disables automatic metadata refresh (sets to 0 days)
- Disables real-time monitoring (except for xxx libraries)
- Disables automatic collection imports (reduces metadata processing)

**Scheduled Tasks:**
- Sets media library scan interval to minimum 3 hours (limited servers only)
- Unlimited/Baremetal servers keep default scan schedule
- Disables "Scan Metadata Folder" task (no scheduled runs)
- Disables "Download subtitles" task (no scheduled runs)
- Sets "Vacuum Database" to run every 7 days
- Sets "Import playstates from Trakt.tv" to minimum 3 hours (limited servers only)
- Disables "Export Library to Trakt" task (no scheduled runs)

**User Permissions (Unlimited/Baremetal only):**
- Enables subtitle downloading for all users
- Enables content downloading for all users
- Enables all device access

**Home Screen Layout (Unlimited/Baremetal only):**
- Configures consistent home screen with:
  1. My Media
  2. Continue Watching
  3. Latest Media
  4. Recently Released Movies
  5. Collections

#### Usage:

```bash
# Run optimization on new/unoptimized servers only (default)
python3 /data/server_optimize/emby_optimization_settings.py

# Run optimization on ALL servers (full scan)
python3 /data/server_optimize/emby_optimization_settings.py --all-servers
```

#### Systemd Service:

The script runs automatically via systemd service at `/etc/systemd/system/emby-settings-optimizer.service`

```bash
# Start optimization manually
systemctl start emby-settings-optimizer.service

# Check service status
systemctl status emby-settings-optimizer.service

# View logs
journalctl -u emby-settings-optimizer.service -f
```

#### Testing:

A test script is provided to verify all fixes on Louie server only:

```bash
python3 /data/server_optimize/test_louie_only.py
```

This test script verifies:
- Server configuration (DB settings)
- User permissions (subtitle/download enabled)
- Library updates (no duplicate libraries created)

#### Bug Fixes Implemented:

**1. Incorrect Emby API Endpoints (CRITICAL - Fixed 2025-10-18):**
- **Issue**: All API calls were failing or creating duplicates
- **Root Cause**: Missing `/emby/` prefix in URLs and wrong authorization header format
- **Fix**:
  - Changed ALL endpoints to include `/emby/` prefix (e.g., `/Library/VirtualFolders` → `/emby/Library/VirtualFolders`)
  - Changed auth header from `X-Emby-Authorization: MediaBrowser Token="..."` to `X-Emby-Token: ...`
  - Affected endpoints: VirtualFolders, System/Configuration, ScheduledTasks, Users, Policy, Configuration

**2. Library Duplication Bug (CRITICAL - Fixed 2025-10-18):**
- **Issue**: Script was creating 10+ duplicate libraries on every run (e.g., 56 copies of "4K Movies")
- **Root Cause**: POSTing library config to `/Library/VirtualFolders/LibraryOptions` without library ID
- **Fix**:
  - Changed to POST to `/emby/Library/VirtualFolders/LibraryOptions?id={library_id}`
  - POST only the `LibraryOptions` object, not the entire config
  - This updates the existing library instead of creating a new one

**3. User Permission Updates (Fixed):**
- **Issue**: User permissions weren't persisting
- **Root Cause**: POSTing to `/Users/{user_id}` endpoint
- **Fix**: Changed to POST to `/emby/Users/{user_id}/Policy` endpoint

**4. User Home Screen Updates (Fixed):**
- **Issue**: Home screen configuration wasn't persisting
- **Root Cause**: POSTing to `/Users/{user_id}` endpoint
- **Fix**: Changed to POST to `/emby/Users/{user_id}/Configuration` endpoint

**5. Video Preview Thumbnail Extraction Task (Fixed 2025-10-18):**
- **Issue**: Daily scheduled task for "Video preview thumbnail extraction" was still running at 2:00 AM despite library settings being disabled
- **Root Cause**: Scheduled tasks have independent triggers that need to be removed separately from library settings
- **Fix**: Added code to remove all triggers from the video preview task by POSTing empty array to `/emby/ScheduledTasks/{task_id}/Triggers`
- **Impact**: Prevents unnecessary CPU and disk usage from thumbnail extraction task running nightly

#### Optimization Enhancements (2025-10-18):

**Additional efficiency improvements added:**
1. **UPnP/DLNA Discovery Disabled** - Reduces network scanning and broadcast overhead
2. **DLNA Plugin Uninstalled** - Completely removes DLNA server functionality to eliminate overhead
3. **Transcoding Throttling Enabled** - Reduces CPU usage when streaming by throttling based on buffer size
4. **Automatic Collection Imports Disabled** - Prevents metadata processing for collection creation during scans

**Rollback Instructions:**
If these changes cause issues, you can manually revert via Emby web UI:
- **UPnP**: Settings → Network → Enable UPnP = ON
- **DLNA Plugin**: Settings → Plugins → Catalog → Install DLNA plugin
- **Throttling**: Settings → Transcoding → Enable throttling = OFF
- **Collections**: Settings → Libraries → [Library] → Import collections = ON

Or run this script to revert programmatically:
```bash
python3 /data/server_optimize/rollback_optimizations.py --service-id <ID>
```

#### Configuration Files:

The script uses the following settings:
- Kronos API: `https://yellow-sky-1850.kronosapp.io/api/v1`
- Filters for: `ducktv@duck.com` reseller Emby services only
- Discord notifications on completion
- Optimization tracking log: `/var/log/emby_optimization_tracking.log`

---

### 2. Plex Settings Manager (`plex_settings_manager.py`)

Script for managing Plex server settings (see file for details).

---

## Cache Files

### Processed Servers Tracking:
- `plex_processed.txt` - List of Plex server IDs that have been optimized
- `emby_processed.txt` - List of Emby server IDs that have been optimized

### Token Cache (created as needed):
- `plex_tokens.json` - Cached Plex server tokens and connection info
- `emby_tokens.json` - Cached Emby server tokens and connection info

## Purpose:
- Avoid re-processing already optimized servers
- Cache server tokens to reduce API calls to Kronos
- Only refresh tokens when they fail to connect
- Prevent API rate limiting by minimizing requests

## Maintenance:
- Files are automatically maintained by the optimization scripts
- To re-optimize all servers, delete the processed.txt files or use `--all-servers` flag
- Token cache is automatically refreshed when connections fail

## Recent Updates

**2025-10-18:**
- **CRITICAL FIX**: Corrected all Emby API endpoint URLs to include `/emby/` prefix
- **CRITICAL FIX**: Fixed library duplication bug - now uses library ID to update instead of create
- Changed auth header format from `X-Emby-Authorization` to `X-Emby-Token` (correct format)
- Library updates now POST LibraryOptions object directly with `?id={library_id}` parameter
- All API calls now match the format used by the working duplicate cleanup script

**2025-10-16:**
- Fixed critical library duplication bug in Emby optimization script (partial fix)
- Fixed user permissions and home screen configuration not persisting
- Added comprehensive test script for Louie server verification
- Updated database cache from 1200 MB to 600 MB
- Updated database analysis limit from 600 to 400
- Successfully optimized 27/28 Emby servers with 39 total changes
- All settings now apply without server restart
