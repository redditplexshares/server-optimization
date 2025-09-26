# Server Optimization Cache Directory

This directory contains cache files for Plex and Emby server optimization scripts.

## Files:

### Processed Servers Tracking:
- `plex_processed.txt` - List of Plex server IDs that have been optimized (87 servers)
- `emby_processed.txt` - List of Emby server IDs that have been optimized (32 servers)

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
- To re-optimize all servers, delete the processed.txt files
- Token cache is automatically refreshed when connections fail